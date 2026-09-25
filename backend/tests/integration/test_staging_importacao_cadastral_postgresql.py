import io
import re
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

from openpyxl import load_workbook
import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import (
    ComposicaoMateriaPrima,
    MateriaPrima,
    Nutriente,
    PrecoMateriaPrima,
    SessaoImportacaoCadastral,
)
from services.planilha_cadastral import gerar_template_cadastral
from services.staging_importacao_cadastral import preparar_sessao


def planilha_valida():
    workbook = load_workbook(io.BytesIO(gerar_template_cadastral()))
    for aba in ("MATERIAS_PRIMAS", "NUTRIENTES", "COMPOSICAO_NUTRICIONAL", "PRECOS_MP"):
        ws = workbook[aba]
        if ws.max_row > 1:
            ws.delete_rows(2, ws.max_row - 1)
    workbook["MATERIAS_PRIMAS"].append(("CRIAR", "PG_STAGE_MP", "MP staging PG", "SIM"))
    workbook["NUTRIENTES"].append(("CRIAR", "PG_STAGE_NUT", "Nutriente staging PG", "g/100 g"))
    workbook["COMPOSICAO_NUTRICIONAL"].append(("CRIAR", "PG_STAGE_MP", "PG_STAGE_NUT", "20.000000"))
    workbook["PRECOS_MP"].append(("CRIAR", "PG_STAGE_MP", "8.000000", "2026-01-01", None))
    saida = io.BytesIO()
    workbook.save(saida)
    return saida.getvalue()


def snapshot_cadastros(engine):
    with Session(engine) as db:
        return (
            tuple(db.execute(select(MateriaPrima.id, MateriaPrima.codigo, MateriaPrima.nome,
                                    MateriaPrima.ativa).order_by(MateriaPrima.id)).all()),
            tuple(db.execute(select(Nutriente.id, Nutriente.codigo, Nutriente.nome,
                                    Nutriente.unidade).order_by(Nutriente.id)).all()),
            tuple(db.execute(select(ComposicaoMateriaPrima.id,
                                    ComposicaoMateriaPrima.materia_prima_id,
                                    ComposicaoMateriaPrima.nutriente_id,
                                    ComposicaoMateriaPrima.valor)
                             .order_by(ComposicaoMateriaPrima.id)).all()),
            tuple(db.execute(select(PrecoMateriaPrima.id, PrecoMateriaPrima.materia_prima_id,
                                    PrecoMateriaPrima.preco_kg,
                                    PrecoMateriaPrima.vigencia_inicio,
                                    PrecoMateriaPrima.vigencia_fim)
                             .order_by(PrecoMateriaPrima.id)).all()),
        )


def test_preparacao_postgresql_persiste_somente_staging(pg_client, postgres_app):
    _, engine, _ = postgres_app
    antes = snapshot_cadastros(engine)
    conteudo = planilha_valida()
    resposta = pg_client.post(
        "/api/v1/importacoes-cadastrais/preparar",
        files={"arquivo": ("cadastros.xlsx", conteudo)},
    )
    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["arquivo_sha256"] == sha256(conteudo).hexdigest()
    assert corpo["status"] == "PENDENTE"
    assert corpo["operacoes_total"] == 4
    assert snapshot_cadastros(engine) == antes

    with Session(engine) as db:
        sessao = db.scalar(select(SessaoImportacaoCadastral))
        assert sessao is not None
        assert sessao.token_hash != corpo["token_confirmacao"]
        assert corpo["token_confirmacao"] not in str(sessao.payload_normalizado)
        assert sessao.payload_normalizado["dados"]["PRECOS_MP"][0]["preco_kg"] == "8.000000"
        assert sessao.confirmado_em is None
        assert sessao.resultado is None

    consulta = pg_client.get(f'/api/v1/importacoes-cadastrais/{corpo["sessao_id"]}')
    assert consulta.status_code == 200
    assert "token" not in consulta.text.lower()
    assert "payload_normalizado" not in consulta.text


def test_planilha_invalida_nao_cria_staging_postgresql(pg_client, postgres_app):
    _, engine, _ = postgres_app
    resposta = pg_client.post(
        "/api/v1/importacoes-cadastrais/preparar",
        files={"arquivo": ("cadastros.xlsx", "inválido".encode())},
    )
    assert resposta.status_code == 422
    with Session(engine) as db:
        assert db.scalar(select(SessaoImportacaoCadastral)) is None


def test_todos_os_campos_permanentes_sao_imutaveis_postgresql(
    pg_client, postgres_app,
):
    _, engine, _ = postgres_app
    criada = pg_client.post(
        "/api/v1/importacoes-cadastrais/preparar",
        files={"arquivo": ("cadastros.xlsx", planilha_valida())},
    ).json()
    sessao_id = criada["sessao_id"]
    mutacoes = (
        "id = id + 1000",
        "uuid_publico = gen_random_uuid()",
        "token_hash = repeat('b', 64)",
        "arquivo_sha256 = repeat('0', 64)",
        "versao_contrato = '9.9'",
        "payload_normalizado = '{}'::jsonb",
        "resumo = '{}'::jsonb",
        "avisos = '[{}]'::jsonb",
        "criado_em = criado_em - interval '1 second'",
        "expira_em = expira_em + interval '1 second'",
    )
    for atribuicao in mutacoes:
        with pytest.raises(IntegrityError, match="imutável"):
            with engine.begin() as conn:
                conn.execute(text(
                    f"UPDATE sessoes_importacao_cadastral SET {atribuicao} "
                    "WHERE uuid_publico = :id"
                ), {"id": sessao_id})
    with pytest.raises(IntegrityError, match="removida"):
        with engine.begin() as conn:
            conn.execute(text(
                "DELETE FROM sessoes_importacao_cadastral WHERE uuid_publico = :id"
            ), {"id": sessao_id})


def _preparar(pg_client):
    resposta = pg_client.post(
        "/api/v1/importacoes-cadastrais/preparar",
        files={"arquivo": ("cadastros.xlsx", planilha_valida())},
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def test_transicoes_permitidas_exigem_metadados_coerentes(pg_client, postgres_app):
    _, engine, _ = postgres_app
    confirmada, expirada, falhou = (_preparar(pg_client) for _ in range(3))
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE sessoes_importacao_cadastral
            SET status = 'CONFIRMADA', confirmado_em = clock_timestamp(),
                resultado = '{"aplicadas": 4}'::jsonb
            WHERE uuid_publico = :id
        """), {"id": confirmada["sessao_id"]})
        conn.execute(text("""
            UPDATE sessoes_importacao_cadastral SET status = 'EXPIRADA'
            WHERE uuid_publico = :id
        """), {"id": expirada["sessao_id"]})
        conn.execute(text("""
            UPDATE sessoes_importacao_cadastral
            SET status = 'FALHOU', resultado = '{"diagnostico": "Falha segura."}'::jsonb
            WHERE uuid_publico = :id
        """), {"id": falhou["sessao_id"]})
    assert pg_client.get(f'/api/v1/importacoes-cadastrais/{confirmada["sessao_id"]}').json()["status"] == "CONFIRMADA"
    assert pg_client.get(f'/api/v1/importacoes-cadastrais/{expirada["sessao_id"]}').json()["status"] == "EXPIRADA"
    assert pg_client.get(f'/api/v1/importacoes-cadastrais/{falhou["sessao_id"]}').json()["status"] == "FALHOU"


def test_transicoes_incompletas_e_estados_finais_sao_rejeitados(pg_client, postgres_app):
    _, engine, _ = postgres_app
    pendente_confirmacao = _preparar(pg_client)
    pendente_falha = _preparar(pg_client)
    pendente_campos = _preparar(pg_client)
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("UPDATE sessoes_importacao_cadastral SET status = 'CONFIRMADA' WHERE uuid_publico = :id"), {"id": pendente_confirmacao["sessao_id"]})
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("UPDATE sessoes_importacao_cadastral SET status = 'FALHOU' WHERE uuid_publico = :id"), {"id": pendente_falha["sessao_id"]})
    for atribuicao in ("confirmado_em=clock_timestamp()", "resultado='{}'::jsonb"):
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(text(f"UPDATE sessoes_importacao_cadastral SET {atribuicao} WHERE uuid_publico=:id"), {"id": pendente_campos["sessao_id"]})

    finais = {}
    for estado in ("CONFIRMADA", "EXPIRADA", "FALHOU"):
        criada = _preparar(pg_client)
        finais[estado] = criada["sessao_id"]
        with engine.begin() as conn:
            if estado == "CONFIRMADA":
                conn.execute(text("UPDATE sessoes_importacao_cadastral SET status='CONFIRMADA', confirmado_em=clock_timestamp(), resultado='{}'::jsonb WHERE uuid_publico=:id"), {"id": criada["sessao_id"]})
            elif estado == "FALHOU":
                conn.execute(text("UPDATE sessoes_importacao_cadastral SET status='FALHOU', resultado='{}'::jsonb WHERE uuid_publico=:id"), {"id": criada["sessao_id"]})
            else:
                conn.execute(text("UPDATE sessoes_importacao_cadastral SET status='EXPIRADA' WHERE uuid_publico=:id"), {"id": criada["sessao_id"]})

    tentativas = (
        (finais["CONFIRMADA"], "status='EXPIRADA'"),
        (finais["CONFIRMADA"], "status='FALHOU'"),
        (finais["CONFIRMADA"], "resultado=jsonb_build_object('alterado', true)"),
        (finais["EXPIRADA"], "status='PENDENTE'"),
        (finais["EXPIRADA"], "status='CONFIRMADA', confirmado_em=clock_timestamp(), resultado='{}'::jsonb"),
        (finais["FALHOU"], "status='PENDENTE'"),
        (finais["FALHOU"], "status='CONFIRMADA', confirmado_em=clock_timestamp()"),
        (finais["FALHOU"], "resultado=jsonb_build_object('alterado', true)"),
    )
    for identificador, atribuicao in tentativas:
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(text(f"UPDATE sessoes_importacao_cadastral SET {atribuicao} WHERE uuid_publico=:id"), {"id": identificador})


def test_token_original_ausente_de_todas_as_colunas_e_digests_validos(pg_client, postgres_app):
    _, engine, _ = postgres_app
    criada = _preparar(pg_client)
    with engine.connect() as conn:
        contem_token = conn.scalar(text("""
            SELECT row_to_json(s)::text LIKE :padrao
            FROM sessoes_importacao_cadastral s WHERE uuid_publico = :id
        """), {"id": criada["sessao_id"], "padrao": f'%{criada["token_confirmacao"]}%'})
        hashes = conn.execute(text("SELECT token_hash, arquivo_sha256 FROM sessoes_importacao_cadastral WHERE uuid_publico=:id"), {"id": criada["sessao_id"]}).one()
    assert contem_token is False
    assert re.fullmatch(r"[0-9a-f]{64}", hashes.token_hash)
    assert re.fullmatch(r"[0-9a-f]{64}", hashes.arquivo_sha256)


def test_expiracao_persistida_nao_altera_cadastros_postgresql(pg_client, postgres_app):
    _, engine, _ = postgres_app
    antes = snapshot_cadastros(engine)
    with Session(engine) as db:
        sessao, _, _ = preparar_sessao(
            planilha_valida(), "dados.xlsx", db,
            agora=datetime.now(timezone.utc) - timedelta(hours=25),
        )
        sessao_id = sessao.uuid_publico
        registro_id = sessao.id
        db.commit()
    with Session(engine) as db:
        original = db.get(SessaoImportacaoCadastral, registro_id)
        staging_antes = (original.payload_normalizado, original.resumo, original.avisos)
    resposta = pg_client.get(f"/api/v1/importacoes-cadastrais/{sessao_id}")
    repetida = pg_client.get(f"/api/v1/importacoes-cadastrais/{sessao_id}")
    assert resposta.status_code == repetida.status_code == 200
    assert resposta.json() == repetida.json()
    assert resposta.json()["status"] == "EXPIRADA"
    with Session(engine) as db:
        atual = db.scalar(select(SessaoImportacaoCadastral).where(SessaoImportacaoCadastral.uuid_publico == sessao_id))
        assert (atual.payload_normalizado, atual.resumo, atual.avisos) == staging_antes
    assert snapshot_cadastros(engine) == antes


def test_uuid_inexistente_retorna_mensagem_segura_postgresql(pg_client):
    resposta = pg_client.get(f"/api/v1/importacoes-cadastrais/{uuid4()}")
    assert resposta.status_code == 404
    assert resposta.json() == {"detail": "Sessão de importação não encontrada."}


def test_migracao_08_downgrade_e_upgrade(postgres_app, alembic_runner):
    _, engine, _ = postgres_app
    alembic_runner(engine.url, "downgrade", "20260919_07")
    assert "sessoes_importacao_cadastral" not in inspect(engine).get_table_names()
    alembic_runner(engine.url, "upgrade", "head")
    assert "sessoes_importacao_cadastral" in inspect(engine).get_table_names()
