#!/usr/bin/env python3
"""Observations officielles Nivôse -> repères KML/KMZ hors ligne."""
import argparse
import csv
import datetime as dt
import html
import io
import json
import math
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
API = 'https://public-api.meteofrance.fr/public/DPObs/v2/'
PARIS = ZoneInfo('Europe/Paris')
K = 'http://www.opengis.net/kml/2.2'
ET.register_namespace('', K)


def get(url, key=None):
    headers = {'User-Agent': 'CAF-BERA-Nivose/1.0'}
    if key:
        headers['apikey'] = key
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=25) as r:
        return r.read()


def stamp(s):
    value = dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('Heure de mesure sans fuseau')
    return value


def number(value):
    if value is None or value == '':
        return None
    n = float(value)
    return n if math.isfinite(n) else None


def parse_observation(payload, station_id, now):
    data = json.loads(payload)
    if isinstance(data, dict):
        rows = data.get('features', [data] if data.get('type') == 'Feature' else [])
    elif isinstance(data, list):
        rows = data
    else:
        raise ValueError('Format observation inattendu')
    candidates = []
    for row in rows:
        p = row.get('properties', row)
        if str(p.get('geo_id_insee', '')).zfill(8) != station_id:
            raise ValueError('Identifiant de station incohérent')
        measured = stamp(p['validity_time'])
        if measured > now:
            continue
        # Unités officielles DPObs : température K, neige m, vent m/s.
        t, snow, wind, gust = [number(p.get(k)) for k in ('t', 'sss', 'ff', 'raf')]
        candidates.append(dict(measured_at=measured.isoformat(),
            temperature_c=None if t is None else round(t - 273.15, 2),
            snow_cm=None if snow is None or snow < 0 else round(snow * 100, 2),
            wind_kmh=None if wind is None or wind < 0 else round(wind * 3.6, 2),
            gust_kmh=None if gust is None or gust < 0 else round(gust * 3.6, 2),
            wind_direction_deg=number(p.get('dd')), humidity_percent=number(p.get('u'))))
    return max(candidates, key=lambda b: stamp(b['measured_at'])) if candidates else None


def date_label(s):
    return stamp(s).astimezone(PARIS).strftime('%d/%m/%Y à %H:%M %Z')


def merge_history(old, incoming, now):
    """Dédupliquer les heures réelles de mesure, sans inventer de points."""
    merged = {}
    for row in old + incoming:
        try:
            measured = stamp(row['measured_at']).astimezone(dt.timezone.utc)
            if now - dt.timedelta(days=3) <= measured <= now:
                merged[measured] = dict(row, measured_at=measured.isoformat())
        except (KeyError, ValueError, TypeError):
            continue
    return [merged[t] for t in sorted(merged)]


def missing_hours(history, now):
    known = {stamp(b['measured_at']).astimezone(dt.timezone.utc).replace(minute=0,second=0,microsecond=0) for b in history}
    end = now.astimezone(dt.timezone.utc).replace(minute=0,second=0,microsecond=0)
    return [end-dt.timedelta(hours=i) for i in range(1,24) if end-dt.timedelta(hours=i) not in known]


def graph_series(history, field, max_gap_hours=1.5):
    times, values = [], []
    previous = None
    for b in history:
        t = stamp(b['measured_at']).astimezone(PARIS)
        if previous and t.astimezone(dt.timezone.utc)-previous.astimezone(dt.timezone.utc) > dt.timedelta(hours=max_gap_hours):
            times.append(previous+dt.timedelta(minutes=30)); values.append(float('nan'))
        times.append(t)
        values.append(b.get(field) if b.get(field) is not None else float('nan'))
        previous = t
    return times, values


def chart(s, now, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as dates
    import numpy as np
    history = s.get('history', [])
    if not history:
        return None
    fig, axes = plt.subplots(3, 1, figsize=(8,9), sharex=True, layout='constrained')
    fig.suptitle(s['name'].replace('-NIVOSE','')+' · '+str(s['altitude'])+' m',fontsize=19,weight='bold')
    def line(ax, key, color, label):
        x,y = graph_series(history,key,s.get('sampling_hours',1)+.5)
        ax.plot(x,y,color=color,label=label,linewidth=1.8,marker='.',markersize=3)
        return x,np.array(y,dtype=float)
    line(axes[0],'wind_kmh','#e69100','Vent moyen')
    line(axes[0],'gust_kmh','#b62025','Rafale horaire')
    axes[0].set_ylabel('Vent (km/h)',fontsize=14); axes[0].set_ylim(bottom=0)
    axes[0].legend(loc='upper left',fontsize=11,ncol=2)
    x,y = line(axes[1],'temperature_c','#575757','Température')
    axes[1].fill_between(x,y,0,where=y>=0,color='#ff7777',alpha=.65,interpolate=True)
    axes[1].fill_between(x,y,0,where=y<0,color='#7373ff',alpha=.65,interpolate=True)
    axes[1].axhline(0,color='#777',linewidth=.6)
    axes[1].set_ylabel('Température (°C)',fontsize=14)
    line(axes[2],'snow_cm','#15803d','Hauteur totale')
    axes[2].set_ylabel('Neige au sol (cm)',fontsize=14); axes[2].set_ylim(bottom=0)
    if axes[2].get_ylim()[1] < 1:
        axes[2].set_ylim(0,1)
    for ax,field in zip(axes,('wind_kmh','temperature_c','snow_cm')):
        ax.grid(True,color='#d4d4d4',linewidth=.6); ax.tick_params(labelsize=12)
        keys = ('wind_kmh','gust_kmh') if field=='wind_kmh' else (field,)
        if not any(b.get(k) is not None for b in history for k in keys):
            ax.text(.5,.5,'Mesures indisponibles',transform=ax.transAxes,ha='center',fontsize=14)
    start = max(now-dt.timedelta(days=3),min(stamp(b['measured_at']) for b in history))
    if now-start < dt.timedelta(hours=24):
        start = now-dt.timedelta(hours=24)
    axes[2].set_xlim(start,now)
    locator = dates.AutoDateLocator(minticks=4,maxticks=6,tz=PARIS)
    axes[2].xaxis.set_major_locator(locator)
    axes[2].xaxis.set_major_formatter(dates.DateFormatter('%d/%m\n%H h',tz=PARIS))
    axes[2].set_xlabel('Heure de Paris · interruptions = données manquantes',fontsize=12)
    fig.supxlabel('Source : Météo-France · dernière mesure '+stamp(history[-1]['measured_at']).astimezone(PARIS).strftime('%d/%m/%Y %H:%M')+'\nHauteur totale du manteau, pas cumul de neige fraîche',fontsize=10)
    target = out/'nivose-media'/f'{s["id"]}.png'; target.parent.mkdir(exist_ok=True)
    fig.savefig(target,dpi=140,facecolor='white'); plt.close(fig)
    return target


def description(s, now):
    esc = html.escape
    b = s.get('observation')
    parts = [f'<div style="font-size:18px;max-width:320px;line-height:1.4"><h2>{esc(s["name"])}</h2>',
             f'<p>{esc(s["region"])} · {s["altitude"]} m<br/>Station Météo-France {s["id"]}</p>']
    if s.get('live_url'):
        parts.append('<p><a href="'+esc(s['live_url'],quote=True)+'"><b>Courbes actualisées en ligne — connexion requise</b></a></p>')
    if s.get('sampling_hours') == 4:
        parts.append('<p>Courbes hors ligne : un point par tranche de quatre heures ; trois jours maximum.</p>')
    if s.get('chart_local'):
        parts.append('<p><b>Courbes enregistrées hors ligne</b></p><img src="'+esc(s['chart_local'],quote=True)+'" width="320" alt="Vent, température et hauteur totale de neige"/>')
        history = s.get('history',[])
        if history:
            parts.append('<p>Historique disponible depuis le '+esc(date_label(history[0]['measured_at']))+'. Conservation : 3 jours.</p>')
    if b:
        parts.append('<p><b>Mesure du ' + esc(date_label(b['measured_at'])) + '</b></p>')
        if now - stamp(b['measured_at']) > dt.timedelta(hours=3):
            parts.append('<p><b>Mesure ancienne : plus de 3 heures.</b></p>')
        if s.get('retained_previous'):
            parts.append('<p>Dernière copie conservée ; nouvelle mesure non récupérée.</p>')
        for key, name, unit in [('snow_cm','Hauteur totale de neige','cm'),
                               ('temperature_c','Température','°C'),
                               ('wind_kmh','Vent moyen (10 min)','km/h'),
                               ('gust_kmh','Rafale maximale sur l’heure','km/h'),
                               ('wind_direction_deg','Direction du vent (provenance)','°'),
                               ('humidity_percent','Humidité','%')]:
            v = b.get(key)
            text = 'non disponible' if v is None else f'{v:g} {unit}'
            parts.append(f'<p><b>{name} :</b> {text}</p>')
    else:
        parts.append('<p><b>Mesures indisponibles.</b></p>')
    if s.get('error'):
        parts.append('<p>' + esc(s['error']) + '</p>')
    if s.get('history_error'):
        parts.append('<p>'+esc(s['history_error'])+'</p>')
    parts.append('<p>Copie préparée le ' + esc(date_label(now.isoformat())) + '.</p>')
    parts.append(f'<p><a href="https://donneespubliques.meteofrance.fr/metadonnees_publiques/fiches/fiche_{s["id"]}.pdf">Fiche officielle de la station — connexion requise</a></p>')
    parts.append('<p>Source : Météo-France · Licence Ouverte 2.0. Mesures ponctuelles au site de la station ; elles ne décrivent pas chaque pente. Une variation de hauteur totale de neige n’est pas une mesure de neige fraîche. Ce KMZ est un instantané : réimporter pour actualiser.</p></div>')
    return ''.join(parts)


def make_kml(stations, now, online_only=False):
    def sub(parent, tag, text=None, **attrs):
        child = ET.SubElement(parent, '{'+K+'}'+tag, attrs)
        if text is not None:
            child.text = str(text)
        return child
    root = ET.Element('{'+K+'}kml')
    doc = sub(root, 'Document')
    sub(doc, 'name', 'Nivôse Alpes — '+now.astimezone(PARIS).strftime('%d/%m/%Y %H:%M'))
    for style_id, color in [('observed','ffff8800'),('missing','ff888888')]:
        st = sub(doc, 'Style', id=style_id)
        icon = sub(st, 'IconStyle'); sub(icon, 'color', color); sub(icon, 'scale', 0.8)
        sub(sub(icon, 'Icon'), 'href', 'icons/station.png')
        sub(sub(st, 'LabelStyle'), 'scale', 1.0)
    for s in stations:
        pm = sub(doc, 'Placemark')
        sub(pm, 'name', s['name'].replace('-NIVOSE','')+' · '+str(s['altitude'])+' m')
        sub(pm, 'styleUrl', '#observed' if s.get('observation') else '#missing')
        info = ('<div style="font-size:18px;max-width:320px"><h2>'+html.escape(s['name'])+'</h2><p>'+str(s['altitude'])+' m</p><p><a href="'+html.escape(s.get('live_url',''),quote=True)+'"><b>Ouvrir les courbes actualisées — connexion requise</b></a></p><p>Ce repère est un lien permanent ; les mesures se consultent en ligne.</p></div>') if online_only else description(s, now)
        sub(pm, 'description', info)
        pt = sub(pm, 'Point'); sub(pt,'altitudeMode','clampToGround')
        sub(pt, 'coordinates', f'{s["longitude"]},{s["latitude"]},0')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def build(stations, now, out, offline=True):
    from PIL import Image, ImageDraw
    im = Image.new('RGBA',(48,48)); draw = ImageDraw.Draw(im)
    draw.ellipse((4,4,44,44),fill='white',outline='black',width=3)
    draw.line((24,11,24,37),fill='black',width=3)
    draw.line((12,17,36,31),fill='black',width=3)
    draw.line((12,31,36,17),fill='black',width=3)
    buf = io.BytesIO(); im.save(buf,format='PNG')
    for s in stations:
        image = chart(s,now,out)
        if image:
            s['chart_local'] = image.relative_to(out).as_posix()
    live_dir=out/'nivose'; live_dir.mkdir(exist_ok=True)
    style='<style>body{font:18px/1.4 system-ui;max-width:850px;margin:20px auto;padding:0 12px}img{max-width:100%;height:auto}h1{font-size:1.5em}</style>'
    for s in stations:
        online = dict(s)
        if s.get('chart_local'):
            online['chart_local'] = '../'+s['chart_local']+'?v='+urllib.parse.quote(now.isoformat())
        body=description(online,now).replace('width="320"','width="800"').replace('max-width:320px','max-width:850px').replace('Courbes enregistrées hors ligne','Courbes actualisées').replace('Ce KMZ est un instantané : réimporter pour actualiser.','Cette page donne accès aux dernières courbes publiées.')
        js='<script>const built='+json.dumps(now.isoformat())+';async function refresh(){try{const r=await fetch("../nivose-version.json",{cache:"no-store"});if(!r.ok)return;const d=await r.json();if(d.generated_at!==built){const u=new URL(location.href);if(u.searchParams.get("v")!==d.generated_at){u.searchParams.set("v",d.generated_at);location.replace(u.href);}}}catch(e){}}refresh();setInterval(refresh,300000);</script>'
        (live_dir/(s['id']+'.html')).write_text('<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(s['name'])+'</title>'+style+'<body><p><a href="../nivose.html">Toutes les stations</a> · Actualisation de la page toutes les 5 minutes</p>'+body+js+'</body></html>')
    for name, selected in [('nivose-alpes',stations),('nivose-belledonne',[s for s in stations if s['id']=='38005402'])]:
        kml = make_kml(selected,now,online_only=not offline)
        (out/(name+'.kml')).write_bytes(kml)
        with zipfile.ZipFile(out/(name+'.kmz'),'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('doc.kml',kml); z.writestr('icons/station.png',buf.getvalue())
            for s in selected:
                if offline and s.get('chart_local'):
                    z.write(out/s['chart_local'],s['chart_local'])
    sections = ''.join('<li><a href="nivose/'+s['id']+'.html">'+html.escape(s['name'])+'</a> · '+str(s['altitude'])+' m</li>' for s in stations)
    (out/'nivose-version.json').write_text(json.dumps({'generated_at':now.isoformat()}))
    (out/'nivose.html').write_text('<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Nivôse Alpes</title>'+style+'<body><h1>Nivôse Alpes</h1><p><a href="hors-ligne.html">Paquet hors ligne — génération manuelle</a></p><p>Collecte à 06 h 30, 10 h 30, 14 h 30, 16 h 30, 18 h 30 et 20 h 30 (Paris). Mesures horaires ; historique progressif de trois jours. GitHub peut retarder le démarrage.</p><p><a href="nivose-alpes.kmz">Repères Alpes — liens vers les courbes</a> · <a href="nivose-belledonne.kmz">Repère Aigleton — lien vers les courbes</a></p><ul>'+sections+'</ul></body></html>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', default='dist'); ap.add_argument('--base-url',default='https://jfmouret.github.io/caf-bera')
    ap.add_argument('--online-only',action='store_true')
    args = ap.parse_args(); out = Path(args.output); out.mkdir(parents=True,exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    catalog = json.loads((ROOT/'data/nivose-stations.json').read_text())
    stations = catalog['stations']
    key = os.getenv('MF_OBS_API_KEY') or os.getenv('MF_API_KEY')
    previous = {}
    if (out/'nivose.json').exists():
        previous={s['id']:s for s in json.loads((out/'nivose.json').read_text())['stations']}
    else:
        try:
            previous = {s['id']:s for s in json.loads(get(args.base_url.rstrip('/')+'/nivose.json'))['stations']}
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise RuntimeError('Historique précédent non récupéré ; publication interrompue pour le préserver') from e
        except Exception as e:
            raise RuntimeError('Historique précédent non récupéré ; publication interrompue pour le préserver') from e
    access_error = None
    if key:
        try:
            data = get(API+'liste-stations',key)
            rows = list(csv.DictReader(data.decode('utf-8-sig').splitlines(),delimiter=';'))
            selected = [r for r in rows if 'NIVOSE' in r.get('Nom_usuel','') and r['Id_station'][:2] in ('04','05','06','38','73','74')]
            if not selected:
                raise ValueError('Catalogue API sans station Nivôse alpine')
            stations = [dict(id=r['Id_station'],name=r['Nom_usuel'],latitude=float(r['Latitude']),longitude=float(r['Longitude']),altitude=int(r['Altitude']),region='Alpes du Sud' if r['Id_station'][:2] in ('04','05','06') else 'Alpes du Nord') for r in selected]
        except urllib.error.HTTPError as e:
            if e.code in (401,403):
                access_error = f'API Observation : accès refusé (HTTP {e.code}). Souscription ou clé Observation à vérifier.'
            else:
                print(f'Catalogue API : HTTP {e.code} ; catalogue officiel enregistré utilisé.')
        except Exception as e:
            print('Catalogue API : '+type(e).__name__+' ; catalogue officiel enregistré utilisé.')
    else:
        access_error = 'Clé API Observation absente.'
    for s in stations:
        s['checked_at'] = now.isoformat(); s['observation'] = None
        s['source'] = API+'station/horaire?'+urllib.parse.urlencode({'id_station':s['id'],'format':'geojson'})
        if access_error:
            s['error'] = access_error
        else:
            try:
                payload = get(s['source'],key)
                s['observation'] = parse_observation(payload,s['id'],now)
                if not s['observation']:
                    s['error'] = 'Aucune mesure horaire exploitable reçue.'
            except urllib.error.HTTPError as e:
                s['error'] = f'API Observation : HTTP {e.code}.'
                if e.code in (401,403):
                    access_error = f'API Observation : accès refusé (HTTP {e.code}). Souscription ou clé Observation à vérifier.'
            except Exception as e:
                s['error'] = 'Téléchargement ou contrôle des mesures : '+type(e).__name__
            time.sleep(0.7)
        prior = previous.get(s['id'],{}).get('observation')
        if prior:
            try:
                if stamp(prior['measured_at']) <= now and (not s['observation'] or stamp(prior['measured_at']) > stamp(s['observation']['measured_at'])):
                    s['observation'] = prior; s['retained_previous'] = True
            except (KeyError,TypeError,ValueError):
                pass
        old = previous.get(s['id'],{}).get('history',[])
        if prior:
            old=old+[prior]
        incoming=[s['observation']] if s['observation'] else []
        history=merge_history(old,incoming,now)
        errors=0
        if not access_error:
            for hour in missing_hours(history,now):
                try:
                    url=s['source']+'&date='+urllib.parse.quote(hour.strftime('%Y-%m-%dT%H:%M:%SZ'))
                    row=parse_observation(get(url,key),s['id'],now)
                    if row:
                        incoming.append(row)
                except urllib.error.HTTPError as e:
                    errors+=1
                    if e.code in (401,403,429):
                        s['history_error']='Récupération historique suspendue : HTTP '+str(e.code)
                        break
                except Exception:
                    errors+=1
                time.sleep(.7)
        s['history']=merge_history(old,incoming,now)
        if s['history']:
            s['observation']=s['history'][-1]
        if errors:
            s['history_error']=s.get('history_error',f'{errors} requête(s) historique(s) en échec ; lacunes conservées.')
        s['live_url']=args.base_url.rstrip('/')+'/nivose/'+s['id']+'.html'
        print(s['name']+': '+str(len(s['history']))+' mesures ; '+(s['observation']['measured_at'] if s['observation'] else s.get('error','indisponible')),flush=True)
    result = dict(generated_at=now.isoformat(),source='Météo-France',licence=catalog['licence'],catalog_source=catalog['source'],access_error=access_error,stations=stations)
    build(stations,now,out,offline=not args.online_only)
    (out/'nivose.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    index = out/'index.html'
    if index.exists():
        text = index.read_text(); marker='<p><a href="nivose.html">Stations Nivôse Alpes — observations et téléchargements</a></p>'
        if marker not in text:
            index.write_text(text.replace('<h1>',marker+'<h1>',1))
    print(f'Nivôse : {len(stations)} stations ; {sum(bool(s["observation"]) for s in stations)} avec une mesure.')


if __name__ == '__main__':
    main()
