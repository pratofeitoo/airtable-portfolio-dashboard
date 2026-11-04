"""Exercise collection and fail-closed deployment behavior without external credentials."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from test_refresh import BASE, RAW, NOW, r

class WorkflowTests(unittest.TestCase):
    def test_collect_requires_every_configured_table_before_build(self):
        client=Mock()
        client.get.return_value=RAW[0]['schema']
        client.records.side_effect=lambda base,table,fields:RAW[0]['tables'][table]
        raw=r.collect(client,[BASE])
        rows=r.normalize([BASE],raw,NOW)
        with tempfile.TemporaryDirectory() as output:
            r.build(rows,[BASE],NOW,Path(output))
            self.assertEqual(json.loads((Path(output)/'snapshot.json').read_text())['metadata']['mode'],'automated')
            self.assertEqual(len(json.loads((Path(output)/'snapshot.json').read_text())['records']),2)
            previous=(Path(output)/'index.html').read_bytes()
            client.records.side_effect=RuntimeError('API unavailable')
            with self.assertRaises(RuntimeError):r.collect(client,[BASE])
            self.assertEqual((Path(output)/'index.html').read_bytes(),previous)

    def test_index_has_valid_executable_scripts(self):
        import re,subprocess
        html=Path('index.html').read_text()
        scripts=re.findall(r'<script(.*?)>(.*?)</script>',html,re.S)
        with tempfile.TemporaryDirectory() as directory:
            for i,(attrs,source) in enumerate(scripts):
                if 'application/json' in attrs:
                    json.loads(source)
                    continue
                file=Path(directory)/f'script-{i}.js';file.write_text(source)
                subprocess.run(['node','--check',str(file)],check=True,capture_output=True)
