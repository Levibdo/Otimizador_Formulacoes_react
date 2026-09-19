"""PostgreSQL real, com migrações e um schema descartável por teste."""
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from db.session import get_db
from routers import (
    apresentacoes_router,
    cenarios_router,
    materias_primas_router,
    projetos_router,
    regulatorio_router,
)


@pytest.fixture
def alembic_runner():
    def executar(url, comando, revisao):
        env = {**os.environ, "DATABASE_URL": url.render_as_string(hide_password=False)}
        migration = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", comando, revisao],
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        migration_error = migration.stderr.replace(env["DATABASE_URL"], "[DATABASE_URL]")
        if url.password:
            migration_error = migration_error.replace(url.password, "[REDACTED]")
        assert migration.returncode == 0, migration_error

    return executar


@pytest.fixture
def postgres_app(alembic_runner):
    raw_url = os.getenv("TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("Defina TEST_DATABASE_URL para executar contra PostgreSQL real.")
    url = make_url(raw_url)
    assert url.get_backend_name() == "postgresql", "TEST_DATABASE_URL deve usar PostgreSQL"
    schema = "test_" + uuid4().hex
    admin = create_engine(url)
    engine = None
    try:
        with admin.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        isolated_url = url.update_query_dict({
            "options": f"-csearch_path={schema} -clock_timeout=15000 -cstatement_timeout=20000",
            "application_name": schema,
        })
        alembic_runner(isolated_url, "upgrade", "head")
        engine = create_engine(isolated_url, pool_size=10)
        app = FastAPI()
        for router in (projetos_router, materias_primas_router, apresentacoes_router, cenarios_router, regulatorio_router):
            app.include_router(router)

        def database_session():
            with Session(engine, expire_on_commit=False) as session:
                yield session

        app.dependency_overrides[get_db] = database_session
        yield app, engine, schema
    finally:
        if engine is not None:
            engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def pg_client(postgres_app):
    with TestClient(postgres_app[0]) as client:
        yield client
