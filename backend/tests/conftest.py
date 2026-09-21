"""Configuração mínima dos testes que não acessam o banco oficial."""

import os


os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
