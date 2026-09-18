"""Cria itens de embalagem e custos imutáveis por apresentação."""

from alembic import op
import sqlalchemy as sa


revision = "20260918_03"
down_revision = "20260918_02"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "itens_embalagem",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(length=30), nullable=False, unique=True),
        sa.Column("nome", sa.String(length=150), nullable=False, unique=True),
        sa.Column("unidade", sa.String(length=20), nullable=False),
        sa.Column("custo_unitario", sa.Numeric(18, 6), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.CheckConstraint("custo_unitario >= 0", name="ck_item_embalagem_custo"),
    )
    op.create_table(
        "apresentacoes_produto",
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
        sa.Column("codigo", sa.String(length=30), nullable=False, unique=True),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("peso_liquido_g", sa.Numeric(18, 6), nullable=False),
        sa.Column("unidades_por_caixa", sa.Integer(), nullable=False),
        sa.Column("custo_formula", sa.Numeric(18, 6), nullable=False),
        sa.Column("custo_embalagem", sa.Numeric(18, 6), nullable=False),
        sa.Column("custo_unitario", sa.Numeric(18, 6), nullable=False),
        sa.Column("custo_caixa", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("peso_liquido_g > 0", name="ck_apresentacao_peso"),
        sa.CheckConstraint(
            "unidades_por_caixa > 0", name="ck_apresentacao_unidades"
        ),
        sa.CheckConstraint("custo_formula >= 0", name="ck_apresentacao_custo_formula"),
        sa.CheckConstraint(
            "custo_embalagem >= 0", name="ck_apresentacao_custo_embalagem"
        ),
        sa.CheckConstraint(
            "custo_unitario >= 0", name="ck_apresentacao_custo_unitario"
        ),
        sa.CheckConstraint("custo_caixa >= 0", name="ck_apresentacao_custo_caixa"),
    )
    op.create_table(
        "componentes_apresentacao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "apresentacao_id",
            sa.Integer(),
            sa.ForeignKey("apresentacoes_produto.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "item_embalagem_id",
            sa.Integer(),
            sa.ForeignKey("itens_embalagem.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("item_codigo_snapshot", sa.String(length=30), nullable=False),
        sa.Column("item_nome_snapshot", sa.String(length=150), nullable=False),
        sa.Column("unidade_snapshot", sa.String(length=20), nullable=False),
        sa.Column("quantidade", sa.Numeric(18, 6), nullable=False),
        sa.Column("custo_unitario_snapshot", sa.Numeric(18, 6), nullable=False),
        sa.Column("custo_total", sa.Numeric(18, 6), nullable=False),
        sa.UniqueConstraint(
            "apresentacao_id", "item_embalagem_id", name="uq_apresentacao_item"
        ),
        sa.CheckConstraint("quantidade > 0", name="ck_componente_quantidade"),
        sa.CheckConstraint(
            "custo_unitario_snapshot >= 0", name="ck_componente_custo_unitario"
        ),
        sa.CheckConstraint("custo_total >= 0", name="ck_componente_custo_total"),
    )


def downgrade():
    op.drop_table("componentes_apresentacao")
    op.drop_table("apresentacoes_produto")
    op.drop_table("itens_embalagem")
