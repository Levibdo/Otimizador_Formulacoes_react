"""Cria cenários auditáveis de custos de matérias-primas."""

from alembic import op
import sqlalchemy as sa


revision = "20260918_04"
down_revision = "20260918_03"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cenarios_custo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "projeto_id",
            sa.Integer(),
            sa.ForeignKey("projetos.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "versao_formula_id",
            sa.Integer(),
            sa.ForeignKey("versoes_formulas.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("observacao", sa.Text()),
        sa.Column("precos_cenario", sa.JSON(), nullable=False),
        sa.Column("detalhes_materias_primas", sa.JSON(), nullable=False),
        sa.Column("impacto_apresentacoes", sa.JSON(), nullable=False),
        sa.Column("custo_base_kg", sa.Numeric(18, 6), nullable=False),
        sa.Column("custo_cenario_kg", sa.Numeric(18, 6), nullable=False),
        sa.Column("variacao_absoluta", sa.Numeric(18, 6), nullable=False),
        sa.Column("variacao_percentual", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("custo_base_kg >= 0", name="ck_cenario_custo_base"),
        sa.CheckConstraint(
            "custo_cenario_kg >= 0", name="ck_cenario_custo_projetado"
        ),
    )


def downgrade():
    op.drop_table("cenarios_custo")
