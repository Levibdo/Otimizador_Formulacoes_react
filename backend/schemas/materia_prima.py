from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ComposicaoCreate(BaseModel):
    nutriente_codigo: str = Field(min_length=1, max_length=30)
    nutriente_nome: str = Field(min_length=1, max_length=120)
    unidade: str = Field(min_length=1, max_length=30)
    valor: Decimal = Field(ge=0)


class PrecoCreate(BaseModel):
    preco_kg: Decimal = Field(ge=0)
    vigencia_inicio: date
    vigencia_fim: date | None = None

    @model_validator(mode="after")
    def validar_periodo(self):
        if self.vigencia_fim and self.vigencia_fim < self.vigencia_inicio:
            raise ValueError("A vigência final não pode ser anterior à inicial.")
        return self


class MateriaPrimaCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=30)
    nome: str = Field(min_length=1, max_length=200)
    composicao: list[ComposicaoCreate] = Field(default_factory=list)
    preco_inicial: PrecoCreate

    @model_validator(mode="after")
    def validar_nutrientes_unicos(self):
        codigos = [item.nutriente_codigo for item in self.composicao]
        if len(codigos) != len(set(codigos)):
            raise ValueError("A composição não pode repetir o mesmo nutriente.")
        return self


class MateriaPrimaUpdate(BaseModel):
    codigo: str | None = Field(default=None, min_length=1, max_length=30)
    nome: str | None = Field(default=None, min_length=1, max_length=200)
    ativa: bool | None = None
    composicao: list[ComposicaoCreate] | None = None

    @model_validator(mode="after")
    def validar_atualizacao(self):
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualização.")
        if self.composicao is not None:
            codigos = [item.nutriente_codigo for item in self.composicao]
            if len(codigos) != len(set(codigos)):
                raise ValueError("A composição não pode repetir o mesmo nutriente.")
        return self


class ComposicaoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nutriente_codigo: str
    nutriente_nome: str
    unidade: str
    valor: Decimal


class PrecoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    preco_kg: Decimal
    vigencia_inicio: date
    vigencia_fim: date | None


class MateriaPrimaRead(BaseModel):
    id: int
    codigo: str
    nome: str
    ativa: bool
    composicao: list[ComposicaoRead]
    precos: list[PrecoRead]


class MatrizOtimizacaoRead(BaseModel):
    data_referencia: date
    materias_primas: list[str]
    nutrientes: list[str]
    matriz: dict[str, dict[str, float]]
