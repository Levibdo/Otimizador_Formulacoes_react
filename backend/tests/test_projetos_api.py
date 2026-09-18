from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from db.base import Base
from db.session import get_db
from routers.projetos import router


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


def projeto_payload():
    return {
        "codigo": "P&D-001",
        "nome": "Bebida proteica",
        "descricao": "Protótipo inicial",
        "requisitos": [
            {
                "origem": "TECNICO",
                "tipo_item": "NUTRIENTE",
                "item": "Proteína",
                "minimo": 20,
                "unidade": "g/100 g",
            }
        ],
    }


def versao_payload(custo=4.25):
    return {
        "observacao": "Primeiro protótipo",
        "status_solver": "Optimal",
        "custo_total": custo,
        "inclusoes": {"Proteína de soja": 25.0},
        "custos_individuais": {"Proteína de soja": 4.25},
        "composicao_nutricional": {"Proteína": 22.0},
        "parametros": {"metas": {"Proteína": {"min": 20}}},
        "matriz_snapshot": {
            "Proteína de soja": {"Custo": 17.0, "Proteína": 88.0}
        },
    }


def test_cria_lista_e_atualiza_projeto_com_requisitos(client):
    criada = client.post("/api/v1/projetos", json=projeto_payload())

    assert criada.status_code == 201
    assert criada.json()["status"] == "ATIVO"
    assert criada.json()["requisitos"][0]["item"] == "Proteína"
    projeto_id = criada.json()["id"]

    atualizada = client.patch(
        f"/api/v1/projetos/{projeto_id}",
        json={"status": "CONCLUIDO", "descricao": "Protótipo aprovado"},
    )
    assert atualizada.status_code == 200
    assert atualizada.json()["status"] == "CONCLUIDO"
    assert client.get("/api/v1/projetos").json()[0]["codigo"] == "P&D-001"


def test_rejeita_codigo_duplicado_e_requisito_invalido(client):
    assert client.post("/api/v1/projetos", json=projeto_payload()).status_code == 201
    duplicado = client.post("/api/v1/projetos", json=projeto_payload())
    assert duplicado.status_code == 409

    invalido = projeto_payload()
    invalido["codigo"] = "P&D-002"
    invalido["requisitos"][0].update({"minimo": 30, "maximo": 10})
    resposta = client.post("/api/v1/projetos", json=invalido)
    assert resposta.status_code == 422


def test_numera_versoes_e_preserva_snapshot_dos_requisitos(client):
    projeto = client.post("/api/v1/projetos", json=projeto_payload()).json()
    projeto_id = projeto["id"]

    primeira = client.post(
        f"/api/v1/projetos/{projeto_id}/versoes", json=versao_payload()
    )
    assert primeira.status_code == 201
    assert primeira.json()["numero"] == 1
    assert primeira.json()["requisitos_snapshot"][0]["minimo"] == "20"

    novos_requisitos = [
        {
            "origem": "REGULATORIO",
            "tipo_item": "CUSTO",
            "item": "Custo total",
            "maximo": 5,
            "unidade": "R$/kg",
        }
    ]
    assert client.patch(
        f"/api/v1/projetos/{projeto_id}", json={"requisitos": novos_requisitos}
    ).status_code == 200
    segunda = client.post(
        f"/api/v1/projetos/{projeto_id}/versoes", json=versao_payload(4.5)
    )
    assert segunda.status_code == 201
    assert segunda.json()["numero"] == 2

    versoes = client.get(f"/api/v1/projetos/{projeto_id}/versoes").json()
    assert versoes[0]["requisitos_snapshot"][0]["item"] == "Proteína"
    assert versoes[1]["requisitos_snapshot"][0]["item"] == "Custo total"
    assert float(versoes[0]["custo_total"]) == pytest.approx(4.25)


def test_retorna_404_para_projeto_inexistente(client):
    assert client.get("/api/v1/projetos/999").status_code == 404
    resposta = client.post(
        "/api/v1/projetos/999/versoes", json=versao_payload()
    )
    assert resposta.status_code == 404
