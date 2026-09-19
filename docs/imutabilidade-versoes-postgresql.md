# Imutabilidade de versões no PostgreSQL

## Diagnóstico antes da implementação

O trabalho iniciou na `main`, limpa e sincronizada com `origin/main` (`0 0`),
e seguiu no branch `feat/imutabilidade-versoes-postgresql`.

A versão de fórmula é uma única linha em `versoes_formulas`. As colunas JSON
`inclusoes`, `custos_individuais`, `composicao_nutricional`, `parametros`,
`matriz_snapshot` e `requisitos_snapshot` contêm seus itens e snapshots. Não há
tabelas-filhas que armazenem partes desse snapshot. Alterar ou remover um item
JSON exige um `UPDATE` na linha da versão.

`ProjetoRepository.criar_versao` preenche todos os campos antes do `INSERT` e
serializa a numeração com `SELECT FOR UPDATE` no projeto. Não foi encontrado
fluxo legítimo que atualize uma versão após a criação. O router de projetos
expõe criação e leitura de versões, sem atualização ou exclusão. Não há endpoint
de exclusão de projetos; existe atualização de status para `ARQUIVADO`.

| Relacionamento | ON DELETE | Consequência |
| --- | --- | --- |
| `versoes_formulas.projeto_id` → `projetos.id` | `CASCADE` | Excluir projeto tenta excluir suas versões |
| `apresentacoes_produto.versao_formula_id` → `versoes_formulas.id` | `RESTRICT` | Uma apresentação já impedia excluir a versão referenciada |
| `cenarios_custo.versao_formula_id` → `versoes_formulas.id` | `RESTRICT` | Um cenário já impedia excluir a versão referenciada |
| Apresentações e cenários → projeto | `RESTRICT` | Continuam sujeitos às FKs existentes |
| `componentes_apresentacao.apresentacao_id` → apresentação | `CASCADE` | Componentes pertencem à apresentação, não ao snapshot da fórmula |

O ORM também declara `cascade="all, delete-orphan"` de projeto para versões.
Apresentações e cenários são criados depois, referenciando uma versão já completa;
seus snapshots descrevem esses registros derivados, não compõem a versão original.
Por isso não foram incluídos na proteção deste bloco.

## Migração e escopo

- Revisão: `20260919_05`, posterior a `20260918_04`.
- Tabela protegida: **`versoes_formulas`**, incluindo todos os seus campos.
- Função: `impedir_mutacao_versao_formula()`.
- Trigger: `trg_versoes_formulas_imutaveis`, `BEFORE UPDATE OR DELETE`, por linha.
- Erro: SQLSTATE `23514`, com mensagem “Versões de fórmula são imutáveis:
  UPDATE e DELETE não são permitidos.” e orientação para criar nova versão ou
  arquivar o projeto.

O trigger rejeita atualizações mesmo que atribuam o valor já existente. Protege
linhas antigas e novas e vale para SQL direto, ORM e quaisquer clientes de banco.
`INSERT` não é interceptado e a numeração concorrente mantém o lock existente
no projeto. Não foram alterados endpoints, FKs ou tabelas da aplicação.

Não foram adicionados triggers em `projetos`, `apresentacoes_produto`,
`componentes_apresentacao`, `cenarios_custo` ou nos cadastros de matérias-primas
e embalagens. Um teste real confirma que as operações SQL desses registros
derivados não receberam restrições adicionais.

## Exclusão de projetos e cascatas

**A exclusão SQL de um projeto com versões passa a falhar**, mesmo sem apresentações
ou cenários associados. A cascata tenta excluir as versões e o trigger rejeita a
operação; a transação preserva projeto e versões. A exclusão via ORM também falha.
A FK `ON DELETE CASCADE` foi mantida: esta é uma consequência explícita da
imutabilidade, não uma substituição silenciosa da regra da FK.

Arquivar o projeto permanece permitido e preserva as versões. Projetos sem versões
podem ser excluídos por SQL se não houver outras referências impeditivas. Nenhum
endpoint de exclusão foi criado, e nenhum fluxo legítimo existente foi removido.

## Downgrade e limites administrativos

`alembic downgrade 20260918_04` remove primeiro o trigger e depois a função,
sem apagar versões. Com isso, `UPDATE`, `DELETE` e as cascatas originais voltam
a obedecer somente às restrições anteriores. O teste em schema isolado verifica
a ausência da função e de triggers de usuário na tabela, executa atualização e
exclusão e reaplica o upgrade para proteger uma versão criada antes da migração.
O downgrade não é executado no schema da aplicação durante os testes.

Proprietários de tabelas/funções e superusuários ainda podem desabilitar ou remover
triggers e executar DDL. Privilégios administrativos capazes de alterar o modo
de replicação também podem contornar triggers normais. Esta migração cobre
`UPDATE` e `DELETE`; não intercepta `TRUNCATE`, `DROP TABLE` ou `DROP SCHEMA`.
Logo, permissões de DDL/TRUNCATE e administração devem ser limitadas fora deste
bloco. O trigger não valida a veracidade dos dados no `INSERT` inicial.

## Validação

Suíte: **67 testes aprovados**, sendo 42 originais e 25 de integração PostgreSQL.
O teste anterior que demonstrava a mutação SQL foi substituído por testes de
rejeição; o comportamento anterior permanece documentado no relatório histórico.

Cobertura PostgreSQL inclui:

- snapshots históricos e rejeição de métodos de alteração pela API;
- rejeição de `UPDATE` e `DELETE` SQL da versão, com rollback e leitura inalterada;
- alteração e remoção de itens em cada uma das seis colunas JSON rejeitadas;
- criação normal e criação concorrente de quatro versões;
- arquivamento do projeto mantendo as versões;
- rejeição da exclusão de projeto por cascatas SQL e ORM;
- exclusão SQL de projeto vazio ainda permitida;
- registros derivados fora do escopo mantendo suas operações SQL;
- downgrade completo e novo upgrade protegendo linhas preexistentes.

Verificações locais realizadas:

| Comando/verificação | Resultado |
| --- | --- |
| `alembic upgrade head` | Aplicada `20260918_04` → `20260919_05` |
| `alembic current` | `20260919_05 (head)` |
| `pytest -q`, com `TEST_DATABASE_URL` | 67 aprovados, nenhum pulado; 22 avisos de dependências; 53,35 s |
| `npm run build` | Aprovado, 1.276 módulos; 28,49 s |
| `git diff --check` | Sem erros |
| `docker compose up --build --detach --wait` | PostgreSQL, backend e frontend saudáveis |
| `docker compose config --quiet` | Válido |
| `GET http://localhost:8001/health` | HTTP 200, `{"status":"ok"}` |
| `GET http://localhost:8001/api/v1/projetos` | HTTP 200, consulta ao PostgreSQL |
| `GET http://localhost:5173/` | HTTP 200 |

As migrações e o pytest foram executados pela venv do backend com o auxiliar local
`/tmp/otimizador_validar_postgresql.py`, que configura a conexão a partir do `.env`.
Os downgrades dos testes ficaram restritos aos schemas temporários.

Foi necessário restaurar o `pyvenv.cfg` com
`python3 -m venv --without-pip backend/.venv` e a instalação frontend com
`npm ci --include=optional`: após a transição de branches da higienização, faltavam
arquivos antes rastreados. Os manifests e lockfiles não foram alterados.
O build mantém os avisos de bases Browserslist antigas, API CJS do Vite e tamanho
de bundle. Nenhuma atualização de dependências foi realizada neste bloco.
