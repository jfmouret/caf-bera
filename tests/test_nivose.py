import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

import nivose


class NivoseTests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 11, 17, 20, tzinfo=dt.timezone.utc)
        self.station = dict(id='38005402',name='AIGLETON-NIVOSE',altitude=2240,
                            latitude=45.231,longitude=6.038167,region='Alpes du Nord')

    def payload(self, **values):
        p = dict(geo_id_insee='38005402',validity_time='2026-11-17T19:00:00Z',
                 t=273.15,sss=0.32,ff=5,raf=10,dd=270,u=75)
        p.update(values)
        return json.dumps([dict(type='Feature',properties=p)]).encode()

    def test_official_units(self):
        b = nivose.parse_observation(self.payload(),'38005402',self.now)
        self.assertEqual((b['snow_cm'],b['temperature_c'],b['wind_kmh'],b['gust_kmh']),(32,0,18,36))

    def test_null_is_not_zero(self):
        b = nivose.parse_observation(self.payload(sss=None,t=None,ff=None,raf=None),'38005402',self.now)
        self.assertIsNone(b['snow_cm']); self.assertIsNone(b['temperature_c'])
        self.assertIn('non disponible',nivose.description(dict(self.station,observation=b),self.now))

    def test_station_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            nivose.parse_observation(self.payload(geo_id_insee='73040402'),'38005402',self.now)

    def test_future_measure_not_used(self):
        self.assertIsNone(nivose.parse_observation(self.payload(validity_time='2026-11-18T19:00:00Z'),'38005402',self.now))

    def test_kmz_self_contained_and_coordinates(self):
        with tempfile.TemporaryDirectory() as d:
            nivose.build([self.station],self.now,Path(d))
            with zipfile.ZipFile(Path(d)/'nivose-belledonne.kmz') as z:
                root=ET.fromstring(z.read('doc.kml')); ns={'k':nivose.K}
                self.assertEqual(root.findtext('.//k:coordinates',namespaces=ns),'6.038167,45.231,0')
                self.assertIn('Mesures indisponibles',root.findtext('.//k:Placemark/k:description',namespaces=ns))
                for icon in root.findall('.//k:href',ns):
                    self.assertIn(icon.text,z.namelist())

    def test_official_alpine_catalog(self):
        rows=json.loads((nivose.ROOT/'data/nivose-stations.json').read_text())['stations']
        self.assertEqual(len({s['id'] for s in rows}),len(rows))
        self.assertTrue(any(s['id']=='38005402' and s['altitude']==2240 for s in rows))
        self.assertEqual({s['region'] for s in rows},{'Alpes du Nord','Alpes du Sud'})
