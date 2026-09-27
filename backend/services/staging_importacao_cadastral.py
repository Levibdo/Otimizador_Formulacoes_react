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
ABAS_DADOS_POR_VERSAO = {
    "1.0": (
        "MATERIAS_PRIMAS", "NUTRIENTES", "COMPOSICAO_NUTRICIONAL", "PRECOS_MP",
    ),
    "1.1": (
        "MATERIAS_PRIMAS", "NUTRIENTES", "COMPOSICAO_NUTRICIONAL", "PRECOS_MP",
        "CATEGORIAS_PRODUTO", "COMPONENTES_REGULATORIOS",
        "COMPOSICAO_COMPONENTES_MP", "REGRAS_REGULATORIAS_MP",
        "REGRAS_REGULATORIAS_COMPONENTE",
    ),
}
RESULTADOS_RESUMO = {
    "CRIAR": "criar", "ATUALIZAR": "atualizar",
    "DESATIVAR": "desativar", "SEM_ALTERACAO": "sem_alteracao",
}


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


def _payload_consistente(validacao, internos):
    versao = validacao["versao"]
    abas = ABAS_DADOS_POR_VERSAO.get(versao)
    dados = internos["dados"]
    operacoes = internos["operacoes"]
    if abas is None or set(dados) != set(abas):
        raise RuntimeError("Estrutura interna inconsistente para preparação.")
    if validacao["operacoes_total"] != len(operacoes):
        raise RuntimeError("Totais internos inconsistentes para preparação.")
    contagens = {
        aba: {chave: 0 for chave in RESULTADOS_RESUMO.values()}
        for aba in abas
    }
    for operacao in operacoes:
        aba = operacao.get("aba")
        resultado = RESULTADOS_RESUMO.get(operacao.get("resultado"))
        if aba not in contagens or resultado is None:
            raise RuntimeError("Operação interna inconsistente para preparação.")
        contagens[aba][resultado] += 1
    for aba in abas:
        if any(
            contagens[aba][chave] != validacao["resumo"][aba][chave]
            for chave in RESULTADOS_RESUMO.values()
        ):
            raise RuntimeError("Resumo interno inconsistente para preparação.")
    dados_canonicos = {
        aba: sorted(dados[aba], key=lambda item: item["linha"])
        for aba in abas
    }
    return {
        "versao": versao,
        "dados": dados_canonicos,
        # A classificação completa registra a decisão preparada; os dados de
        # origem continuam sendo a base da futura revalidação contra o banco.
        "operacoes": operacoes,
    }


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

    payload, _ = serializar_canonico(_payload_consistente(validacao, internos))
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
