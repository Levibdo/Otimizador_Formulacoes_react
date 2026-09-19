from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class ItemEmbalagemCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=30)
    nome: str = Field(min_length=1, max_length=150)
    unidade: str = Field(default="un", min_length=1, max_length=20)
    custo_unitario: Decimal = Field(ge=0)


class ItemEmbalagemUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    unidade: str | None = Field(default=None, min_length=1, max_length=20)
    custo_unitario: Decimal | None = Field(default=None, ge=0)
    ativo: bool | None = None

    @model_validator(mode="after")
    def validar_campos(self):
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualização.")
        return self


class ItemEmbalagemRead(BaseModel):
    id: int
    codigo: str
    nome: str
    unidade: str
    custo_unitario: Decimal
    ativo: bool


class ComponenteApresentacaoCreate(BaseModel):
    item_embalagem_id: int = Field(gt=0)
    quantidade: Decimal = Field(gt=0)


class ApresentacaoCreate(BaseModel):
    projeto_id: int = Field(gt=0)
    versao_formula_id: int = Field(gt=0)
    codigo: str = Field(min_length=1, max_length=30)
    nome: str = Field(min_length=1, max_length=200)
    peso_liquido_g: Decimal = Field(gt=0)
    unidades_por_caixa: int = Field(default=1, gt=0)
    componentes: list[ComponenteApresentacaoCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validar_componentes_unicos(self):
        ids = [item.item_embalagem_id for item in self.componentes]
        if len(ids) != len(set(ids)):
            raise ValueError("A apresentação não pode repetir o mesmo componente.")
        return self


class ComponenteApresentacaoRead(BaseModel):
    item_embalagem_id: int
    item_codigo_snapshot: str
    item_nome_snapshot: str
    unidade_snapshot: str
    quantidade: Decimal
    custo_unitario_snapshot: Decimal
    custo_total: Decimal


class ApresentacaoRead(BaseModel):
    id: int
    projeto_id: int
    versao_formula_id: int
    codigo: str
    nome: str
    peso_liquido_g: Decimal
    unidades_por_caixa: int
    custo_formula: Decimal
    custo_embalagem: Decimal
    custo_unitario: Decimal
    custo_caixa: Decimal
    criado_em: datetime
    componentes: list[ComponenteApresentacaoRead]
