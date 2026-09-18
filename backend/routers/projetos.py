from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.session import get_db
from repositories.projeto_repository import (
    ProjetoConflitoError,
    ProjetoNaoEncontradoError,
    ProjetoRepository,
)
from schemas import (
    ProjetoCreate,
    ProjetoRead,
    ProjetoUpdate,
    VersaoFormulaCreate,
    VersaoFormulaRead,
)


router = APIRouter(prefix="/api/v1/projetos", tags=["Projetos"])


def executar_escrita(db, operacao):
    try:
        resultado = operacao()
        db.commit()
        return resultado
    except ProjetoConflitoError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProjetoNaoEncontradoError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A operação viola uma regra de integridade dos projetos.",
        ) from exc


@router.post("", response_model=ProjetoRead, status_code=status.HTTP_201_CREATED)
def criar_projeto(dados: ProjetoCreate, db: Session = Depends(get_db)):
    projeto = executar_escrita(db, lambda: ProjetoRepository(db).criar(dados))
    return projeto


@router.get("", response_model=list[ProjetoRead])
def listar_projetos(db: Session = Depends(get_db)):
    return ProjetoRepository(db).listar()


@router.get("/{projeto_id}", response_model=ProjetoRead)
def obter_projeto(projeto_id: int, db: Session = Depends(get_db)):
    try:
        return ProjetoRepository(db).obter(projeto_id)
    except ProjetoNaoEncontradoError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{projeto_id}", response_model=ProjetoRead)
def atualizar_projeto(
    projeto_id: int,
    dados: ProjetoUpdate,
    db: Session = Depends(get_db),
):
    return executar_escrita(
        db,
        lambda: ProjetoRepository(db).atualizar(projeto_id, dados),
    )


@router.post(
    "/{projeto_id}/versoes",
    response_model=VersaoFormulaRead,
    status_code=status.HTTP_201_CREATED,
)
def criar_versao_formula(
    projeto_id: int,
    dados: VersaoFormulaCreate,
    db: Session = Depends(get_db),
):
    return executar_escrita(
        db,
        lambda: ProjetoRepository(db).criar_versao(projeto_id, dados),
    )


@router.get("/{projeto_id}/versoes", response_model=list[VersaoFormulaRead])
def listar_versoes(projeto_id: int, db: Session = Depends(get_db)):
    try:
        return ProjetoRepository(db).obter(projeto_id).versoes
    except ProjetoNaoEncontradoError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
