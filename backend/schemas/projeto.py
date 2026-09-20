from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class RequisitoProjeto(BaseModel):
    origem: Literal["DESENVOLVIMENTO", "TECNICO", "REGULATORIO"] = "DESENVOLVIMENTO"
    tipo_item: Literal["NUTRIENTE", "MP", "CUSTO"]
    item: str = Field(min_length=1, max_length=200)
    minimo: Decimal | None = None
    maximo: Decimal | None = None
    unidade: str | None = Field(default=None, max_length=30)
    observacao: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validar_limites(self):
        if self.minimo is None and self.maximo is None:
            raise ValueError("O requisito deve possuir limite mínimo ou máximo.")
        if (
            self.minimo is not None
            and self.maximo is not None
            and self.minimo > self.maximo
        ):
            raise ValueError("O limite mínimo não pode superar o máximo.")
        return self


class ProjetoCreate(BaseModel):
    categoria_produto_id: int | None = Field(default=None, gt=0)
    codigo: str = Field(min_length=1, max_length=30)
    nome: str = Field(min_length=1, max_length=200)
    descricao: str | None = None
    requisitos: list[RequisitoProjeto] = Field(default_factory=list)


class ProjetoUpdate(BaseModel):
    categoria_produto_id: int | None = Field(default=None, gt=0)
    nome: str | None = Field(default=None, min_length=1, max_length=200)
    descricao: str | None = None
    status: Literal["ATIVO", "CONCLUIDO", "ARQUIVADO"] | None = None
    requisitos: list[RequisitoProjeto] | None = None

    @model_validator(mode="after")
    def validar_campos(self):
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualização.")
        return self


class VersaoFormulaCreate(BaseModel):
    execucao_id: int | None = Field(default=None, gt=0)
    observacao: str | None = None
    status_solver: str | None = Field(default=None, min_length=1, max_length=30)
    custo_total: Decimal | None = Field(default=None, ge=0)
    inclusoes: dict[str, float] | None = None
    custos_individuais: dict[str, float] | None = None
    composicao_nutricional: dict[str, float] | None = None
    parametros: dict = Field(default_factory=dict)
    matriz_snapshot: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validar_origem(self):
        if self.execucao_id is None:
            obrigatorios = (self.status_solver, self.inclusoes, self.custos_individuais, self.composicao_nutricional)
            if any(valor is None for valor in obrigatorios):
                raise ValueError("O fluxo legado exige o resultado completo da otimização.")
        elif any(valor is not None for valor in (self.status_solver, self.custo_total, self.inclusoes, self.custos_individuais, self.composicao_nutricional)) or self.parametros or self.matriz_snapshot:
            raise ValueError("Com execucao_id, o servidor obtém todos os dados da execução persistida.")
        return self


class VersaoFormulaRead(BaseModel):
    id: int
    numero: int
    observacao: str | None
    status_solver: str
    custo_total: Decimal | None
    inclusoes: dict
    custos_individuais: dict
    composicao_nutricional: dict
    parametros: dict
    matriz_snapshot: dict
    requisitos_snapshot: list
    criado_em: datetime


class ProjetoRead(BaseModel):
    categoria_produto_id: int | None = None
    id: int
    codigo: str
    nome: str
    descricao: str | None
    status: str
    requisitos: list[RequisitoProjeto]
    criado_em: datetime
    atualizado_em: datetime
    versoes: list[VersaoFormulaRead]
