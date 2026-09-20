from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.postgresql


def post(client, path, payload):
    resposta = client.post("/api/v1/" + path, json=payload)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def criar_mp(client, codigo, nome, preco, proteina):
    return post(client, "materias-primas", {
        "codigo": codigo, "nome": nome,
        "composicao": [{"nutriente_codigo": "PROT", "nutriente_nome": "Proteína", "unidade": "g/100 g", "valor": proteina}],
        "preco_inicial": {"preco_kg": preco, "vigencia_inicio": "2026-01-01"},
    })


@pytest.fixture
def base_motor(pg_client):
    categoria = pg_client.get("/api/v1/categorias-produto").json()[0]
    barata = criar_mp(pg_client, "BARATA", "MP barata", 10, 10)
    proteica = criar_mp(pg_client, "PROTEICA", "MP proteica", 20, 30)
    projeto = post(pg_client, "projetos", {
        "codigo": "MOTOR", "nome": "Motor regulatório", "categoria_produto_id": categoria["id"],
        "requisitos": [{"tipo_item": "NUTRIENTE", "item": "PROT", "minimo": 20, "unidade": "g/100 g"}],
    })
    return categoria, barata, proteica, projeto


def regra(client, categoria, tratamento, mp=None, componente=None, minimo=None, maximo=None):
    tipo = "MATERIA_PRIMA" if mp else "COMPONENTE"
    payload = {"categoria_id": categoria["id"], "tipo_alvo": tipo,
               "tratamento": tratamento, "minimo": minimo, "maximo": maximo,
               "justificativa": "Regra manual de teste, sem norma real"}
    payload["materia_prima_id" if mp else "componente_id"] = (mp or componente)["id"]
    return post(client, "regras-regulatorias", payload)


def test_requisitos_regras_limites_alertas_persistencia_e_versao(pg_client, base_motor, postgres_app):
    categoria, barata, proteica, projeto = base_motor
    regra(pg_client, categoria, "LIMITADA", mp=barata, maximo=60)
    resposta = post(pg_client, f"projetos/{projeto['id']}/otimizacoes", {
        "materias_primas_ids": [barata["id"], proteica["id"]],
        "limites_tecnicos": [{"materia_prima_id": barata["id"], "maximo": 55}],
        "data_referencia": "2026-06-01",
    })
    assert resposta["status"] == "ATENDE_COM_ALERTAS"
    assert resposta["inclusoes"]["MP barata"] == pytest.approx(50)
    assert resposta["limites_efetivos"]["BARATA"]["maximo"] == 55
    assert any("PROTEICA" in alerta for alerta in resposta["alertas"])
    execucao = pg_client.get(f"/api/v1/otimizacoes/{resposta['execucao_id']}").json()
    assert execucao["entradas_contexto"]["materias_primas"][0]["preco"] == 10
    assert "resultado_bruto" in execucao["resultado_diagnostico"]["resultado"]
    versao = post(pg_client, f"projetos/{projeto['id']}/versoes", {"execucao_id": resposta["execucao_id"], "observacao": "Gerada no servidor"})
    assert versao["parametros"]["execucao_id"] == resposta["execucao_id"]
    assert versao["requisitos_snapshot"][0]["item"] == "PROT"
    outro = post(pg_client, "projetos", {"codigo": "OUTRO", "nome": "Outro"})
    assert pg_client.post(f"/api/v1/projetos/{outro['id']}/versoes", json={"execucao_id": resposta["execucao_id"]}).status_code == 409
    with postgres_app[1].begin() as conn:
        for sql in ("UPDATE execucoes_otimizacao SET status = 'INVIAVEL' WHERE id = :id", "DELETE FROM execucoes_otimizacao WHERE id = :id"):
            with pytest.raises(IntegrityError), conn.begin_nested():
                conn.execute(text(sql), {"id": resposta["execucao_id"]})


@pytest.mark.parametrize("tratamento,minimo,maximo,esperado", [
    ("PERMITIDA", 40, 80, 50), ("OBRIGATORIA", 10, None, 50),
    ("LIMITADA", None, 30, 30), ("PROIBIDA", None, None, 0),
])
def test_tratamentos_individuais_de_mp(pg_client, base_motor, tratamento, minimo, maximo, esperado):
    categoria, barata, proteica, projeto = base_motor
    regra(pg_client, categoria, tratamento, mp=barata, minimo=minimo, maximo=maximo)
    resposta = post(pg_client, f"projetos/{projeto['id']}/otimizacoes", {"data_referencia": "2026-06-01"})
    assert resposta["status"] in ("ATENDE", "ATENDE_COM_ALERTAS")
    assert resposta["inclusoes"]["MP barata"] == pytest.approx(esperado)


def test_componente_agregado_zero_confirmado_desconhecido_e_snapshot(pg_client, base_motor):
    categoria, barata, proteica, projeto = base_motor
    componente = post(pg_client, "componentes-regulatorios", {"codigo": "COMP_X", "nome": "Componente X"})
    regra(pg_client, categoria, "LIMITADA", componente=componente, maximo=5)
    post(pg_client, f"materias-primas/{barata['id']}/componentes-regulatorios", {"componente_id": componente["id"], "situacao": "INFORMADO", "concentracao": 10, "data_referencia": "2026-01-01"})
    inconclusiva = post(pg_client, f"projetos/{projeto['id']}/otimizacoes", {"data_referencia": "2026-06-01"})
    assert inconclusiva["status"] == "INCONCLUSIVA" and inconclusiva["pendencias"]
    post(pg_client, f"materias-primas/{proteica['id']}/componentes-regulatorios", {"componente_id": componente["id"], "situacao": "AUSENTE_CONFIRMADO", "concentracao": 0, "data_referencia": "2026-01-01"})
    concluida = post(pg_client, f"projetos/{projeto['id']}/otimizacoes", {"data_referencia": "2026-06-01"})
    assert concluida["status"] == "ATENDE_COM_ALERTAS"
    assert concluida["componentes"]["COMP_X"] == pytest.approx(5)
    antes = pg_client.get(f"/api/v1/otimizacoes/{concluida['execucao_id']}").json()
    assert pg_client.post(f"/api/v1/materias-primas/{barata['id']}/precos", json={"preco_kg": 99, "vigencia_inicio": "2027-01-01"}).status_code == 200
    depois = pg_client.get(f"/api/v1/otimizacoes/{concluida['execucao_id']}").json()
    assert antes == depois


def test_rejeita_adulteracao_diagnosticos_previos_e_inviabilidade(pg_client, base_motor):
    categoria, barata, proteica, projeto = base_motor
    assert pg_client.post(f"/api/v1/projetos/{projeto['id']}/otimizacoes", json={"precos": {"BARATA": 0}}).status_code == 422
    conflito = post(pg_client, f"projetos/{projeto['id']}/otimizacoes", {"limites_tecnicos": [
        {"materia_prima_id": barata["id"], "minimo": 60}, {"materia_prima_id": proteica["id"], "minimo": 60}], "data_referencia": "2026-06-01"})
    assert conflito["status"] == "INVIAVEL"
    assert "soma dos mínimos" in conflito["diagnostico"]["erros"][0].lower()


def test_execucoes_concorrentes_e_versoes_concorrentes(pg_client, base_motor, postgres_app):
    _, barata, proteica, projeto = base_motor
    app = postgres_app[0]
    barrier = Barrier(2)
    def executar():
        with TestClient(app) as client:
            barrier.wait(timeout=10)
            return client.post(f"/api/v1/projetos/{projeto['id']}/otimizacoes", json={"data_referencia": "2026-06-01"}).json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        execucoes = [f.result(timeout=30) for f in [pool.submit(executar), pool.submit(executar)]]
    assert len({e["execucao_id"] for e in execucoes}) == 2
    barrier = Barrier(2)
    def versionar(execucao):
        with TestClient(app) as client:
            barrier.wait(timeout=10)
            return client.post(f"/api/v1/projetos/{projeto['id']}/versoes", json={"execucao_id": execucao["execucao_id"]})
    with ThreadPoolExecutor(max_workers=2) as pool:
        respostas = [f.result(timeout=30) for f in [pool.submit(versionar, execucoes[0]), pool.submit(versionar, execucoes[1])]]
    assert [r.status_code for r in respostas] == [201, 201]
    assert sorted(r.json()["numero"] for r in respostas) == [1, 2]


def test_migracao_07_downgrade_upgrade(pg_client, postgres_app, alembic_runner):
    engine = postgres_app[1]
    alembic_runner(engine.url, "downgrade", "20260919_06")
    with engine.begin() as conn:
        assert conn.scalar(text("SELECT to_regclass('execucoes_otimizacao')")) is None
        assert conn.scalar(text("SELECT to_regprocedure('impedir_mutacao_execucao_otimizacao()')")) is None
    alembic_runner(engine.url, "upgrade", "head")
    with engine.begin() as conn:
        assert conn.scalar(text("SELECT to_regclass('execucoes_otimizacao')")) == "execucoes_otimizacao"
