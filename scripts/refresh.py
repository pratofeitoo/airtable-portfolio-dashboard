"""Read-only Airtable collection and atomic static-site build (Python standard library)."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo('America/Sao_Paulo')

class Airtable:
    def __init__(self, token, opener=urlopen, sleep=time.sleep):
        if not token:
            raise ValueError('Configure o secret AIRTABLE_TOKEN antes de executar a atualização.')
        self.token, self.opener, self.sleep = token, opener, sleep

    def get(self, path, params=()):
        url = 'https://api.airtable.com/v0/' + path + ('?' + urlencode(params) if params else '')
        for attempt in range(5):
            self.sleep(.22)  # Below five requests/second, including consecutive tables.
            try:
                with self.opener(Request(url, headers={'Authorization': 'Bearer ' + self.token}), timeout=30) as response:
                    return json.load(response)
            except HTTPError as error:
                if error.code not in (429, 500, 502, 503, 504) or attempt == 4:
                    raise RuntimeError(f'Airtable HTTP {error.code}; coleta interrompida.') from None
                self.sleep(max(30 if error.code == 429 else 2 ** attempt, 0))
            except (URLError, TimeoutError):
                if attempt == 4:
                    raise RuntimeError('Airtable indisponível; coleta interrompida.') from None
                self.sleep(2 ** attempt)

    def records(self, base, table, fields):
        rows, seen, offset = [], set(), None
        while True:
            params = [('pageSize', '100'), ('returnFieldsByFieldId', 'true')]
            params.extend(('fields[]', f) for f in sorted(set(fields)))
            if offset:
                params.append(('offset', offset))
            data = self.get(f'{base}/{table}', params)
            if not isinstance(data.get('records'), list):
                raise ValueError('Resposta de registros inválida.')
            rows.extend(data['records'])
            offset = data.get('offset')
            if not offset:
                return rows
            if offset in seen:
                raise ValueError('Paginação repetida; coleta interrompida.')
            seen.add(offset)


def validate_schema(base, schema):
    tables = {t['id']: t for t in schema['tables']}
    for config in base['tables']:
        table = tables.get(config['id'])
        if not table:
            raise ValueError(f"Tabela configurada ausente em {base['id']}: {config['id']}")
        fields = {f['id']: f for f in table['fields']}
        expected = config.get('schema', {config.get('primary'): {}})
        for fid, spec in expected.items():
            field = fields.get(fid)
            if not field or (spec.get('type') and field['type'] != spec['type']):
                raise ValueError(f'Campo removido ou com tipo alterado: {fid}')
            if spec.get('linkedTableId') and field.get('options', {}).get('linkedTableId') != spec['linkedTableId']:
                raise ValueError(f'Vínculo alterado: {fid}')


def collect(client, sources):
    raw = []
    for base in sources:
        schema = client.get(f"meta/bases/{base['id']}/tables")
        validate_schema(base, schema)
        tables = {}
        for table in base['tables']:
            fields = table.get('fields', {}).values() if table['kind'] != 'lookup' else [table['primary']]
            tables[table['id']] = client.records(base['id'], table['id'], fields)
        raw.append({'id': base['id'], 'schema': schema, 'tables': tables})
    return raw


def text(value):
    if isinstance(value, list):
        return '; '.join(filter(None, (text(v) for v in value)))
    if isinstance(value, dict):
        return str(value.get('name') or value.get('id') or '')
    return '' if value is None else str(value)


def normalized_status(value, complete=False):
    if complete:
        return 'Concluída'
    original = text(value).strip()
    return {'done': 'Concluída', 'feito': 'Concluída', 'complete': 'Concluída',
            'to do': 'A fazer', 'to-do': 'A fazer', 'pendete': 'A fazer',
            'doing': 'Em andamento', 'in progress': 'Em andamento', 'fazendo': 'Em andamento',
            'review': 'Em revisão', 'blocked': 'Bloqueada', 'atrasado': 'Atrasada (conforme status)'}.get(original.lower(), original or 'Não informado')


def normalize(sources, raw, now):
    if len(raw) != len(sources) or {b['id'] for b in raw} != {b['id'] for b in sources}:
        raise ValueError('Coleta incompleta: faltam bases.')
    raw_by_id = {b['id']: b for b in raw}
    rows, seen = [], set()
    for base in sources:
        data = raw_by_id[base['id']]
        validate_schema(base, data['schema'])
        records, names = {}, {}
        for table in base['tables']:
            for record in data['tables'][table['id']]:
                key = (table['id'], record['id'])
                if key in records:
                    raise ValueError('Registro duplicado na paginação.')
                records[key] = record
                title_id = table.get('primary') or table['fields']['title']
                names[key] = text(record['fields'].get(title_id)).strip() or record['id']
        def linked(table, role, value):
            fid = table['fields'].get(role)
            target = table.get('schema', {}).get(fid, {}).get('linkedTableId')
            if target:
                return '; '.join(names.get((target, rid), rid) for rid in (value or []))
            return text(value)
        for table in base['tables']:
            if table['kind'] == 'lookup':
                continue
            for record in data['tables'][table['id']]:
                key = (base['id'], table['id'], record['id'])
                if key in seen:
                    raise ValueError('Registro duplicado.')
                seen.add(key)
                fields = record['fields']
                get = lambda role: fields.get(table['fields'].get(role))
                complete = get('complete') is True
                status = normalized_status(get('status'), complete)
                due = text(get('due'))[:10]
                if due:
                    datetime.strptime(due, '%Y-%m-%d')
                owners = linked(table, 'owners', get('owners'))
                row = dict(base=base['name'], id_base=base['id'], id_tabela=table['id'],
                           id_registro=record['id'], tipo=table['kind'], tarefa=text(get('title')),
                           status=status, status_original=text(get('status')), marcador_concluido=str(complete),
                           prioridade=text(get('priority')), prazo=due, data_generica=text(get('date')),
                           dias_atraso=str(max(0, (now.astimezone(TZ).date()-datetime.strptime(due, '%Y-%m-%d').date()).days)) if due and status != 'Concluída' else '',
                           projeto_ou_setor=linked(table, 'project', get('project')),
                           tarefa_principal=linked(table, 'parent', get('parent')),
                           ids_tarefas_principais=text(get('parent')), responsaveis=owners,
                           criado_em=record.get('createdTime', ''),
                           url=f"https://airtable.com/{base['id']}/{table['id']}/{record['id']}",
                           descricao_original=text(get('description')), atualizacoes_originais=text(get('updates')))
                rows.append(row)
    # Preserve the original portfolio grouping: subtasks without their own project
    # use the explicit parent-task link. Owners and due dates are never inherited.
    by_record = {(r['id_base'], r['id_registro']): r for r in rows}
    for row in rows:
        if row['tipo'] == 'Subtarefa' and not row['projeto_ou_setor']:
            projects = []
            for rid in row['ids_tarefas_principais'].split('; '):
                parent = by_record.get((row['id_base'], rid))
                if parent:
                    projects.extend(parent['projeto_ou_setor'].split('; '))
            row['projeto_ou_setor'] = '; '.join(dict.fromkeys(filter(None, projects)))
    if not rows:
        raise ValueError('Coleta vazia; publicação cancelada.')
    return rows


def safe_json(data):
    # JSON embedded in a script element must never be able to terminate that element.
    return json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def build(rows, sources, now, output, template=None):
    source = template if template is not None else (ROOT/'index.html').read_text()
    metadata = {'collectedAt': now.isoformat(), 'timeZone': 'America/Sao_Paulo',
                'mode': 'automated', 'bases': [{'id': b['id'], 'name': b['name']} for b in sources]}
    for element, data in [('data', rows), ('metadata', metadata)]:
        pattern = rf'(<script id="{element}" type="application/json">).*?(</script>)'
        source, count = re.subn(pattern, lambda m: m[1]+safe_json(data)+m[2], source, flags=re.S)
        if count != 1:
            raise ValueError(f'Bloco {element} ausente ou duplicado.')
    output.mkdir(parents=True, exist_ok=True)
    temporary = output/'index.html.tmp'
    temporary.write_text(source)
    temporary.replace(output/'index.html')
    (output/'.nojekyll').touch()
    (output/'snapshot.json').write_text(safe_json({'metadata': metadata, 'records': rows}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw', type=Path, help='Coleta já concluída, somente para validação local.')
    parser.add_argument('--output', type=Path, default=ROOT/'_site')
    args = parser.parse_args()
    sources = json.loads((ROOT/'sources.json').read_text())
    now = datetime.now(timezone.utc)
    raw = json.loads(args.raw.read_text()) if args.raw else collect(Airtable(os.getenv('AIRTABLE_TOKEN')), sources)
    rows = normalize(sources, raw, now)
    build(rows, sources, now, args.output)
    counts = {kind: sum(r['tipo'] == kind for r in rows) for kind in ['Tarefa','Subtarefa','Documento']}
    print(json.dumps({'collectedAt': now.isoformat(), 'counts': counts}, ensure_ascii=False))

if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, KeyError, OSError) as error:
        print(f'Atualização cancelada: {error}', file=sys.stderr)
        sys.exit(1)
