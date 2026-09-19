from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class DatasCadastro:
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CategoriaProduto(DatasCadastro, Base):
    __tablename__ = 'categorias_produto'
    __table_args__ = (CheckConstraint('revisao > 0', name='ck_categoria_revisao'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(50), unique=True)
    nome: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str | None] = mapped_column(Text)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true')
    revisao: Mapped[int] = mapped_column(Integer, default=1, server_default='1')


class ComponenteRegulatorio(DatasCadastro, Base):
    __tablename__ = 'componentes_regulatorios'
    __table_args__ = (CheckConstraint("unidade = '%' AND base = 'MASSA_MASSA'", name='ck_componente_base'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(50), unique=True)
    nome: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str | None] = mapped_column(Text)
    unidade: Mapped[str] = mapped_column(String(10), default='%', server_default='%')
    base: Mapped[str] = mapped_column(String(30), default='MASSA_MASSA', server_default='MASSA_MASSA')
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true')


class ComposicaoComponenteMP(DatasCadastro, Base):
    __tablename__ = 'composicoes_componentes_mp'
    __table_args__ = (
        UniqueConstraint('materia_prima_id', 'componente_id', 'data_referencia', name='uq_componente_mp_data'),
        CheckConstraint('concentracao IS NULL OR (concentracao >= 0 AND concentracao <= 100)', name='ck_concentracao_percentual'),
        CheckConstraint("(situacao = 'INFORMADO' AND concentracao IS NOT NULL) OR (situacao = 'AUSENTE_CONFIRMADO' AND concentracao IS NOT NULL AND concentracao = 0) OR (situacao = 'DESCONHECIDO' AND concentracao IS NULL)", name='ck_concentracao_situacao'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    materia_prima_id: Mapped[int] = mapped_column(ForeignKey('materias_primas.id', ondelete='RESTRICT'))
    componente_id: Mapped[int] = mapped_column(ForeignKey('componentes_regulatorios.id', ondelete='RESTRICT'))
    concentracao: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    situacao: Mapped[str] = mapped_column(String(30))
    fonte: Mapped[str | None] = mapped_column(Text)
    observacao: Mapped[str | None] = mapped_column(Text)
    data_referencia: Mapped[date] = mapped_column(Date)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true')


class RegraRegulatoria(DatasCadastro, Base):
    __tablename__ = 'regras_regulatorias'
    __table_args__ = (
        CheckConstraint("(tipo_alvo = 'MATERIA_PRIMA' AND materia_prima_id IS NOT NULL AND componente_id IS NULL) OR (tipo_alvo = 'COMPONENTE' AND componente_id IS NOT NULL AND materia_prima_id IS NULL)", name='ck_regra_alvo'),
        CheckConstraint("tratamento IN ('PERMITIDA', 'PROIBIDA', 'OBRIGATORIA', 'LIMITADA')", name='ck_regra_tratamento'),
        CheckConstraint('minimo IS NULL OR (minimo >= 0 AND minimo <= 100)', name='ck_regra_minimo'),
        CheckConstraint('maximo IS NULL OR (maximo >= 0 AND maximo <= 100)', name='ck_regra_maximo'),
        CheckConstraint('minimo IS NULL OR maximo IS NULL OR minimo <= maximo', name='ck_regra_limites'),
        CheckConstraint("tratamento != 'OBRIGATORIA' OR (minimo IS NOT NULL AND minimo > 0)", name='ck_regra_obrigatoria'),
        CheckConstraint("tratamento != 'PROIBIDA' OR (maximo IS NOT NULL AND maximo = 0 AND (minimo IS NULL OR minimo = 0))", name='ck_regra_proibida'),
        CheckConstraint("tratamento != 'LIMITADA' OR minimo IS NOT NULL OR maximo IS NOT NULL", name='ck_regra_limitada'),
        CheckConstraint("unidade = '%' AND base = 'MASSA_MASSA'", name='ck_regra_base'),
        CheckConstraint('vigencia_inicio IS NULL OR vigencia_fim IS NULL OR vigencia_fim >= vigencia_inicio', name='ck_regra_vigencia'),
        CheckConstraint('revisao > 0', name='ck_regra_revisao'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    categoria_id: Mapped[int] = mapped_column(ForeignKey('categorias_produto.id', ondelete='RESTRICT'), index=True)
    tipo_alvo: Mapped[str] = mapped_column(String(20))
    materia_prima_id: Mapped[int | None] = mapped_column(ForeignKey('materias_primas.id', ondelete='RESTRICT'))
    componente_id: Mapped[int | None] = mapped_column(ForeignKey('componentes_regulatorios.id', ondelete='RESTRICT'))
    tratamento: Mapped[str] = mapped_column(String(20))
    minimo: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    maximo: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    unidade: Mapped[str] = mapped_column(String(10), default='%', server_default='%')
    base: Mapped[str] = mapped_column(String(30), default='MASSA_MASSA', server_default='MASSA_MASSA')
    justificativa: Mapped[str] = mapped_column(Text)
    referencia_normativa: Mapped[str | None] = mapped_column(Text)
    revisao: Mapped[int] = mapped_column(Integer, default=1, server_default='1')
    regra_anterior_id: Mapped[int | None] = mapped_column(ForeignKey('regras_regulatorias.id', ondelete='RESTRICT'), unique=True)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true')
    vigencia_inicio: Mapped[date | None] = mapped_column(Date)
    vigencia_fim: Mapped[date | None] = mapped_column(Date)
