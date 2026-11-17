"""Serveur de test local. Sur Android, lancer dans Termux depuis le projet."""
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
import argparse
p=argparse.ArgumentParser();p.add_argument('--directory',default='dist');p.add_argument('--port',type=int,default=8765);a=p.parse_args()
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=a.directory,**kwargs)
    def end_headers(self):
        self.send_header('Cache-Control','no-store');super().end_headers()
    def do_GET(self):
        if self.path.startswith('/tiles/') and self.path.endswith('.png') and not Path(self.translate_path(self.path)).is_file():self.path='/empty.png'
        super().do_GET()
ThreadingHTTPServer(('0.0.0.0',a.port),Handler).serve_forever()
