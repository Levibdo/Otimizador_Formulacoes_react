import logging
from hashlib import sha256
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from db.session import get_db
from services.pre_validacao_cadastral import pre_validar_planilha_cadastral
from services.planilha_cadastral import MAX_ARQUIVO_BYTES, gerar_template_cadastral
from services.staging_importacao_cadastral import PlanilhaInvalidaError, preparar_sessao
from repositories.importacao_cadastral_repository import ImportacaoCadastralRepository
from schemas.importacao_cadastral import SessaoImportacaoPreparada, SessaoImportacaoRead


router = APIRouter(prefix="/api/v1/importacoes-cadastrais", tags=["Importação cadastral"])
logger = logging.getLogger(__name__)


async def _ler_upload(arquivo: UploadFile) -> tuple[bytes, str]:
    digest = sha256()
    conteudo = bytearray()
    while trecho := await arquivo.read(64 * 1024):
        digest.update(trecho)
        if len(conteudo) <= MAX_ARQUIVO_BYTES:
            restante = MAX_ARQUIVO_BYTES + 1 - len(conteudo)
            conteudo.extend(trecho[:restante])
    return bytes(conteudo), digest.hexdigest()


def _operacoes_total(resumo: dict) -> int:
    return sum(
        valores[chave]
        for aba, valores in resumo.items()
        if aba != "GERAL"
        for chave in ("criar", "atualizar", "desativar", "sem_alteracao")
    )


def _serializar_sessao(sessao, incluir_avisos=True):
    resposta = {
        "sessao_id": sessao.uuid_publico,
        "status": sessao.status,
        "arquivo_sha256": sessao.arquivo_sha256,
        "versao": sessao.versao_contrato,
        "resumo": sessao.resumo,
        "operacoes_total": _operacoes_total(sessao.resumo),
        "criado_em": sessao.criado_em,
        "expira_em": sessao.expira_em,
    }
    if incluir_avisos:
        resposta["avisos"] = sessao.avisos
    return resposta


@router.get("/template")
def baixar_template():
    conteudo = gerar_template_cadastral()
    return Response(
        content=conteudo,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="template-cadastral-v1.0.xlsx"',
            "Content-Security-Policy": "default-src 'none'",
            "X-Content-Type-Options": "nosniff",
            "X-Template-Version": "1.0",
        },
    )


@router.post("/validar")
async def validar_planilha(
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        conteudo, digest = await _ler_upload(arquivo)
        return pre_validar_planilha_cadastral(
            conteudo,
            arquivo.filename or "",
            db,
            digest,
        )
    except Exception as exc:
        logger.exception("Falha interna na pré-validação cadastral.")
        raise HTTPException(
            status_code=500,
            detail="Não foi possível pré-validar a planilha cadastral.",
        ) from exc


@router.post("/preparar", status_code=201, response_model=SessaoImportacaoPreparada)
async def preparar_planilha(
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        conteudo, digest = await _ler_upload(arquivo)
        sessao, token, validacao = preparar_sessao(
            conteudo, arquivo.filename or "", db, digest
        )
        db.commit()
        resposta = _serializar_sessao(sessao)
        resposta["token_confirmacao"] = token
        resposta["operacoes_total"] = validacao["operacoes_total"]
        return resposta
    except PlanilhaInvalidaError as exc:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail={
                "mensagem": "A planilha possui erros e não pode ser preparada.",
                "validacao": exc.validacao,
            },
        ) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Falha interna na preparação da importação cadastral.")
        raise HTTPException(
            status_code=500,
            detail="Não foi possível preparar a importação cadastral.",
        ) from exc


@router.get("/{sessao_id:uuid}", response_model=SessaoImportacaoRead)
def consultar_sessao(sessao_id: UUID, db: Session = Depends(get_db)):
    try:
        repo = ImportacaoCadastralRepository(db)
        sessao = repo.obter(sessao_id)
        if sessao is None:
            raise HTTPException(status_code=404, detail="Sessão de importação não encontrada.")
        if repo.marcar_expirada(sessao):
            db.commit()
        return _serializar_sessao(sessao)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Falha interna na consulta da sessão de importação cadastral.")
        raise HTTPException(
            status_code=500,
            detail="Não foi possível consultar a sessão de importação.",
        ) from exc
