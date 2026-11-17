#!/usr/bin/env python3
"""Paquet hors ligne produit seulement sur demande explicite."""
import argparse
import copy
import datetime as dt
import html
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile
import io
import re
import xml.etree.ElementTree as ET
import bera
import nivose


def sample_four_hours(history,now):
    buckets={}
    for row in nivose.merge_history([],history,now):
        measured=nivose.stamp(row['measured_at'])
        bucket=int(measured.timestamp())//(4*3600)
        buckets[bucket]=row
    return [buckets[k] for k in sorted(buckets)]


def validate_package(archive):
    from PIL import Image
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name in ('bera-contours.kmz','nivose-alpes.kmz'):
            with zipfile.ZipFile(io.BytesIO(z.read(name))) as inner:
                assert inner.testzip() is None
                root=ET.fromstring(inner.read('doc.kml'))
                images=0
                for e in root.iter():
                    if e.tag.endswith('description') and e.text:
                        for src in re.findall(r'src="([^"]+)"',e.text):
                            Image.open(io.BytesIO(inner.read(src))).verify();images+=1
                print(name,'images hors ligne vérifiées :',images)
        assert z.read('bera.mbtile').startswith(b'SQLite format 3')


def generate(dist,archive,base):
    now=dt.datetime.now(dt.timezone.utc)
    bulletin=json.loads((dist/'bulletins.json').read_text())
    observations=json.loads((dist/'nivose.json').read_text())
    bs={int(b['code']):copy.deepcopy(b) for b in bulletin['bulletins']}
    features=[f for f in json.loads((bera.ROOT/'data/massifs.geojson').read_text())['features'] if f['properties']['code'] in bs]
    with tempfile.TemporaryDirectory() as tmp:
        out=Path(tmp)
        shutil.copytree(dist/'raw',out/'raw')
        bera.build(features,bs,out,now,base,title='BERA hors ligne — vérifier les dates',offline=True)
        stations=copy.deepcopy(observations['stations'])
        for s in stations:
            s['history']=sample_four_hours(s.get('history',[]),now)
            s['sampling_hours']=4
        nivose.build(stations,now,out,offline=True)
        readme=('CAF — PAQUET HORS LIGNE\nGénéré le '+nivose.date_label(now.isoformat())+
                '\n\nImporter bera-contours.kmz et nivose-alpes.kmz comme repères dans AlpineQuest.\n'
                'Ouvrir bera.mbtile comme carte/couche transparente au-dessus de votre fond IGN.\n'
                'Le fond IGN ne fait pas partie du paquet.\n\n'
                'BERA : dernier bulletin reçu avec ses dates officielles.\n'
                'Nivôse : trois jours maximum, dernier point de chaque tranche UTC de quatre heures.\n'
                'Les heures des graphiques sont affichées en heure de Paris.\n'
                'Les lacunes restent visibles. Hauteur totale de neige, pas cumul de neige fraîche.\n'
                'Ces copies ne se mettent pas à jour sans nouveau téléchargement.\n'
                'Source : Météo-France — Licence Ouverte 2.0.\n')
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for filename in ('bera-contours.kmz','nivose-alpes.kmz','bera.mbtile'):
                z.write(out/filename,filename)
            z.writestr('LIRE-MOI.txt',readme)
    validate_package(archive)
    print('Paquet hors ligne généré :',archive,archive.stat().st_size,'octets')


def release(repo):
    r=subprocess.run(['gh','api',f'repos/{repo}/releases/tags/hors-ligne'],capture_output=True,text=True)
    if r.returncode:
        return None
    return json.loads(r.stdout)


def download_page(dist,data):
    assets=(data or {}).get('assets',[])
    asset=next((a for a in assets if a['name']=='caf-bera-hors-ligne.zip'),None)
    content='<h1>Paquet hors ligne CAF</h1>'
    if asset:
        content+='<p><a href="'+html.escape(asset['browser_download_url'],quote=True)+'">Télécharger le dernier paquet hors ligne</a></p><p>Mis à disposition le '+html.escape(nivose.date_label(asset['updated_at']))+'. Taille : '+str(round(asset['size']/1_000_000,1))+' Mo.</p>'
    else:
        content+='<p>Aucun paquet hors ligne manuel publié pour le moment.</p>'
    content+='<p>Le paquet contient les contours BERA avec bulletins et illustrations, les Nivôse avec trois jours maximum de courbes (un point par tranche de quatre heures), et une couche raster BERA MBTiles. Aucun fond IGN.</p><p>Pour demander une nouvelle génération : propriétaire du dépôt → GitHub Actions → BERA quotidien → Run workflow → cocher Générer le paquet hors ligne. Les visiteurs peuvent télécharger le paquet sans compte GitHub.</p><p><a href="index.html">BERA en ligne</a> · <a href="nivose.html">Courbes Nivôse en ligne</a></p>'
    (dist/'hors-ligne.html').write_text('<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Paquet hors ligne CAF</title><style>body{font:18px/1.5 system-ui;max-width:48rem;margin:20px auto;padding:0 16px}</style><body>'+content+'</body></html>')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',default='dist');ap.add_argument('--generate',action='store_true');ap.add_argument('--publish',action='store_true')
    ap.add_argument('--base-url',default='https://jfmouret.github.io/caf-bera')
    args=ap.parse_args();dist=Path(args.output)
    repo=os.getenv('GITHUB_REPOSITORY','jfmouret/caf-bera')
    data=release(repo)
    if args.generate:
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/'caf-bera-hors-ligne.zip'
            generate(dist,archive,args.base_url)
            if args.publish:
                notes='Instantané hors ligne CAF. Source : Météo-France. Contrôler les dates des bulletins. Nivôse : trois jours maximum, un point par tranche de quatre heures.'
                if data:
                    subprocess.run(['gh','release','upload','hors-ligne',str(archive),'--clobber','--repo',repo],check=True)
                else:
                    subprocess.run(['gh','release','create','hors-ligne',str(archive),'--title','CAF — dernier paquet hors ligne','--notes',notes,'--target',os.environ['GITHUB_SHA'],'--repo',repo],check=True)
                data=release(repo)
                if not data or not any(a['name']==archive.name for a in data.get('assets',[])):
                    raise RuntimeError('Paquet publié non retrouvé')
            else:
                shutil.copyfile(archive,Path.cwd()/archive.name)
    elif args.publish:
        raise ValueError('--publish nécessite --generate')
    download_page(dist,data)


if __name__=='__main__':
    main()
