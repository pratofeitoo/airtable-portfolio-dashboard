import json
import tempfile
import unittest
from pathlib import Path
from test_refresh import BASE, RAW, NOW, r

class HistoryTests(unittest.TestCase):
    def test_unique_folders_and_complete_report_outputs(self):
        with tempfile.TemporaryDirectory() as root:
            first,state=r.history.start(root,NOW.astimezone(r.TZ),'replay')
            second,_=r.history.start(root,NOW.astimezone(r.TZ),'replay')
            self.assertNotEqual(first,second)
            rows=r.normalize([BASE],RAW,NOW)
            r.build(rows,[BASE],NOW,first)
            r.history.reports(first,rows,[BASE],NOW.astimezone(r.TZ))
            self.assertEqual(json.loads((first/'run.json').read_text())['status'],'running')
            self.assertTrue((first/'Todos-Itens-pt-BR.csv').exists())
            self.assertIn('Relatorio-Portfolio-Airtable-pt-BR.md',json.loads((first/'manifest.json').read_text()))
            self.assertNotIn('private@example.test',(first/'Todos-Itens-pt-BR.csv').read_text())
            self.assertEqual(len(json.loads((first/'snapshot.json').read_text())['records']),len(rows))
