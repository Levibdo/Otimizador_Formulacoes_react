from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.session import get_db
from models import MateriaPrima
from models.regulatorio import CategoriaProduto, ComponenteRegulatorio, ComposicaoComponenteMP, RegraRegulatoria
from schemas.regulatorio import (
    CategoriaCreate, CategoriaUpdate, CategoriaRead, ComponenteCreate, ComponenteUpdate,
    ComponenteRead, ComposicaoCreate, ComposicaoRead, AtivacaoComposicao,
    RegraCreate, RegraRead, AtivacaoRegra,
)
from services.regulatorio_service import RegulatorioService, CadastroNaoEncontrado, ConflitoRegulatorio

router = APIRouter(prefix='/api/v1', tags=['Cadastro regulatório'])


def executar(db, operacao, escrita=False):
    try:
        resultado = operacao(RegulatorioService(db))
        if escrita:
            db.commit()
        return resultado
    except CadastroNaoEncontrado as exc:
        db.rollback()
        raise HTTPException(404, str(exc)) from exc
    except ConflitoRegulatorio as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'Conflito de integridade: duplicidade, referência inválida ou regra ativa com vigência sobreposta.') from exc


@router.get('/categorias-produto', response_model=list[CategoriaRead])
def listar_categorias(ativa: bool | None = None, db: Session = Depends(get_db)):
    return executar(db, lambda s: s.repo.listar(CategoriaProduto, ativa=ativa))


@router.post('/categorias-produto', response_model=CategoriaRead, status_code=201)
def criar_categoria(dados: CategoriaCreate, db: Session = Depends(get_db)):
    return executar(db, lambda s: s.criar_catalogo(CategoriaProduto, dados), True)


@router.get('/categorias-produto/{identificador}', response_model=CategoriaRead)
def obter_categoria(identificador: int, db: Session = Depends(get_db)):
    return executar(db, lambda s: s.obter(CategoriaProduto, identificador))


@router.patch('/categorias-produto/{identificador}', response_model=CategoriaRead)
def atualizar_categoria(identificador: int, dados: CategoriaUpdate, db: Session = Depends(get_db)):
    return executar(db, lambda s: s.atualizar_catalogo(CategoriaProduto, identificador, dados), True)


@router.get('/categorias-produto/{identificador}/diagnostico-cadastral')
def diagnostico(identificador: int, data_referencia: date | None = None, db: Session = Depends(get_db)):
    return executar(db, lambda s: s.diagnostico(identificador, data_referencia or date.today()))


@router.get('/componentes-regulatorios', response_model=list[ComponenteRead])
def listar_componentes(ativo: bool | None = None, db: Session = Depends(get_db)):
    return executar(db, lambda s: s.repo.listar(ComponenteRegulatorio, ativo=ativo))


@router.post('/componentes-regulatorios', response_model=ComponenteRead, status_code=201)
def criar_componente(dados: ComponenteCreate, db: Session = Depends(get_db)):
    return executar(db, lambda s: s.criar_catalogo(ComponenteRegulatorio, dados), True)


@router.get('/componentes-regulatorios/{identificador}', response_model=ComponenteRead)
def obter_componente(identificador: int, db: Session = Depends(get_db)):
    return executar(db, lambda s: s.obter(ComponenteRegulatorio, identificador))


@router.patch('/componentes-regulatorios/{identificador}', response_model=ComponenteRead)
def atualizar_componente(identificador: int, dados: ComponenteUpdate, db: Session = Depends(get_db)):
    return executar(db, lambda s: s.atualizar_catalogo(ComponenteRegulatorio, identificador, dados), True)


@router.get('/materias-primas/{mp_id}/componentes-regulatorios', response_model=list[ComposicaoRead])
def listar_composicoes(mp_id: int, db: Session = Depends(get_db)):
    def operacao(s):
        s.obter(MateriaPrima, mp_id)
        return s.repo.listar(ComposicaoComponenteMP, materia_prima_id=mp_id)
    return executar(db, operacao)


@router.post('/materias-primas/{mp_id}/componentes-regulatorios', response_model=ComposicaoRead, status_code=201)
def criar_composicao(mp_id: int, dados: ComposicaoCreate, db: Session = Depends(get_db)):
    return executar(db, lambda s: s.criar_composicao(mp_id, dados), True)


@router.get('/composicoes-componentes-mp/{identificador}', response_model=ComposicaoRead)
def obter_composicao(identificador: int, db: Session = Depends(get_db)):
    return executar(db, lambda s: s.obter(ComposicaoComponenteMP, identificador))


@router.patch('/composicoes-componentes-mp/{identificador}', response_model=ComposicaoRead)
def ativar_composicao(identificador: int, dados: AtivacaoComposicao, db: Session = Depends(get_db)):
    return executar(db, lambda s: s.ativar_composicao(identificador, dados), True)


@router.get('/regras-regulatorias', response_model=list[RegraRead])
def listar_regras(categoria_id: int | None = Query(None, gt=0), ativa: bool | None = None,
                  db: Session = Depends(get_db)):
    return executar(db, lambda s: s.repo.listar(RegraRegulatoria, categoria_id=categoria_id, ativa=ativa))


@router.post('/regras-regulatorias', response_model=RegraRead, status_code=201)
def criar_regra(dados: RegraCreate, db: Session = Depends(get_db)):
    return executar(db, lambda s: s.criar_regra(dados), True)


@router.get('/regras-regulatorias/{identificador}', response_model=RegraRead)
def obter_regra(identificador: int, db: Session = Depends(get_db)):
    return executar(db, lambda s: s.obter(RegraRegulatoria, identificador))


@router.patch('/regras-regulatorias/{identificador}', response_model=RegraRead)
def ativar_regra(identificador: int, dados: AtivacaoRegra, db: Session = Depends(get_db)):
    return executar(db, lambda s: s.ativar_regra(identificador, dados), True)


@router.post('/regras-regulatorias/{identificador}/revisoes', response_model=RegraRead, status_code=201)
def revisar_regra(identificador: int, dados: RegraCreate, db: Session = Depends(get_db)):
    return executar(db, lambda s: s.revisar_regra(identificador, dados), True)
