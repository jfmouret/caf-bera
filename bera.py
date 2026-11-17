#!/usr/bin/env python3
"""BERA officiel -> KML/KMZ + tuiles PNG transparentes + AQX + MBTiles."""
import argparse, datetime as dt, html, io, json, math, os, re, shutil, sqlite3, time, urllib.request, urllib.parse, urllib.error, zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
import unicodedata
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from PIL import Image, ImageDraw
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
            req=urllib.request.Request(url,headers={'User-Agent':'CAF-BERA/1.0',**(headers or {})})
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

def description(b):
    esc=lambda x:html.escape(str(x))
    chunks=[f"<h2>{esc(b['name'])}</h2><p><b>{esc(b['state'])}</b></p>",f"<p>Vérifié : {esc(b['checked_at'])}</p>"]
    if 'risk' in b:
        chunks.append(f"<p>Rédaction : {esc(b['issued'])}<br/>Fin de validité : {esc(b['valid_until'])}</p>")
        a=b['risk'];old=b['display_level'] is None
        chunks.append('<p><b>'+('DONNÉES ANCIENNES, PAS LE DANGER ACTUEL. ' if old else '')+'Estimation à l’échelle du massif.</b></p>')
        for i in (1,2):
            if a.get(f'RISQUE{i}'):
                chunks.append(f"<p>{esc(a.get(f'LOC{i}') or 'Ensemble du massif')} : {esc(a[f'RISQUE{i}'])}/5 ; évolution : {esc(a.get(f'EVOLURISQUE{i}') or 'non précisée')}</p>")
        chunks.append('<p>'+esc(a.get('COMMENTAIRE',''))+'</p>')
        orientations=[k for k in ('N','NE','E','SE','S','SW','W','NW') if b['orientations'].get(k)=='true']
        chunks.append('<p>Rose des pentes les plus dangereuses : '+esc(', '.join(orientations) or 'non renseignée')+'<br/>'+esc(b['orientations'].get('COMMENTAIRE',''))+'</p>')
        chunks.append('<p>Situations avalancheuses typiques (codes officiels ; libellés vérifiés lorsqu’ils sont disponibles) : '+esc('; '.join(k+'='+v+' ('+SAT_NAMES.get(v,'libellé non vérifié')+')' for k,v in b['sat'].items() if v))+'. Localisations et altitudes propres aux problèmes : lire le texte intégral ci-dessous.</p>')
        for key,label in [('resume','Synthèse'),('stabilite','Problèmes avalancheux et stabilité'),('accidentel','Déclenchements provoqués'),('naturel','Départs spontanés'),('tendance','Évolution J+2')]:
            chunks.append('<h3>'+label+'</h3><p>'+esc(b['texts'][key] or 'Non renseigné').replace('\n','<br/>')+'</p>')
        chunks.append('<p>J+2 : '+esc(a.get('DATE_RISQUE_J2',''))+' ; niveau '+esc(a.get('RISQUEMAXIJ2','non renseigné'))+'</p>')
        chunks.append(f'<p><a href="{esc(b["source"])}">XML officiel complet</a></p>')
        if b.get('public_xml'):chunks.append(f'<p><a href="{esc(b["public_xml"])}">Copie du XML téléchargé</a></p>')
        if b.get('pdf_local') and b.get('public_pdf'):chunks.append(f'<p><a href="{esc(b["public_pdf"])}">PDF officiel téléchargé, copie complète</a></p>')
        if b.get('pdf'):chunks.append(f'<p><a href="{esc(b["pdf"])}">PDF officiel complet</a></p>')
    chunks.append('<p><a href="https://meteofrance.com/meteo-montagne">Bulletins officiels Météo-France</a></p><p>Source : Météo-France — Licence Ouverte 2.0. Transformation CAF. Un niveau de massif ne décrit pas le risque local sur une pente. Vérifier les dates avant toute utilisation ; une copie hors ligne ne se met pas à jour.</p>')
    chunks.append('<p>'+esc('; '.join(b.get('notes',[])))+'</p>')
    return ''.join(chunks)

def sub(p,tag,text=None,**attrs):
    e=ET.SubElement(p,'{'+K+'}'+tag,attrs)
    if text is not None:e.text=str(text)
    return e

def kml(features,bulletins,title,contours_base=None):
    root=ET.Element('{'+K+'}kml');doc=sub(root,'Document');sub(doc,'name',title)
    for f in features:
        p=f['properties'];b=bulletins[p['code']];level=None if contours_base else b['display_level'];rgb=COLORS[level]
        color='55'+rgb[4:6]+rgb[2:4]+rgb[0:2]
        info=description(b) if contours_base is None else '<p>Contour officiel du massif. Les informations actualisées sont accessibles en ligne :</p><p><a href="'+html.escape(contours_base.rstrip('/')+'/index.html#massif-'+str(p['code']))+'">Ouvrir la fiche BERA actualisée</a></p><p>Source : Météo-France, Licence Ouverte 2.0. La couleur de la couche AQX indique le maximum du massif ; vérifier sa date.</p>'
        pm=sub(doc,'Placemark');sub(pm,'name',p['title'] if contours_base else p['title']+' — '+(str(level)+'/5' if level else 'INDISPONIBLE')+' — '+title)
        sub(pm,'description',info);style=sub(pm,'Style');line=sub(style,'LineStyle');sub(line,'color',color);sub(line,'width',3)
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
        wp=sub(doc,'Placemark');sub(wp,'name',p['title']+' — fiche BERA');sub(wp,'description',info);pt=sub(wp,'Point');sub(pt,'coordinates',f'{p["lon_center"]},{p["lat_center"]},0')
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)

def project(lon,lat,z):
    lat=max(-85.05112878,min(85.05112878,lat));n=2**z
    return ((lon+180)/360*n,(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n)

def tiles(features,bs,out,zmin,zmax):
    count=0
    for z in range(zmin,zmax+1):
        geometries=[];coords=[]
        for f in features:
            g=f['geometry'];polys=[g['coordinates']] if g['type']=='Polygon' else g['coordinates']
            polys=[[[project(x,y,z) for x,y,*_ in ring] for ring in rings] for rings in polys]
            geometries.append((f,polys));coords.extend(pt for rings in polys for ring in rings for pt in ring)
        xmin,ymin=map(math.floor,(min(x for x,y in coords),min(y for x,y in coords)));xmax,ymax=map(math.floor,(max(x for x,y in coords),max(y for x,y in coords)))
        for x in range(xmin,xmax+1):
            for y in range(ymin,ymax+1):
                im=Image.new('RGBA',(256,256));labels=[]
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
                    end=b.get('valid_until','?')[:16];labels.append((('ARCHIVE ' if 'ARCHIVE' in b['state'] else '')+f['properties']['title'],str(level)+'/5' if level else 'INDISPONIBLE',end))
                # Conserver aussi les tuiles transparentes du rectangle de couverture.
                d=ImageDraw.Draw(im)
                for i,(name,lev,end) in enumerate(labels[:3]):
                    text=f'{name} {lev}\nFin {end}'
                    # Pillow embarque DejaVu dans les environnements courants ; sinon défaut ASCII.
                    text=text.encode('ascii','replace').decode();d.rectangle((2,2+i*28,252,29+i*28),fill=(255,255,255,210));d.text((4,3+i*28),text,fill=(0,0,0,255))
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

def aqx(base,title):
    url=html.escape(base.rstrip('/')+'/tiles/{$z}/{$x}/{$y}.png')
    return f'''<?xml version="1.0" encoding="utf-8"?>
<aqx version="11"><name>CAF BERA</name><description>Source Météo-France — Licence Ouverte 2.0. Vérifier la date imprimée.</description><source id="CAFBERA2026" layer="true" opacity="100"><name>{html.escape(title)}</name><default-location>6.00201,45.27395</default-location><zoom-levels z="6-12"><update-delay>0D</update-delay><max-threads>2</max-threads><server>{url}</server></zoom-levels></source></aqx>'''

def build(features,bs,out,now,base,errors=(),title='BERA',offline=False):
    out.mkdir(parents=True,exist_ok=True)
    for code,b in bs.items():
        if (out/'raw'/f'{code}.xml').exists():b['public_xml']=base.rstrip('/')+f'/raw/{code}.xml'
        if (out/'raw'/f'{code}.pdf').exists():b['public_pdf']=base.rstrip('/')+f'/raw/{code}.pdf'
    for filename,fs in [('bera-alpes',features),('bera-belledonne',[f for f in features if f['properties']['code']==8])]:
        if not fs:continue
        data=kml(fs,bs,title+' '+now.strftime('%Y-%m-%d %H:%M %Z'));(out/(filename+'.kml')).write_bytes(data)
        with zipfile.ZipFile(out/(filename+'.kmz'),'w',zipfile.ZIP_DEFLATED) as z:z.writestr('doc.kml',data)
    (out/'bulletins.json').write_text(json.dumps({'generated_at':now.isoformat(),'errors':list(errors),'bulletins':list(bs.values())},ensure_ascii=False,indent=2))
    data=kml(features,bs,'Contours BERA — fiches en ligne',base)
    (out/'bera-contours.kml').write_bytes(data)
    with zipfile.ZipFile(out/'bera-contours.kmz','w',zipfile.ZIP_DEFLATED) as z:z.writestr('doc.kml',data)
    n=tiles(features,bs,out,6,12)
    (out/'bera.aqx').write_text(aqx(base,title))
    if offline:mbtiles(out)
    if offline:shutil.copyfile(out/'bera.mbtiles',out/'bera.mbtile')
    pages=''.join('<section id="massif-'+str(b['code'])+'">'+description(b)+'</section>' for b in bs.values())
    (out/'index.html').write_text('<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>CAF BERA</title><h1>'+html.escape(title)+'</h1><p>Généré '+now.isoformat()+'</p><p><a href="bera-alpes.kmz">KMZ Alpes</a> · <a href="bera-belledonne.kmz">KMZ Belledonne</a> · <a href="bera.aqx">AQX</a> · <a href="bera-contours.kmz">Contours et fiches en ligne</a></p><p>1 vert faible · 2 jaune limité · 3 orange marqué · 4 rouge fort · 5 rouge hachuré noir très fort · gris indisponible. La couleur est le maximum du massif, sans découpage altimétrique des pentes. AQX : actualisation à chaque affichage en ligne ; KML : réimporter la copie actualisée.</p>'+pages+'</html>')
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
