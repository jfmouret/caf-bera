import datetime as dt
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import offline_package
import nivose


class OfflinePackageTests(TestCase):
    def test_three_days_one_point_per_four_hour_bucket(self):
        now=dt.datetime(2026,11,17,20,tzinfo=dt.timezone.utc)
        history=[dict(measured_at=(now-dt.timedelta(hours=i)).isoformat(),snow_cm=i) for i in range(100)]
        sampled=offline_package.sample_four_hours(history,now)
        times=[nivose.stamp(b['measured_at']) for b in sampled]
        self.assertTrue(all(now-dt.timedelta(days=3)<=t<=now for t in times))
        self.assertEqual(len({int(t.timestamp())//14400 for t in times}),len(times))
        self.assertEqual(times[-1],now)
        self.assertLessEqual(len(times),19)

    def test_four_hour_samples_are_connected_but_real_gaps_break(self):
        import math
        h=[dict(measured_at='2026-11-17T00:00:00Z',snow_cm=1),dict(measured_at='2026-11-17T04:00:00Z',snow_cm=2),dict(measured_at='2026-11-17T12:00:00Z',snow_cm=3)]
        times,values=nivose.graph_series(h,'snow_cm',max_gap_hours=4.5)
        self.assertEqual(values[:2],[1,2]);self.assertTrue(math.isnan(values[2]));self.assertEqual(values[-1],3)

    def test_default_does_not_generate_or_publish_offline_package(self):
        with tempfile.TemporaryDirectory() as d,patch('sys.argv',['offline_package.py','--output',d]),patch('offline_package.release',return_value=None),patch('offline_package.generate') as generate:
            offline_package.main()
            generate.assert_not_called()
            self.assertIn('Aucun paquet hors ligne manuel',(Path(d)/'hors-ligne.html').read_text())
