# Operação local da v0.1.0

## Escopo de segurança

A v0.1.0 é destinada exclusivamente ao uso local em uma única máquina. Ela não
possui autenticação e não deve ser exposta diretamente à rede local, VPN,
internet ou serviço de túnel. O Docker Compose publica PostgreSQL, API e interface
somente em `127.0.0.1`; processos dentro dos containers continuam escutando em
`0.0.0.0` para funcionar na rede interna do Compose.

O sistema aplica regras cadastradas manualmente e não interpreta normas, não
certifica formulações e não declara conformidade regulatória.

## Dependências e conteúdo não confiável

A auditoria npm da v0.1.0 identificou vulnerabilidades conhecidas. Esta versão é
aceitável somente para uso local em `127.0.0.1`, não deve ser exposta à LAN ou à
internet e não deve processar arquivos ou conteúdo de origem não confiável.
`jspdf`, `xlsx`, `axios` e o servidor Vite precisam ser revisados antes de
qualquer uso compartilhado. A atualização das dependências será tratada em uma
versão posterior. Este aviso não representa alegação de segurança para produção.

## Configuração obrigatória

Copie o modelo local e substitua a senha de exemplo antes de iniciar:

```bash
cp .env.example .env
```

Campos obrigatórios:

| Variável | Finalidade | Exemplo local |
| --- | --- | --- |
| `POSTGRES_DB` | Nome do banco | `otimizador_formulacoes` |
| `POSTGRES_USER` | Usuário local do PostgreSQL | `otimizador` |
| `POSTGRES_PASSWORD` | Senha local, definida pelo operador | Não reutilize o valor de exemplo |
| `POSTGRES_PORT` | Porta PostgreSQL no host | `5432` |
| `BACKEND_PORT` | Porta da API no host | `8000` |
| `FRONTEND_PORT` | Porta da interface no host | `5173` |

O Compose interrompe a inicialização com uma mensagem indicando a variável
ausente. O backend também exige `DATABASE_URL` e não registra seu valor completo.

Se uma porta estiver ocupada, altere somente o lado do host no `.env`. Exemplo:

```dotenv
POSTGRES_PORT=5433
BACKEND_PORT=8001
FRONTEND_PORT=5174
```

## Inicialização e endereços

```bash
docker compose up --build --detach --wait
docker compose ps
```

Com as portas padrão:

- interface: <http://localhost:5173>;
- API: <http://localhost:8000>;
- Swagger: <http://localhost:8000/docs>;
- saúde: <http://localhost:8000/health>;
- PostgreSQL: `127.0.0.1:5432`.

O backend aplica `alembic upgrade head` antes de iniciar. PostgreSQL usa o volume
nomeado `postgres_data`, montado em `/var/lib/postgresql/data` no container.

## Parada segura e persistência

Para parar e preservar os dados:

```bash
docker compose down
```

Para apenas interromper os containers, mantendo-os criados:

```bash
docker compose stop
```

O comando seguinte remove containers **e o volume com o banco**. Use somente
quando a perda integral dos dados for intencional e houver backup testado:

```bash
docker compose down --volumes
```

## Backup com checksum

Crie o backup fora do repositório. O comando lê usuário e banco do ambiente do
container, sem colocar credenciais na linha de comando:

```bash
mkdir -p "$HOME/otimizador-backups"
backup="$HOME/otimizador-backups/otimizador-$(date +%Y%m%d-%H%M%S).dump"

docker compose exec -T postgres sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup"

test -s "$backup"
sha256sum "$backup" > "$backup.sha256"
docker compose exec -T postgres pg_restore --list < "$backup" > /dev/null
```

Guarde o `.dump` e o arquivo `.sha256` juntos em local protegido. Confira o
checksum antes de qualquer restauração:

```bash
sha256sum --check "$backup.sha256"
```

## Restauração em banco de teste

Nunca valide um backup restaurando sobre o banco atual. Crie um banco separado,
restaure nele e faça consultas de conferência:

```bash
docker compose exec -T postgres sh -c \
  'createdb -U "$POSTGRES_USER" "${POSTGRES_DB}_restore_test"'

docker compose exec -T postgres sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "${POSTGRES_DB}_restore_test" --exit-on-error' \
  < "$backup"

docker compose exec -T postgres sh -c \
  'psql -U "$POSTGRES_USER" -d "${POSTGRES_DB}_restore_test" -c "SELECT version_num FROM alembic_version"'
```

Remova o banco de teste somente após a validação, confirmando cuidadosamente o
nome informado. Teste periodicamente a restauração; um arquivo criado sem teste
não deve ser considerado um backup confiável.

## Limitações conhecidas

- não há autenticação;
- o frontend usa o servidor de desenvolvimento do Vite no container;
- as dependências Python não possuem lock completo;
- as imagens Docker usam tags móveis, sem digest;
- o healthcheck não testa continuamente a conexão com o banco;
- o bundle frontend ainda é grande;
- as regras são manuais e não representam certificação regulatória.
