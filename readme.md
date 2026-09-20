# Otimizador de Formulações Nutricionais

[![CI](https://github.com/Levibdo/Otimizador_Formulacoes_react/actions/workflows/ci.yml/badge.svg)](https://github.com/Levibdo/Otimizador_Formulacoes_react/actions/workflows/ci.yml)

Aplicação para cadastrar matérias-primas, calcular composição nutricional e encontrar formulações de menor custo com programação linear.

O PostgreSQL é a única fonte oficial da aplicação. O backend não depende de
MongoDB nem de uma planilha local para iniciar ou executar otimizações.

## Arquitetura

- React + Vite: interface;
- FastAPI: API;
- PuLP + CBC: otimização matemática;
- PostgreSQL: matérias-primas, nutrientes, preços, projetos e versões de fórmula;
- SQLAlchemy + Alembic: persistência e migrações.

## Executar com Docker

Requisitos:

- Docker Engine;
- Docker Compose v2.

Clone o repositório e entre na pasta:

```bash
git clone https://github.com/Levibdo/Otimizador_Formulacoes_react.git
cd Otimizador_Formulacoes_react
```

Opcionalmente, crie o arquivo local de configuração:

```bash
cp .env.example .env
```

Para uso fora de um ambiente local, altere `POSTGRES_PASSWORD` antes de iniciar.

Construa e inicie os três serviços:

```bash
docker compose up --build
```

O backend aguarda o PostgreSQL, executa `alembic upgrade head` automaticamente e só então inicia a API. O frontend aguarda a API ficar saudável.

Endereços padrão:

- Interface: <http://localhost:5173>
- API: <http://localhost:8000>
- Swagger: <http://localhost:8000/docs>
- PostgreSQL: `localhost:5432`

Para executar em segundo plano:

```bash
docker compose up --build -d
docker compose ps
```

Para acompanhar os logs:

```bash
docker compose logs -f backend frontend
```

Para parar preservando os dados:

```bash
docker compose down
```

O comando abaixo também apaga definitivamente o volume do PostgreSQL e deve ser usado somente quando a intenção for reiniciar o banco do zero:

```bash
docker compose down -v
```

## Primeiro uso

1. Abra a aba **Matérias-Primas**.
2. Cadastre manualmente uma MP ou importe `.xlsx`/`.csv`.
3. Revise nutrientes cuja unidade tenha sido marcada como `não informada`.
4. Abra **Otimização**, defina metas e limites e execute o solver.
5. Em **Projetos**, registre o briefing e os requisitos de desenvolvimento.
6. Em **Resultados**, salve a formulação como uma versão do projeto.
7. Em **Apresentações**, cadastre os componentes de embalagem e calcule o custo
   por unidade e por caixa a partir de uma versão da fórmula.
8. Em **Cenários**, simule alterações nos preços das matérias-primas e compare o
   impacto no custo por kg, por apresentação e por caixa.

Cada salvamento cria uma versão numerada e imutável. A versão preserva a fórmula,
o custo, a composição calculada, as restrições, a matriz de matérias-primas e os
requisitos vigentes naquele momento, mesmo que os cadastros sejam alterados depois.

O custo de uma apresentação também é histórico: utiliza o custo da fórmula em
R$/kg, proporcional ao peso líquido, e guarda um snapshot dos custos de pote,
tampa, selo, rótulo, caixa e demais componentes usados no cálculo.

## Base regulatória cadastral

A revisão `20260919_06` adiciona a categoria piloto **Fórmula enteral em pó** e
cadastros manuais para regras sobre matérias-primas comerciais e componentes
agregados. Projetos podem receber uma categoria opcional; projetos anteriores
continuam compatíveis sem categoria.

MP sem regra individual pode participar, mas o diagnóstico cadastral gera alerta.
Concentração desconhecida de componente permanece nula e nunca é interpretada
como zero; zero exige a situação `AUSENTE_CONFIRMADO`. O cadastro usa inicialmente
percentuais em massa (`% m/m`).

O novo fluxo server-side aplica essas regras sem representar certificação ou
alegação automática de conformidade normativa. `POST
/api/v1/projetos/{id}/otimizacoes` busca matriz, requisitos e regras no
PostgreSQL, persiste uma execução imutável e permite criar uma versão histórica
com `execucao_id`. Consulte o [contrato do motor](docs/motor-regulatorio-solver.md)
e o [escopo da base regulatória](docs/base-regulatoria-enterais.md).

A interface React possui uma aba **Regulatório** para categorias, componentes,
composições e regras. A tela de otimização separa o modo recomendado, ligado ao
projeto e ao PostgreSQL, da simulação manual legada. Resultados server-side são
versionados exclusivamente pelo `execucao_id`. Consulte o
[guia da interface regulatória](docs/interface-regulatoria.md).

A importação aceita:

- formato transposto: MPs nas colunas, `Custo` na segunda linha e nutrientes nas linhas seguintes;
- formato vertical: uma MP por linha, com as colunas `Nome`, `Custo`, `Código` opcional e nutrientes nas demais colunas.

Cada importação é transacional: se uma MP conflitar ou houver valor inválido, o lote inteiro é desfeito.

## Executar sem Docker

Configure um PostgreSQL e exporte a conexão:

```bash
export DATABASE_URL='postgresql+psycopg://usuario:senha@localhost:5432/otimizador_formulacoes'
```

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic -c alembic.ini upgrade head
uvicorn main:app --reload
```

Frontend, em outro terminal:

```bash
cd frontend
npm ci
npm run dev
```

## Testes

Na raiz do repositório, com as dependências Python instaladas:

```bash
pytest -q
```

### Integração com PostgreSQL real

Os 42 casos originais continuam disponíveis sem banco externo. Há também 25
casos de integração (marcador `postgresql`), habilitados por `TEST_DATABASE_URL`:

```bash
export TEST_DATABASE_URL='postgresql+psycopg://usuario:senha@localhost:5433/otimizador_formulacoes'
backend/.venv/bin/python -m pytest -q
# Somente integração:
backend/.venv/bin/python -m pytest -q -m postgresql
```

Use as credenciais e a porta do seu PostgreSQL. O usuário precisa poder criar e
remover schemas. Cada caso cria um schema exclusivo, aplica `alembic upgrade head`
e remove apenas esse schema ao terminar. As tabelas da aplicação não são limpas.
Sem `TEST_DATABASE_URL`, esses 25 casos são pulados; no CI a variável é definida
para que sejam obrigatoriamente executados. Uma conexão inválida causa erro.

Os testes verificam snapshots de fórmulas, requisitos, apresentações e cenários
após mudanças nos cadastros e abertura de novas conexões; rejeição de `PATCH`,
`PUT` e `DELETE` de versões pela API; e quatro salvamentos concorrentes do mesmo
projeto, observando a disputa de locks no PostgreSQL antes de liberar a execução.

A revisão `20260919_05` também garante a imutabilidade no PostgreSQL: um trigger
rejeita `UPDATE` e `DELETE` em `versoes_formulas`, inclusive alterações ou remoções
dos itens JSON da fórmula e dos snapshots. `INSERT` continua permitido. Todos os
snapshots da fórmula ficam nessa linha; não há tabelas-filhas desse snapshot.
Apresentações, componentes de apresentação e cenários não recebem essa proteção.

A FK de projeto para versões mantém `ON DELETE CASCADE`, mas o trigger rejeita
a exclusão de versões pela cascata e desfaz a exclusão do projeto. Não há endpoint
de exclusão de projeto: o fluxo disponível é arquivar. Projetos sem versões ainda
podem ser excluídos por SQL, respeitando as demais FKs. Os testes cobrem cascatas
SQL e ORM, criação normal, concorrência, downgrade e reaplicação da migração.

Proprietários e superusuários ainda podem desabilitar/remover triggers. A proteção
não substitui o controle de privilégios administrativos e não intercepta `TRUNCATE`
ou DDL. Consulte [o escopo e as limitações](docs/imutabilidade-versoes-postgresql.md).

Valores `NUMERIC(18, 6)` podem retornar com seis casas decimais na releitura,
enquanto a resposta de criação conserva a escala recebida. Os testes comparam
os valores monetários como `Decimal`.

Para reconstruir as dependências do frontend, use `npm ci --include=optional`
em `frontend/`. O lockfile inclui os binários do Rollup por plataforma; não é
necessário editar `package.json` ou atualizar versões para instalar o binário Linux.

O relatório da validação anterior está em [docs/validacao-postgresql.md](docs/validacao-postgresql.md).

## Validação automática

O workflow **CI** é executado em cada pull request e atualização da `main`. Ele:

1. aplica todas as migrações em uma instância PostgreSQL 16;
2. executa a suíte do backend com o solver CBC e os testes de integração PostgreSQL;
3. gera o build de produção do frontend;
4. constrói e inicia PostgreSQL, API e interface com Docker Compose;
5. verifica os endpoints de saúde da API e da interface.

O merge deve ser realizado somente após os três jobs ficarem verdes no GitHub.
