import json
import math
import secrets
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from hashlib import sha256

from sqlalchemy.orm import Session

from repositories.importacao_cadastral_repository import ImportacaoCadastralRepository
from services.pre_validacao_cadastral import pre_validar_planilha_cadastral_completo


DURACAO_SESSAO = timedelta(hours=24)


class PlanilhaInvalidaError(ValueError):
    def __init__(self, validacao: dict):
        super().__init__("A planilha possui erros e não pode ser preparada.")
        self.validacao = validacao


def _normalizar_json(valor):
    if isinstance(valor, Enum):
        return _normalizar_json(valor.value)
    if isinstance(valor, Decimal):
        return format(valor, "f")
    if isinstance(valor, datetime):
        if valor.tzinfo is None or valor.utcoffset() is None:
            raise TypeError("Datetime sem timezone não é serializável.")
        return valor.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(valor, date):
        return valor.isoformat()
    if valor is None or isinstance(valor, (str, bool, int)):
        return valor
    if isinstance(valor, float):
        if not math.isfinite(valor):
            raise ValueError("Número não finito não é serializável.")
        return valor
    if isinstance(valor, (list, tuple)):
        return [_normalizar_json(item) for item in valor]
    if isinstance(valor, dict):
        if not all(isinstance(chave, str) for chave in valor):
            raise TypeError("Chaves JSON devem ser texto.")
        return {chave: _normalizar_json(item) for chave, item in valor.items()}
    raise TypeError(f"Tipo não serializável: {type(valor).__name__}")


def serializar_canonico(valor) -> tuple[dict | list, str]:
    normalizado = _normalizar_json(valor)
    texto = json.dumps(
        normalizado,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return json.loads(texto), texto


def preparar_sessao(
    conteudo: bytes,
    nome_arquivo: str,
    db: Session,
    digest_arquivo: str | None = None,
    agora: datetime | None = None,
) -> tuple[object, str, dict]:
    validacao, internos = pre_validar_planilha_cadastral_completo(
        conteudo, nome_arquivo, db, digest_arquivo
    )
    if not validacao["valido_para_confirmacao"]:
        raise PlanilhaInvalidaError(validacao)

    payload, _ = serializar_canonico({
        "versao": validacao["versao"],
        "dados": internos["dados"],
        "operacoes": internos["operacoes"],
    })
    resumo, _ = serializar_canonico(validacao["resumo"])
    avisos, _ = serializar_canonico([
        item for item in internos["diagnosticos"] if item["severidade"] == "AVISO"
    ])
    token = secrets.token_urlsafe(32)
    instante = (agora or datetime.now(timezone.utc)).astimezone(timezone.utc)
    sessao = ImportacaoCadastralRepository(db).criar(
        token_hash=sha256(token.encode("utf-8")).hexdigest(),
        arquivo_sha256=validacao["sha256"],
        versao_contrato=validacao["versao"],
        payload_normalizado=payload,
        resumo=resumo,
        avisos=avisos,
        status="PENDENTE",
        criado_em=instante,
        expira_em=instante + DURACAO_SESSAO,
    )
    return sessao, token, validacao
