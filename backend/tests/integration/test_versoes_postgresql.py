"""Contrato atual: snapshots persistentes, API sem edição e lock por projeto."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from time import monotonic, sleep

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text
from schemas import ApresentacaoRead, CenarioCustoRead, VersaoFormulaRead

pytestmark = pytest.mark.postgresql


def post(client, path, payload):
    response = client.post('/api/v1/' + path, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def criar_versao(client):
    projeto = post(client, 'projetos', {
        'codigo': 'PG-1', 'nome': 'Projeto PostgreSQL',
        'requisitos': [{'tipo_item': 'NUTRIENTE', 'item': 'Proteína', 'minimo': 20}],
    })
    payload = {
        'status_solver': 'Optimal', 'custo_total': 10,
        'inclusoes': {'MP A': 100}, 'custos_individuais': {'MP A': 10},
        'composicao_nutricional': {'Proteína': 25},
        'parametros': {'metas': {'Proteína': {'min': 20}}},
        'matriz_snapshot': {'MP A': {'Custo': 10, 'Proteína': 25}},
    }
    versao = post(client, f"projetos/{projeto['id']}/versoes", payload)
    return projeto, versao, payload


def test_snapshots_persistem_apos_alterar_cadastros_e_reabrir_conexoes(pg_client, postgres_app):
    mp = post(pg_client, 'materias-primas', {
        'codigo': 'MP-A', 'nome': 'MP A',
        'composicao': [{'nutriente_codigo': 'PROT', 'nutriente_nome': 'Proteína',
                       'unidade': 'g/100 g', 'valor': 25}],
        'preco_inicial': {'preco_kg': 10, 'vigencia_inicio': '2026-01-01'},
    })
    projeto, versao, payload = criar_versao(pg_client)
    item = post(pg_client, 'itens-embalagem', {
        'codigo': 'POTE', 'nome': 'Pote', 'custo_unitario': 2,
    })
    apresentacao = post(pg_client, 'apresentacoes', {
        'projeto_id': projeto['id'], 'versao_formula_id': versao['id'],
        'codigo': 'AP-1', 'nome': 'Pote 500 g', 'peso_liquido_g': 500,
        'unidades_por_caixa': 12,
        'componentes': [{'item_embalagem_id': item['id'], 'quantidade': 1}],
    })
    cenario = post(pg_client, 'cenarios', {
        'projeto_id': projeto['id'], 'versao_formula_id': versao['id'],
        'nome': 'Aumento', 'precos_cenario': {'MP A': 12},
    })
    assert float(apresentacao['custo_unitario']) == 7
    assert float(cenario['custo_cenario_kg']) == 12
    assert float(cenario['impacto_apresentacoes'][0]['custo_unitario_cenario']) == 8
    assert pg_client.patch(f"/api/v1/projetos/{projeto['id']}", json={
        'requisitos': [{'tipo_item': 'NUTRIENTE', 'item': 'Proteína', 'minimo': 30}],
    }).status_code == 200
    assert pg_client.post(f"/api/v1/materias-primas/{mp['id']}/precos", json={
        'preco_kg': 99, 'vigencia_inicio': '2026-02-01',
    }).status_code == 200
    assert pg_client.patch(f"/api/v1/materias-primas/{mp['id']}", json={
        'nome': 'MP renomeada', 'composicao': [{
            'nutriente_codigo': 'PROT', 'nutriente_nome': 'Proteína',
            'unidade': 'g/100 g', 'valor': 50,
        }],
    }).status_code == 200
    assert pg_client.patch(f"/api/v1/itens-embalagem/{item['id']}", json={
        'nome': 'Pote atualizado', 'custo_unitario': 9,
    }).status_code == 200
    segunda = post(pg_client, f"projetos/{projeto['id']}/versoes", payload)
    assert segunda['numero'] == 2
    assert float(segunda['requisitos_snapshot'][0]['minimo']) == 30

    # Descarta o pool: consultas seguintes não reutilizam conexões nem sessões ORM.
    postgres_app[1].dispose()
    with TestClient(postgres_app[0]) as novo_client:
        versoes = novo_client.get(f"/api/v1/projetos/{projeto['id']}/versoes").json()
        # NUMERIC(18, 6) acrescenta casas decimais na releitura; comparar valores.
        assert VersaoFormulaRead.model_validate(versoes[0]) == VersaoFormulaRead.model_validate(versao)
        atual = novo_client.get(f"/api/v1/apresentacoes/{apresentacao['id']}").json()
        assert ApresentacaoRead.model_validate(atual) == ApresentacaoRead.model_validate(apresentacao)
        atual = novo_client.get(f"/api/v1/cenarios/{cenario['id']}").json()
        assert CenarioCustoRead.model_validate(atual) == CenarioCustoRead.model_validate(cenario)


@pytest.mark.parametrize('method', ['PATCH', 'PUT', 'DELETE'])
def test_api_nao_permite_alterar_ou_excluir_versoes(pg_client, method):
    projeto, versao, _ = criar_versao(pg_client)
    path = f"/api/v1/projetos/{projeto['id']}/versoes"
    for target, status in ((path, 405), (f"{path}/{versao['id']}", 404)):
        response = pg_client.request(method, target, json={'custo_total': 999})
        assert response.status_code == status
    salvas = pg_client.get(path).json()
    assert len(salvas) == 1
    assert VersaoFormulaRead.model_validate(salvas[0]) == VersaoFormulaRead.model_validate(versao)


def test_numera_versoes_concorrentes_do_mesmo_projeto(pg_client, postgres_app):
    projeto, primeira, payload = criar_versao(pg_client)
    app, engine, schema = postgres_app
    workers = 4
    inicio = Barrier(workers)

    def salvar(indice):
        with TestClient(app) as client:
            inicio.wait(timeout=10)
            return post(client, f"projetos/{projeto['id']}/versoes", {
                **payload, 'observacao': f'Concorrente {indice}',
            })

    # Segura a linha até observar as quatro requisições bloqueadas no PostgreSQL.
    # Assim o teste prova contenção real, sem depender da velocidade das threads.
    with engine.connect() as lock_conn:
        transaction = lock_conn.begin()
        lock_conn.execute(text('SELECT id FROM projetos WHERE id = :id FOR UPDATE'),
                          {'id': projeto['id']})
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(salvar, i) for i in range(workers)]
            try:
                deadline = monotonic() + 10
                bloqueadas = 0
                with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as monitor:
                    while monotonic() < deadline:
                        bloqueadas = monitor.scalar(text("""
                            SELECT count(*) FROM pg_stat_activity
                            WHERE application_name = :name AND wait_event_type = 'Lock'
                              AND query LIKE '%FOR UPDATE%'
                        """), {'name': schema})
                        if bloqueadas == workers:
                            break
                        sleep(0.05)
                assert bloqueadas == workers, 'As requisições não disputaram o lock esperado'
            finally:
                transaction.rollback()
            resultados = [future.result(timeout=20) for future in futures]
    assert sorted(item['numero'] for item in resultados) == [2, 3, 4, 5]
    assert len({item['id'] for item in resultados}) == workers
    salvas = pg_client.get(f"/api/v1/projetos/{projeto['id']}/versoes").json()
    assert VersaoFormulaRead.model_validate(salvas[0]) == VersaoFormulaRead.model_validate(primeira)
    assert sorted(item['numero'] for item in salvas) == [1, 2, 3, 4, 5]
    assert {item['observacao'] for item in salvas[1:]} == {
        f'Concorrente {i}' for i in range(workers)
    }


def test_documenta_que_sql_direto_ainda_pode_alterar_versao(pg_client, postgres_app):
    """Caracterização da limitação atual; não promete imutabilidade no banco."""
    projeto, versao, _ = criar_versao(pg_client)
    with postgres_app[1].begin() as conn:
        conn.execute(text('UPDATE versoes_formulas SET custo_total = 99 WHERE id = :id'),
                     {'id': versao['id']})
    salvas = pg_client.get(f"/api/v1/projetos/{projeto['id']}/versoes").json()
    assert float(salvas[0]['custo_total']) == 99
    assert salvas[0]['matriz_snapshot'] == versao['matriz_snapshot']
