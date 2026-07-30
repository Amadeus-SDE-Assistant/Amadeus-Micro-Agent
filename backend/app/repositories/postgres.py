"""Postgres implementations of the repository protocols."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import session_scope
from app.models import Conversation, Credential, Document, Message
from app.repositories.base import (
    CredentialIn,
    CredentialOut,
    DocumentOut,
    MessageOut,
)


class PgConversationRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def ensure_conversation(self, sdk_session_id: str) -> uuid.UUID:
        async with session_scope(self._factory) as session:
            existing = await session.scalar(
                select(Conversation).where(Conversation.sdk_session_id == sdk_session_id)
            )
            if existing is not None:
                return existing.id
            row = Conversation(sdk_session_id=sdk_session_id)
            session.add(row)
            await session.flush()
            return row.id

    async def add_message(
        self, conversation_id: uuid.UUID, role: str, content: dict[str, Any]
    ) -> None:
        async with session_scope(self._factory) as session:
            session.add(
                Message(conversation_id=conversation_id, role=role, content=content)
            )

    async def get_messages(self, sdk_session_id: str) -> list[MessageOut]:
        async with session_scope(self._factory) as session:
            conv = await session.scalar(
                select(Conversation).where(Conversation.sdk_session_id == sdk_session_id)
            )
            if conv is None:
                return []
            rows = await session.scalars(
                select(Message).where(Message.conversation_id == conv.id).order_by(Message.at)
            )
            return [MessageOut(role=m.role, content=m.content) for m in rows]


class PgCredentialRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def add_many(
        self, candidate_id: uuid.UUID, credentials: list[CredentialIn]
    ) -> list[uuid.UUID]:
        async with session_scope(self._factory) as session:
            rows = [
                Credential(candidate_id=candidate_id, **cred.model_dump())
                for cred in credentials
            ]
            session.add_all(rows)
            await session.flush()
            return [r.id for r in rows]

    async def list_for(self, candidate_id: uuid.UUID) -> list[CredentialOut]:
        async with session_scope(self._factory) as session:
            rows = await session.scalars(
                select(Credential)
                .where(Credential.candidate_id == candidate_id)
                .order_by(Credential.created_at)
            )
            return [
                CredentialOut(
                    id=r.id,
                    candidate_id=r.candidate_id,
                    kind=r.kind,
                    title=r.title,
                    org=r.org,
                    start_date=r.start_date,
                    end_date=r.end_date,
                    body=r.body,
                )
                for r in rows
            ]


class PgDocumentRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def add(
        self, candidate_id: uuid.UUID, kind: str, uri: str, sha256: str
    ) -> DocumentOut:
        async with session_scope(self._factory) as session:
            row = Document(candidate_id=candidate_id, kind=kind, uri=uri, sha256=sha256)
            session.add(row)
            await session.flush()
            return DocumentOut(
                id=row.id, kind=row.kind, uri=row.uri, sha256=row.sha256, status=row.status
            )

    async def get_by_sha256(self, sha256: str) -> DocumentOut | None:
        async with session_scope(self._factory) as session:
            row = await session.scalar(select(Document).where(Document.sha256 == sha256))
            if row is None:
                return None
            return DocumentOut(
                id=row.id,
                kind=row.kind,
                uri=row.uri,
                sha256=row.sha256,
                status=row.status,
                extraction_method=row.extraction_method,
                error=row.error,
            )

    async def set_status(
        self,
        document_id: uuid.UUID,
        status: str,
        *,
        extraction_method: str | None = None,
        error: str | None = None,
    ) -> None:
        async with session_scope(self._factory) as session:
            row = await session.get(Document, document_id)
            if row is None:
                raise KeyError(f"document {document_id} not found")
            row.status = status
            if extraction_method is not None:
                row.extraction_method = extraction_method
            row.error = error
