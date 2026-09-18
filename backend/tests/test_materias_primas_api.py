from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from db.base import Base
from db.session import get_db
from routers.materias_primas import router


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


def payload_mp(codigo="MP0001", nome="Proteína isolada de soja"):
    return {
        "codigo": codigo,
        "nome": nome,
        "composicao": [
            {
                "nutriente_codigo": "PROT",
                "nutriente_nome": "Proteína",
                "unidade": "g/100 g",
                "valor": 88.2,
            },
            {
                "nutriente_codigo": "LIP",
                "nutriente_nome": "Lipídios",
                "unidade": "g/100 g",
                "valor": 1.4,
            },
        ],
        "preco_inicial": {
            "preco_kg": 25.5,
            "vigencia_inicio": "2026-01-01",
        },
    }


def test_cadastra_lista_e_monta_matriz_por_preco_vigente(client):
    resposta = client.post("/api/v1/materias-primas", json=payload_mp())

    assert resposta.status_code == 201
    materia_prima_id = resposta.json()["id"]
    assert resposta.json()["composicao"][0]["nutriente_codigo"] in {"PROT", "LIP"}

    resposta_preco = client.post(
        f"/api/v1/materias-primas/{materia_prima_id}/precos",
        json={"preco_kg": 27.0, "vigencia_inicio": "2026-07-01"},
    )
    assert resposta_preco.status_code == 200
    precos = resposta_preco.json()["precos"]
    assert precos[0]["vigencia_inicio"] == "2026-07-01"
    assert precos[1]["vigencia_fim"] == "2026-06-30"

    matriz_antiga = client.get(
        "/api/v1/materias-primas/matriz?data_referencia=2026-06-30"
    ).json()
    matriz_nova = client.get(
        "/api/v1/materias-primas/matriz?data_referencia=2026-07-01"
    ).json()

    assert matriz_antiga["matriz"]["Proteína isolada de soja"]["Custo"] == 25.5
    assert matriz_nova["matriz"]["Proteína isolada de soja"] == {
        "Custo": 27.0,
        "Proteína": 88.2,
        "Lipídios": 1.4,
    }
    assert matriz_nova["nutrientes"] == ["Lipídios", "Proteína"]

    listagem = client.get("/api/v1/materias-primas")
    assert listagem.status_code == 200
    assert len(listagem.json()) == 1


def test_rejeita_codigo_ou_nome_duplicado(client):
    assert client.post("/api/v1/materias-primas", json=payload_mp()).status_code == 201

    resposta = client.post(
        "/api/v1/materias-primas",
        json=payload_mp(nome="Outro nome"),
    )

    assert resposta.status_code == 409
    assert "mesmo código ou nome" in resposta.json()["detail"]


def test_desativacao_remove_mp_da_matriz_sem_apagar_historico(client):
    criada = client.post("/api/v1/materias-primas", json=payload_mp()).json()

    resposta = client.delete(f"/api/v1/materias-primas/{criada['id']}")

    assert resposta.status_code == 204
    assert client.get("/api/v1/materias-primas/matriz").json()["matriz"] == {}
    listagem = client.get("/api/v1/materias-primas").json()
    assert listagem[0]["ativa"] is False

    reativada = client.patch(
        f"/api/v1/materias-primas/{criada['id']}",
        json={"ativa": True},
    )
    assert reativada.status_code == 200
    assert reativada.json()["ativa"] is True


def test_edita_identificacao_composicao_e_unidade_do_nutriente(client):
    criada = client.post("/api/v1/materias-primas", json=payload_mp()).json()

    resposta = client.patch(
        f"/api/v1/materias-primas/{criada['id']}",
        json={
            "codigo": "MP0099",
            "nome": "Proteína de soja revisada",
            "composicao": [
                {
                    "nutriente_codigo": "PROT",
                    "nutriente_nome": "Proteína",
                    "unidade": "g/100 g de produto",
                    "valor": 90.0,
                }
            ],
        },
    )

    assert resposta.status_code == 200
    assert resposta.json()["codigo"] == "MP0099"
    assert resposta.json()["nome"] == "Proteína de soja revisada"
    composicao = resposta.json()["composicao"]
    assert len(composicao) == 1
    assert composicao[0]["nutriente_codigo"] == "PROT"
    assert composicao[0]["nutriente_nome"] == "Proteína"
    assert composicao[0]["unidade"] == "g/100 g de produto"
    assert float(composicao[0]["valor"]) == pytest.approx(90.0)


def test_rejeita_sobreposicao_de_precos(client):
    criada = client.post("/api/v1/materias-primas", json=payload_mp()).json()
    primeiro = client.post(
        f"/api/v1/materias-primas/{criada['id']}/precos",
        json={
            "preco_kg": 27,
            "vigencia_inicio": "2026-07-01",
            "vigencia_fim": "2026-12-31",
        },
    )
    assert primeiro.status_code == 200

    sobreposto = client.post(
        f"/api/v1/materias-primas/{criada['id']}/precos",
        json={"preco_kg": 28, "vigencia_inicio": "2026-10-01"},
    )

    assert sobreposto.status_code == 409
    assert "sobrepõe" in sobreposto.json()["detail"]
    atual = client.get(f"/api/v1/materias-primas/{criada['id']}").json()
    assert len(atual["precos"]) == 2


def test_valida_composicao_duplicada_e_vigencia_invalida(client):
    duplicada = payload_mp()
    duplicada["composicao"].append(duplicada["composicao"][0].copy())

    resposta_composicao = client.post("/api/v1/materias-primas", json=duplicada)
    resposta_vigencia = client.post(
        "/api/v1/materias-primas",
        json={
            **payload_mp(),
            "preco_inicial": {
                "preco_kg": 25.5,
                "vigencia_inicio": "2026-02-01",
                "vigencia_fim": "2026-01-01",
            },
        },
    )

    assert resposta_composicao.status_code == 422
    assert resposta_vigencia.status_code == 422
