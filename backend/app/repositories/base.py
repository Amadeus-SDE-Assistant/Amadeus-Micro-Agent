"""Repository protocols (SPEC §3, §11: capabilities depend on these, never on
concrete implementations). DTOs are plain Pydantic models so callers never touch
SQLAlchemy entities.
"""

import uuid
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

CredentialKind = Literal["experience", "education", "skill", "project", "certification"]


class CredentialIn(BaseModel):
    kind: CredentialKind
    title: str
    org: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    body: dict[str, Any] = Field(default_factory=dict)


class CredentialOut(CredentialIn):
    id: uuid.UUID
    candidate_id: uuid.UUID


class MessageOut(BaseModel):
    role: str
    content: dict[str, Any]


class DocumentOut(BaseModel):
    id: uuid.UUID
    kind: str
    uri: str
    sha256: str
    status: str
    extraction_method: str | None = None
    error: str | None = None


class ConversationRepository(Protocol):
    async def ensure_conversation(self, sdk_session_id: str) -> uuid.UUID:
        """Get-or-create by external session id; returns the conversation pk."""
        ...

    async def add_message(
        self, conversation_id: uuid.UUID, role: str, content: dict[str, Any]
    ) -> None: ...

    async def get_messages(self, sdk_session_id: str) -> list[MessageOut]: ...


class CredentialRepository(Protocol):
    async def add_many(
        self, candidate_id: uuid.UUID, credentials: list[CredentialIn]
    ) -> list[uuid.UUID]: ...

    async def list_for(self, candidate_id: uuid.UUID) -> list[CredentialOut]: ...


class DocumentRepository(Protocol):
    async def add(
        self, candidate_id: uuid.UUID, kind: str, uri: str, sha256: str
    ) -> DocumentOut: ...

    async def get_by_sha256(self, sha256: str) -> DocumentOut | None: ...

    async def get_by_id(self, document_id: uuid.UUID) -> DocumentOut | None: ...

    async def set_status(
        self,
        document_id: uuid.UUID,
        status: str,
        *,
        extraction_method: str | None = None,
        error: str | None = None,
    ) -> None: ...


class ApprovalRepository(Protocol):
    """Audit trail for every write decision (SPEC §10, §11)."""

    async def create(
        self,
        tool_name: str,
        intent: str,
        args: dict[str, Any],
        sdk_session_id: str | None = None,
    ) -> uuid.UUID: ...

    async def decide(self, approval_id: uuid.UUID, decision: str) -> bool:
        """Record a decision; False if unknown or already decided."""
        ...


class BlobStore(Protocol):
    async def put(self, data: bytes, suggested_name: str) -> str:
        """Store bytes, return a URI."""
        ...

    async def get(self, uri: str) -> bytes: ...
