"""Immutable per-run report folders; only normalized published fields are archived."""
import csv
import hashlib
import json
from pathlib import Path
from uuid import uuid4

def start(root, now, mode):
    folder=Path(root)/(now.strftime('%Y-%m-%d_%H-%M-%S')+'_'+uuid4().hex[:8])
    folder.mkdir(parents=True,exist_ok=False)
    state={'status':'running','started_at':now.isoformat(),'mode':mode,'timezone':'America/Sao_Paulo'}
    finish(folder,state)
    return folder,state

def finish(folder,state):
    (folder/'run.json').write_text(json.dumps(state,ensure_ascii=False,indent=2))

def reports(folder,rows,sources,now):
    tasks=[r for r in rows if r['tipo']=='Tarefa'];opened=[r for r in tasks if r['status']!='Concluída']
    for name,items in [('Todos-Itens',rows),('Todas-Tarefas',tasks),('Tarefas-Abertas',opened)]:
        with (folder/(name+'-pt-BR.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(items)
    def table(head,items):
        return '\n| '+' | '.join(head)+' |\n| '+' | '.join(['---']*len(head))+' |\n'+''.join('| '+' | '.join(str(x).replace('|','/').replace('\n',' ') for x in line)+' |\n' for line in items)
    text=f'# Relatório do portfólio Airtable — {now:%d/%m/%Y}\n\nColeta: {now.isoformat()}. Todas as atribuições incluídas.\n\n## Status e progresso\n'
    text+=table(['Indicador','Quantidade'],[['Tarefas principais',len(tasks)],['Concluídas',len(tasks)-len(opened)],['Abertas',len(opened)],['Taxa de conclusão',f'{100*(len(tasks)-len(opened))/len(tasks) if tasks else 0:.1f}%'],['Atrasadas',sum(int(r['dias_atraso'] or 0)>0 for r in opened)],['Sem responsável (abertas)',sum(not r['responsaveis'] for r in opened)],['Sem prazo (abertas)',sum(not r['prazo'] for r in opened)],['Bloqueadas',sum(r['status']=='Bloqueada' for r in opened)],['Subtarefas',sum(r['tipo']=='Subtarefa' for r in rows)],['Documentos',sum(r['tipo']=='Documento' for r in rows)]])
    for title,key in [('Bases','base'),('Status','status'),('Projetos / combinação de setores','projeto_ou_setor'),('Responsáveis / combinação de atribuições','responsaveis')]:
        text+='\n## '+title+'\n'+table(['Grupo','Total','Abertas','Atrasadas'],[[k or 'Não informado',len(q:=[r for r in tasks if r[key]==k]),sum(r['status']!='Concluída' for r in q),sum(int(r['dias_atraso'] or 0)>0 for r in q)] for k in sorted({r[key] for r in tasks})])
    text+='\n## Registro de tarefas\n'+table(['Tarefa','Status','Responsáveis','Prazo'],[[f'[{r["tarefa"] or "Sem título"}]({r["url"]})',r['status'],r['responsaveis'] or 'Sem responsável',r['prazo'] or 'Sem prazo'] for r in tasks])
    text+='\n## Metodologia\n\nFontes e regras de normalização estão em sources.json. Conclusão é contagem por status, não esforço ou aceite. Categorias de risco se sobrepõem. Subtarefas são separadas de tarefas principais. Data genérica não é prazo. Reuniões, transcrições e anexos não são extraídos. Responsáveis não são presumidos. O snapshot normalizado permite reproduzir os artefatos sem consultar o Airtable.\n'
    (folder/'Relatorio-Portfolio-Airtable-pt-BR.md').write_text(text)
    (folder/'sources.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2))
    manifest={str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file() and p.name not in {'run.json','manifest.json'}}
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2))
