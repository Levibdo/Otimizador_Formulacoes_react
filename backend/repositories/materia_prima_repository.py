from datetime import date, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from models import (
    ComposicaoMateriaPrima,
    MateriaPrima,
    Nutriente,
    PrecoMateriaPrima,
)
from schemas import ComposicaoCreate, MateriaPrimaCreate, MateriaPrimaUpdate, PrecoCreate


class ConflitoDeDadosError(ValueError):
    pass


class MateriaPrimaNaoEncontradaError(ValueError):
    pass


class MateriaPrimaRepository:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _opcoes_relacionamentos():
        return (
            selectinload(MateriaPrima.composicao).selectinload(
                ComposicaoMateriaPrima.nutriente
            ),
            selectinload(MateriaPrima.precos),
        )

    def listar(self) -> list[MateriaPrima]:
        query = (
            select(MateriaPrima)
            .options(*self._opcoes_relacionamentos())
            .order_by(MateriaPrima.nome)
        )
        return list(self.db.scalars(query).all())

    def obter(self, materia_prima_id: int) -> MateriaPrima:
        query = (
            select(MateriaPrima)
            .where(MateriaPrima.id == materia_prima_id)
            .options(*self._opcoes_relacionamentos())
        )
        materia_prima = self.db.scalar(query)
        if materia_prima is None:
            raise MateriaPrimaNaoEncontradaError("Matéria-prima não encontrada.")
        return materia_prima

    def _obter_ou_criar_nutriente(
        self,
        item: ComposicaoCreate,
        permitir_atualizar_unidade: bool = False,
    ) -> Nutriente:
        nutriente = self.db.scalar(
            select(Nutriente).where(Nutriente.codigo == item.nutriente_codigo)
        )
        if nutriente is None:
            return Nutriente(
                codigo=item.nutriente_codigo,
                nome=item.nutriente_nome,
                unidade=item.unidade,
            )
        if nutriente.nome != item.nutriente_nome:
            raise ConflitoDeDadosError(
                f"O nutriente {item.nutriente_codigo} já possui outro nome."
            )
        if nutriente.unidade != item.unidade:
            if permitir_atualizar_unidade:
                nutriente.unidade = item.unidade
            else:
                raise ConflitoDeDadosError(
                    f"O nutriente {item.nutriente_codigo} já possui outra unidade."
                )
        return nutriente

    def criar(self, dados: MateriaPrimaCreate) -> MateriaPrima:
        existente = self.db.scalar(
            select(MateriaPrima).where(
                or_(
                    MateriaPrima.codigo == dados.codigo,
                    MateriaPrima.nome == dados.nome,
                )
            )
        )
        if existente:
            raise ConflitoDeDadosError(
                "Já existe matéria-prima com o mesmo código ou nome."
            )

        materia_prima = MateriaPrima(codigo=dados.codigo, nome=dados.nome)

        for item in dados.composicao:
            nutriente = self._obter_ou_criar_nutriente(item)

            materia_prima.composicao.append(
                ComposicaoMateriaPrima(nutriente=nutriente, valor=item.valor)
            )

        materia_prima.precos.append(PrecoMateriaPrima(**dados.preco_inicial.model_dump()))
        self.db.add(materia_prima)
        self.db.flush()
        return self.obter(materia_prima.id)

    def importar_lote(self, itens: list[MateriaPrimaCreate]) -> list[MateriaPrima]:
        importadas = []
        for item in itens:
            importadas.append(self.criar(item))
        return importadas

    def atualizar(
        self,
        materia_prima_id: int,
        dados: MateriaPrimaUpdate,
    ) -> MateriaPrima:
        materia_prima = self.obter(materia_prima_id)
        novo_codigo = dados.codigo if dados.codigo is not None else materia_prima.codigo
        novo_nome = dados.nome if dados.nome is not None else materia_prima.nome
        conflito = self.db.scalar(
            select(MateriaPrima).where(
                MateriaPrima.id != materia_prima_id,
                or_(
                    MateriaPrima.codigo == novo_codigo,
                    MateriaPrima.nome == novo_nome,
                ),
            )
        )
        if conflito:
            raise ConflitoDeDadosError(
                "Já existe matéria-prima com o mesmo código ou nome."
            )

        materia_prima.codigo = novo_codigo
        materia_prima.nome = novo_nome
        if dados.ativa is not None:
            materia_prima.ativa = dados.ativa

        if dados.composicao is not None:
            materia_prima.composicao.clear()
            self.db.flush()
            for item in dados.composicao:
                nutriente = self._obter_ou_criar_nutriente(
                    item,
                    permitir_atualizar_unidade=True,
                )
                materia_prima.composicao.append(
                    ComposicaoMateriaPrima(nutriente=nutriente, valor=item.valor)
                )

        self.db.flush()
        return self.obter(materia_prima_id)

    def adicionar_preco(
        self, materia_prima_id: int, dados: PrecoCreate
    ) -> MateriaPrima:
        materia_prima = self.obter(materia_prima_id)
        anteriores_abertos = [
            preco
            for preco in materia_prima.precos
            if preco.vigencia_inicio < dados.vigencia_inicio
            and preco.vigencia_fim is None
        ]
        if anteriores_abertos:
            anterior = max(anteriores_abertos, key=lambda preco: preco.vigencia_inicio)
            anterior.vigencia_fim = dados.vigencia_inicio - timedelta(days=1)

        for preco in materia_prima.precos:
            fim_existente = preco.vigencia_fim or date.max
            fim_novo = dados.vigencia_fim or date.max
            if preco.vigencia_inicio <= fim_novo and dados.vigencia_inicio <= fim_existente:
                raise ConflitoDeDadosError(
                    "A vigência do novo preço se sobrepõe a um preço existente."
                )

        materia_prima.precos.append(PrecoMateriaPrima(**dados.model_dump()))
        self.db.flush()
        return self.obter(materia_prima_id)

    def desativar(self, materia_prima_id: int) -> MateriaPrima:
        return self.atualizar(
            materia_prima_id,
            MateriaPrimaUpdate(ativa=False),
        )

    def construir_matriz(self, data_referencia: date) -> dict:
        materias_primas = [mp for mp in self.listar() if mp.ativa]
        matriz = {}
        nutrientes = set()

        for materia_prima in materias_primas:
            precos_vigentes = [
                preco
                for preco in materia_prima.precos
                if preco.vigencia_inicio <= data_referencia
                and (preco.vigencia_fim is None or preco.vigencia_fim >= data_referencia)
            ]
            if not precos_vigentes:
                continue

            preco_vigente = max(
                precos_vigentes,
                key=lambda preco: (preco.vigencia_inicio, preco.id),
            )
            dados_mp = {"Custo": float(preco_vigente.preco_kg)}

            for composicao in materia_prima.composicao:
                nome_nutriente = composicao.nutriente.nome
                nutrientes.add(nome_nutriente)
                dados_mp[nome_nutriente] = float(composicao.valor)

            matriz[materia_prima.nome] = dados_mp

        return {
            "data_referencia": data_referencia,
            "materias_primas": list(matriz),
            "nutrientes": sorted(nutrientes),
            "matriz": matriz,
        }
