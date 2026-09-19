from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class CenarioCusto(Base):
    __tablename__ = "cenarios_custo"
    __table_args__ = (
        CheckConstraint("custo_base_kg >= 0", name="ck_cenario_custo_base"),
        CheckConstraint("custo_cenario_kg >= 0", name="ck_cenario_custo_projetado"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    projeto_id: Mapped[int] = mapped_column(
        ForeignKey("projetos.id", ondelete="RESTRICT"), nullable=False
    )
    versao_formula_id: Mapped[int] = mapped_column(
        ForeignKey("versoes_formulas.id", ondelete="RESTRICT"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    observacao: Mapped[str | None] = mapped_column(Text)
    precos_cenario: Mapped[dict] = mapped_column(JSON, nullable=False)
    detalhes_materias_primas: Mapped[list] = mapped_column(JSON, nullable=False)
    impacto_apresentacoes: Mapped[list] = mapped_column(JSON, nullable=False)
    custo_base_kg: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    custo_cenario_kg: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    variacao_absoluta: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    variacao_percentual: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
