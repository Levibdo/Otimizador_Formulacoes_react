from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from db.base import Base
from db.session import get_db
from routers.apresentacoes import router as apresentacoes_router
from routers.projetos import router as projetos_router


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
    app.include_router(projetos_router)
    app.include_router(apresentacoes_router)

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    session.close()


def criar_projeto_e_versao(client, codigo="PD-001", custo=10):
    projeto = client.post(
        "/api/v1/projetos",
        json={"codigo": codigo, "nome": f"Projeto {codigo}", "requisitos": []},
    ).json()
    versao = client.post(
        f"/api/v1/projetos/{projeto['id']}/versoes",
        json={
            "status_solver": "Optimal",
            "custo_total": custo,
            "inclusoes": {"MP A": 100},
            "custos_individuais": {"MP A": custo},
            "composicao_nutricional": {},
            "parametros": {},
            "matriz_snapshot": {"MP A": {"Custo": custo}},
        },
    ).json()
    return projeto, versao


def criar_item(client, codigo, nome, custo):
    resposta = client.post(
        "/api/v1/itens-embalagem",
        json={
            "codigo": codigo,
            "nome": nome,
            "unidade": "un",
            "custo_unitario": custo,
        },
    )
    assert resposta.status_code == 201
    return resposta.json()


def test_calcula_custo_da_formula_embalagem_unidade_e_caixa(client):
    projeto, versao = criar_projeto_e_versao(client)
    pote = criar_item(client, "POTE-800", "Pote 800 g", 1.5)
    tampa = criar_item(client, "TAMPA", "Tampa", 0.4)
    rotulo = criar_item(client, "ROTULO", "Rótulo", 0.2)

    resposta = client.post(
        "/api/v1/apresentacoes",
        json={
            "projeto_id": projeto["id"],
            "versao_formula_id": versao["id"],
            "codigo": "PROD-800",
            "nome": "Produto 800 g",
            "peso_liquido_g": 800,
            "unidades_por_caixa": 12,
            "componentes": [
                {"item_embalagem_id": pote["id"], "quantidade": 1},
                {"item_embalagem_id": tampa["id"], "quantidade": 1},
                {"item_embalagem_id": rotulo["id"], "quantidade": 1},
            ],
        },
    )

    assert resposta.status_code == 201
    dados = resposta.json()
    assert float(dados["custo_formula"]) == pytest.approx(8.0)
    assert float(dados["custo_embalagem"]) == pytest.approx(2.1)
    assert float(dados["custo_unitario"]) == pytest.approx(10.1)
    assert float(dados["custo_caixa"]) == pytest.approx(121.2)
    assert len(dados["componentes"]) == 3


def test_preserva_snapshot_quando_preco_da_embalagem_muda(client):
    projeto, versao = criar_projeto_e_versao(client)
    pote = criar_item(client, "POTE", "Pote", 1.5)
    payload = {
        "projeto_id": projeto["id"],
        "versao_formula_id": versao["id"],
        "codigo": "AP-1",
        "nome": "Apresentação 1",
        "peso_liquido_g": 1000,
        "componentes": [{"item_embalagem_id": pote["id"], "quantidade": 1}],
    }
    primeira = client.post("/api/v1/apresentacoes", json=payload).json()

    atualizada = client.patch(
        f"/api/v1/itens-embalagem/{pote['id']}",
        json={"custo_unitario": 2.5},
    )
    assert atualizada.status_code == 200

    payload.update({"codigo": "AP-2", "nome": "Apresentação 2"})
    segunda = client.post("/api/v1/apresentacoes", json=payload).json()
    listagem = client.get("/api/v1/apresentacoes").json()

    antiga = next(item for item in listagem if item["id"] == primeira["id"])
    assert float(antiga["componentes"][0]["custo_unitario_snapshot"]) == 1.5
    assert float(antiga["custo_unitario"]) == 11.5
    assert float(segunda["custo_unitario"]) == 12.5


def test_rejeita_versao_de_outro_projeto_e_item_inativo(client):
    projeto_a, _ = criar_projeto_e_versao(client, "PD-A")
    _, versao_b = criar_projeto_e_versao(client, "PD-B")
    item = criar_item(client, "SELO", "Selo", 0.1)
    base = {
        "projeto_id": projeto_a["id"],
        "versao_formula_id": versao_b["id"],
        "codigo": "INVALIDA",
        "nome": "Inválida",
        "peso_liquido_g": 400,
        "componentes": [{"item_embalagem_id": item["id"], "quantidade": 1}],
    }
    resposta = client.post("/api/v1/apresentacoes", json=base)
    assert resposta.status_code == 409
    assert "não pertence" in resposta.json()["detail"]

    projeto_c, versao_c = criar_projeto_e_versao(client, "PD-C")
    assert client.patch(
        f"/api/v1/itens-embalagem/{item['id']}", json={"ativo": False}
    ).status_code == 200
    base.update(
        projeto_id=projeto_c["id"],
        versao_formula_id=versao_c["id"],
        codigo="INATIVA",
    )
    resposta = client.post("/api/v1/apresentacoes", json=base)
    assert resposta.status_code == 409
    assert "inativo" in resposta.json()["detail"]


def test_valida_duplicidades_e_valores_positivos(client):
    item = criar_item(client, "CX", "Caixa", 1)
    duplicado = client.post(
        "/api/v1/itens-embalagem",
        json={"codigo": "CX", "nome": "Outra caixa", "custo_unitario": 2},
    )
    assert duplicado.status_code == 409

    projeto, versao = criar_projeto_e_versao(client)
    resposta = client.post(
        "/api/v1/apresentacoes",
        json={
            "projeto_id": projeto["id"],
            "versao_formula_id": versao["id"],
            "codigo": "REP",
            "nome": "Repetida",
            "peso_liquido_g": 100,
            "componentes": [
                {"item_embalagem_id": item["id"], "quantidade": 1},
                {"item_embalagem_id": item["id"], "quantidade": 2},
            ],
        },
    )
    assert resposta.status_code == 422
