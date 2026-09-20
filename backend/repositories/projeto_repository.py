from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from models import ExecucaoOtimizacao, Projeto, VersaoFormula, CategoriaProduto
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
        self.validar_categoria(dados.categoria_produto_id)
        if self.db.scalar(select(Projeto).where(Projeto.codigo == dados.codigo)):
            raise ProjetoConflitoError("Já existe projeto com o mesmo código.")
        projeto = Projeto(
            codigo=dados.codigo,
            nome=dados.nome,
            descricao=dados.descricao,
            categoria_produto_id=dados.categoria_produto_id,
            requisitos=[item.model_dump(mode="json") for item in dados.requisitos],
        )
        self.db.add(projeto)
        self.db.flush()
        return self.obter(projeto.id)

    def atualizar(self, projeto_id: int, dados: ProjetoUpdate) -> Projeto:
        projeto = self.obter(projeto_id)
        if "categoria_produto_id" in dados.model_fields_set:
            if dados.categoria_produto_id != projeto.categoria_produto_id:
                self.validar_categoria(dados.categoria_produto_id)
            projeto.categoria_produto_id = dados.categoria_produto_id
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

    def validar_categoria(self, categoria_id):
        if categoria_id is None:
            return
        categoria = self.db.scalar(select(CategoriaProduto).where(
            CategoriaProduto.id == categoria_id
        ).with_for_update())
        if categoria is None:
            raise ProjetoNaoEncontradoError("Categoria de produto não encontrada.")
        if not categoria.ativa:
            raise ProjetoConflitoError("Categoria de produto inativa.")

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
        if dados.execucao_id is not None:
            execucao = self.db.get(ExecucaoOtimizacao, dados.execucao_id)
            if execucao is None:
                raise ProjetoNaoEncontradoError("Execução de otimização não encontrada.")
            if execucao.projeto_id != projeto_id:
                raise ProjetoConflitoError("A execução não pertence ao projeto informado.")
            resultado = execucao.resultado_diagnostico.get("resultado", {})
            if execucao.status not in ("ATENDE", "ATENDE_COM_ALERTAS", "SEM_AVALIACAO_REGULATORIA") or resultado.get("status") != "Optimal":
                raise ProjetoConflitoError("Somente uma execução concluída com solução ótima pode gerar versão.")
            contexto = execucao.entradas_contexto
            status_solver = resultado["status"]
            custo_total = resultado.get("custo_total")
            inclusoes = resultado.get("inclusoes", {})
            custos_individuais = resultado.get("custos_individuais", {})
            composicao_nutricional = resultado.get("conferencia_nutricional", {})
            parametros = {
                "execucao_id": execucao.id,
                "versao_motor": execucao.versao_motor,
                "status_regulatorio": execucao.status,
                "regras_regulatorias": execucao.regras_regulatorias_usadas,
                "limites_efetivos": execucao.limites_efetivos,
                "alertas": execucao.alertas,
                "pendencias": execucao.pendencias,
                "componentes_regulatorios": resultado.get("componentes_regulatorios", {}),
            }
            matriz_snapshot = {mp["nome"]: mp["composicao"] for mp in contexto["materias_primas"]}
            requisitos_snapshot = execucao.requisitos_usados
        else:
            status_solver = dados.status_solver
            custo_total = dados.custo_total
            inclusoes = dados.inclusoes
            custos_individuais = dados.custos_individuais
            composicao_nutricional = dados.composicao_nutricional
            parametros = dados.parametros
            matriz_snapshot = dados.matriz_snapshot
            requisitos_snapshot = list(projeto.requisitos)
        versao = VersaoFormula(
            projeto_id=projeto_id,
            numero=(maior_numero or 0) + 1,
            observacao=dados.observacao,
            status_solver=status_solver,
            custo_total=custo_total,
            inclusoes=inclusoes,
            custos_individuais=custos_individuais,
            composicao_nutricional=composicao_nutricional,
            parametros=parametros,
            matriz_snapshot=matriz_snapshot,
            requisitos_snapshot=requisitos_snapshot,
        )
        self.db.add(versao)
        self.db.flush()
        return versao
