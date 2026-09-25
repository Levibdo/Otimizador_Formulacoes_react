from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


StatusSessaoImportacao = Literal["PENDENTE", "CONFIRMADA", "EXPIRADA", "FALHOU"]


class SessaoImportacaoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sessao_id: UUID
    status: StatusSessaoImportacao
    arquivo_sha256: str
    versao: str
    resumo: dict
    operacoes_total: int
    avisos: list[dict]
    criado_em: datetime
    expira_em: datetime


class SessaoImportacaoPreparada(SessaoImportacaoRead):
    token_confirmacao: str
