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

    def test_history_merge_deduplicates_utc_and_keeps_three_days(self):
        old=[dict(measured_at='2026-11-17T20:00:00+01:00',snow_cm=2),
             dict(measured_at='2026-11-13T19:00:00Z',snow_cm=99),
             dict(measured_at='2026-11-18T19:00:00Z',snow_cm=99)]
        new=[dict(measured_at='2026-11-17T19:00:00Z',snow_cm=3)]
        h=nivose.merge_history(old,new,self.now)
        self.assertEqual(len(h),1);self.assertEqual(h[0]['snow_cm'],3)

    def test_missing_hours_backfills_only_recent_gaps(self):
        h=[dict(measured_at='2026-11-17T19:00:00Z')]
        hours=nivose.missing_hours(h,self.now)
        self.assertEqual(len(hours),22)
        self.assertNotIn(dt.datetime(2026,11,17,19,tzinfo=dt.timezone.utc),hours)
        self.assertTrue(all(self.now-dt.timedelta(hours=24)<t<self.now for t in hours))

    def test_graph_breaks_across_missing_hours(self):
        import math
        h=[dict(measured_at='2026-11-17T16:00:00Z',snow_cm=0),dict(measured_at='2026-11-17T19:00:00Z',snow_cm=3)]
        times,values=nivose.graph_series(h,'snow_cm')
        self.assertEqual(len(times),3);self.assertTrue(math.isnan(values[1]))

    def test_kmz_embeds_chart_and_has_permanent_online_link(self):
        from PIL import Image
        b=nivose.parse_observation(self.payload(),'38005402',self.now)
        s=dict(self.station,observation=b,history=[b],live_url='https://example.org/nivose/38005402.html')
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);nivose.build([s],self.now,out)
            with zipfile.ZipFile(out/'nivose-belledonne.kmz') as z:
                self.assertIn('nivose-media/38005402.png',z.namelist())
                import io
                Image.open(io.BytesIO(z.read('nivose-media/38005402.png'))).verify()
                root=ET.fromstring(z.read('doc.kml'));desc=root.findtext('.//{'+nivose.K+'}Placemark/{'+nivose.K+'}description')
                self.assertIn('https://example.org/nivose/38005402.html',desc)
                self.assertIn('src="nivose-media/38005402.png"',desc)
            self.assertIn('cache:"no-store"',(out/'nivose/38005402.html').read_text())

    def test_online_reperes_do_not_embed_offline_charts(self):
        b=nivose.parse_observation(self.payload(),'38005402',self.now)
        s=dict(self.station,observation=b,history=[b],live_url='https://example.org/nivose/38005402.html')
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);nivose.build([s],self.now,out,offline=False)
            with zipfile.ZipFile(out/'nivose-alpes.kmz') as z:
                self.assertFalse(any(n.startswith('nivose-media/') for n in z.namelist()))
                root=ET.fromstring(z.read('doc.kml'))
                desc=root.findtext('.//{'+nivose.K+'}Placemark/{'+nivose.K+'}description')
                self.assertIn(s['live_url'],desc)
                self.assertNotIn('Mesure du ',desc)
            self.assertTrue((out/'nivose-media/38005402.png').exists())
