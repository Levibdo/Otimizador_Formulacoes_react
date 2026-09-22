from fastapi import APIRouter, Response

from services.planilha_cadastral import gerar_template_cadastral


router = APIRouter(prefix="/api/v1/importacoes-cadastrais", tags=["Importação cadastral"])


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
