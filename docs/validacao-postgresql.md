# Validação PostgreSQL — 19/09/2026

Registro histórico do bloco anterior à revisão `20260919_05`. A limitação de
`UPDATE`/`DELETE` direto descrita aqui foi tratada no bloco de
[imutabilidade de versões](imutabilidade-versoes-postgresql.md); os resultados
abaixo documentam a validação realizada antes dessa proteção.

Branch: `chore/validacao-postgresql-ci`. Sem commit, push ou PR neste bloco.

## Resultado

- **48 testes aprovados**, nenhum pulado: 42 existentes e seis de integração real.
- Quatro migrações aplicadas; revisão atual: `20260918_04 (head)`.
- Build Vite concluído (1.276 módulos).
- PostgreSQL, backend e frontend saudáveis no Docker Compose.
- `/health`: HTTP 200, `{"status":"ok"}`.
- Interface e `/api/v1/projetos`: HTTP 200. A segunda consulta também exercita o banco.
- `frontend/package.json` e `frontend/package-lock.json` preservados.

## Ambientes e comandos executados

Na raiz, salvo indicação diferente:

| Comando | Resultado |
| --- | --- |
| `git switch -c chore/validacao-postgresql-ci` | Branch criado; main não alterada |
| `mv backend/.venv /tmp/otimizador-venv-incompleto-20260919` | Ambiente incompleto preservado fora do projeto |
| `uv venv backend/.venv --python python3` | Novo ambiente Python 3.12.3 |
| `uv pip install --python backend/.venv/bin/python -r backend/requirements.txt` | 37 pacotes instalados conforme os requisitos existentes |
| `npm ci --include=optional` em `frontend/` | 262 pacotes instalados com o lockfile existente |
| `docker compose up -d --wait postgres` | PostgreSQL 16 saudável |
| `python -m alembic -c alembic.ini upgrade head` em `backend/`, com o Python da nova venv | Migrações aplicadas |
| `python -m alembic -c alembic.ini current` no mesmo ambiente | `20260918_04 (head)` |
| `backend/.venv/bin/python -m pytest -q`, com `DATABASE_URL` e `TEST_DATABASE_URL` | `48 passed, 22 warnings in 26.32s` |
| `npm run build` em `frontend/` | Sucesso, 21,12 s |
| `docker compose up --build --detach --wait` | Três serviços saudáveis |
| `docker compose config --quiet` | Configuração válida |
| `curl --fail --show-error http://localhost:8001/health` | HTTP 200 |
| `curl --fail --show-error --output /dev/null --write-out 'Frontend HTTP %{http_code}\n' http://localhost:5173/` | HTTP 200 |
| `curl --fail --show-error --output /dev/null --write-out 'API PostgreSQL HTTP %{http_code}\n' http://localhost:8001/api/v1/projetos` | HTTP 200 |
| `docker compose ps` | Todos `healthy` |
| `git diff --exit-code -- frontend/package-lock.json frontend/package.json` | Sem diferenças |

As migrações e a suíte foram invocadas por um auxiliar temporário
`/tmp/otimizador_validar_postgresql.py`, que leu as credenciais do `.env`, montou as
URLs com SQLAlchemy e executou os comandos acima sem imprimir as credenciais.
A última execução foi `backend/.venv/bin/python
/tmp/otimizador_validar_postgresql.py --tests-only`.

A porta 5432 estava ocupada e o `.env` já continha `POSTGRES_PORT=5433`.
A primeira subida completa falhou porque 8000 também estava ocupada; foi definido
`BACKEND_PORT=8001` no `.env` local. Frontend em 5173. Os serviços foram mantidos
em execução e nenhum volume foi removido.

## Achados e correções

O lockfile já possuía `@rollup/rollup-linux-x64-gnu` 4.52.5. A árvore instalada
continha binários Windows rastreados pelo Git, sem o binário Linux necessário.
`npm ci --include=optional` corrigiu a instalação sem atualizar versões nem editar
os manifests. As primeiras tentativas de instalação/execução dentro da sandbox
foram bloqueadas por acesso a cache, rede ou sockets; as execuções autorizadas
fora dela permitiram concluir a validação.

Os testes novos inicialmente demonstraram uma falha do Alembic: parâmetros da URL
codificados com `%` provocavam `ValueError: invalid interpolation syntax` no
`ConfigParser`, antes de aplicar as migrações. `backend/alembic/env.py` agora escapa
`%` como `%%` ao configurar a URL. Todas as fixtures de integração exercitam essa
URL codificada, aplicando as migrações em schemas exclusivos.

As primeiras comparações textuais de custos diferiram entre `10` e `10.000000`.
Os valores eram iguais: PostgreSQL aplica a escala de `NUMERIC(18, 6)` na releitura.
Os testes passaram a comparar os schemas tipados, com `Decimal`, preservando a
comparação integral dos demais campos. A API não foi modificada para esse caso.

## O que os seis casos demonstram

1. Snapshots de fórmula, requisitos, matriz, apresentação, componentes e cenário
   persistem após mudanças de preço, composição, nome de MP, requisitos do projeto
   e dados da embalagem. A leitura final utiliza conexões novas.
2. `PATCH` de versões é rejeitado, preservando a versão persistida.
3. `PUT` de versões é rejeitado, preservando a versão persistida.
4. `DELETE` de versões é rejeitado, preservando a versão persistida.
5. Quatro requisições concorrentes aguardam locks observados em `pg_stat_activity`.
   Ao liberar a linha do projeto, geram versões 2, 3, 4 e 5, sem duplicações,
   preservando a versão 1 e as observações individuais.
6. SQL direto consegue alterar `custo_total` de uma versão, preservando a matriz
   anterior. Trata-se de teste de caracterização da limitação, sem `xfail`.

Na coleção `/projetos/{id}/versoes`, os métodos de alteração retornam 405;
no caminho individual, inexistente, retornam 404. A imutabilidade atual é garantida
pelo conjunto de operações expostas pela API, não por triggers. Nenhum bloqueio
ou trigger de imutabilidade foi implementado.

Cada caso de integração cria e remove somente seu próprio schema, com as tabelas
criadas por Alembic. As sessões são independentes por requisição. Sem
`TEST_DATABASE_URL`, esses seis casos são pulados; o CI agora define a variável
explicitamente. O workflow foi alterado localmente, sem execução remota neste bloco.

## Observações restantes

- O npm reportou 19 vulnerabilidades nas versões instaladas. Não foi executado
  `npm audit fix` nem houve atualização de dependências.
- O build emitiu avisos de bases Browserslist antigas, API CJS do Vite e bundle
  maior que 500 kB. Os testes emitiram 22 avisos de depreciação das dependências.
- A instalação revelou 7.054 arquivos de `frontend/node_modules` e um de
  `backend/.venv` (`pyvenv.cfg`) rastreados, apesar do `.gitignore`. Não havia
  arquivos rastreados em `node_modules` na raiz.
- Na higienização posterior, esses 7.055 artefatos foram retirados somente do
  índice com `git rm -r --cached --quiet -- frontend/node_modules backend/.venv`.
  Os diretórios locais foram preservados, sem reinstalar dependências.
  A comparação integral do índice antes/depois confirmou que nenhum arquivo
  fora da lista de artefatos foi removido. Os dois lockfiles mantiveram seus hashes.
- O `.gitignore` agora inclui `.pytest_cache/` e `.env.*`, com exceção explícita
  para `.env.example`. As regras existentes de `node_modules/`, `.venv/`,
  `__pycache__/`, `*.pyc`, `build/` e `dist/` já se aplicam em qualquer nível.
- Após a higienização, a suíte foi reexecutada: **48 passed, 22 warnings in
  30.72s**, incluindo os seis casos PostgreSQL, e o build passou em 24,49 s.
  `git diff --check` e `git diff --cached --check` passaram. Nenhum commit,
  push ou PR foi realizado.
