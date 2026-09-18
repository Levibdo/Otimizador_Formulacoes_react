from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from db.base import Base
from models import (
    ComposicaoMateriaPrima,
    MateriaPrima,
    Nutriente,
    PrecoMateriaPrima,
)


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def test_persiste_mp_com_composicao_e_historico_de_preco(session):
    proteina = Nutriente(codigo="PROT", nome="Proteína", unidade="g/100 g")
    soja = MateriaPrima(codigo="MP0001", nome="Proteína isolada de soja")
    soja.composicao.append(
        ComposicaoMateriaPrima(nutriente=proteina, valor=Decimal("88.2"))
    )
    soja.precos.append(
        PrecoMateriaPrima(
            preco_kg=Decimal("25.50"),
            vigencia_inicio=date(2026, 9, 18),
        )
    )

    session.add(soja)
    session.commit()

    assert soja.id is not None
    assert soja.composicao[0].nutriente.codigo == "PROT"
    assert soja.precos[0].preco_kg == Decimal("25.500000")


def test_impede_composicao_duplicada_para_mesma_mp_e_nutriente(session):
    proteina = Nutriente(codigo="PROT", nome="Proteína", unidade="g/100 g")
    soja = MateriaPrima(codigo="MP0001", nome="Proteína isolada de soja")
    soja.composicao.extend(
        [
            ComposicaoMateriaPrima(nutriente=proteina, valor=Decimal("88.2")),
            ComposicaoMateriaPrima(nutriente=proteina, valor=Decimal("87.5")),
        ]
    )
    session.add(soja)

    with pytest.raises(IntegrityError):
        session.commit()


@pytest.mark.parametrize(
    "preco, inicio, fim",
    [
        (Decimal("-1"), date(2026, 9, 18), None),
        (Decimal("10"), date(2026, 9, 18), date(2026, 9, 17)),
    ],
)
def test_impede_preco_negativo_ou_periodo_invalido(session, preco, inicio, fim):
    mp = MateriaPrima(codigo="MP0001", nome="Matéria-prima")
    mp.precos.append(
        PrecoMateriaPrima(
            preco_kg=preco,
            vigencia_inicio=inicio,
            vigencia_fim=fim,
        )
    )
    session.add(mp)

    with pytest.raises(IntegrityError):
        session.commit()
