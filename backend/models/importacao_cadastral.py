from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Integer, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class SessaoImportacaoCadastral(Base):
    __tablename__ = "sessoes_importacao_cadastral"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDENTE', 'CONFIRMADA', 'EXPIRADA', 'FALHOU')",
            name="ck_sessao_importacao_status",
        ),
        CheckConstraint(
            "expira_em > criado_em",
            name="ck_sessao_importacao_expiracao",
        ),
        CheckConstraint("length(token_hash) = 64 AND token_hash = lower(token_hash)", name="ck_sessao_importacao_token_hash"),
        CheckConstraint("length(arquivo_sha256) = 64 AND arquivo_sha256 = lower(arquivo_sha256)", name="ck_sessao_importacao_arquivo_sha256"),
        CheckConstraint("(status = 'CONFIRMADA') = (confirmado_em IS NOT NULL)", name="ck_sessao_importacao_confirmacao"),
        CheckConstraint("(status IN ('CONFIRMADA', 'FALHOU')) = (resultado IS NOT NULL)", name="ck_sessao_importacao_resultado"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uuid_publico: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, unique=True, default=uuid4, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    arquivo_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    versao_contrato: Mapped[str] = mapped_column(String(20), nullable=False)
    payload_normalizado: Mapped[dict] = mapped_column(JSON, nullable=False)
    resumo: Mapped[dict] = mapped_column(JSON, nullable=False)
    avisos: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDENTE")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resultado: Mapped[dict | None] = mapped_column(JSON)
