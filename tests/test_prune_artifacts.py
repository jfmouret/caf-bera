import unittest
from prune_artifacts import plan


class PruneTests(unittest.TestCase):
    def setUp(self):
        self.artifacts=[]
        for i in range(1,5):
            for j,name in enumerate(('bera-en-ligne','github-pages')):
                self.artifacts.append(dict(id=i*10+j,name=name,created_at=f'2026-11-17T0{i}:00:00Z',workflow_run={'id':i}))
        self.artifacts.append(dict(id=99,name='autre-document',created_at='2026-11-01T00:00:00Z'))

    def test_preserves_two_backups_latest_page_and_other_names(self):
        gone={a['id'] for a in plan(self.artifacts,current_run=4)}
        self.assertEqual(gone,{10,11,20,21,31})
        self.assertNotIn(99,gone)

    def test_refuses_cleanup_without_current_backups(self):
        with self.assertRaises(ValueError):plan(self.artifacts,current_run=5)

    def test_pre_upload_always_preserves_latest_complete_backup(self):
        gone={a['id'] for a in plan(self.artifacts,before_upload=True)}
        self.assertEqual(gone,{10,11,20,21,30,31})
        self.assertNotIn(40,gone);self.assertNotIn(41,gone)

    def test_pre_upload_handles_first_run_without_deleting_other_files(self):
        self.assertEqual(plan([self.artifacts[-1]],before_upload=True),[])

    def test_legacy_archives_removed_only_after_new_publication_present(self):
        legacy=[dict(id=80,name='bera-fichiers',created_at='2026-11-16T00:00:00Z'),dict(id=81,name='bera-fichiers',created_at='2026-11-17T00:00:00Z')]
        before={a['id'] for a in plan(self.artifacts+legacy,before_upload=True)}
        after={a['id'] for a in plan(self.artifacts+legacy,current_run=4)}
        self.assertIn(80,before);self.assertNotIn(81,before)
        self.assertIn(80,after);self.assertIn(81,after)
