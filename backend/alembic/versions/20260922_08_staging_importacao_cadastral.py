"""Sessões temporárias para preparação da importação cadastral."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260922_08"
down_revision = "20260919_07"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sessoes_importacao_cadastral",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid_publico", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("arquivo_sha256", sa.String(64), nullable=False),
        sa.Column("versao_contrato", sa.String(20), nullable=False),
        sa.Column("payload_normalizado", postgresql.JSONB(), nullable=False),
        sa.Column("resumo", postgresql.JSONB(), nullable=False),
        sa.Column("avisos", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmado_em", sa.DateTime(timezone=True)),
        sa.Column("resultado", postgresql.JSONB()),
        sa.CheckConstraint(
            "status IN ('PENDENTE', 'CONFIRMADA', 'EXPIRADA', 'FALHOU')",
            name="ck_sessao_importacao_status",
        ),
        sa.CheckConstraint("expira_em > criado_em", name="ck_sessao_importacao_expiracao"),
        sa.CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="ck_sessao_importacao_token_hash"),
        sa.CheckConstraint("arquivo_sha256 ~ '^[0-9a-f]{64}$'", name="ck_sessao_importacao_arquivo_sha256"),
        sa.CheckConstraint("(status = 'CONFIRMADA') = (confirmado_em IS NOT NULL)", name="ck_sessao_importacao_confirmacao"),
        sa.CheckConstraint("(status IN ('CONFIRMADA', 'FALHOU')) = (resultado IS NOT NULL)", name="ck_sessao_importacao_resultado"),
        sa.CheckConstraint("resultado IS NULL OR jsonb_typeof(resultado) = 'object'", name="ck_sessao_importacao_resultado_objeto"),
    )
    op.create_index(
        "ix_sessoes_importacao_uuid_publico",
        "sessoes_importacao_cadastral",
        ["uuid_publico"],
        unique=True,
    )
    op.create_index(
        "ix_sessoes_importacao_arquivo_sha256",
        "sessoes_importacao_cadastral",
        ["arquivo_sha256"],
    )
    op.execute("""
        CREATE FUNCTION proteger_sessao_importacao_cadastral() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Sessão de importação não pode ser removida.' USING ERRCODE = '23514';
            END IF;
            IF NEW.id IS DISTINCT FROM OLD.id
               OR NEW.uuid_publico IS DISTINCT FROM OLD.uuid_publico
               OR NEW.token_hash IS DISTINCT FROM OLD.token_hash
               OR NEW.arquivo_sha256 IS DISTINCT FROM OLD.arquivo_sha256
               OR NEW.versao_contrato IS DISTINCT FROM OLD.versao_contrato
               OR NEW.payload_normalizado IS DISTINCT FROM OLD.payload_normalizado
               OR NEW.resumo IS DISTINCT FROM OLD.resumo
               OR NEW.avisos IS DISTINCT FROM OLD.avisos
               OR NEW.criado_em IS DISTINCT FROM OLD.criado_em
               OR NEW.expira_em IS DISTINCT FROM OLD.expira_em THEN
                RAISE EXCEPTION 'Conteúdo preparado da sessão de importação é imutável.' USING ERRCODE = '23514';
            END IF;
            IF OLD.status <> NEW.status AND NOT (
                OLD.status = 'PENDENTE' AND NEW.status IN ('CONFIRMADA', 'EXPIRADA', 'FALHOU')
            ) THEN
                RAISE EXCEPTION 'Transição de status da sessão de importação é inválida.' USING ERRCODE = '23514';
            END IF;
            IF OLD.status = NEW.status AND (
                NEW.confirmado_em IS DISTINCT FROM OLD.confirmado_em
                OR NEW.resultado IS DISTINCT FROM OLD.resultado
            ) THEN
                RAISE EXCEPTION 'Resultado exige uma transição válida de status.' USING ERRCODE = '23514';
            END IF;
            IF NEW.status = 'EXPIRADA' AND (
                NEW.confirmado_em IS NOT NULL OR NEW.resultado IS NOT NULL
            ) THEN
                RAISE EXCEPTION 'Sessão expirada não pode possuir confirmação ou resultado.' USING ERRCODE = '23514';
            END IF;
            IF NEW.status = 'CONFIRMADA' AND (
                NEW.confirmado_em IS NULL OR NEW.resultado IS NULL
            ) THEN
                RAISE EXCEPTION 'Confirmação exige data e resultado.' USING ERRCODE = '23514';
            END IF;
            IF OLD.status = 'PENDENTE' AND NEW.status = 'CONFIRMADA'
               AND OLD.expira_em <= clock_timestamp() THEN
                RAISE EXCEPTION 'Sessão vencida não pode ser confirmada.' USING ERRCODE = '23514';
            END IF;
            IF NEW.status = 'FALHOU' AND (
                NEW.confirmado_em IS NOT NULL OR NEW.resultado IS NULL
            ) THEN
                RAISE EXCEPTION 'Falha exige diagnóstico seguro e não admite data de confirmação.' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE TRIGGER trg_sessoes_importacao_cadastral_imutaveis
        BEFORE UPDATE OR DELETE ON sessoes_importacao_cadastral
        FOR EACH ROW EXECUTE FUNCTION proteger_sessao_importacao_cadastral()
    """)


def downgrade():
    op.execute(
        "DROP TRIGGER trg_sessoes_importacao_cadastral_imutaveis "
        "ON sessoes_importacao_cadastral"
    )
    op.execute("DROP FUNCTION proteger_sessao_importacao_cadastral()")
    op.drop_index(
        "ix_sessoes_importacao_arquivo_sha256",
        table_name="sessoes_importacao_cadastral",
    )
    op.drop_index(
        "ix_sessoes_importacao_uuid_publico",
        table_name="sessoes_importacao_cadastral",
    )
    op.drop_table("sessoes_importacao_cadastral")
