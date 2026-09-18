"""Cria matérias-primas, nutrientes, composição e preços."""

from alembic import op
import sqlalchemy as sa


revision = "20260918_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "materias_primas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(length=30), nullable=False, unique=True),
        sa.Column("nome", sa.String(length=200), nullable=False, unique=True),
        sa.Column("ativa", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "nutrientes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(length=30), nullable=False, unique=True),
        sa.Column("nome", sa.String(length=120), nullable=False, unique=True),
        sa.Column("unidade", sa.String(length=30), nullable=False),
    )
    op.create_table(
        "composicoes_materias_primas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "materia_prima_id",
            sa.Integer(),
            sa.ForeignKey("materias_primas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "nutriente_id",
            sa.Integer(),
            sa.ForeignKey("nutrientes.id"),
            nullable=False,
        ),
        sa.Column("valor", sa.Numeric(18, 6), nullable=False),
        sa.CheckConstraint("valor >= 0", name="ck_composicao_valor_nao_negativo"),
        sa.UniqueConstraint(
            "materia_prima_id",
            "nutriente_id",
            name="uq_composicao_mp_nutriente",
        ),
    )
    op.create_table(
        "precos_materias_primas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "materia_prima_id",
            sa.Integer(),
            sa.ForeignKey("materias_primas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("preco_kg", sa.Numeric(18, 6), nullable=False),
        sa.Column("vigencia_inicio", sa.Date(), nullable=False),
        sa.Column("vigencia_fim", sa.Date()),
        sa.CheckConstraint("preco_kg >= 0", name="ck_preco_kg_nao_negativo"),
        sa.CheckConstraint(
            "vigencia_fim IS NULL OR vigencia_fim >= vigencia_inicio",
            name="ck_preco_periodo_valido",
        ),
        sa.UniqueConstraint(
            "materia_prima_id",
            "vigencia_inicio",
            name="uq_preco_mp_vigencia_inicio",
        ),
    )


def downgrade():
    op.drop_table("precos_materias_primas")
    op.drop_table("composicoes_materias_primas")
    op.drop_table("nutrientes")
    op.drop_table("materias_primas")
