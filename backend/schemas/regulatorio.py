from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Percentual = Annotated[Decimal, Field(ge=0, le=100, max_digits=18, decimal_places=6)]
Codigo = Annotated[str, Field(min_length=1, max_length=50, pattern=r'^[A-Z][A-Z0-9_]*$')]


class CadastroBase(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, from_attributes=True)


class CategoriaCreate(CadastroBase):
    codigo: Codigo
    nome: str = Field(min_length=1, max_length=200)
    descricao: str | None = None


class CategoriaUpdate(CadastroBase):
    nome: str | None = Field(default=None, min_length=1, max_length=200)
    descricao: str | None = None
    ativa: bool | None = None

    @model_validator(mode='after')
    def validar(self):
        if not self.model_fields_set:
            raise ValueError('Informe ao menos um campo.')
        for campo in self.model_fields_set - {'descricao'}:
            if getattr(self, campo) is None:
                raise ValueError(f'{campo} não pode ser nulo.')
        return self


class CategoriaRead(CategoriaCreate):
    id: int
    ativa: bool
    revisao: int
    criado_em: datetime
    atualizado_em: datetime


class ComponenteCreate(CategoriaCreate):
    unidade: Literal['%'] = '%'
    base: Literal['MASSA_MASSA'] = 'MASSA_MASSA'


class ComponenteUpdate(CadastroBase):
    nome: str | None = Field(default=None, min_length=1, max_length=200)
    descricao: str | None = None
    ativo: bool | None = None

    @model_validator(mode='after')
    def validar(self):
        if not self.model_fields_set:
            raise ValueError('Informe ao menos um campo.')
        for campo in self.model_fields_set - {'descricao'}:
            if getattr(self, campo) is None:
                raise ValueError(f'{campo} não pode ser nulo.')
        return self


class ComponenteRead(ComponenteCreate):
    id: int
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime


class ComposicaoCreate(CadastroBase):
    componente_id: int = Field(gt=0)
    concentracao: Percentual | None = None
    situacao: Literal['INFORMADO', 'AUSENTE_CONFIRMADO', 'DESCONHECIDO']
    fonte: str | None = None
    observacao: str | None = None
    data_referencia: date

    @model_validator(mode='after')
    def validar(self):
        if self.situacao == 'DESCONHECIDO' and self.concentracao is not None:
            raise ValueError('Concentração desconhecida deve ser nula, nunca zero presumido.')
        if self.situacao == 'AUSENTE_CONFIRMADO' and self.concentracao != Decimal('0'):
            raise ValueError('Ausência confirmada exige concentração zero explícita.')
        if self.situacao == 'INFORMADO' and self.concentracao is None:
            raise ValueError('Dado informado exige concentração.')
        return self


class ComposicaoRead(ComposicaoCreate):
    id: int
    materia_prima_id: int
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime


class AtivacaoComposicao(CadastroBase):
    ativo: bool


class AtivacaoRegra(CadastroBase):
    ativa: bool


class RegraCreate(CadastroBase):
    categoria_id: int = Field(gt=0)
    tipo_alvo: Literal['MATERIA_PRIMA', 'COMPONENTE']
    materia_prima_id: int | None = Field(default=None, gt=0)
    componente_id: int | None = Field(default=None, gt=0)
    tratamento: Literal['PERMITIDA', 'PROIBIDA', 'OBRIGATORIA', 'LIMITADA']
    minimo: Percentual | None = None
    maximo: Percentual | None = None
    unidade: Literal['%'] = '%'
    base: Literal['MASSA_MASSA'] = 'MASSA_MASSA'
    justificativa: str = Field(min_length=1)
    referencia_normativa: str | None = None
    vigencia_inicio: date | None = None
    vigencia_fim: date | None = None

    @model_validator(mode='after')
    def validar(self):
        if self.tipo_alvo == 'MATERIA_PRIMA':
            correto = self.materia_prima_id is not None and self.componente_id is None
        else:
            correto = self.componente_id is not None and self.materia_prima_id is None
        if not correto:
            raise ValueError('Informe somente o alvo correspondente ao tipo da regra.')
        if self.tratamento == 'PROIBIDA':
            if self.maximo not in (None, Decimal('0')) or self.minimo not in (None, Decimal('0')):
                raise ValueError('PROIBIDA exige máximo zero e não admite mínimo positivo.')
            self.maximo = Decimal('0')
        if self.minimo is not None and self.maximo is not None and self.minimo > self.maximo:
            raise ValueError('O mínimo não pode superar o máximo.')
        if self.tratamento == 'OBRIGATORIA' and (self.minimo is None or self.minimo <= 0):
            raise ValueError('OBRIGATORIA exige mínimo maior que zero.')
        if self.tratamento == 'LIMITADA' and self.minimo is None and self.maximo is None:
            raise ValueError('LIMITADA exige ao menos um limite.')
        if self.vigencia_inicio and self.vigencia_fim and self.vigencia_fim < self.vigencia_inicio:
            raise ValueError('Vigência final anterior à inicial.')
        return self


class RegraRead(RegraCreate):
    id: int
    revisao: int
    regra_anterior_id: int | None
    ativa: bool
    criado_em: datetime
    atualizado_em: datetime
