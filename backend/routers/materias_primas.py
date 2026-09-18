from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.session import get_db
from repositories.materia_prima_repository import (
    ConflitoDeDadosError,
    MateriaPrimaNaoEncontradaError,
    MateriaPrimaRepository,
)
from schemas import (
    MateriaPrimaCreate,
    MateriaPrimaRead,
    MatrizOtimizacaoRead,
    PrecoCreate,
)
from services.importacao_materias_primas import PlanilhaImportacaoError, parsear_planilha


router = APIRouter(prefix="/api/v1/materias-primas", tags=["Matérias-primas"])


def serializar_materia_prima(materia_prima):
    return {
        "id": materia_prima.id,
        "codigo": materia_prima.codigo,
        "nome": materia_prima.nome,
        "ativa": materia_prima.ativa,
        "composicao": [
            {
                "nutriente_codigo": item.nutriente.codigo,
                "nutriente_nome": item.nutriente.nome,
                "unidade": item.nutriente.unidade,
                "valor": item.valor,
            }
            for item in materia_prima.composicao
        ],
        "precos": sorted(
            materia_prima.precos,
            key=lambda item: item.vigencia_inicio,
            reverse=True,
        ),
    }


def executar_escrita(db, operacao):
    try:
        resultado = operacao()
        db.commit()
        return resultado
    except ConflitoDeDadosError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except MateriaPrimaNaoEncontradaError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A operação viola uma regra de integridade dos dados.",
        ) from exc


@router.post("", response_model=MateriaPrimaRead, status_code=status.HTTP_201_CREATED)
def criar_materia_prima(dados: MateriaPrimaCreate, db: Session = Depends(get_db)):
    repository = MateriaPrimaRepository(db)
    materia_prima = executar_escrita(db, lambda: repository.criar(dados))
    return serializar_materia_prima(materia_prima)


@router.get("", response_model=list[MateriaPrimaRead])
def listar_materias_primas(db: Session = Depends(get_db)):
    repository = MateriaPrimaRepository(db)
    return [serializar_materia_prima(mp) for mp in repository.listar()]


@router.get("/matriz", response_model=MatrizOtimizacaoRead)
def obter_matriz(
    data_referencia: date | None = None,
    db: Session = Depends(get_db),
):
    referencia = data_referencia or date.today()
    return MateriaPrimaRepository(db).construir_matriz(referencia)


@router.post("/importar", status_code=status.HTTP_201_CREATED)
async def importar_materias_primas(
    arquivo: UploadFile = File(...),
    vigencia_inicio: date = Form(...),
    unidade_padrao: str = Form("não informada"),
    db: Session = Depends(get_db),
):
    try:
        itens = parsear_planilha(
            await arquivo.read(),
            arquivo.filename or "",
            vigencia_inicio,
            unidade_padrao,
        )
    except PlanilhaImportacaoError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    repository = MateriaPrimaRepository(db)
    importadas = executar_escrita(db, lambda: repository.importar_lote(itens))
    unidades_nao_informadas = sum(
        1
        for item in itens
        for composicao in item.composicao
        if composicao.unidade == "não informada"
    )
    return {
        "materias_primas_importadas": len(importadas),
        "nutrientes_por_mp": len(itens[0].composicao) if itens else 0,
        "unidades_nao_informadas": unidades_nao_informadas,
    }


@router.post("/{materia_prima_id}/precos", response_model=MateriaPrimaRead)
def adicionar_preco(
    materia_prima_id: int,
    dados: PrecoCreate,
    db: Session = Depends(get_db),
):
    repository = MateriaPrimaRepository(db)
    materia_prima = executar_escrita(
        db,
        lambda: repository.adicionar_preco(materia_prima_id, dados),
    )
    return serializar_materia_prima(materia_prima)


@router.delete("/{materia_prima_id}", status_code=status.HTTP_204_NO_CONTENT)
def desativar_materia_prima(
    materia_prima_id: int,
    db: Session = Depends(get_db),
):
    repository = MateriaPrimaRepository(db)
    executar_escrita(db, lambda: repository.desativar(materia_prima_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
