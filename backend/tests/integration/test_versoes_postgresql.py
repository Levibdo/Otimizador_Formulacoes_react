"""Contrato atual: snapshots persistentes, API sem edição e lock por projeto."""
from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier
from time import monotonic, sleep

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from models import Projeto
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


def executar_mutacao_rejeitada(engine, sql, parametros):
    with pytest.raises(IntegrityError, match='Versões de fórmula são imutáveis') as erro:
        with engine.begin() as conn:
            conn.execute(text(sql), parametros)
    assert erro.value.orig.sqlstate == '23514'


@pytest.mark.parametrize('operacao', [
    'UPDATE versoes_formulas SET custo_total = 99 WHERE id = :id',
    'DELETE FROM versoes_formulas WHERE id = :id',
])
def test_rejeita_update_e_delete_diretos_da_versao(pg_client, postgres_app, operacao):
    projeto, _, _ = criar_versao(pg_client)
    path = f"/api/v1/projetos/{projeto['id']}/versoes"
    antes = pg_client.get(path).json()
    executar_mutacao_rejeitada(postgres_app[1], operacao, {'id': antes[0]['id']})
    assert pg_client.get(path).json() == antes


@pytest.mark.parametrize('campo,chave,novo_valor', [
    ('inclusoes', 'MP A', '50'),
    ('custos_individuais', 'MP A', '99'),
    ('composicao_nutricional', 'Proteína', '99'),
    ('parametros', 'metas', '{}'),
    ('matriz_snapshot', 'MP A', '{}'),
    ('requisitos_snapshot', '0', '{}'),
])
@pytest.mark.parametrize('operacao', ['alterar_item', 'remover_item'])
def test_rejeita_alteracao_e_remocao_de_itens_json(
    pg_client, postgres_app, campo, chave, novo_valor, operacao,
):
    # Os snapshots não têm tabelas-filhas: alterar/remover um item JSON é UPDATE.
    projeto, versao, _ = criar_versao(pg_client)
    path = f"/api/v1/projetos/{projeto['id']}/versoes"
    antes = pg_client.get(path).json()
    if operacao == 'alterar_item':
        expressao = f'jsonb_set({campo}::jsonb, ARRAY[:chave]::text[], CAST(:valor AS jsonb))'
    else:
        tipo = 'integer' if campo == 'requisitos_snapshot' else 'text'
        expressao = f'{campo}::jsonb - CAST(:chave AS {tipo})'
    executar_mutacao_rejeitada(
        postgres_app[1],
        f'UPDATE versoes_formulas SET {campo} = ({expressao})::json WHERE id = :id',
        {'id': versao['id'], 'chave': chave, 'valor': novo_valor},
    )
    assert pg_client.get(path).json() == antes


def test_cria_nova_versao_e_arquiva_projeto_sem_alterar_historico(pg_client):
    projeto, primeira, payload = criar_versao(pg_client)
    path = f"/api/v1/projetos/{projeto['id']}"
    segunda = post(pg_client, f"projetos/{projeto['id']}/versoes", {
        **payload, 'observacao': 'Revisão', 'custo_total': 12,
        'custos_individuais': {'MP A': 12},
        'matriz_snapshot': {'MP A': {'Custo': 12, 'Proteína': 25}},
    })
    assert segunda['numero'] == 2
    assert segunda['id'] != primeira['id']
    response = pg_client.patch(path, json={'status': 'ARQUIVADO'})
    assert response.status_code == 200
    assert response.json()['status'] == 'ARQUIVADO'
    salvas = pg_client.get(path + '/versoes').json()
    assert [VersaoFormulaRead.model_validate(v) for v in salvas] == [
        VersaoFormulaRead.model_validate(v) for v in (primeira, segunda)
    ]


@pytest.mark.parametrize('origem', ['sql', 'orm'])
def test_excluir_projeto_com_versao_rejeita_cascata_e_preserva_projeto(
    pg_client, postgres_app, origem,
):
    projeto, _, _ = criar_versao(pg_client)
    engine = postgres_app[1]
    path = f"/api/v1/projetos/{projeto['id']}"
    antes = pg_client.get(path).json()
    # Não há endpoint DELETE de projeto. A cascata existe no banco e no ORM.
    assert pg_client.delete(path).status_code == 405
    if origem == 'sql':
        executar_mutacao_rejeitada(
            engine, 'DELETE FROM projetos WHERE id = :id', {'id': projeto['id']},
        )
    else:
        with pytest.raises(IntegrityError, match='Versões de fórmula são imutáveis'):
            with Session(engine) as session, session.begin():
                session.delete(session.get(Projeto, projeto['id']))
    assert pg_client.get(path).json() == antes


def test_sql_pode_excluir_projeto_sem_versoes(pg_client, postgres_app):
    projeto = post(pg_client, 'projetos', {'codigo': 'VAZIO', 'nome': 'Sem versões'})
    with postgres_app[1].begin() as conn:
        conn.execute(text('DELETE FROM projetos WHERE id = :id'), {'id': projeto['id']})
    assert pg_client.get(f"/api/v1/projetos/{projeto['id']}").status_code == 404


def test_protecao_nao_se_estende_a_apresentacoes_componentes_e_cenarios(pg_client, postgres_app):
    projeto, versao, _ = criar_versao(pg_client)
    item = post(pg_client, 'itens-embalagem', {
        'codigo': 'POTE', 'nome': 'Pote', 'custo_unitario': 2,
    })
    apresentacao = post(pg_client, 'apresentacoes', {
        'projeto_id': projeto['id'], 'versao_formula_id': versao['id'],
        'codigo': 'AP-1', 'nome': 'Pote', 'peso_liquido_g': 500,
        'componentes': [{'item_embalagem_id': item['id'], 'quantidade': 1}],
    })
    cenario = post(pg_client, 'cenarios', {
        'projeto_id': projeto['id'], 'versao_formula_id': versao['id'],
        'nome': 'Aumento', 'precos_cenario': {'MP A': 12},
    })
    with postgres_app[1].begin() as conn:
        assert conn.execute(text('UPDATE apresentacoes_produto SET nome = :nome WHERE id = :id'),
                            {'nome': 'Outro nome', 'id': apresentacao['id']}).rowcount == 1
        assert conn.execute(text('UPDATE componentes_apresentacao SET quantidade = 2 WHERE apresentacao_id = :id'),
                            {'id': apresentacao['id']}).rowcount == 1
        assert conn.execute(text('UPDATE cenarios_custo SET nome = :nome WHERE id = :id'),
                            {'nome': 'Outro cenário', 'id': cenario['id']}).rowcount == 1
        assert conn.execute(text('DELETE FROM cenarios_custo WHERE id = :id'),
                            {'id': cenario['id']}).rowcount == 1
        assert conn.execute(text('DELETE FROM apresentacoes_produto WHERE id = :id'),
                            {'id': apresentacao['id']}).rowcount == 1
        assert conn.scalar(text('SELECT count(*) FROM componentes_apresentacao')) == 0
    salvas = pg_client.get(f"/api/v1/projetos/{projeto['id']}/versoes").json()
    assert VersaoFormulaRead.model_validate(salvas[0]) == VersaoFormulaRead.model_validate(versao)


def test_downgrade_remove_protecao_e_upgrade_protege_versoes_preexistentes(
    pg_client, postgres_app, alembic_runner,
):
    projeto, versao, payload = criar_versao(pg_client)
    engine = postgres_app[1]
    alembic_runner(engine.url, 'downgrade', '20260918_04')
    with engine.begin() as conn:
        assert conn.scalar(text("SELECT to_regprocedure('impedir_mutacao_versao_formula()')")) is None
        assert conn.scalar(text("""
            SELECT count(*) FROM pg_trigger
            WHERE tgrelid = 'versoes_formulas'::regclass AND NOT tgisinternal
        """)) == 0
        assert conn.execute(text('UPDATE versoes_formulas SET custo_total = 99 WHERE id = :id'),
                            {'id': versao['id']}).rowcount == 1
        assert conn.execute(text('DELETE FROM versoes_formulas WHERE id = :id'),
                            {'id': versao['id']}).rowcount == 1
    # Cria antes do upgrade: a proteção também deve valer para linhas antigas.
    # No schema antigo, o modelo atual de Projeto pode conter colunas posteriores.
    # Insere a versão usando somente o contrato da tabela histórica.
    existente = {**versao, 'projeto_id': projeto['id']}
    with engine.begin() as conn:
        conn.execute(text('''INSERT INTO versoes_formulas
            SELECT * FROM json_populate_record(NULL::versoes_formulas, CAST(:dados AS json))'''),
            {'dados': json.dumps(existente)})
    alembic_runner(engine.url, 'upgrade', 'head')
    for sql in (
        'UPDATE versoes_formulas SET custo_total = 99 WHERE id = :id',
        'DELETE FROM versoes_formulas WHERE id = :id',
    ):
        executar_mutacao_rejeitada(engine, sql, {'id': existente['id']})
    assert pg_client.get(f"/api/v1/projetos/{projeto['id']}/versoes").status_code == 200
