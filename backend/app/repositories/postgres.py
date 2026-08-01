"""Postgres implementations of the repository protocols."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import session_scope
from app.models import (
    Application,
    ApplicationEvent,
    Approval,
    Candidate,
    Conversation,
    Credential,
    Document,
    Job,
    Message,
    ProfileFact,
)
from app.repositories.base import (
    ApplicationOut,
    CredentialIn,
    CredentialOut,
    DocumentOut,
    JobIn,
    JobOut,
    MessageOut,
    ProfileFactOut,
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
            # model_validate re-validates kind against the Literal at the boundary.
            return [
                CredentialOut.model_validate(
                    {
                        "id": r.id,
                        "candidate_id": r.candidate_id,
                        "kind": r.kind,
                        "title": r.title,
                        "org": r.org,
                        "start_date": r.start_date,
                        "end_date": r.end_date,
                        "body": r.body,
                    }
                )
                for r in rows
            ]


def _document_out(row: Document) -> DocumentOut:
    return DocumentOut(
        id=row.id,
        kind=row.kind,
        uri=row.uri,
        sha256=row.sha256,
        status=row.status,
        extraction_method=row.extraction_method,
        error=row.error,
    )


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
            return _document_out(row)

    async def get_by_sha256(self, sha256: str) -> DocumentOut | None:
        async with session_scope(self._factory) as session:
            row = await session.scalar(select(Document).where(Document.sha256 == sha256))
            return _document_out(row) if row is not None else None

    async def get_by_id(self, document_id: uuid.UUID) -> DocumentOut | None:
        async with session_scope(self._factory) as session:
            row = await session.get(Document, document_id)
            return _document_out(row) if row is not None else None

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


class PgJobRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def add(self, job: JobIn) -> JobOut:
        async with session_scope(self._factory) as session:
            row = Job(**job.model_dump())
            session.add(row)
            await session.flush()
            return JobOut(id=row.id, **job.model_dump())

    async def list_for(self, candidate_id: uuid.UUID) -> list[JobOut]:
        async with session_scope(self._factory) as session:
            rows = await session.scalars(select(Job).order_by(Job.created_at))
            return [
                JobOut(
                    id=r.id,
                    title=r.title,
                    company=r.company,
                    source=r.source,
                    jd_text=r.jd_text,
                    raw=r.raw,
                )
                for r in rows
            ]


def _application_out(row: Application) -> ApplicationOut:
    return ApplicationOut(
        id=row.id, candidate_id=row.candidate_id, job_id=row.job_id, status=row.status
    )


class PgApplicationRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def create(
        self, candidate_id: uuid.UUID, job_id: uuid.UUID, status: str
    ) -> ApplicationOut:
        async with session_scope(self._factory) as session:
            row = Application(candidate_id=candidate_id, job_id=job_id, status=status)
            session.add(row)
            await session.flush()
            return _application_out(row)

    async def get_by_id(self, application_id: uuid.UUID) -> ApplicationOut | None:
        async with session_scope(self._factory) as session:
            row = await session.get(Application, application_id)
            return _application_out(row) if row is not None else None

    async def set_status(self, application_id: uuid.UUID, status: str) -> None:
        async with session_scope(self._factory) as session:
            row = await session.get(Application, application_id)
            if row is None:
                raise KeyError(f"application {application_id} not found")
            row.status = status

    async def add_event(
        self, application_id: uuid.UUID, event_type: str, payload: dict[str, Any]
    ) -> None:
        async with session_scope(self._factory) as session:
            session.add(
                ApplicationEvent(
                    application_id=application_id, event_type=event_type, payload=payload
                )
            )


class PgProfileRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def set(self, candidate_id: uuid.UUID, key: str, value: str) -> ProfileFactOut:
        async with session_scope(self._factory) as session:
            stmt = (
                pg_insert(ProfileFact)
                .values(candidate_id=candidate_id, key=key, value=value)
                .on_conflict_do_update(
                    index_elements=[ProfileFact.candidate_id, ProfileFact.key],
                    set_={"value": value, "updated_at": func.now()},
                )
                .returning(ProfileFact)
            )
            row = (await session.execute(stmt)).scalar_one()
            return ProfileFactOut(
                id=row.id, candidate_id=row.candidate_id, key=row.key, value=row.value
            )

    async def get_all(self, candidate_id: uuid.UUID) -> list[ProfileFactOut]:
        async with session_scope(self._factory) as session:
            rows = await session.scalars(
                select(ProfileFact)
                .where(ProfileFact.candidate_id == candidate_id)
                .order_by(ProfileFact.key)
            )
            return [
                ProfileFactOut(id=r.id, candidate_id=r.candidate_id, key=r.key, value=r.value)
                for r in rows
            ]


class PgApprovalRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def create(
        self,
        tool_name: str,
        intent: str,
        args: dict[str, Any],
        sdk_session_id: str | None = None,
    ) -> uuid.UUID:
        async with session_scope(self._factory) as session:
            conversation_id: uuid.UUID | None = None
            if sdk_session_id is not None:
                conversation_id = await session.scalar(
                    select(Conversation.id).where(
                        Conversation.sdk_session_id == sdk_session_id
                    )
                )
            row = Approval(
                tool_name=tool_name,
                intent=intent,
                args=args,
                conversation_id=conversation_id,
            )
            session.add(row)
            await session.flush()
            return row.id

    async def decide(self, approval_id: uuid.UUID, decision: str) -> bool:
        async with session_scope(self._factory) as session:
            row = await session.get(Approval, approval_id)
            if row is None or row.decision is not None:
                return False
            row.decision = decision
            row.decided_at = datetime.now(UTC)
            return True


async def ensure_default_candidate(factory: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    """v1 is single-user: one implicit candidate owns everything (SPEC §12 q2)."""
    async with session_scope(factory) as session:
        existing = await session.scalar(
            select(Candidate).where(Candidate.name == "default")
        )
        if existing is not None:
            return existing.id
        row = Candidate(name="default", contact={})
        session.add(row)
        await session.flush()
        return row.id
