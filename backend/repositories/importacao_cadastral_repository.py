from hashlib import sha256
from hmac import compare_digest
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import SessaoImportacaoCadastral


class ImportacaoCadastralRepository:
    def __init__(self, db: Session):
        self.db = db

    def criar(self, **campos) -> SessaoImportacaoCadastral:
        sessao = SessaoImportacaoCadastral(**campos)
        self.db.add(sessao)
        self.db.flush()
        self.db.refresh(sessao)
        return sessao

    def obter(self, sessao_id: UUID, bloquear: bool = False) -> SessaoImportacaoCadastral | None:
        query = select(SessaoImportacaoCadastral).where(
            SessaoImportacaoCadastral.uuid_publico == sessao_id
        )
        if bloquear:
            query = query.with_for_update()
        return self.db.scalar(query)

    @staticmethod
    def token_valido(sessao: SessaoImportacaoCadastral, token: str) -> bool:
        alfabeto = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        formato_valido = len(token) == 43 and all(caractere in alfabeto for caractere in token)
        digest = sha256(token.encode("utf-8")).hexdigest()
        corresponde = compare_digest(sessao.token_hash, digest)
        return bool(formato_valido & corresponde)

    def marcar_expirada(self, sessao: SessaoImportacaoCadastral) -> bool:
        agora = self.db.scalar(select(func.now()))
        expira_em = sessao.expira_em
        if agora.tzinfo is None and expira_em.tzinfo is not None:
            agora = agora.replace(tzinfo=expira_em.tzinfo)
        elif agora.tzinfo is not None and expira_em.tzinfo is None:
            expira_em = expira_em.replace(tzinfo=agora.tzinfo)
        if sessao.status == "PENDENTE" and expira_em <= agora:
            sessao.status = "EXPIRADA"
            self.db.flush()
            return True
        return False
