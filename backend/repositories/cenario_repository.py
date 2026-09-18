from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import ApresentacaoProduto, CenarioCusto, Projeto, VersaoFormula
from schemas import CenarioCustoCreate


class CenarioConflitoError(ValueError):
    pass


class CenarioNaoEncontradoError(ValueError):
    pass


def decimal_json(valor) -> Decimal:
    return Decimal(str(valor))


class CenarioRepository:
    def __init__(self, db: Session):
        self.db = db

    def listar(self, projeto_id: int | None = None) -> list[CenarioCusto]:
        query = select(CenarioCusto)
        if projeto_id is not None:
            query = query.where(CenarioCusto.projeto_id == projeto_id)
        return list(self.db.scalars(query.order_by(CenarioCusto.criado_em.desc())).all())

    def obter(self, cenario_id: int) -> CenarioCusto:
        cenario = self.db.get(CenarioCusto, cenario_id)
        if cenario is None:
            raise CenarioNaoEncontradoError("Cenário não encontrado.")
        return cenario

    def criar(self, dados: CenarioCustoCreate) -> CenarioCusto:
        projeto = self.db.get(Projeto, dados.projeto_id)
        versao = self.db.get(VersaoFormula, dados.versao_formula_id)
        if projeto is None:
            raise CenarioNaoEncontradoError("Projeto não encontrado.")
        if versao is None:
            raise CenarioNaoEncontradoError("Versão de fórmula não encontrada.")
        if versao.projeto_id != projeto.id:
            raise CenarioConflitoError(
                "A versão de fórmula não pertence ao projeto informado."
            )
        if versao.custo_total is None:
            raise CenarioConflitoError(
                "A versão de fórmula não possui custo-base calculado."
            )

        inclusoes = versao.inclusoes
        desconhecidas = set(dados.precos_cenario) - set(inclusoes)
        if desconhecidas:
            raise CenarioConflitoError(
                f"Matéria-prima não pertence à fórmula: {sorted(desconhecidas)[0]}."
            )

        detalhes = []
        custo_cenario = Decimal("0")
        for materia_prima, inclusao_raw in inclusoes.items():
            dados_matriz = versao.matriz_snapshot.get(materia_prima, {})
            if "Custo" not in dados_matriz:
                raise CenarioConflitoError(
                    f"A matriz da versão não possui custo para {materia_prima}."
                )
            inclusao = decimal_json(inclusao_raw)
            preco_base = decimal_json(dados_matriz["Custo"])
            preco_cenario = dados.precos_cenario.get(materia_prima, preco_base)
            contribuicao_base = preco_base * inclusao / Decimal("100")
            contribuicao_cenario = preco_cenario * inclusao / Decimal("100")
            custo_cenario += contribuicao_cenario
            detalhes.append(
                {
                    "materia_prima": materia_prima,
                    "inclusao_percentual": str(inclusao),
                    "preco_base_kg": str(preco_base),
                    "preco_cenario_kg": str(preco_cenario),
                    "contribuicao_base": str(contribuicao_base),
                    "contribuicao_cenario": str(contribuicao_cenario),
                }
            )

        custo_base = versao.custo_total
        variacao = custo_cenario - custo_base
        percentual = (
            variacao * Decimal("100") / custo_base
            if custo_base != 0
            else Decimal("0")
        )
        impacto_apresentacoes = []
        apresentacoes = self.db.scalars(
            select(ApresentacaoProduto).where(
                ApresentacaoProduto.versao_formula_id == versao.id
            )
        ).all()
        for apresentacao in apresentacoes:
            novo_custo_formula = (
                custo_cenario * apresentacao.peso_liquido_g / Decimal("1000")
            )
            novo_unitario = novo_custo_formula + apresentacao.custo_embalagem
            impacto_apresentacoes.append(
                {
                    "apresentacao_id": apresentacao.id,
                    "codigo": apresentacao.codigo,
                    "nome": apresentacao.nome,
                    "custo_unitario_base": str(apresentacao.custo_unitario),
                    "custo_unitario_cenario": str(novo_unitario),
                    "custo_caixa_base": str(apresentacao.custo_caixa),
                    "custo_caixa_cenario": str(
                        novo_unitario * apresentacao.unidades_por_caixa
                    ),
                }
            )

        cenario = CenarioCusto(
            projeto_id=projeto.id,
            versao_formula_id=versao.id,
            nome=dados.nome,
            observacao=dados.observacao,
            precos_cenario={
                nome: str(preco) for nome, preco in dados.precos_cenario.items()
            },
            detalhes_materias_primas=detalhes,
            impacto_apresentacoes=impacto_apresentacoes,
            custo_base_kg=custo_base,
            custo_cenario_kg=custo_cenario,
            variacao_absoluta=variacao,
            variacao_percentual=percentual,
        )
        self.db.add(cenario)
        self.db.flush()
        return cenario
