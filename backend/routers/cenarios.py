from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.session import get_db
from repositories.cenario_repository import (
    CenarioConflitoError,
    CenarioNaoEncontradoError,
    CenarioRepository,
)
from schemas import CenarioCustoCreate, CenarioCustoRead


router = APIRouter(prefix="/api/v1/cenarios", tags=["Cenários de custo"])


@router.post("", response_model=CenarioCustoRead, status_code=status.HTTP_201_CREATED)
def criar_cenario(dados: CenarioCustoCreate, db: Session = Depends(get_db)):
    try:
        cenario = CenarioRepository(db).criar(dados)
        db.commit()
        return cenario
    except CenarioConflitoError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CenarioNaoEncontradoError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Cenário inválido.") from exc


@router.get("", response_model=list[CenarioCustoRead])
def listar_cenarios(
    projeto_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
):
    return CenarioRepository(db).listar(projeto_id)


@router.get("/{cenario_id}", response_model=CenarioCustoRead)
def obter_cenario(cenario_id: int, db: Session = Depends(get_db)):
    try:
        return CenarioRepository(db).obter(cenario_id)
    except CenarioNaoEncontradoError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
