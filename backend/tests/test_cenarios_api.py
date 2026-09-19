from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from db.base import Base
from db.session import get_db
from routers.apresentacoes import router as apresentacoes_router
from routers.cenarios import router as cenarios_router
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
    app.include_router(cenarios_router)

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    session.close()


def preparar_base(client):
    projeto = client.post(
        "/api/v1/projetos",
        json={"codigo": "CEN-001", "nome": "Produto cenário", "requisitos": []},
    ).json()
    versao = client.post(
        f"/api/v1/projetos/{projeto['id']}/versoes",
        json={
            "status_solver": "Optimal",
            "custo_total": 14,
            "inclusoes": {"MP A": 60, "MP B": 40},
            "custos_individuais": {"MP A": 6, "MP B": 8},
            "composicao_nutricional": {},
            "parametros": {},
            "matriz_snapshot": {
                "MP A": {"Custo": 10},
                "MP B": {"Custo": 20},
            },
        },
    ).json()
    embalagem = client.post(
        "/api/v1/itens-embalagem",
        json={"codigo": "POTE", "nome": "Pote", "custo_unitario": 1},
    ).json()
    apresentacao = client.post(
        "/api/v1/apresentacoes",
        json={
            "projeto_id": projeto["id"],
            "versao_formula_id": versao["id"],
            "codigo": "AP-500",
            "nome": "Produto 500 g",
            "peso_liquido_g": 500,
            "unidades_por_caixa": 10,
            "componentes": [
                {"item_embalagem_id": embalagem["id"], "quantidade": 1}
            ],
        },
    ).json()
    return projeto, versao, apresentacao


def test_calcula_cenario_e_impacto_nas_apresentacoes(client):
    projeto, versao, apresentacao = preparar_base(client)
    resposta = client.post(
        "/api/v1/cenarios",
        json={
            "projeto_id": projeto["id"],
            "versao_formula_id": versao["id"],
            "nome": "Alta de 20% na MP A",
            "precos_cenario": {"MP A": 12},
        },
    )

    assert resposta.status_code == 201
    dados = resposta.json()
    assert float(dados["custo_base_kg"]) == pytest.approx(14)
    assert float(dados["custo_cenario_kg"]) == pytest.approx(15.2)
    assert float(dados["variacao_absoluta"]) == pytest.approx(1.2)
    assert float(dados["variacao_percentual"]) == pytest.approx(8.571428, rel=1e-5)
    impacto = dados["impacto_apresentacoes"][0]
    assert impacto["apresentacao_id"] == apresentacao["id"]
    assert float(impacto["custo_unitario_base"]) == pytest.approx(8)
    assert float(impacto["custo_unitario_cenario"]) == pytest.approx(8.6)
    assert float(impacto["custo_caixa_cenario"]) == pytest.approx(86)


def test_lista_por_projeto_e_preserva_premissas(client):
    projeto, versao, _ = preparar_base(client)
    criada = client.post(
        "/api/v1/cenarios",
        json={
            "projeto_id": projeto["id"],
            "versao_formula_id": versao["id"],
            "nome": "Queda MP B",
            "observacao": "Negociação com fornecedor",
            "precos_cenario": {"MP B": 18},
        },
    ).json()
    listagem = client.get(
        f"/api/v1/cenarios?projeto_id={projeto['id']}"
    ).json()
    assert len(listagem) == 1
    assert listagem[0]["id"] == criada["id"]
    assert listagem[0]["precos_cenario"] == {"MP B": "18"}
    assert listagem[0]["observacao"] == "Negociação com fornecedor"


def test_rejeita_mp_estranha_e_versao_de_outro_projeto(client):
    projeto, versao, _ = preparar_base(client)
    estranha = client.post(
        "/api/v1/cenarios",
        json={
            "projeto_id": projeto["id"],
            "versao_formula_id": versao["id"],
            "nome": "Inválido",
            "precos_cenario": {"MP inexistente": 5},
        },
    )
    assert estranha.status_code == 409
    assert "não pertence" in estranha.json()["detail"]

    outro = client.post(
        "/api/v1/projetos",
        json={"codigo": "OUTRO", "nome": "Outro", "requisitos": []},
    ).json()
    resposta = client.post(
        "/api/v1/cenarios",
        json={
            "projeto_id": outro["id"],
            "versao_formula_id": versao["id"],
            "nome": "Versão cruzada",
            "precos_cenario": {"MP A": 11},
        },
    )
    assert resposta.status_code == 409


def test_rejeita_preco_negativo(client):
    projeto, versao, _ = preparar_base(client)
    resposta = client.post(
        "/api/v1/cenarios",
        json={
            "projeto_id": projeto["id"],
            "versao_formula_id": versao["id"],
            "nome": "Preço inválido",
            "precos_cenario": {"MP A": -1},
        },
    )
    assert resposta.status_code == 422
