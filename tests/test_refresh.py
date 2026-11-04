import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone
from urllib.error import HTTPError
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('refresh', 'scripts/refresh.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
NOW = datetime(2026, 11, 5, 1, tzinfo=timezone.utc)
BASE = {'id':'appA','name':'Base', 'tables':[
    {'id':'tasks','kind':'Tarefa','fields':{'title':'name','owners':'owner','project':'project','due':'due','status':'status'},'schema':{'name':{'type':'singleLineText'},'owner':{'type':'multipleCollaborators'},'project':{'type':'multipleRecordLinks','linkedTableId':'projects'},'due':{'type':'date'},'status':{'type':'singleSelect'}}},
    {'id':'subtasks','kind':'Subtarefa','fields':{'title':'name','owners':'assigned','parent':'parent','date':'generic','complete':'complete'},'schema':{'name':{'type':'singleLineText'},'assigned':{'type':'multipleRecordLinks','linkedTableId':'team'},'parent':{'type':'multipleRecordLinks','linkedTableId':'tasks'},'generic':{'type':'date'},'complete':{'type':'checkbox'}}},
    {'id':'projects','kind':'lookup','primary':'name'}, {'id':'team','kind':'lookup','primary':'name'}]}
SCHEMA={'tables':[{'id':t['id'],'fields':[dict(id=f, type=v.get('type','singleLineText'),options={'linkedTableId':v.get('linkedTableId')}) for f,v in t.get('schema',{'name':{}}).items()]} for t in BASE['tables']]}
RAW=[{'id':'appA','schema':SCHEMA,'tables':{
    'tasks':[{'id':'parent','fields':{'name':'Entrega','owner':[{'id':'usr1','name':'Ana','email':'private@example.test'},{'id':'usr2','name':'Bia'}],'due':'2026-11-03','project':['p1'],'status':'to-do'}}],
    'subtasks':[{'id':'step','fields':{'name':'Etapa','parent':['parent'],'generic':'2026-11-01','assigned':['person1'],'complete':True}}],
    'projects':[{'id':'p1','fields':{'name':'Projeto A'}}], 'team':[{'id':'person1','fields':{'name':'Caio'}}]}}]

class RefreshTests(unittest.TestCase):
    def test_preserves_all_owners_and_linked_names_without_email(self):
        rows=r.normalize([BASE], RAW, NOW)
        self.assertEqual(rows[0]['responsaveis'],'Ana; Bia')
        self.assertEqual(rows[1]['responsaveis'],'Caio')
        self.assertNotIn('private@example.test',json.dumps(rows))
        self.assertEqual(rows[1]['projeto_ou_setor'],'Projeto A')
        self.assertEqual(rows[1]['tarefa_principal'],'Entrega')

    def test_generic_subtask_date_is_not_a_due_date(self):
        rows=r.normalize([BASE], RAW, NOW)
        self.assertEqual(rows[1]['prazo'],'')
        self.assertEqual(rows[1]['data_generica'],'2026-11-01')
        self.assertEqual(rows[0]['dias_atraso'],'1')  # São Paulo is still November 4.

    def test_does_not_inherit_owner_or_deadline(self):
        raw=copy.deepcopy(RAW);raw[0]['tables']['subtasks'][0]['fields'].pop('assigned')
        row=r.normalize([BASE],raw,NOW)[1]
        self.assertEqual(row['responsaveis'],'');self.assertEqual(row['prazo'],'')

    def test_unknown_status_and_unresolved_owner_are_preserved(self):
        raw=copy.deepcopy(RAW);raw[0]['tables']['tasks'][0]['fields']['status']='Aguardando cliente';raw[0]['tables']['subtasks'][0]['fields']['assigned']=['missing']
        rows=r.normalize([BASE],raw,NOW)
        self.assertEqual(rows[0]['status'],'Aguardando cliente');self.assertEqual(rows[1]['responsaveis'],'missing')
        self.assertEqual(rows[1]['status'],'Concluída')

    def test_incomplete_schema_and_duplicate_records_stop_publication(self):
        with self.assertRaises(ValueError):r.normalize([BASE],[],NOW)
        broken=copy.deepcopy(RAW);broken[0]['schema']['tables'][0]['fields'][0]['type']='number'
        with self.assertRaises(ValueError):r.normalize([BASE],broken,NOW)
        duplicated=copy.deepcopy(RAW);duplicated[0]['tables']['tasks']*=2
        with self.assertRaises(ValueError):r.normalize([BASE],duplicated,NOW)

    def test_pagination_keeps_fields_and_opaque_offset(self):
        client=r.Airtable('test-token',sleep=lambda _:None)
        with patch.object(client,'get',side_effect=[{'records':[{'id':'a'}],'offset':'opaque/cursor'},{'records':[{'id':'b'}]}]) as get:
            self.assertEqual(client.records('base','table',['f']),[{'id':'a'},{'id':'b'}])
            self.assertIn(('offset','opaque/cursor'),get.call_args_list[1].args[1])
            self.assertIn(('fields[]','f'),get.call_args_list[1].args[1])
        with patch.object(client,'get',return_value={'records':[],'offset':'same'}):
            with self.assertRaises(ValueError):client.records('base','table',['f'])

    def test_transient_rate_limit_retry_and_redacted_auth_error(self):
        responses=[HTTPError('url',429,'secret must not appear',{},None),io.BytesIO(b'{"records":[]}')]
        def opener(*args,**kwargs):
            value=responses.pop(0)
            if isinstance(value,Exception):raise value
            return value
        delays=[];client=r.Airtable('test-secret',opener=opener,sleep=delays.append)
        self.assertEqual(client.get('base/table'),{'records':[]});self.assertIn(30,delays)
        with patch.object(client,'opener',side_effect=HTTPError('url',401,'test-secret',{},None)):
            with self.assertRaisesRegex(RuntimeError,'HTTP 401') as error:client.get('base/table')
            self.assertNotIn('test-secret',str(error.exception))

    def test_html_embedding_cannot_execute_airtable_content(self):
        rows=r.normalize([BASE],RAW,NOW);rows[0]['tarefa']='</script><script>alert(1)</script>'
        template='<script id="metadata" type="application/json">{}</script><script id="data" type="application/json">[]</script>'
        with tempfile.TemporaryDirectory() as output:
            r.build(rows,[BASE],NOW,Path(output),template)
            html=(Path(output)/'index.html').read_text()
            self.assertNotIn('</script><script>alert',html)
            self.assertEqual(json.loads((Path(output)/'snapshot.json').read_text())['records'][0]['tarefa'],rows[0]['tarefa'])

    def test_empty_token_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'AIRTABLE_TOKEN'):r.Airtable(None)

if __name__=='__main__':unittest.main()
