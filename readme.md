# Otimizador de Formulações Nutricionais

Aplicação para cadastrar matérias-primas, calcular composição nutricional e encontrar formulações de menor custo com programação linear.

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

Cada salvamento cria uma versão numerada e imutável. A versão preserva a fórmula,
o custo, a composição calculada, as restrições, a matriz de matérias-primas e os
requisitos vigentes naquele momento, mesmo que os cadastros sejam alterados depois.

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
