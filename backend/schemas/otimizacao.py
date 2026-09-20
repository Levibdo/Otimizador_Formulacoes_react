from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LimiteTecnicoMP(BaseModel):
    model_config = ConfigDict(extra="forbid")
    materia_prima_id: int = Field(gt=0)
    minimo: Decimal | None = Field(default=None, ge=0, le=100)
    maximo: Decimal | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def validar_intervalo(self):
        if self.minimo is None and self.maximo is None:
            raise ValueError("Informe limite mínimo ou máximo.")
        if self.minimo is not None and self.maximo is not None and self.minimo > self.maximo:
            raise ValueError("O mínimo técnico não pode superar o máximo.")
        return self


class OtimizacaoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    materias_primas_ids: list[int] | None = None
    limites_tecnicos: list[LimiteTecnicoMP] = Field(default_factory=list)
    data_referencia: date | None = None

    @model_validator(mode="after")
    def validar_candidatas(self):
        if self.materias_primas_ids is not None:
            if not self.materias_primas_ids:
                raise ValueError("Informe ao menos uma matéria-prima candidata.")
            if len(self.materias_primas_ids) != len(set(self.materias_primas_ids)):
                raise ValueError("Matérias-primas candidatas não podem se repetir.")
        ids_limites = [item.materia_prima_id for item in self.limites_tecnicos]
        if len(ids_limites) != len(set(ids_limites)):
            raise ValueError("Limites técnicos não podem repetir a matéria-prima.")
        return self


StatusRegulatorio = Literal[
    "SEM_AVALIACAO_REGULATORIA", "ATENDE", "ATENDE_COM_ALERTAS",
    "INCONCLUSIVA", "INVIAVEL", "ERRO_TECNICO",
]


class ExecucaoOtimizacaoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    projeto_id: int
    instante: datetime
    status: StatusRegulatorio
    versao_motor: str
    entradas_contexto: dict
    requisitos_usados: list
    regras_regulatorias_usadas: list
    limites_efetivos: dict
    alertas: list
    pendencias: list
    resultado_diagnostico: dict
    referencia_precos: dict
    criado_em: datetime
    atualizado_em: datetime


class OtimizacaoResponse(BaseModel):
    execucao_id: int
    status: StatusRegulatorio
    status_solver: str | None = None
    inclusoes: dict[str, float] = Field(default_factory=dict)
    composicao: dict[str, float] = Field(default_factory=dict)
    componentes: dict[str, float] = Field(default_factory=dict)
    custo_total: float | None = None
    custos_individuais: dict[str, float] = Field(default_factory=dict)
    regras_aplicadas: list = Field(default_factory=list)
    limites_efetivos: dict = Field(default_factory=dict)
    alertas: list[str] = Field(default_factory=list)
    pendencias: list[str] = Field(default_factory=list)
    diagnostico: dict = Field(default_factory=dict)
