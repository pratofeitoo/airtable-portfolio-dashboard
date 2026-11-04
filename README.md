# DiverCidade · Airtable Portfolio Dashboard

Dashboard em português (Brasil) com todas as atribuições explícitas, filtros, gráficos interativos, modo escuro, paginação e exportação CSV.

[Dashboard publicado](https://pratofeitoo.github.io/airtable-portfolio-dashboard/) · [Execuções da atualização](https://github.com/pratofeitoo/airtable-portfolio-dashboard/actions/workflows/refresh-pages.yml)

## Atualização automática

O GitHub Actions consulta o Airtable com uma credencial guardada em **Actions Secrets**, valida a coleta completa, gera `_site/` e publica um artefato diretamente no GitHub Pages. Nenhum token vai para o HTML, JSON, histórico Git ou artefato. O navegador consulta apenas os arquivos públicos do Pages.

- Agendamento: `17 */6 * * *` UTC, aproximadamente **03h17, 09h17, 15h17 e 21h17 em São Paulo**. O agendador pode atrasar; repositórios públicos inativos por 60 dias podem ter agendamentos desativados pelo GitHub.
- Atualização manual: **Actions → Atualizar portfólio e publicar → Run workflow**.
- Uma página aberta verifica `snapshot.json` a cada cinco minutos, mantendo os filtros ainda válidos. “Verificar atualização” consulta a última publicação; não dispara uma coleta no Airtable.
- A última coleta e a referência de prazos ficam visíveis. Após 18 horas sem coleta, o painel sinaliza dados desatualizados. Os prazos usam a data atual em `America/Sao_Paulo`.
- Falha de autenticação, leitura, paginação, configuração ou validação interrompe a publicação. A versão anterior continua disponível; a falha aparece no Actions. Não existe publicação parcial ou fallback silencioso para o snapshot inicial.
- Os dados atuais não são gravados na branch: são publicados apenas pelo artefato do Pages. O `index.html` do repositório mantém o snapshot inicial como referência local e template.

## Configuração única

1. Crie um [Personal Access Token do Airtable](https://airtable.com/create/tokens) com **`data.records:read`** e **`schema.bases:read`**, limitado às cinco bases em `sources.json`.
2. Salve-o como **`AIRTABLE_TOKEN`** em [Settings → Secrets and variables → Actions](https://github.com/pratofeitoo/airtable-portfolio-dashboard/settings/secrets/actions). Não cole o token em arquivos ou no chat.
3. Em **Settings → Pages → Build and deployment**, use **GitHub Actions** como Source.
4. Execute o workflow na branch `main` e confira a etapa de coleta e o deploy. O selo “Coleta automática” com nova data no dashboard confirma a publicação.

O acesso OAuth conectado ao Composio permite leituras durante o chat, mas não fornece automaticamente uma credencial para um runner do GitHub. O PAT dedicado elimina essa dependência. Para trocar a credencial, atualize o secret; o código não muda.

## Fontes e regras

`sources.json` configura as cinco bases por ID, nove tabelas de itens e seis tabelas auxiliares. IDs de campos resistem a renomeações; remoções, mudanças de tipo e mudanças de tabela vinculada interrompem a coleta para revisão. Tabelas e campos novos não entram automaticamente: revise a configuração para ampliar o escopo.

- Tarefas principais são o escopo padrão. Subtarefas e documentos podem ser selecionados separadamente.
- Responsáveis únicos, múltiplos e vínculos de Team são preservados. IDs sem nome resolvido continuam visíveis. Liderança de projeto não vira responsável presumido; sem filtro por pessoa na coleta.
- Projetos/setores de subtarefas sem vínculo próprio são obtidos da tarefa principal explícita. Responsáveis e prazos não são herdados.
- `Data` genérica de subtarefa é preservada, sem ser interpretada como prazo. `Complete` marcado indica conclusão. Status originais e desconhecidos são preservados nos detalhes.
- Meetings, Transcripts e textos de reuniões não são convertidos em obrigações. Clientes Ativos — Drive Mirror é verificada no esquema e contribui com zero tarefas.
- O snapshot inicial contém 325 tarefas, 148 subtarefas e 2 documentos em 04/11/2026. A nova coleta de validação encontrou 328 tarefas, 148 subtarefas e 2 documentos, sem perda de responsáveis no conjunto original.

A coleta é paginada, sem filtros de responsável, view ou limite total. A API não oferece uma transação entre tabelas: uma edição simultânea pode aparecer somente na execução seguinte. Há retentativas limitadas para 429 e falhas transitórias. O agendamento a cada seis horas consome a cota de API do plano Airtable; ajuste o cron se necessário.

O Pages e o repositório são públicos. Os campos publicados continuam disponíveis para qualquer visitante: títulos, responsáveis, descrições, status e vínculos de tarefas. O exportador usa uma lista explícita de campos; não publica emails de colaboradores, anexos, fotos ou tabelas auxiliares completas. Credenciais ficam restritas à etapa de coleta. JSON embutido escapa terminadores de script e conteúdo é escapado ao renderizar.

## Desenvolvimento e verificação

Python 3.12+ e Node.js (sem dependências adicionais):

```sh
python3 -m unittest discover -s tests -v
node --test tests/calendar.test.cjs
# AIRTABLE_TOKEN deve ser fornecido pelo ambiente, sem gravá-lo no comando/arquivo.
python3 scripts/refresh.py
python3 -m http.server 8765 --directory _site
```

Para validar uma coleta local já concluída, fora do Git:

```sh
python3 scripts/refresh.py --raw /caminho/privado/coleta.json
```

`--raw` é exclusivo da validação local; o workflow sempre consulta a API. O arquivo deve conter as cinco bases, esquemas e tabelas completos. Não comite arquivos brutos de coleta.

Referências: [tokens do Airtable](https://support.airtable.com/articles/9934989703-creating-personal-access-tokens), [limites da API](https://support.airtable.com/articles/7735693959-Managing-API-call-limits-in-Airtable), [workflows do Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).
