from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from models import (
    ApresentacaoProduto,
    ComponenteApresentacao,
    ItemEmbalagem,
    Projeto,
    VersaoFormula,
)
from schemas import ApresentacaoCreate, ItemEmbalagemCreate, ItemEmbalagemUpdate


class ApresentacaoConflitoError(ValueError):
    pass


class ApresentacaoNaoEncontradaError(ValueError):
    pass


class ApresentacaoRepository:
    def __init__(self, db: Session):
        self.db = db

    def listar_itens(self) -> list[ItemEmbalagem]:
        return list(
            self.db.scalars(select(ItemEmbalagem).order_by(ItemEmbalagem.nome)).all()
        )

    def criar_item(self, dados: ItemEmbalagemCreate) -> ItemEmbalagem:
        existente = self.db.scalar(
            select(ItemEmbalagem).where(
                or_(
                    ItemEmbalagem.codigo == dados.codigo,
                    ItemEmbalagem.nome == dados.nome,
                )
            )
        )
        if existente:
            raise ApresentacaoConflitoError(
                "Já existe item de embalagem com o mesmo código ou nome."
            )
        item = ItemEmbalagem(**dados.model_dump())
        self.db.add(item)
        self.db.flush()
        return item

    def atualizar_item(
        self, item_id: int, dados: ItemEmbalagemUpdate
    ) -> ItemEmbalagem:
        item = self.db.get(ItemEmbalagem, item_id)
        if item is None:
            raise ApresentacaoNaoEncontradaError("Item de embalagem não encontrado.")
        if dados.nome is not None:
            conflito = self.db.scalar(
                select(ItemEmbalagem).where(
                    ItemEmbalagem.id != item_id,
                    ItemEmbalagem.nome == dados.nome,
                )
            )
            if conflito:
                raise ApresentacaoConflitoError(
                    "Já existe item de embalagem com o mesmo nome."
                )
            item.nome = dados.nome
        for campo in ("unidade", "custo_unitario", "ativo"):
            valor = getattr(dados, campo)
            if valor is not None:
                setattr(item, campo, valor)
        self.db.flush()
        return item

    @staticmethod
    def _opcoes_componentes():
        return selectinload(ApresentacaoProduto.componentes)

    def listar_apresentacoes(self) -> list[ApresentacaoProduto]:
        query = (
            select(ApresentacaoProduto)
            .options(self._opcoes_componentes())
            .order_by(ApresentacaoProduto.criado_em.desc())
        )
        return list(self.db.scalars(query).all())

    def obter_apresentacao(self, apresentacao_id: int) -> ApresentacaoProduto:
        apresentacao = self.db.scalar(
            select(ApresentacaoProduto)
            .where(ApresentacaoProduto.id == apresentacao_id)
            .options(self._opcoes_componentes())
        )
        if apresentacao is None:
            raise ApresentacaoNaoEncontradaError("Apresentação não encontrada.")
        return apresentacao

    def criar_apresentacao(self, dados: ApresentacaoCreate) -> ApresentacaoProduto:
        if self.db.scalar(
            select(ApresentacaoProduto).where(
                ApresentacaoProduto.codigo == dados.codigo
            )
        ):
            raise ApresentacaoConflitoError(
                "Já existe apresentação com o mesmo código."
            )

        projeto = self.db.get(Projeto, dados.projeto_id)
        versao = self.db.get(VersaoFormula, dados.versao_formula_id)
        if projeto is None:
            raise ApresentacaoNaoEncontradaError("Projeto não encontrado.")
        if versao is None:
            raise ApresentacaoNaoEncontradaError("Versão de fórmula não encontrada.")
        if versao.projeto_id != projeto.id:
            raise ApresentacaoConflitoError(
                "A versão de fórmula não pertence ao projeto informado."
            )
        if versao.custo_total is None:
            raise ApresentacaoConflitoError(
                "A versão de fórmula não possui custo calculado."
            )

        ids_itens = [componente.item_embalagem_id for componente in dados.componentes]
        itens = {
            item.id: item
            for item in self.db.scalars(
                select(ItemEmbalagem).where(ItemEmbalagem.id.in_(ids_itens))
            ).all()
        }
        ausentes = set(ids_itens) - set(itens)
        if ausentes:
            raise ApresentacaoNaoEncontradaError(
                f"Item de embalagem não encontrado: {min(ausentes)}."
            )
        inativos = [itens[item_id].nome for item_id in ids_itens if not itens[item_id].ativo]
        if inativos:
            raise ApresentacaoConflitoError(
                f"Item de embalagem inativo: {inativos[0]}."
            )

        custo_formula = versao.custo_total * dados.peso_liquido_g / Decimal("1000")
        componentes = []
        custo_embalagem = Decimal("0")
        for componente_dados in dados.componentes:
            item = itens[componente_dados.item_embalagem_id]
            custo_total = item.custo_unitario * componente_dados.quantidade
            custo_embalagem += custo_total
            componentes.append(
                ComponenteApresentacao(
                    item_embalagem_id=item.id,
                    item_codigo_snapshot=item.codigo,
                    item_nome_snapshot=item.nome,
                    unidade_snapshot=item.unidade,
                    quantidade=componente_dados.quantidade,
                    custo_unitario_snapshot=item.custo_unitario,
                    custo_total=custo_total,
                )
            )

        custo_unitario = custo_formula + custo_embalagem
        apresentacao = ApresentacaoProduto(
            projeto_id=projeto.id,
            versao_formula_id=versao.id,
            codigo=dados.codigo,
            nome=dados.nome,
            peso_liquido_g=dados.peso_liquido_g,
            unidades_por_caixa=dados.unidades_por_caixa,
            custo_formula=custo_formula,
            custo_embalagem=custo_embalagem,
            custo_unitario=custo_unitario,
            custo_caixa=custo_unitario * dados.unidades_por_caixa,
            componentes=componentes,
        )
        self.db.add(apresentacao)
        self.db.flush()
        return self.obter_apresentacao(apresentacao.id)
