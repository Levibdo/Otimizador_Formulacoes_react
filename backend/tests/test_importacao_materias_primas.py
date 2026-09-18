from datetime import date
import io

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from db.base import Base
from db.session import get_db
from routers.materias_primas import router
from services.importacao_materias_primas import (
    PlanilhaImportacaoError,
    parsear_planilha,
)


def gerar_xlsx(dataframe: pd.DataFrame, header=False) -> bytes:
    arquivo = io.BytesIO()
    with pd.ExcelWriter(arquivo, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, header=header)
    return arquivo.getvalue()


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    session.close()


def test_parseia_planilha_transposta_e_preserva_unidade_explicita():
    planilha = pd.DataFrame(
        [
            [None, "MP A", "MP B"],
            ["Custo", 10, 20],
            ["Valor energético (kcal)", 100, 200],
            ["Proteínas", 5, 30],
            ["Ác. Oléico, g/100g", 1.2, 2.4],
        ]
    )

    itens = parsear_planilha(
        gerar_xlsx(planilha),
        "materias.xlsx",
        date(2026, 9, 18),
    )

    assert [item.nome for item in itens] == ["MP A", "MP B"]
    assert itens[0].preco_inicial.preco_kg == 10
    assert [item.unidade for item in itens[0].composicao] == [
        "kcal/100 g",
        "não informada",
        "g/100 g",
    ]


def test_importa_planilha_vertical_diretamente_no_banco(client):
    planilha = pd.DataFrame(
        [
            {
                "Código": "MP001",
                "Nome": "Maltodextrina",
                "Custo": 8.5,
                "Carboidratos, g/100g": 96.0,
            },
            {
                "Código": "MP002",
                "Nome": "Proteína de soja",
                "Custo": 25.0,
                "Carboidratos, g/100g": 3.0,
            },
        ]
    )

    resposta = client.post(
        "/api/v1/materias-primas/importar",
        files={
            "arquivo": (
                "materias.xlsx",
                gerar_xlsx(planilha, header=True),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={"vigencia_inicio": "2026-09-18"},
    )

    assert resposta.status_code == 201
    assert resposta.json() == {
        "materias_primas_importadas": 2,
        "nutrientes_por_mp": 1,
        "unidades_nao_informadas": 0,
    }
    matriz = client.get(
        "/api/v1/materias-primas/matriz?data_referencia=2026-09-18"
    ).json()["matriz"]
    assert matriz["Maltodextrina"] == {"Custo": 8.5, "Carboidratos": 96.0}


def test_rollback_integral_quando_lote_conflita_com_dado_existente(client):
    existente = {
        "codigo": "MP_EXISTENTE",
        "nome": "MP existente",
        "composicao": [],
        "preco_inicial": {"preco_kg": 10, "vigencia_inicio": "2026-01-01"},
    }
    assert client.post("/api/v1/materias-primas", json=existente).status_code == 201

    planilha = pd.DataFrame(
        [
            {"Código": "MP_NOVA", "Nome": "MP nova", "Custo": 11},
            {"Código": "MP_EXISTENTE", "Nome": "Outro nome", "Custo": 12},
        ]
    )
    resposta = client.post(
        "/api/v1/materias-primas/importar",
        files={"arquivo": ("lote.xlsx", gerar_xlsx(planilha, header=True))},
        data={"vigencia_inicio": "2026-09-18"},
    )

    assert resposta.status_code == 409
    listagem = client.get("/api/v1/materias-primas").json()
    assert [(item["codigo"], item["nome"]) for item in listagem] == [
        ("MP_EXISTENTE", "MP existente")
    ]


def test_rejeita_planilha_com_valor_nao_numerico():
    planilha = pd.DataFrame(
        [
            [None, "MP A"],
            ["Custo", 10],
            ["Proteínas", "não informado"],
        ]
    )

    with pytest.raises(PlanilhaImportacaoError, match="Valor numérico inválido"):
        parsear_planilha(
            gerar_xlsx(planilha),
            "materias.xlsx",
            date(2026, 9, 18),
        )
