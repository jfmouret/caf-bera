#!/usr/bin/env python3
"""BERA officiel -> KML/KMZ + tuiles PNG transparentes + AQX + MBTiles."""
import argparse, datetime as dt, html, io, json, math, os, re, shutil, sqlite3, time, urllib.request, urllib.parse, urllib.error, zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
import unicodedata
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont
import fitz
ROOT=Path(__file__).resolve().parent
PARIS=ZoneInfo('Europe/Paris')
ARCHIVE='https://files.data.gouv.fr/meteofrance/data/BULLETIN/BRA/'
API='https://public-api.meteofrance.fr/public/DPBRA/v1/'
_LAST_API_CALL=0.0
# Couleurs EAWS : 1 vert, 2 jaune, 3 orange, 4 rouge, 5 rouge/noir (hachures).
COLORS={1:'ccff66',2:'ffff00',3:'ff9900',4:'ff0000',5:'ff0000',None:'888888'}
# Correspondances vérifiées par rapprochement XML/PDF officiels joints.
SAT_NAMES={'2':'neige ventée','6':'pas de situation prédominante'}
K='http://www.opengis.net/kml/2.2'
ET.register_namespace('',K)

def _download(url,headers=None):
    global _LAST_API_CALL
    for attempt in range(3):
        try:
            if url.startswith(API):
                time.sleep(max(0,1.3-(time.monotonic()-_LAST_API_CALL)))
                _LAST_API_CALL=time.monotonic()
            req=urllib.request.Request(url,headers={'User-Agent':'CAF-BERA/1.0','Cache-Control':'no-cache',**(headers or {})})
            with urllib.request.urlopen(req,timeout=25) as r:return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429,500,502,503,504) or attempt==2:raise
        except (OSError,TimeoutError):
            if attempt==2:raise
        time.sleep(2**attempt)

@lru_cache(maxsize=200)
def public_get(url):return _download(url)
def get(url,headers=None):
    return _download(url,headers) if headers else public_get(url)

def stamp(s):
    x=dt.datetime.fromisoformat(s)
    # Le XML ne porte généralement pas de fuseau : convention heure civile française.
    return x.replace(tzinfo=PARIS) if x.tzinfo is None else x

def parse_xml(data,code):
    if b'<!DOCTYPE' in data.upper():raise ValueError('DOCTYPE refusé')
    r=ET.fromstring(data)
    if r.tag!='BULLETINS_NEIGE_AVALANCHE' or int(r.get('ID','-1'))!=int(code):raise ValueError('Racine ou identifiant massif inattendu')
    risk=r.find('./CARTOUCHERISQUE/RISQUE')
    if risk is None:raise ValueError('Cartouche risque absent')
    a=dict(risk.attrib)
    for key in ('RISQUE1','RISQUE2','RISQUEMAXI','EVOLURISQUE1','EVOLURISQUE2','RISQUEMAXIJ2'):
        if a.get(key) and a[key] not in ('1','2','3','4','5'):raise ValueError('Niveau non reconnu : '+key)
    levels=[int(a[x]) for x in ('RISQUE1','RISQUE2') if a.get(x)]
    if not levels:raise ValueError('Niveaux absents')
    maximum=int(a.get('RISQUEMAXI') or max(levels))
    if maximum!=max(levels):raise ValueError('Maximum incohérent')
    start=stamp(r.attrib['DATEBULLETIN']);end=stamp(r.attrib['DATEVALIDITE'])
    expiry=stamp(r.get('DATEECHEANCE') or r.attrib['DATEVALIDITE'])
    end=min(end,expiry)
    if end<=start:raise ValueError('Dates incohérentes')
    p=r.find('./CARTOUCHERISQUE/PENTE');sat=r.find('./STABILITE/SitAvalTyp')
    def txt(path):return ''.join(r.find(path).itertext()).strip() if r.find(path) is not None else ''
    return dict(code=int(code),name=r.get('MASSIF'),issued=start.isoformat(),valid_until=end.isoformat(),dates=dict(r.attrib),risk=a,maximum=maximum,
        orientations=dict(p.attrib) if p is not None else {},sat=dict(sat.attrib) if sat is not None else {},
        texts={k:txt(v) for k,v in {'resume':'./CARTOUCHERISQUE/RESUME','accidentel':'./CARTOUCHERISQUE/ACCIDENTEL','naturel':'./CARTOUCHERISQUE/NATUREL','stabilite':'./STABILITE/TEXTE','tendance':'./CARTOUCHERISQUE/CommentaireRisqueJ2','risque_j2':'./CARTOUCHERISQUE/RisqueJ2','qualite':'./QUALITE/TEXTE'}.items()})

def active(b,now):return stamp(b['issued'])<=now<stamp(b['valid_until'])

def normal_name(s):
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().upper()
    s=re.sub('[^A-Z0-9]','',s)
    return {'EMBRUNNAISPARPAILLON':'EMBRUNAISPARPAILLON'}.get(s,s)

def archive_index(day):
    u=ARCHIVE+day.strftime('%Y/%m/%d/')+'xml/'
    s=get(u).decode('utf-8')
    return sorted(set(urllib.parse.urljoin(u,html.unescape(x)) for x in re.findall(r'href="([^"]+\.xml)"',s)),reverse=True)

def fetch(features,now,rawdir):
    headers={}
    if os.getenv('MF_API_KEY'):headers['apikey']=os.environ['MF_API_KEY']
    elif os.getenv('MF_BEARER_TOKEN'):headers['Authorization']='Bearer '+os.environ['MF_BEARER_TOKEN']
    indexes=[];errors=[];pdf_indexes={}
    # Archives publiques de secours, le bulletin d'hier peut rester valide aujourd'hui.
    for offset in range(3):
        try:indexes.extend(archive_index(now.date()-dt.timedelta(days=offset)))
        except Exception as e:errors.append('Index archive : '+type(e).__name__)
    # Préchargement parallèle des seules archives publiques ; les appels API restent limités.
    wanted={normal_name(f['properties']['title']) for f in features}
    preload=[u for u in indexes if normal_name(urllib.parse.unquote(u.rsplit('/',1)[-1]).split('_')[0]) in wanted]
    preload+=list({u.split('/xml/')[0]+'/pdf/' for u in preload})
    def warm(u):
        try:get(u)
        except Exception:pass
    with ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(warm,preload))
    result={}
    for f in features:
        p=f['properties'];code=p['code'];name=p['title'];b=None;notes=[]
        if headers:
            try:
                data=get(API+'massif/BRA?'+urllib.parse.urlencode({'id-massif':code,'format':'xml'}),headers)
                b=parse_xml(data,code);b['source']=API+'massif/BRA?id-massif='+str(code)+'&format=xml'
                (rawdir/f'{code}.xml').write_bytes(data)
            except Exception as e:notes.append('API : '+type(e).__name__+((' HTTP '+str(e.code)) if isinstance(e,urllib.error.HTTPError) else ''))
        else:notes.append('API non interrogée : authentification absente')
        if b is None or not active(b,now):
            candidates=[u for u in indexes if normal_name(urllib.parse.unquote(u.rsplit('/',1)[-1]).split('_')[0])==normal_name(name)]
            for u in sorted(candidates,reverse=True):
                try:
                    data=get(u);candidate=parse_xml(data,code);candidate['source']=u
                    if b is None or stamp(candidate['issued'])>stamp(b['issued']):
                        b=candidate;(rawdir/f'{code}.xml').write_bytes(data)
                    break
                except Exception as e:notes.append('Archive : '+type(e).__name__)
        if b:
            b['state']='VALIDE' if active(b,now) else 'PÉRIMÉ OU FUTUR — DANGER ACTUEL INDISPONIBLE'
            b['display_level']=b['maximum'] if active(b,now) else None
            # Le nom du PDF est découvert dans son index, sans supposer le même horodatage.
            b['pdf']=None
            if b['source'].startswith(API) and headers:
                try:
                    payload=get(API+'massif/BRA?id-massif='+str(code)+'&format=pdf',headers)
                    if not payload.startswith(b'%PDF'):raise ValueError('Réponse non PDF')
                    (rawdir/f'{code}.pdf').write_bytes(payload);b['pdf_local']=f'raw/{code}.pdf'
                except Exception as e:notes.append('PDF API indisponible : '+type(e).__name__)
            if b['source'].startswith(ARCHIVE):
                daypath=b['source'].split('/xml/')[0]+'/pdf/'
                try:
                    if daypath not in pdf_indexes:pdf_indexes[daypath]=get(daypath).decode()
                    listing=pdf_indexes[daypath]
                    links=[urllib.parse.urljoin(daypath,html.unescape(x)) for x in re.findall(r'href="([^"]+\.pdf)"',listing)]
                    links=[u for u in links if normal_name(urllib.parse.unquote(u.rsplit('/',1)[-1]).split('_')[0])==normal_name(name)]
                    if links:
                        pdf=max(links);payload=get(pdf)
                        if payload.startswith(b'%PDF'):b['pdf']=pdf;(rawdir/f'{code}.pdf').write_bytes(payload)
                except Exception as e:notes.append('PDF indisponible : '+type(e).__name__)
        else:b={'code':code,'name':name,'state':'INDISPONIBLE','display_level':None}
        b['notes']=notes;b['checked_at']=now.isoformat();result[code]=b
        print(name+' : '+b['state'],flush=True)
    return result,errors

def prepare_offline_images(b,out):
    """Copier en images des parties du PDF officiel, sans dessiner de pictogrammes."""
    pdf=out/'raw'/f'{b["code"]}.pdf'
    b['offline_images']=[]
    if not pdf.is_file():return
    directory=out/'media'/str(b['code']);directory.mkdir(parents=True,exist_ok=True)
    try:
        with fitz.open(pdf) as doc:
            if not len(doc):return
            page=doc[0];width=page.rect.width
            text=page.get_text().replace(chr(65279),'')
            massif=re.search(r'MASSIF\s*:\s*([^\n]+)',text)
            date=re.search(r'Rédigé le .*?(\d{1,2})\s+(\w+)\s+(\d{4})\s+à\s+(\d{1,2})h(?:\s*(\d{2}))?',text)
            months=['janvier','février','mars','avril','mai','juin','juillet','août','septembre','octobre','novembre','décembre']
            if not massif or normal_name(massif.group(1))!=normal_name(b['name']):raise ValueError('massif PDF différent')
            if not date or date.group(2).lower() not in months:raise ValueError('date PDF non vérifiable')
            day,month,year,hour,minute=date.groups()
            issued=stamp(b['issued'])
            if (issued.year,issued.month,issued.day,issued.hour,issued.minute)!=(int(year),months.index(month.lower())+1,int(day),int(hour),int(minute or 0)):raise ValueError('date PDF différente du XML')
            def save(rect,name,caption):
                rect=fitz.Rect(rect)&page.rect
                if rect.is_empty:return
                dest=directory/name
                page.get_pixmap(matrix=fitz.Matrix(2.5,2.5),clip=rect,alpha=False).save(dest)
                b['offline_images'].append({'path':dest.relative_to(out).as_posix(),'caption':caption})
            # Le cartouche contient aussi des éléments vectoriels : on rend la zone,
            # sans extraire uniquement le bitmap du symbole de danger.
            stability=page.search_for('Stabilité du manteau neigeux')
            if stability:
                bottom=stability[0].y0-3
                candidates=[r for item in page.get_images(full=True) for r in page.get_image_rects(item[0])
                            if 80<r.y0<bottom and r.x0<width*.45]
                if candidates:
                    top=min(r.y0 for r in candidates)-4
                    save((0,top,width*.48,bottom),'cartouche.png','Cartouche officiel : danger, altitudes et orientations')
            # Associer chaque image SAT à son libellé imprimé immédiatement à droite.
            rows=page.search_for('Situation avalancheuse typique')
            if rows:
                row=rows[0];zone=fitz.Rect(0,row.y0-16,width,row.y1+16)
                icons=[]
                for item in page.get_images(full=True):
                    for rect in page.get_image_rects(item[0]):
                        if rect.intersects(zone) and rect.width<80 and rect.height<80 and rect.x0>row.x1:
                            icons.append(rect)
                icons.sort(key=lambda r:r.x0)
                words=page.get_text('words',clip=zone)
                labels=[]
                for i,rect in enumerate(icons):
                    limit=icons[i+1].x0-3 if i+1<len(icons) else width
                    following=[w for w in words if rect.x1<=w[0]<limit and w[1]>=row.y0-2 and w[3]<=row.y1+2]
                    caption=' '.join(w[4] for w in sorted(following,key=lambda w:w[0])).replace(chr(65279),'').strip()
                    right=max([w[2] for w in following]+[rect.x1])
                    save((rect.x0-2,min(rect.y0,row.y0)-2,right+3,max(rect.y1,row.y1)+2),f'probleme-{i+1}.png',caption or 'Pictogramme officiel du bulletin')
                    if caption:labels.append(caption)
                b['pdf_problem_labels']=labels
            # La page complète garde tous les pictogrammes et le contexte officiel,
            # y compris si une nouvelle mise en page empêche les découpes ci-dessus.
            for number,page in enumerate(doc,1):
                save(page.rect,f'page-{number}.png',f'Page {number} du bulletin officiel, conservée en image hors ligne')
    except Exception as e:
        b.setdefault('notes',[]).append('Illustrations PDF indisponibles : '+type(e).__name__)

def write_kmz(path,data,features,bs,out):
    """Vérifier et embarquer chaque image référencée dans le document KML."""
    media={img['path'] for f in features for img in bs[f['properties']['code']].get('offline_images',[])}
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('doc.kml',data)
        for name in sorted(media):
            if name.startswith('/') or '..' in Path(name).parts:raise ValueError('Chemin image invalide')
            z.write(out/name,name)

def description(b):
    esc=lambda x:html.escape(str(x))
    chunks=['<div style="max-width:320px;font-size:20px;line-height:1.4"><font size="4">',f"<h2>{esc(b['name'])}</h2><p><b>État lors de l’enregistrement : {esc(b['state'])}</b></p>",f"<p>Copie enregistrée : {esc(b['checked_at'])}</p>",'<p><b>Lecture hors ligne.</b> Cette copie ne se met pas à jour ; contrôler sa date de validité.</p>']
    if 'risk' in b:
        chunks.append(f"<p>Rédaction : {esc(b['issued'])}<br/>Fin de validité : {esc(b['valid_until'])}</p>")
        if b.get('online_pdf'):
            chunks.append(f'<p><a href="{esc(b["online_pdf"])}"><font size="5"><b>PDF officiel — connexion requise</b></font></a></p>')
        a=b['risk'];old=b['display_level'] is None
        chunks.append('<p><b>'+('DONNÉES ANCIENNES, PAS LE DANGER ACTUEL. ' if old else '')+'Estimation à l’échelle du massif.</b></p>')
        for i in (1,2):
            if a.get(f'RISQUE{i}'):
                chunks.append(f"<p>{esc(a.get(f'LOC{i}') or 'Ensemble du massif')} : {esc(a[f'RISQUE{i}'])}/5 ; évolution : {esc(a.get(f'EVOLURISQUE{i}') or 'non précisée')}</p>")
        chunks.append('<p>'+esc(a.get('COMMENTAIRE',''))+'</p>')
        orientations=[k for k in ('N','NE','E','SE','S','SW','W','NW') if b['orientations'].get(k)=='true']
        chunks.append('<p>Rose des pentes les plus dangereuses : '+esc(', '.join(orientations) or 'non renseignée')+'<br/>'+esc(b['orientations'].get('COMMENTAIRE',''))+'</p>')
        chunks.append('<p>Situations avalancheuses typiques (codes officiels ; libellés vérifiés lorsqu’ils sont disponibles) : '+esc('; '.join(k+'='+v+' ('+SAT_NAMES.get(v,'libellé non vérifié')+')' for k,v in b['sat'].items() if v))+'. Localisations et altitudes propres aux problèmes : lire le texte intégral ci-dessous.</p>')
        if b.get('offline_images'):
            chunks.append('<h3>Pictogrammes officiels embarqués</h3>')
            for img in b['offline_images']:
                if Path(img['path']).name.startswith('page-'):continue
                chunks.append(f'<p>{esc(img["caption"])}</p><p><img src="{esc(img["path"])}" width="300" alt="{esc(img["caption"])}"/></p>')
        for key,label in [('resume','Synthèse'),('stabilite','Problèmes avalancheux et stabilité'),('accidentel','Déclenchements provoqués'),('naturel','Départs spontanés'),('tendance','Évolution J+2'),('qualite','Qualité de la neige')]:
            chunks.append('<h3>'+label+'</h3><p>'+esc(b['texts'][key] or 'Non renseigné').replace('\n','<br/>')+'</p>')
        chunks.append('<p>J+2 : '+esc(a.get('DATE_RISQUE_J2',''))+' ; niveau '+esc(a.get('RISQUEMAXIJ2','non renseigné'))+'</p>')
        for img in b.get('offline_images',[]):
            if Path(img['path']).name.startswith('page-'):
                chunks.append(f'<h3>{esc(img["caption"])}</h3><p><img src="{esc(img["path"])}" width="300" alt="Page officielle du bulletin"/></p>')
    chunks.append('<p><a href="https://meteofrance.com/meteo-montagne">Bulletins officiels Météo-France</a></p><p>Source : Météo-France — Licence Ouverte 2.0. Transformation CAF. Un niveau de massif ne décrit pas le risque local sur une pente. Vérifier les dates avant toute utilisation ; une copie hors ligne ne se met pas à jour.</p>')
    chunks.append('<p>'+esc('; '.join(b.get('notes',[])))+'</p>')
    return ''.join(chunks)+'</font></div>'

def pdf_page(b,pdf_url=None):
    """Adresse stable : ouverture du PDF à jour, ou indisponibilité explicite."""
    esc=lambda x:html.escape(str(x))
    page=('<!doctype html><html lang="fr"><head><meta charset="utf-8">'
          '<meta name="viewport" content="width=device-width, initial-scale=1">'
          '<meta http-equiv="Cache-Control" content="no-cache">'
          f'<title>BERA {esc(b["name"])}</title>'
          '<style>body{font:20px/1.5 system-ui,sans-serif;max-width:30rem;margin:24px auto;padding:0 16px;color:#16252c}'
          'a{display:inline-block;background:#163e57;color:white;padding:14px 18px;border-radius:8px}h1{font-size:1.4em}</style></head><body>'
          f'<h1>BERA {esc(b["name"])}</h1>')
    if pdf_url and b.get('display_level') is not None:
        page+=(f'<p id="status">Ouverture du PDF officiel…</p><p>Fin de validité : {esc(b["valid_until"])}</p>'
               f'<p><a href="{esc(pdf_url)}">Ouvrir le PDF Météo-France</a></p>')
        # Vérification côté téléphone : ne pas ouvrir silencieusement un ancien bulletin
        # si la publication serveur n'a pas pu être renouvelée avant son échéance.
        js=lambda x:json.dumps(x,ensure_ascii=True).replace('<',chr(92)+'u003c')
        page+=('<script>const from=Date.parse('+js(b['issued'])+');const until=Date.parse('+js(b['valid_until'])+');'
               'if(Date.now()>=from&&Date.now()<until){window.location.replace('+js(pdf_url)+');}'
               'else{document.getElementById("status").textContent="Bulletin périmé ou pas encore valide. Vérifier les dates avant d’ouvrir le PDF archivé.";}</script>')
    else:
        page+='<p><b>BERA PDF actuel indisponible.</b></p><p>'+esc(b.get('state','INDISPONIBLE'))+'</p>'
        if b.get('valid_until'):page+='<p>Échéance du bulletin obtenu : '+esc(b['valid_until'])+'</p>'
        page+='<p><a href="https://meteofrance.com/meteo-montagne">Consulter Météo-France</a></p>'
    return page+'<p>Source : Météo-France. Vérifier la date du PDF avant utilisation.</p></body></html>'

def tile_font(size):
    try:return ImageFont.truetype('DejaVuSans.ttf',size)
    except OSError:return ImageFont.load_default(size=size)

def label_lines(name,level,end):
    first=f'{name} {level}'
    # Respecter la largeur d'une tuile, y compris les longs noms de massifs.
    font=tile_font(16);probe=ImageDraw.Draw(Image.new('RGBA',(1,1)))
    lines=[];line=''
    for word in first.replace('-','- ').split():
        candidate=(line+' '+word).strip()
        if line and probe.textbbox((0,0),candidate,font=font)[2]>232:lines.append(line);line=word
        else:line=candidate
    lines.append(line)
    try:expiry=stamp(end).strftime('%d/%m %H:%M')
    except (ValueError,TypeError):expiry='non disponible'
    return lines+['Fin '+expiry]

def draw_tile_label(im,name,level,end,y):
    draw=ImageDraw.Draw(im);lines=label_lines(name,level,end);font=tile_font(16)
    widths=[draw.textbbox((0,0),line,font=font)[2] for line in lines]
    width=min(252,max(widths)+12);height=22*len(lines)+8
    if y+height>254:return y
    draw.rounded_rectangle((2,y,2+width,y+height),radius=4,fill=(255,255,255,230))
    for i,line in enumerate(lines):draw.text((8,y+4+i*22),line,font=font,fill=(12,25,32,255))
    return y+height+4

def sub(p,tag,text=None,**attrs):
    e=ET.SubElement(p,'{'+K+'}'+tag,attrs)
    if text is not None:e.text=str(text)
    return e

def kml(features,bulletins,title,contours_base=None):
    root=ET.Element('{'+K+'}kml');doc=sub(root,'Document');sub(doc,'name',title)
    for f in features:
        p=f['properties'];b=bulletins[p['code']];level=None if contours_base else b['display_level'];rgb=COLORS[level]
        color='55'+rgb[4:6]+rgb[2:4]+rgb[0:2]
        info=description(b)
        pm=sub(doc,'Placemark');sub(pm,'name',p['title'] if contours_base else p['title']+' — '+(str(level)+'/5' if level else 'INDISPONIBLE')+' — '+title)
        sub(pm,'description',info);style=sub(pm,'Style');label=sub(style,'LabelStyle');sub(label,'scale',1.3);line=sub(style,'LineStyle');sub(line,'color',color);sub(line,'width',3)
        poly=sub(style,'PolyStyle');sub(poly,'color',color);sub(poly,'fill',0 if contours_base else 1);sub(poly,'outline',1)
        g=f['geometry'];polys=[g['coordinates']] if g['type']=='Polygon' else g['coordinates'];multi=sub(pm,'MultiGeometry')
        for rings in polys:
            pg=sub(multi,'Polygon');sub(pg,'tessellate',1);sub(pg,'altitudeMode','clampToGround')
            for i,ring in enumerate(rings):
                if len(ring)<4 or ring[0]!=ring[-1]:raise ValueError('Anneau non fermé')
                signed=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ring,ring[1:]))
                if (i==0 and signed<0) or (i>0 and signed>0):ring=list(reversed(ring))
                boundary=sub(pg,'outerBoundaryIs' if i==0 else 'innerBoundaryIs');lr=sub(boundary,'LinearRing')
                sub(lr,'coordinates',' '.join(f'{x},{y},0' for x,y,*_ in ring))
        # Repère central distinct, utile si la sélection d'une zone est peu commode.
        wp=sub(doc,'Placemark');sub(wp,'name',p['title']+' · BERA hors ligne' if contours_base else p['title']+' — fiche BERA');sub(wp,'description',info);pt=sub(wp,'Point');sub(pt,'coordinates',f'{p["lon_center"]},{p["lat_center"]},0')
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)

def project(lon,lat,z):
    lat=max(-85.05112878,min(85.05112878,lat));n=2**z
    return ((lon+180)/360*n,(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n)

def map_bounds(features,z):
    coords=[]
    for f in features:
        g=f['geometry'];polys=[g['coordinates']] if g['type']=='Polygon' else g['coordinates']
        coords.extend(project(x,y,z) for rings in polys for ring in rings for x,y,*_ in ring)
    return (math.floor(min(x for x,y in coords)),math.floor(min(y for x,y in coords)),
            math.floor(max(x for x,y in coords)),math.floor(max(y for x,y in coords)))

def map_labels(features,bs,z):
    # Un libellé par massif, ancré sur sa position géographique. Aucun texte dans
    # les tuiles de vue générale : leur réutilisation agrandie créait des fantômes.
    if z<9:return []
    result=[]
    for f in features:
        p=f['properties'];b=bs[p['code']];level=b['display_level']
        name=('ARCHIVE ' if 'ARCHIVE' in b['state'] else '')+p['title']
        sprite=Image.new('RGBA',(256,256))
        draw_tile_label(sprite,name,str(level)+'/5' if level else 'INDISPONIBLE',b.get('valid_until','?'),2)
        box=sprite.getbbox()
        if box is None:continue
        sprite=sprite.crop(box)
        ax,ay=project(p['lon_center'],p['lat_center'],z)
        result.append((round(ax*256-sprite.width/2),round(ay*256-sprite.height/2),sprite))
    return result

def tiles(features,bs,out,zmin,zmax):
    count=0
    for z in range(zmin,zmax+1):
        anchored_labels=map_labels(features,bs,z)
        geometries=[];coords=[]
        for f in features:
            g=f['geometry'];polys=[g['coordinates']] if g['type']=='Polygon' else g['coordinates']
            polys=[[[project(x,y,z) for x,y,*_ in ring] for ring in rings] for rings in polys]
            geometries.append((f,polys));coords.extend(pt for rings in polys for ring in rings for pt in ring)
        xmin,ymin=map(math.floor,(min(x for x,y in coords),min(y for x,y in coords)));xmax,ymax=map(math.floor,(max(x for x,y in coords),max(y for x,y in coords)))
        for x in range(xmin,xmax+1):
            for y in range(ymin,ymax+1):
                im=Image.new('RGBA',(256,256))
                for f,polys in geometries:
                    mask=Image.new('L',(256,256));d=ImageDraw.Draw(mask)
                    for rings in polys:
                        for i,ring in enumerate(rings):d.polygon([((a-x)*256,(b-y)*256) for a,b in ring],fill=255 if i==0 else 0)
                    if not mask.getbbox():continue
                    b=bs[f['properties']['code']];level=b['display_level'];rgb=tuple(bytes.fromhex(COLORS[level]));layer=Image.new('RGBA',(256,256),rgb+(85,));layer.putalpha(mask.point(lambda p:p*85//255));im=Image.alpha_composite(im,layer)
                    if level==5:
                        hatch=Image.new('RGBA',(256,256));hd=ImageDraw.Draw(hatch)
                        for v in range(-256,512,12):hd.line((v,0,v-256,256),fill=(0,0,0,210),width=3)
                        hatch.putalpha(Image.composite(hatch.getchannel('A'),Image.new('L',(256,256)),mask));im=Image.alpha_composite(im,hatch)
                # Le même libellé est découpé sur la grille globale ; il ne se
                # répète pas à chaque bord de tuile et reste au même endroit.
                for left,top,sprite in anchored_labels:
                    dx,dy=left-x*256,top-y*256
                    if dx<256 and dy<256 and dx+sprite.width>0 and dy+sprite.height>0:
                        im.alpha_composite(sprite,dest=(dx,dy))
                path=out/'tiles'/str(z)/str(x)/f'{y}.png';path.parent.mkdir(parents=True,exist_ok=True);im.save(path);count+=1
    # Toutes les tuiles absentes sont desservies par une image transparente en serveur local.
    Image.new('RGBA',(256,256)).save(out/'empty.png')
    return count

def mbtiles(out):
    db=sqlite3.connect(out/'bera.mbtiles');db.executescript('CREATE TABLE metadata(name TEXT,value TEXT);CREATE TABLE tiles(zoom_level INTEGER,tile_column INTEGER,tile_row INTEGER,tile_data BLOB,UNIQUE(zoom_level,tile_column,tile_row));')
    for k,v in dict(name='BERA — instantané daté',format='png',type='overlay',version='1.3',description='Source Météo-France. Consulter validité dans KML.',bounds='4,43,8,47',minzoom='6',maxzoom='12').items():db.execute('INSERT INTO metadata VALUES (?,?)',(k,v))
    for p in (out/'tiles').glob('*/*/*.png'):
        z,x,y=int(p.parts[-3]),int(p.parts[-2]),int(p.stem);db.execute('INSERT INTO tiles VALUES (?,?,?,?)',(z,x,2**z-1-y,p.read_bytes()))
    db.commit();db.close()

def aqx(base,title,features=None):
    url=html.escape(base.rstrip('/')+'/tiles-v3/{$z}/{$x}/{$y}.png')
    levels=[]
    for z in range(6,13):
        bounds=''
        if features:bounds='<tiles-bounds>'+','.join(map(str,map_bounds(features,z)))+'</tiles-bounds>'
        levels.append(f'<zoom-levels z="{z}">{bounds}<update-delay>0D</update-delay><max-threads>2</max-threads><server>{url}</server></zoom-levels>')
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<aqx version="11"><name>CAF BERA V3</name><description>Source Météo-France — Licence Ouverte 2.0. Gris : bulletin actuel indisponible. Contrôler la validité.</description>'
            '<source id="CAFBERA2026V3" layer="true" opacity="100"><name>BERA V3 — '+html.escape(title)+'</name>'
            '<default-location>6.00201,45.27395</default-location>'+''.join(levels)+'</source></aqx>')

def build(features,bs,out,now,base,errors=(),title='BERA',offline=False):
    out.mkdir(parents=True,exist_ok=True)
    for code,b in bs.items():
        if (out/'raw'/f'{code}.xml').exists():b['public_xml']=base.rstrip('/')+f'/raw/{code}.xml'
        if (out/'raw'/f'{code}.pdf').exists():b['public_pdf']=base.rstrip('/')+f'/raw/{code}.pdf'
        b['online_pdf']=base.rstrip('/')+f'/bulletins/{code}.html'
        prepare_offline_images(b,out)
    for filename,fs in [('bera-alpes',features),('bera-belledonne',[f for f in features if f['properties']['code']==8])]:
        if not fs:continue
        data=kml(fs,bs,title+' '+now.strftime('%Y-%m-%d %H:%M %Z'));(out/(filename+'.kml')).write_bytes(data)
        write_kmz(out/(filename+'.kmz'),data,fs,bs,out)
    (out/'bulletins.json').write_text(json.dumps({'generated_at':now.isoformat(),'errors':list(errors),'bulletins':list(bs.values())},ensure_ascii=False,indent=2))
    data=kml(features,bs,'Contours BERA — fiches en ligne',base)
    (out/'bera-contours.kml').write_bytes(data)
    write_kmz(out/'bera-contours.kmz',data,features,bs,out)
    (out/'bulletins').mkdir(exist_ok=True)
    for code,b in bs.items():
        pdf_url=(b.get('public_pdf') if (out/'raw'/f'{code}.pdf').exists() else b.get('pdf'))
        (out/'bulletins'/f'{code}.html').write_text(pdf_page(b,pdf_url))
    n=tiles(features,bs,out,6,12)
    shutil.copytree(out/'tiles',out/'tiles-v3',dirs_exist_ok=True)
    (out/'bera.aqx').write_text(aqx(base,title,features))
    if offline:mbtiles(out)
    if offline:shutil.copyfile(out/'bera.mbtiles',out/'bera.mbtile')
    pages=''.join('<section id="massif-'+str(b['code'])+'">'+description(b)+'</section>' for b in bs.values())
    (out/'index.html').write_text('<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CAF BERA</title><style>body{font:19px/1.5 system-ui,sans-serif;max-width:42rem;margin:20px auto;padding:0 16px;overflow-wrap:anywhere}h1{font-size:1.5em}h2{font-size:1.3em}section{border-top:1px solid #ccc;margin-top:24px;padding-top:12px}a{line-height:1.7}</style><h1>'+html.escape(title)+'</h1><p>Généré '+now.isoformat()+'</p><p><a href="bera-alpes.kmz">KMZ Alpes</a> · <a href="bera-belledonne.kmz">KMZ Belledonne</a> · <a href="bera.aqx">AQX</a> · <a href="bera-contours.kmz">Contours et fiches en ligne</a></p><p>1 vert faible · 2 jaune limité · 3 orange marqué · 4 rouge fort · 5 rouge hachuré noir très fort · gris indisponible. La couleur est le maximum du massif, sans découpage altimétrique des pentes. AQX : actualisation à chaque affichage en ligne ; KML : réimporter la copie actualisée.</p>'+pages+'</html>')
    return n

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--demo',action='store_true');ap.add_argument('--all-alps',action='store_true');ap.add_argument('--base-url',default='http://127.0.0.1:8765');ap.add_argument('--mbtiles',action='store_true');args=ap.parse_args()
    now=dt.datetime.now(PARIS);features=json.loads((ROOT/'data/massifs.geojson').read_text())['features']
    features=[f for f in features if f['properties']['mountain'].startswith('Alpes') and (args.all_alps or f['properties']['code'] in (7,8,12,14,15))]
    tmp=ROOT/('build-demo-temp' if args.demo else 'build-temp');shutil.rmtree(tmp,ignore_errors=True);tmp.mkdir();raw=tmp/'raw';raw.mkdir()
    if args.demo:
        features=[f for f in features if f['properties']['code']==8];b=parse_xml((ROOT/'data/archive-2025.xml').read_bytes(),8)
        b.update(state='ARCHIVE DU 15/02/2025 — EXERCICE UNIQUEMENT',display_level=b['maximum'],checked_at=now.isoformat(),notes=['Données historiques : jamais pour une sortie actuelle.'],source=ARCHIVE+'2025/02/15/xml/Belledonne_20250215162300.xml',pdf=(ROOT/'data/archive-2025-pdf-url.txt').read_text().strip() if (ROOT/'data/archive-2025-pdf-url.txt').exists() else None)
        bs={8:b};errors=[];title='ARCHIVE EXERCICE 2025'
    else:bs,errors=fetch(features,now,raw);title='BERA actuel — vérifier la validité'
    n=build(features,bs,tmp,now,args.base_url,errors,title,args.mbtiles)
    dest=ROOT/('demo' if args.demo else 'dist');shutil.rmtree(dest,ignore_errors=True);tmp.rename(dest)
    print(json.dumps({'output':str(dest),'tiles':n,'states':{b['name']:b['state'] for b in bs.values()}},ensure_ascii=False))
if __name__=='__main__':main()
