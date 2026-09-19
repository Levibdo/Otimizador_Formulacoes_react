from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field


PrecoNaoNegativo = Annotated[Decimal, Field(ge=0)]


class CenarioCustoCreate(BaseModel):
    projeto_id: int = Field(gt=0)
    versao_formula_id: int = Field(gt=0)
    nome: str = Field(min_length=1, max_length=200)
    observacao: str | None = None
    precos_cenario: dict[str, PrecoNaoNegativo] = Field(min_length=1)


class CenarioCustoRead(BaseModel):
    id: int
    projeto_id: int
    versao_formula_id: int
    nome: str
    observacao: str | None
    precos_cenario: dict
    detalhes_materias_primas: list
    impacto_apresentacoes: list
    custo_base_kg: Decimal
    custo_cenario_kg: Decimal
    variacao_absoluta: Decimal
    variacao_percentual: Decimal
    criado_em: datetime
