from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class ItemEmbalagem(Base):
    __tablename__ = "itens_embalagem"
    __table_args__ = (
        CheckConstraint("custo_unitario >= 0", name="ck_item_embalagem_custo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    unidade: Mapped[str] = mapped_column(String(20), nullable=False, default="un")
    custo_unitario: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ApresentacaoProduto(Base):
    __tablename__ = "apresentacoes_produto"
    __table_args__ = (
        CheckConstraint("peso_liquido_g > 0", name="ck_apresentacao_peso"),
        CheckConstraint("unidades_por_caixa > 0", name="ck_apresentacao_unidades"),
        CheckConstraint("custo_formula >= 0", name="ck_apresentacao_custo_formula"),
        CheckConstraint(
            "custo_embalagem >= 0", name="ck_apresentacao_custo_embalagem"
        ),
        CheckConstraint("custo_unitario >= 0", name="ck_apresentacao_custo_unitario"),
        CheckConstraint("custo_caixa >= 0", name="ck_apresentacao_custo_caixa"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    projeto_id: Mapped[int] = mapped_column(
        ForeignKey("projetos.id", ondelete="RESTRICT"), nullable=False
    )
    versao_formula_id: Mapped[int] = mapped_column(
        ForeignKey("versoes_formulas.id", ondelete="RESTRICT"), nullable=False
    )
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    peso_liquido_g: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unidades_por_caixa: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    custo_formula: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    custo_embalagem: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    custo_unitario: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    custo_caixa: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    componentes: Mapped[list["ComponenteApresentacao"]] = relationship(
        back_populates="apresentacao",
        cascade="all, delete-orphan",
        order_by="ComponenteApresentacao.id",
    )


class ComponenteApresentacao(Base):
    __tablename__ = "componentes_apresentacao"
    __table_args__ = (
        UniqueConstraint(
            "apresentacao_id", "item_embalagem_id", name="uq_apresentacao_item"
        ),
        CheckConstraint("quantidade > 0", name="ck_componente_quantidade"),
        CheckConstraint(
            "custo_unitario_snapshot >= 0", name="ck_componente_custo_unitario"
        ),
        CheckConstraint("custo_total >= 0", name="ck_componente_custo_total"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    apresentacao_id: Mapped[int] = mapped_column(
        ForeignKey("apresentacoes_produto.id", ondelete="CASCADE"), nullable=False
    )
    item_embalagem_id: Mapped[int] = mapped_column(
        ForeignKey("itens_embalagem.id", ondelete="RESTRICT"), nullable=False
    )
    item_codigo_snapshot: Mapped[str] = mapped_column(String(30), nullable=False)
    item_nome_snapshot: Mapped[str] = mapped_column(String(150), nullable=False)
    unidade_snapshot: Mapped[str] = mapped_column(String(20), nullable=False)
    quantidade: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    custo_unitario_snapshot: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False
    )
    custo_total: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    apresentacao: Mapped[ApresentacaoProduto] = relationship(
        back_populates="componentes"
    )
    item_embalagem: Mapped[ItemEmbalagem] = relationship()
