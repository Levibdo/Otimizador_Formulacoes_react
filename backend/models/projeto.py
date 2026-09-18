from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class Projeto(Base):
    __tablename__ = "projetos"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ATIVO', 'CONCLUIDO', 'ARQUIVADO')",
            name="ck_projeto_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ATIVO")
    requisitos: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    versoes: Mapped[list["VersaoFormula"]] = relationship(
        back_populates="projeto",
        cascade="all, delete-orphan",
        order_by="VersaoFormula.numero",
    )


class VersaoFormula(Base):
    __tablename__ = "versoes_formulas"
    __table_args__ = (
        UniqueConstraint("projeto_id", "numero", name="uq_versao_projeto_numero"),
        CheckConstraint("numero > 0", name="ck_versao_numero_positivo"),
        CheckConstraint(
            "custo_total IS NULL OR custo_total >= 0",
            name="ck_versao_custo_nao_negativo",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    projeto_id: Mapped[int] = mapped_column(
        ForeignKey("projetos.id", ondelete="CASCADE"), nullable=False
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    observacao: Mapped[str | None] = mapped_column(Text)
    status_solver: Mapped[str] = mapped_column(String(30), nullable=False)
    custo_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    inclusoes: Mapped[dict] = mapped_column(JSON, nullable=False)
    custos_individuais: Mapped[dict] = mapped_column(JSON, nullable=False)
    composicao_nutricional: Mapped[dict] = mapped_column(JSON, nullable=False)
    parametros: Mapped[dict] = mapped_column(JSON, nullable=False)
    matriz_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    requisitos_snapshot: Mapped[list] = mapped_column(JSON, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    projeto: Mapped[Projeto] = relationship(back_populates="versoes")
