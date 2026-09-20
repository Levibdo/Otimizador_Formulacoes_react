"""Execuções rastreáveis do motor regulatório server-side."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260919_07"
down_revision = "20260919_06"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "execucoes_otimizacao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("projeto_id", sa.Integer(), sa.ForeignKey("projetos.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("instante", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("versao_motor", sa.String(30), nullable=False),
        sa.Column("entradas_contexto", postgresql.JSONB(), nullable=False),
        sa.Column("requisitos_usados", postgresql.JSONB(), nullable=False),
        sa.Column("regras_regulatorias_usadas", postgresql.JSONB(), nullable=False),
        sa.Column("limites_efetivos", postgresql.JSONB(), nullable=False),
        sa.Column("alertas", postgresql.JSONB(), nullable=False),
        sa.Column("pendencias", postgresql.JSONB(), nullable=False),
        sa.Column("resultado_diagnostico", postgresql.JSONB(), nullable=False),
        sa.Column("referencia_precos", postgresql.JSONB(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('SEM_AVALIACAO_REGULATORIA', 'ATENDE', 'ATENDE_COM_ALERTAS', "
            "'INCONCLUSIVA', 'INVIAVEL', 'ERRO_TECNICO')",
            name="ck_execucao_otimizacao_status",
        ),
    )
    op.create_index("ix_execucoes_otimizacao_projeto_id", "execucoes_otimizacao", ["projeto_id"])
    op.execute("""
        CREATE FUNCTION impedir_mutacao_execucao_otimizacao() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Execução de otimização é histórica e não pode ser alterada ou excluída.'
                USING ERRCODE = '23514';
        END $$
    """)
    op.execute("""
        CREATE TRIGGER trg_execucoes_otimizacao_imutavel
        BEFORE UPDATE OR DELETE ON execucoes_otimizacao
        FOR EACH ROW EXECUTE FUNCTION impedir_mutacao_execucao_otimizacao()
    """)


def downgrade():
    op.execute("DROP TRIGGER trg_execucoes_otimizacao_imutavel ON execucoes_otimizacao")
    op.execute("DROP FUNCTION impedir_mutacao_execucao_otimizacao()")
    op.drop_index("ix_execucoes_otimizacao_projeto_id", table_name="execucoes_otimizacao")
    op.drop_table("execucoes_otimizacao")
