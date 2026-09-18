from fastapi.testclient import TestClient

from main import app


def test_api_declara_postgresql_como_fonte_oficial():
    with TestClient(app) as client:
        resposta = client.get("/")
        saude = client.get("/health")

    assert resposta.status_code == 200
    assert resposta.json()["fonte_dados"] == "PostgreSQL"
    assert saude.json() == {"status": "ok"}


def test_rotas_legadas_nao_estao_mais_expostas():
    caminhos = set(app.openapi()["paths"])

    assert "/data" not in caminhos
    assert "/mp" not in caminhos
    assert "/mp/{usuario_id}" not in caminhos
    assert "/mp/{mp_id}" not in caminhos
    assert "/importar_materias_primas" not in caminhos
    assert "/exportar_materias_primas" not in caminhos
    assert "/api/v1/materias-primas/importar" in caminhos
