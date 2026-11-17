import datetime as dt,io,json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET
import bera
from PIL import Image
class BeraTests(unittest.TestCase):
    def setUp(self):
        self.raw=(bera.ROOT/'data/archive-2025.xml').read_bytes()
        self.b=bera.parse_xml(self.raw,8)
        self.features=[f for f in json.loads((bera.ROOT/'data/massifs.geojson').read_text())['features'] if f['properties']['code']==8]
    def test_real_archive(self):
        self.assertEqual(self.b['name'],'Belledonne');self.assertIn(self.b['maximum'],range(1,6));self.assertTrue(self.b['texts']['stabilite'])
    def test_altitude_and_evolution(self):
        b=bera.parse_xml((bera.ROOT/'data/belledonne-exemple.xml').read_bytes(),8)
        self.assertEqual((b['risk']['LOC1'],b['risk']['LOC2']),('<2100','>2100'));self.assertEqual(b['risk']['EVOLURISQUE2'],'2')
    def test_wrong_massif_rejected(self):
        with self.assertRaises(ValueError):bera.parse_xml(self.raw,7)
    def test_invalid_level_rejected(self):
        with self.assertRaises(ValueError):bera.parse_xml(self.raw.replace(('RISQUE1="'+self.b['risk']['RISQUE1']+'"').encode(),b'RISQUE1="9"',1),8)
    def test_expiry_and_future(self):
        start=bera.stamp(self.b['issued']);end=bera.stamp(self.b['valid_until'])
        self.assertFalse(bera.active(self.b,start-dt.timedelta(seconds=1)));self.assertTrue(bera.active(self.b,start));self.assertFalse(bera.active(self.b,end))
    def test_xml_escape_and_geometry(self):
        b=self.b;b.update(state='PÉRIMÉ',display_level=None,checked_at='test',source='https://example.org/a?x=1&y=2',notes=[])
        r=ET.fromstring(bera.kml(self.features,{8:b},'test'))
        ns={'k':bera.K};self.assertEqual(len(r.findall('.//k:Polygon',ns)),1)
        self.assertIn('DONNÉES ANCIENNES',r.find('.//k:description',ns).text)
        self.assertIn('55888888',ET.tostring(r).decode())
    def test_network_failure_outputs_unavailable(self):
        with tempfile.TemporaryDirectory() as d,patch('bera.get',side_effect=OSError('offline')),patch.dict('os.environ',{},clear=True):
            bs,errors=bera.fetch(self.features,dt.datetime.now(bera.PARIS),Path(d))
        self.assertIsNone(bs[8]['display_level']);self.assertEqual(bs[8]['state'],'INDISPONIBLE');self.assertTrue(errors)
    def test_transparent_tiles_and_tms(self):
        b=self.b;b.update(state='ARCHIVE',display_level=b['maximum'],checked_at='test',source='https://example.org',notes=[])
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);n=bera.tiles(self.features,{8:b},p,6,6);self.assertGreater(n,0)
            im=Image.open(next((p/'tiles').glob('*/*/*.png')));self.assertEqual(im.mode,'RGBA');self.assertLess(im.getchannel('A').getextrema()[0],255)
            bera.mbtiles(p)
            import sqlite3
            db=sqlite3.connect(p/'bera.mbtiles');self.assertEqual(db.execute('select count(*) from tiles').fetchone()[0],n);db.close()
    def test_aqx_is_raster_layer(self):
        r=ET.fromstring(bera.aqx('https://host.test/bera','BERA'))
        self.assertEqual(r.find('source').get('layer'),'true');self.assertEqual(r.find('.//update-delay').text,'0D');self.assertIn('/tiles-v3/{$z}',r.find('.//server').text)
    def test_contours_keep_offline_text_and_online_pdf(self):
        b=self.b.copy();b.update(checked_at='test',state='ARCHIVE',display_level=None,online_pdf='https://host.test/bulletins/8.html',notes=[])
        root=ET.fromstring(bera.kml(self.features,{8:b},'test','https://host.test'))
        info=root.find('.//{'+bera.K+'}description').text
        self.assertIn('Lecture hors ligne',info)
        self.assertIn(b['valid_until'],info)
        self.assertIn('stabilité',info)
        self.assertIn('https://host.test/bulletins/8.html',info)
    def test_kmz_packages_local_images(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder);(out/'media/8').mkdir(parents=True)
            Image.new('RGB',(10,10)).save(out/'media/8/picto.png')
            b=self.b.copy();b['offline_images']=[{'path':'media/8/picto.png','caption':'image de test'}]
            bera.write_kmz(out/'test.kmz',b'<kml/>',self.features,{8:b},out)
            with zipfile.ZipFile(out/'test.kmz') as z:
                self.assertIsNone(z.testzip())
                self.assertIn('media/8/picto.png',z.namelist())
    def test_pdf_route_only_redirects_when_bulletin_valid(self):
        b=self.b.copy();b['display_level']=b['maximum']
        page=bera.pdf_page(b,'https://host.test/raw/8.pdf')
        self.assertIn('window.location.replace',page)
        self.assertIn('Date.now()<until',page)
        b['display_level']=None
        page=bera.pdf_page(b,'https://host.test/raw/8.pdf')
        self.assertNotIn('window.location.replace',page)
        self.assertIn('indisponible',page)
    def test_overview_has_no_displaced_labels(self):
        vercors=[f for f in json.loads((bera.ROOT/'data/massifs.geojson').read_text())['features'] if f['properties']['code']==14]
        bs={14:{'state':'INDISPONIBLE','display_level':None}}
        self.assertEqual(bera.map_labels(vercors,bs,6),[])
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder);bera.tiles(vercors,bs,out,6,6)
            # Cette tuile couvre aussi une zone très loin à l'ouest du Vercors.
            # Le coin ne doit pas contenir un ancien cartouche blanc de tuile.
            image=Image.open(next((out/'tiles/6').glob('*/*.png')))
            self.assertEqual(image.getpixel((8,8))[3],0)
    def test_one_label_per_massif_and_aqx_coverage(self):
        b={'state':'INDISPONIBLE','display_level':None}
        self.assertEqual(len(bera.map_labels(self.features,{8:b},9)),1)
        r=ET.fromstring(bera.aqx('https://host.test','BERA',self.features))
        for node in r.findall('.//zoom-levels'):
            self.assertEqual(tuple(map(int,node.findtext('tiles-bounds').split(','))),bera.map_bounds(self.features,int(node.get('z'))))
if __name__=='__main__':unittest.main()
