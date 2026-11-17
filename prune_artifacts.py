#!/usr/bin/env python3
"""Limiter uniquement les archives générées par le projet CAF BERA."""
import argparse
import json
import os
import subprocess


def plan(artifacts, before_upload=False, current_run=None):
    limits={'bera-en-ligne':1 if before_upload else 2,'github-pages':1,'bera-fichiers':1 if before_upload else 0}
    active=[a for a in artifacts if not a.get('expired',False)]
    if not before_upload:
        # Ne pas nettoyer après publication sans les deux nouvelles archives.
        for name in ('bera-en-ligne','github-pages'):
            if not any(a['name']==name and str(a.get('workflow_run',{}).get('id'))==str(current_run) for a in active):
                raise ValueError('Nouvelle archive absente : '+name)
    delete=[]
    for name,keep in limits.items():
        matching=sorted((a for a in active if a['name']==name),key=lambda a:(a['created_at'],a['id']),reverse=True)
        delete.extend(matching[keep:])
    return delete


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--apply',action='store_true')
    ap.add_argument('--before-upload',action='store_true')
    args=ap.parse_args()
    repo=os.environ['GITHUB_REPOSITORY'];run=os.environ['GITHUB_RUN_ID']
    pages=json.loads(subprocess.check_output(['gh','api','--paginate','--slurp',f'repos/{repo}/actions/artifacts?per_page=100']))
    artifacts=[a for page in pages for a in page['artifacts']]
    selected=plan(artifacts,args.before_upload,run)
    print('Archives générées à retirer :',len(selected),'soit',round(sum(a['size_in_bytes'] for a in selected)/1_000_000,1),'Mo')
    for a in selected:
        print(a['name'],a['id'])
        if args.apply:
            subprocess.run(['gh','api','--method','DELETE',f'repos/{repo}/actions/artifacts/{a["id"]}'],check=True,capture_output=True)
    remaining=[a for a in artifacts if a not in selected and a['name'] in ('bera-en-ligne','bera-fichiers','github-pages') and not a.get('expired',False)]
    print('Archives du projet conservées :',len(remaining),'soit',round(sum(a['size_in_bytes'] for a in remaining)/1_000_000,1),'Mo')


if __name__=='__main__':
    main()
