"""Cria projetos e versões imutáveis de formulação."""

from alembic import op
import sqlalchemy as sa


revision = "20260918_02"
down_revision = "20260918_01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "projetos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(length=30), nullable=False, unique=True),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("descricao", sa.Text()),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("requisitos", sa.JSON(), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('ATIVO', 'CONCLUIDO', 'ARQUIVADO')",
            name="ck_projeto_status",
        ),
    )
    op.create_table(
        "versoes_formulas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "projeto_id",
            sa.Integer(),
            sa.ForeignKey("projetos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("observacao", sa.Text()),
        sa.Column("status_solver", sa.String(length=30), nullable=False),
        sa.Column("custo_total", sa.Numeric(18, 6)),
        sa.Column("inclusoes", sa.JSON(), nullable=False),
        sa.Column("custos_individuais", sa.JSON(), nullable=False),
        sa.Column("composicao_nutricional", sa.JSON(), nullable=False),
        sa.Column("parametros", sa.JSON(), nullable=False),
        sa.Column("matriz_snapshot", sa.JSON(), nullable=False),
        sa.Column("requisitos_snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("numero > 0", name="ck_versao_numero_positivo"),
        sa.CheckConstraint(
            "custo_total IS NULL OR custo_total >= 0",
            name="ck_versao_custo_nao_negativo",
        ),
        sa.UniqueConstraint("projeto_id", "numero", name="uq_versao_projeto_numero"),
    )


def downgrade():
    op.drop_table("versoes_formulas")
    op.drop_table("projetos")
