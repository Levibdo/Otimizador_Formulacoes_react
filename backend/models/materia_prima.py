from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class MateriaPrima(Base):
    __tablename__ = "materias_primas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    composicao: Mapped[list["ComposicaoMateriaPrima"]] = relationship(
        back_populates="materia_prima",
        cascade="all, delete-orphan",
    )
    precos: Mapped[list["PrecoMateriaPrima"]] = relationship(
        back_populates="materia_prima",
        cascade="all, delete-orphan",
    )


class Nutriente(Base):
    __tablename__ = "nutrientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    unidade: Mapped[str] = mapped_column(String(30), nullable=False)

    composicoes: Mapped[list["ComposicaoMateriaPrima"]] = relationship(
        back_populates="nutriente"
    )


class ComposicaoMateriaPrima(Base):
    __tablename__ = "composicoes_materias_primas"
    __table_args__ = (
        UniqueConstraint(
            "materia_prima_id",
            "nutriente_id",
            name="uq_composicao_mp_nutriente",
        ),
        CheckConstraint("valor >= 0", name="ck_composicao_valor_nao_negativo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    materia_prima_id: Mapped[int] = mapped_column(
        ForeignKey("materias_primas.id", ondelete="CASCADE"), nullable=False
    )
    nutriente_id: Mapped[int] = mapped_column(
        ForeignKey("nutrientes.id"), nullable=False
    )
    valor: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    materia_prima: Mapped[MateriaPrima] = relationship(back_populates="composicao")
    nutriente: Mapped[Nutriente] = relationship(back_populates="composicoes")


class PrecoMateriaPrima(Base):
    __tablename__ = "precos_materias_primas"
    __table_args__ = (
        UniqueConstraint(
            "materia_prima_id",
            "vigencia_inicio",
            name="uq_preco_mp_vigencia_inicio",
        ),
        CheckConstraint("preco_kg >= 0", name="ck_preco_kg_nao_negativo"),
        CheckConstraint(
            "vigencia_fim IS NULL OR vigencia_fim >= vigencia_inicio",
            name="ck_preco_periodo_valido",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    materia_prima_id: Mapped[int] = mapped_column(
        ForeignKey("materias_primas.id", ondelete="CASCADE"), nullable=False
    )
    preco_kg: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    vigencia_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    vigencia_fim: Mapped[date | None] = mapped_column(Date)

    materia_prima: Mapped[MateriaPrima] = relationship(back_populates="precos")
