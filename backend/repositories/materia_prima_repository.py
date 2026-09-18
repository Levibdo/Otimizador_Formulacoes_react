from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from models import (
    ComposicaoMateriaPrima,
    MateriaPrima,
    Nutriente,
    PrecoMateriaPrima,
)
from schemas import MateriaPrimaCreate, PrecoCreate


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
            nutriente = self.db.scalar(
                select(Nutriente).where(Nutriente.codigo == item.nutriente_codigo)
            )
            if nutriente is None:
                nutriente = Nutriente(
                    codigo=item.nutriente_codigo,
                    nome=item.nutriente_nome,
                    unidade=item.unidade,
                )
            elif (
                nutriente.nome != item.nutriente_nome
                or nutriente.unidade != item.unidade
            ):
                raise ConflitoDeDadosError(
                    f"O nutriente {item.nutriente_codigo} já possui nome ou unidade diferente."
                )

            materia_prima.composicao.append(
                ComposicaoMateriaPrima(nutriente=nutriente, valor=item.valor)
            )

        materia_prima.precos.append(PrecoMateriaPrima(**dados.preco_inicial.model_dump()))
        self.db.add(materia_prima)
        self.db.flush()
        return self.obter(materia_prima.id)

    def adicionar_preco(
        self, materia_prima_id: int, dados: PrecoCreate
    ) -> MateriaPrima:
        materia_prima = self.obter(materia_prima_id)
        materia_prima.precos.append(PrecoMateriaPrima(**dados.model_dump()))
        self.db.flush()
        return self.obter(materia_prima_id)

    def desativar(self, materia_prima_id: int) -> MateriaPrima:
        materia_prima = self.obter(materia_prima_id)
        materia_prima.ativa = False
        self.db.flush()
        return materia_prima

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
