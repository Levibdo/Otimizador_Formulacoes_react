import logging
from hashlib import sha256

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from db.session import get_db
from services.pre_validacao_cadastral import pre_validar_planilha_cadastral
from services.planilha_cadastral import MAX_ARQUIVO_BYTES, gerar_template_cadastral


router = APIRouter(prefix="/api/v1/importacoes-cadastrais", tags=["Importação cadastral"])
logger = logging.getLogger(__name__)


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
        digest = sha256()
        conteudo = bytearray()
        while trecho := await arquivo.read(64 * 1024):
            digest.update(trecho)
            if len(conteudo) <= MAX_ARQUIVO_BYTES:
                restante = MAX_ARQUIVO_BYTES + 1 - len(conteudo)
                conteudo.extend(trecho[:restante])
        return pre_validar_planilha_cadastral(
            bytes(conteudo),
            arquivo.filename or "",
            db,
            digest.hexdigest(),
        )
    except Exception as exc:
        logger.exception("Falha interna na pré-validação cadastral.")
        raise HTTPException(
            status_code=500,
            detail="Não foi possível pré-validar a planilha cadastral.",
        ) from exc
