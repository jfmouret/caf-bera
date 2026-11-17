"""Contrôle des images embarquées, sans connexion à partir des fichiers générés."""
import io,json,zipfile,xml.etree.ElementTree as ET
import argparse
from html.parser import HTMLParser
from pathlib import Path
from PIL import Image
class Images(HTMLParser):
    def __init__(self):super().__init__();self.sources=[]
    def handle_starttag(self,tag,attrs):
        if tag=='img':self.sources.append(dict(attrs)['src'])
parser=argparse.ArgumentParser();parser.add_argument('--directory',default=str(Path(__file__).resolve().parent/'dist'));args=parser.parse_args()
out=Path(args.directory)
for name in ['bera-belledonne.kmz','bera-alpes.kmz','bera-contours.kmz']:
    with zipfile.ZipFile(out/name) as z:
        assert z.testzip() is None
        root=ET.fromstring(z.read('doc.kml'));sources=set()
        for node in root.findall('.//{http://www.opengis.net/kml/2.2}description'):
            assert 'Lecture hors ligne' in node.text
            parser=Images();parser.feed(node.text);sources.update(parser.sources)
        for source in sources:
            assert not source.startswith(('http:','https:','data:'))
            assert source in z.namelist(),source
            with Image.open(io.BytesIO(z.read(source))) as image:image.verify()
        print(name,':',len(sources),'images embarquées vérifiées,',round((out/name).stat().st_size/1e6,2),'Mo')
data=json.loads((out/'bulletins.json').read_text())
print('Massifs avec illustrations officielles :',sum(bool(b.get('offline_images')) for b in data['bulletins']),'/',len(data['bulletins']))
