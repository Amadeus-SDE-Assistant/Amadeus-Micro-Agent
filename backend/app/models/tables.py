"""SQLAlchemy models — SPEC §5 schema.

Notes:
- JSONB absorbs schema churn (contact, body, raw, payload, content).
- vector(1536) columns exist but stay unpopulated in v1 (deferral item 4).
- application_event is append-only — the long-term "massive state" table.
- document.sha256 is unique: upload dedupe (SPEC §10 reliability row 4).
"""

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIM = 1536


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSONB, datetime: DateTime(timezone=True)}


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(primary_key=True, default=uuid.uuid4)


def _now() -> Mapped[datetime]:
    return mapped_column(server_default=func.now())


class Candidate(Base):
    __tablename__ = "candidate"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(200))
    contact: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = _now()


class Credential(Base):
    """One decomposed unit of resume truth (experience, education, skill, ...)."""

    __tablename__ = "credential"

    id: Mapped[uuid.UUID] = _uuid_pk()
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidate.id"), index=True)
    # kind: experience|education|skill|project|certification
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(300))
    org: Mapped[str | None] = mapped_column(String(300))
    start_date: Mapped[str | None] = mapped_column(String(10))  # ISO date or YYYY-MM
    end_date: Mapped[str | None] = mapped_column(String(10))
    body: Mapped[dict[str, Any]] = mapped_column(default=dict)
    embedding: Mapped[Any | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    created_at: Mapped[datetime] = _now()


class Document(Base):
    """Blob pointer — the file itself lives in BlobStore, never in a row."""

    __tablename__ = "document"

    id: Mapped[uuid.UUID] = _uuid_pk()
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidate.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # resume|cover_letter|other
    uri: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    # uploaded|extracted|needs_ocr|decomposed|stored|failed
    extraction_method: Mapped[str | None] = mapped_column(String(20))  # text_layer|ocr
    error: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = _now()


class Job(Base):
    __tablename__ = "job"

    id: Mapped[uuid.UUID] = _uuid_pk()
    source: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(300))
    company: Mapped[str] = mapped_column(String(300))
    jd_text: Mapped[str] = mapped_column(Text)
    raw: Mapped[dict[str, Any]] = mapped_column(default=dict)
    embedding: Mapped[Any | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    created_at: Mapped[datetime] = _now()


class Application(Base):
    __tablename__ = "application"

    id: Mapped[uuid.UUID] = _uuid_pk()
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidate.id"), index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    applied_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = _now()


class ApplicationEvent(Base):
    """Append-only status history."""

    __tablename__ = "application_event"

    id: Mapped[uuid.UUID] = _uuid_pk()
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("application.id"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)
    at: Mapped[datetime] = _now()


class Conversation(Base):
    __tablename__ = "conversation"

    id: Mapped[uuid.UUID] = _uuid_pk()
    # Nullable: v1 is single-user with no auth; a default candidate arrives in P5/P6.
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("candidate.id"), nullable=True
    )
    sdk_session_id: Mapped[str] = mapped_column(String(64), unique=True)
    started_at: Mapped[datetime] = _now()


class Message(Base):
    __tablename__ = "message"

    id: Mapped[uuid.UUID] = _uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversation.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))  # user|assistant|system
    content: Mapped[dict[str, Any]] = mapped_column(default=dict)
    at: Mapped[datetime] = _now()


class Approval(Base):
    """Audit row for every write decision (SPEC §10 observability, §11 boundaries)."""

    __tablename__ = "approval"

    id: Mapped[uuid.UUID] = _uuid_pk()
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversation.id"), nullable=True
    )
    tool_name: Mapped[str] = mapped_column(String(200))
    intent: Mapped[str] = mapped_column(Text)  # descriptive one-liner (SPEC §11)
    args: Mapped[dict[str, Any]] = mapped_column(default=dict)
    decision: Mapped[str | None] = mapped_column(String(20))  # approved|denied|expired
    decided_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = _now()
