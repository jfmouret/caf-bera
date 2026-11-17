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


def description(s, now):
    esc = html.escape
    b = s.get('observation')
    parts = [f'<div style="font-size:18px;max-width:320px;line-height:1.4"><h2>{esc(s["name"])}</h2>',
             f'<p>{esc(s["region"])} · {s["altitude"]} m<br/>Station Météo-France {s["id"]}</p>']
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
    parts.append('<p>Copie préparée le ' + esc(date_label(now.isoformat())) + '.</p>')
    parts.append(f'<p><a href="https://donneespubliques.meteofrance.fr/metadonnees_publiques/fiches/fiche_{s["id"]}.pdf">Fiche officielle de la station — connexion requise</a></p>')
    parts.append('<p>Source : Météo-France · Licence Ouverte 2.0. Mesures ponctuelles au site de la station ; elles ne décrivent pas chaque pente. Une variation de hauteur totale de neige n’est pas une mesure de neige fraîche. Ce KMZ est un instantané : réimporter pour actualiser.</p></div>')
    return ''.join(parts)


def make_kml(stations, now):
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
        sub(pm, 'description', description(s, now))
        pt = sub(pm, 'Point'); sub(pt,'altitudeMode','clampToGround')
        sub(pt, 'coordinates', f'{s["longitude"]},{s["latitude"]},0')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def build(stations, now, out):
    from PIL import Image, ImageDraw
    im = Image.new('RGBA',(48,48)); draw = ImageDraw.Draw(im)
    draw.ellipse((4,4,44,44),fill='white',outline='black',width=3)
    draw.line((24,11,24,37),fill='black',width=3)
    draw.line((12,17,36,31),fill='black',width=3)
    draw.line((12,31,36,17),fill='black',width=3)
    buf = io.BytesIO(); im.save(buf,format='PNG')
    for name, selected in [('nivose-alpes',stations),('nivose-belledonne',[s for s in stations if s['id']=='38005402'])]:
        kml = make_kml(selected,now)
        (out/(name+'.kml')).write_bytes(kml)
        with zipfile.ZipFile(out/(name+'.kmz'),'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('doc.kml',kml); z.writestr('icons/station.png',buf.getvalue())
    sections = ''.join(description(s,now) for s in stations)
    (out/'nivose.html').write_text('<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Nivôse Alpes</title><body><h1>Nivôse Alpes</h1><p><a href="nivose-alpes.kmz">Télécharger KMZ Alpes</a> · <a href="nivose-belledonne.kmz">Télécharger KMZ Aigleton</a></p>'+sections+'</body></html>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', default='dist'); ap.add_argument('--base-url',default='https://jfmouret.github.io/caf-bera')
    args = ap.parse_args(); out = Path(args.output); out.mkdir(parents=True,exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    catalog = json.loads((ROOT/'data/nivose-stations.json').read_text())
    stations = catalog['stations']
    key = os.getenv('MF_OBS_API_KEY') or os.getenv('MF_API_KEY')
    previous = {}
    try:
        previous = {s['id']:s for s in json.loads(get(args.base_url.rstrip('/')+'/nivose.json'))['stations']}
    except Exception:
        pass
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
        print(s['name']+': '+(s['observation']['measured_at'] if s['observation'] else s.get('error','indisponible')))
    result = dict(generated_at=now.isoformat(),source='Météo-France',licence=catalog['licence'],catalog_source=catalog['source'],access_error=access_error,stations=stations)
    (out/'nivose.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    build(stations,now,out)
    index = out/'index.html'
    if index.exists():
        text = index.read_text(); marker='<p><a href="nivose.html">Stations Nivôse Alpes — observations et téléchargements</a></p>'
        if marker not in text:
            index.write_text(text.replace('<h1>',marker+'<h1>',1))
    print(f'Nivôse : {len(stations)} stations ; {sum(bool(s["observation"]) for s in stations)} avec une mesure.')


if __name__ == '__main__':
    main()
