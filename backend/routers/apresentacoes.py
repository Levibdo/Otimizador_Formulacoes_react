from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.session import get_db
from repositories.apresentacao_repository import (
    ApresentacaoConflitoError,
    ApresentacaoNaoEncontradaError,
    ApresentacaoRepository,
)
from schemas import (
    ApresentacaoCreate,
    ApresentacaoRead,
    ItemEmbalagemCreate,
    ItemEmbalagemRead,
    ItemEmbalagemUpdate,
)


router = APIRouter(prefix="/api/v1", tags=["Embalagens e apresentações"])


def executar_escrita(db, operacao):
    try:
        resultado = operacao()
        db.commit()
        return resultado
    except ApresentacaoConflitoError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ApresentacaoNaoEncontradaError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A operação viola uma regra de integridade.",
        ) from exc


@router.post(
    "/itens-embalagem",
    response_model=ItemEmbalagemRead,
    status_code=status.HTTP_201_CREATED,
)
def criar_item(dados: ItemEmbalagemCreate, db: Session = Depends(get_db)):
    return executar_escrita(db, lambda: ApresentacaoRepository(db).criar_item(dados))


@router.get("/itens-embalagem", response_model=list[ItemEmbalagemRead])
def listar_itens(db: Session = Depends(get_db)):
    return ApresentacaoRepository(db).listar_itens()


@router.patch("/itens-embalagem/{item_id}", response_model=ItemEmbalagemRead)
def atualizar_item(
    item_id: int,
    dados: ItemEmbalagemUpdate,
    db: Session = Depends(get_db),
):
    return executar_escrita(
        db, lambda: ApresentacaoRepository(db).atualizar_item(item_id, dados)
    )


@router.post(
    "/apresentacoes",
    response_model=ApresentacaoRead,
    status_code=status.HTTP_201_CREATED,
)
def criar_apresentacao(dados: ApresentacaoCreate, db: Session = Depends(get_db)):
    return executar_escrita(
        db, lambda: ApresentacaoRepository(db).criar_apresentacao(dados)
    )


@router.get("/apresentacoes", response_model=list[ApresentacaoRead])
def listar_apresentacoes(db: Session = Depends(get_db)):
    return ApresentacaoRepository(db).listar_apresentacoes()


@router.get("/apresentacoes/{apresentacao_id}", response_model=ApresentacaoRead)
def obter_apresentacao(apresentacao_id: int, db: Session = Depends(get_db)):
    try:
        return ApresentacaoRepository(db).obter_apresentacao(apresentacao_id)
    except ApresentacaoNaoEncontradaError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
