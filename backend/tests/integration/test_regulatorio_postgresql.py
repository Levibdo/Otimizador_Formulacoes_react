from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.postgresql


def post(client, path, payload):
    response = client.post('/api/v1/' + path, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def cadastro(pg_client):
    categorias = pg_client.get('/api/v1/categorias-produto').json()
    assert len(categorias) == 1
    categoria = categorias[0]
    assert categoria['codigo'] == 'FORMULA_ENTERAL_PO'
    assert categoria['nome'] == 'Fórmula enteral em pó'
    mp = post(pg_client, 'materias-primas', {
        'codigo': 'MP01', 'nome': 'MP de teste', 'composicao': [],
        'preco_inicial': {'preco_kg': 10, 'vigencia_inicio': '2026-01-01'},
    })
    componente = post(pg_client, 'componentes-regulatorios', {'codigo': 'SUBSTANCIA_S', 'nome': 'Substância S'})
    return categoria, mp, componente


def payload_regra(cadastro, tipo='MATERIA_PRIMA', **changes):
    categoria, mp, componente = cadastro
    return {
        'categoria_id': categoria['id'], 'tipo_alvo': tipo,
        ('materia_prima_id' if tipo == 'MATERIA_PRIMA' else 'componente_id'):
            mp['id'] if tipo == 'MATERIA_PRIMA' else componente['id'],
        'tratamento': 'LIMITADA', 'maximo': 20, 'justificativa': 'Exemplo manual, sem norma real',
    } | changes


def test_catalogos_crud_desativacao_codigo_estavel_e_seed(pg_client, cadastro, postgres_app):
    categoria, _, componente = cadastro
    criada = post(pg_client, 'categorias-produto', {'codigo': 'OUTRA', 'nome': 'Outra'})
    assert pg_client.post('/api/v1/categorias-produto', json={'codigo': 'OUTRA', 'nome': 'Duplicada'}).status_code == 409
    assert pg_client.post('/api/v1/componentes-regulatorios', json={'codigo': componente['codigo'], 'nome': 'Duplicado'}).status_code == 409
    for prefix, item, flag in [('categorias-produto', criada, 'ativa'), ('componentes-regulatorios', componente, 'ativo')]:
        path = f"/api/v1/{prefix}/{item['id']}"
        response = pg_client.patch(path, json={'nome': 'Nome revisado', flag: False})
        assert response.status_code == 200, response.text
        assert response.json()[flag] is False
        assert response.json()['atualizado_em'] >= item['atualizado_em']
        assert pg_client.get(path).json()['codigo'] == item['codigo']
        assert pg_client.patch(path, json={'codigo': 'TROCA'}).status_code == 422
        assert pg_client.delete(path).status_code == 405
        assert pg_client.patch(path, json={flag: True}).status_code == 200
    assert pg_client.get(f"/api/v1/categorias-produto/{criada['id']}").json()['revisao'] == 3
    with postgres_app[1].begin() as conn:
        for table, item in [('categorias_produto', categoria), ('componentes_regulatorios', componente)]:
            for sql in [f"UPDATE {table} SET codigo = 'TROCADO' WHERE id = :id", f'DELETE FROM {table} WHERE id = :id']:
                with pytest.raises(IntegrityError), conn.begin_nested():
                    conn.execute(text(sql), {'id': item['id']})


def test_composicoes_historicas_zero_desconhecido_e_duplicidade(pg_client, cadastro, postgres_app):
    _, mp, componente = cadastro
    path = f"materias-primas/{mp['id']}/componentes-regulatorios"
    registros = []
    for dia, situacao, concentracao in [(1, 'DESCONHECIDO', None), (2, 'AUSENTE_CONFIRMADO', 0), (3, 'INFORMADO', 12.5)]:
        payload = {'componente_id': componente['id'], 'situacao': situacao, 'concentracao': concentracao,
                   'data_referencia': f'2026-01-0{dia}', 'fonte': 'Declaração de teste'}
        item = post(pg_client, path, payload)
        registros.append(item)
        assert pg_client.post('/api/v1/' + path, json=payload).status_code == 409
    assert registros[0]['concentracao'] is None
    assert float(registros[1]['concentracao']) == 0
    assert len(pg_client.get('/api/v1/' + path).json()) == 3
    item_path = f"/api/v1/composicoes-componentes-mp/{registros[2]['id']}"
    assert pg_client.patch(item_path, json={'ativo': False}).status_code == 200
    assert pg_client.get(item_path).json()['ativo'] is False
    assert pg_client.patch(item_path, json={'concentracao': 99}).status_code == 422
    with postgres_app[1].begin() as conn:
        for sql in ['UPDATE composicoes_componentes_mp SET concentracao = 99 WHERE id = :id',
                    'DELETE FROM composicoes_componentes_mp WHERE id = :id']:
            with pytest.raises(IntegrityError), conn.begin_nested():
                conn.execute(text(sql), {'id': registros[2]['id']})


@pytest.mark.parametrize('tipo', ['MATERIA_PRIMA', 'COMPONENTE'])
def test_regras_crud_revisoes_conflito_vigencia_e_desativacao(pg_client, cadastro, tipo):
    dados = payload_regra(cadastro, tipo, vigencia_inicio='2026-01-01', vigencia_fim='2026-01-31')
    original = post(pg_client, 'regras-regulatorias', dados)
    assert original['revisao'] == 1
    assert pg_client.post('/api/v1/regras-regulatorias', json=dados).status_code == 409
    # Limites compatíveis também são duplicidade: uma regra por alvo/período.
    assert pg_client.post('/api/v1/regras-regulatorias', json=dados | {'maximo': 10}).status_code == 409
    assert pg_client.post('/api/v1/regras-regulatorias', json=dados | {'vigencia_inicio': '2026-01-31'}).status_code == 409
    outra = post(pg_client, 'regras-regulatorias', dados | {'vigencia_inicio': '2026-02-01', 'vigencia_fim': None})
    path = f"/api/v1/regras-regulatorias/{original['id']}"
    nova = post(pg_client, f"regras-regulatorias/{original['id']}/revisoes", dados | {'maximo': 5})
    assert nova['revisao'] == 2 and nova['regra_anterior_id'] == original['id']
    assert pg_client.get(path).json()['ativa'] is False
    assert float(pg_client.get(path).json()['maximo']) == 20
    assert pg_client.patch(path, json={'ativa': True}).status_code == 409
    assert pg_client.patch(f"/api/v1/regras-regulatorias/{nova['id']}", json={'ativa': False}).status_code == 200
    assert pg_client.patch(f"/api/v1/regras-regulatorias/{nova['id']}", json={'ativa': True}).status_code == 200
    assert pg_client.patch(path, json={'maximo': 30}).status_code == 422
    assert pg_client.delete(path).status_code == 405
    assert len(pg_client.get('/api/v1/regras-regulatorias', params={'categoria_id': cadastro[0]['id'], 'ativa': True}).json()) == 2
    # Revisão conflitante não pode deixar a original inativa após rollback.
    resposta = pg_client.post(f"/api/v1/regras-regulatorias/{outra['id']}/revisoes", json=dados | {'maximo': 3})
    assert resposta.status_code == 409
    assert pg_client.get(f"/api/v1/regras-regulatorias/{outra['id']}").json()['ativa'] is True
    assert pg_client.get(f"/api/v1/categorias-produto/{cadastro[0]['id']}").json()['revisao'] > 1


def test_proibida_normaliza_zero_e_alvos_invalidos_retornam_422(pg_client, cadastro):
    regra = post(pg_client, 'regras-regulatorias', payload_regra(cadastro, tratamento='PROIBIDA', maximo=None))
    assert float(regra['maximo']) == 0
    for changes in [{'componente_id': cadastro[2]['id']}, {'materia_prima_id': None},
                    {'tratamento': 'OBRIGATORIA', 'minimo': 0}]:
        assert pg_client.post('/api/v1/regras-regulatorias', json=payload_regra(cadastro, **changes)).status_code == 422


def test_projeto_sem_categoria_associacao_desassociacao_e_inativos(pg_client, cadastro, postgres_app):
    categoria, mp, componente = cadastro
    projeto = post(pg_client, 'projetos', {'codigo': 'ANTIGO', 'nome': 'Projeto compatível'})
    assert projeto['categoria_produto_id'] is None
    path = f"/api/v1/projetos/{projeto['id']}"
    assert pg_client.patch(path, json={'categoria_produto_id': categoria['id']}).json()['categoria_produto_id'] == categoria['id']
    assert pg_client.patch(path, json={'categoria_produto_id': 99999}).status_code == 404
    assert pg_client.patch(f"/api/v1/categorias-produto/{categoria['id']}", json={'ativa': False}).status_code == 200
    assert pg_client.patch(path, json={'nome': 'Continua editável'}).status_code == 200
    assert pg_client.post('/api/v1/projetos', json={'codigo': 'NOVO', 'nome': 'Novo', 'categoria_produto_id': categoria['id']}).status_code == 409
    assert pg_client.post('/api/v1/regras-regulatorias', json=payload_regra(cadastro)).status_code == 409
    assert pg_client.patch(path, json={'categoria_produto_id': None}).json()['categoria_produto_id'] is None
    assert pg_client.patch(f"/api/v1/componentes-regulatorios/{componente['id']}", json={'ativo': False}).status_code == 200
    assert pg_client.post(f"/api/v1/materias-primas/{mp['id']}/componentes-regulatorios", json={
        'componente_id': componente['id'], 'situacao': 'DESCONHECIDO', 'data_referencia': '2026-01-01',
    }).status_code == 409
    with postgres_app[1].begin() as conn:
        with pytest.raises(IntegrityError), conn.begin_nested():
            conn.execute(text('UPDATE projetos SET categoria_produto_id = 99999 WHERE id = :id'), {'id': projeto['id']})


def test_diagnostico_cadastral_alerta_sem_bloquear_e_nao_presume_zero(pg_client, cadastro):
    categoria, mp, componente = cadastro
    post(pg_client, 'regras-regulatorias', payload_regra(cadastro, 'COMPONENTE'))
    path = f"/api/v1/categorias-produto/{categoria['id']}/diagnostico-cadastral"
    def diagnostico(data='2026-01-02'):
        r = pg_client.get(path, params={'data_referencia': data})
        assert r.status_code == 200
        return r.json()
    dados = diagnostico()
    assert dados['escopo'] == 'CADASTRAL_SEM_AVALIACAO_DE_CONFORMIDADE'
    assert dados['mps_sem_regra_individual'][0]['materia_prima_id'] == mp['id']
    assert dados['concentracoes_desconhecidas'][0]['motivo'] == 'SEM_REGISTRO'
    comp_path = f"materias-primas/{mp['id']}/componentes-regulatorios"
    post(pg_client, comp_path, {'componente_id': componente['id'], 'situacao': 'DESCONHECIDO', 'data_referencia': '2026-01-01'})
    assert diagnostico()['concentracoes_desconhecidas'][0]['motivo'] == 'DESCONHECIDO'
    post(pg_client, comp_path, {'componente_id': componente['id'], 'situacao': 'AUSENTE_CONFIRMADO', 'concentracao': 0, 'data_referencia': '2026-01-02'})
    assert diagnostico()['concentracoes_desconhecidas'] == []
    assert diagnostico('2026-01-01')['concentracoes_desconhecidas']
    post(pg_client, 'regras-regulatorias', payload_regra(cadastro))
    assert diagnostico()['mps_sem_regra_individual'] == []


def test_constraints_sql_direto_independentes_da_api(pg_client, cadastro, postgres_app):
    categoria, mp, componente = cadastro
    engine = postgres_app[1]
    regra_sql = '''INSERT INTO regras_regulatorias
        (categoria_id, tipo_alvo, materia_prima_id, componente_id, tratamento, minimo, maximo, justificativa, unidade, base)
        VALUES (:categoria, :tipo, :mp, :componente, :tratamento, :minimo, :maximo, 'Teste', :unidade, :base)'''
    base = dict(categoria=categoria['id'], tipo='MATERIA_PRIMA', mp=mp['id'], componente=None,
                tratamento='LIMITADA', minimo=None, maximo=10, unidade='%', base='MASSA_MASSA')
    invalidas = [dict(componente=componente['id']), dict(mp=None), dict(tipo='OUTRO'), dict(minimo=-1),
                 dict(maximo=101), dict(minimo=11), dict(tratamento='OBRIGATORIA'),
                 dict(tratamento='PROIBIDA'), dict(tratamento='LIMITADA', maximo=None),
                 dict(unidade='mg'), dict(base='VOLUME')]
    with engine.begin() as conn:
        for changes in invalidas:
            with pytest.raises(IntegrityError), conn.begin_nested():
                conn.execute(text(regra_sql), base | changes)
        conn.execute(text(regra_sql), base)
        # Constraint de exclusão rejeita também INSERTs fora do serviço.
        with pytest.raises(IntegrityError) as erro, conn.begin_nested():
            conn.execute(text(regra_sql), base)
        assert erro.value.orig.sqlstate == '23P01'
        for situacao, concentracao in [('AUSENTE_CONFIRMADO', None), ('AUSENTE_CONFIRMADO', 1),
                                       ('DESCONHECIDO', 0), ('INFORMADO', None), ('INFORMADO', 101), ('OUTRO', None)]:
            with pytest.raises(IntegrityError), conn.begin_nested():
                conn.execute(text('''INSERT INTO composicoes_componentes_mp
                    (materia_prima_id, componente_id, data_referencia, situacao, concentracao)
                    VALUES (:mp, :componente, '2026-01-01', :situacao, :concentracao)'''),
                    dict(mp=mp['id'], componente=componente['id'], situacao=situacao, concentracao=concentracao))
        with pytest.raises(IntegrityError), conn.begin_nested():
            conn.execute(text('UPDATE regras_regulatorias SET maximo = 99'))
        with pytest.raises(IntegrityError), conn.begin_nested():
            conn.execute(text('DELETE FROM regras_regulatorias'))


def test_regras_concorrentes_nao_criam_duplicidade(pg_client, cadastro, postgres_app):
    app = postgres_app[0]
    barrier = Barrier(2)
    def cadastrar():
        with TestClient(app) as client:
            barrier.wait(timeout=10)
            return client.post('/api/v1/regras-regulatorias', json=payload_regra(cadastro)).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(cadastrar) for _ in range(2)]
        assert sorted(f.result(timeout=25) for f in futures) == [201, 409]
    assert len(pg_client.get('/api/v1/regras-regulatorias').json()) == 1


def test_migracao_downgrade_upgrade_preserva_projeto_antigo_e_seed_unico(pg_client, postgres_app, alembic_runner):
    engine = postgres_app[1]
    projeto = post(pg_client, 'projetos', {'codigo': 'ANTIGO', 'nome': 'Anterior'})
    alembic_runner(engine.url, 'downgrade', '20260919_05')
    with engine.begin() as conn:
        for table in ('categorias_produto', 'componentes_regulatorios', 'composicoes_componentes_mp', 'regras_regulatorias'):
            assert conn.scalar(text('SELECT to_regclass(:nome)'), {'nome': table}) is None
        for funcao in ('proteger_cadastro_regulatorio()', 'atualizar_revisao_categoria_regulatoria()'):
            assert conn.scalar(text('SELECT to_regprocedure(:nome)'), {'nome': funcao}) is None
        assert conn.scalar(text('SELECT count(*) FROM projetos WHERE id = :id'), {'id': projeto['id']}) == 1
        assert conn.scalar(text("SELECT count(*) FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = 'projetos' AND column_name = 'categoria_produto_id'")) == 0
    alembic_runner(engine.url, 'upgrade', 'head')
    alembic_runner(engine.url, 'upgrade', 'head')
    categorias = pg_client.get('/api/v1/categorias-produto').json()
    assert len(categorias) == 1 and categorias[0]['codigo'] == 'FORMULA_ENTERAL_PO'
    assert pg_client.get('/api/v1/regras-regulatorias').json() == []
    assert pg_client.get(f"/api/v1/projetos/{projeto['id']}").json()['categoria_produto_id'] is None


def test_endpoints_ausentes_retorna_404(pg_client):
    for path in ['categorias-produto/999', 'componentes-regulatorios/999', 'regras-regulatorias/999',
                 'composicoes-componentes-mp/999', 'materias-primas/999/componentes-regulatorios']:
        assert pg_client.get('/api/v1/' + path).status_code == 404
