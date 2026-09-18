from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from models import Projeto, VersaoFormula
from schemas import ProjetoCreate, ProjetoUpdate, VersaoFormulaCreate


class ProjetoConflitoError(ValueError):
    pass


class ProjetoNaoEncontradoError(ValueError):
    pass


class ProjetoRepository:
    def __init__(self, db: Session):
        self.db = db

    def listar(self) -> list[Projeto]:
        query = (
            select(Projeto)
            .options(selectinload(Projeto.versoes))
            .order_by(Projeto.atualizado_em.desc())
        )
        return list(self.db.scalars(query).all())

    def obter(self, projeto_id: int, bloquear: bool = False) -> Projeto:
        query = select(Projeto).where(Projeto.id == projeto_id)
        if bloquear:
            query = query.with_for_update()
        query = query.options(selectinload(Projeto.versoes))
        projeto = self.db.scalar(query)
        if projeto is None:
            raise ProjetoNaoEncontradoError("Projeto não encontrado.")
        return projeto

    def criar(self, dados: ProjetoCreate) -> Projeto:
        if self.db.scalar(select(Projeto).where(Projeto.codigo == dados.codigo)):
            raise ProjetoConflitoError("Já existe projeto com o mesmo código.")
        projeto = Projeto(
            codigo=dados.codigo,
            nome=dados.nome,
            descricao=dados.descricao,
            requisitos=[item.model_dump(mode="json") for item in dados.requisitos],
        )
        self.db.add(projeto)
        self.db.flush()
        return self.obter(projeto.id)

    def atualizar(self, projeto_id: int, dados: ProjetoUpdate) -> Projeto:
        projeto = self.obter(projeto_id)
        if dados.nome is not None:
            projeto.nome = dados.nome
        if "descricao" in dados.model_fields_set:
            projeto.descricao = dados.descricao
        if dados.status is not None:
            projeto.status = dados.status
        if dados.requisitos is not None:
            projeto.requisitos = [
                item.model_dump(mode="json") for item in dados.requisitos
            ]
        self.db.flush()
        return self.obter(projeto_id)

    def criar_versao(
        self,
        projeto_id: int,
        dados: VersaoFormulaCreate,
    ) -> VersaoFormula:
        projeto = self.obter(projeto_id, bloquear=True)
        maior_numero = self.db.scalar(
            select(func.max(VersaoFormula.numero)).where(
                VersaoFormula.projeto_id == projeto_id
            )
        )
        versao = VersaoFormula(
            projeto_id=projeto_id,
            numero=(maior_numero or 0) + 1,
            observacao=dados.observacao,
            status_solver=dados.status_solver,
            custo_total=dados.custo_total,
            inclusoes=dados.inclusoes,
            custos_individuais=dados.custos_individuais,
            composicao_nutricional=dados.composicao_nutricional,
            parametros=dados.parametros,
            matriz_snapshot=dados.matriz_snapshot,
            requisitos_snapshot=list(projeto.requisitos),
        )
        self.db.add(versao)
        self.db.flush()
        return versao
