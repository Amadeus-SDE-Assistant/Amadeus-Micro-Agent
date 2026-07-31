"""In-memory implementations — unit tests and fast local fallback.

Must behave identically to the Postgres implementations: the conformance suite in
tests/unit/test_repositories.py runs against both.
"""

import uuid
from typing import Any

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


class MemoryConversationRepository:
    def __init__(self) -> None:
        self._by_session: dict[str, uuid.UUID] = {}
        self._messages: dict[uuid.UUID, list[MessageOut]] = {}

    async def ensure_conversation(self, sdk_session_id: str) -> uuid.UUID:
        if sdk_session_id not in self._by_session:
            cid = uuid.uuid4()
            self._by_session[sdk_session_id] = cid
            self._messages[cid] = []
        return self._by_session[sdk_session_id]

    async def add_message(
        self, conversation_id: uuid.UUID, role: str, content: dict[str, Any]
    ) -> None:
        self._messages[conversation_id].append(MessageOut(role=role, content=content))

    async def get_messages(self, sdk_session_id: str) -> list[MessageOut]:
        cid = self._by_session.get(sdk_session_id)
        return list(self._messages.get(cid, [])) if cid else []


class MemoryCredentialRepository:
    def __init__(self) -> None:
        self._rows: list[CredentialOut] = []

    async def add_many(
        self, candidate_id: uuid.UUID, credentials: list[CredentialIn]
    ) -> list[uuid.UUID]:
        ids: list[uuid.UUID] = []
        for cred in credentials:
            row = CredentialOut(
                id=uuid.uuid4(), candidate_id=candidate_id, **cred.model_dump()
            )
            self._rows.append(row)
            ids.append(row.id)
        return ids

    async def list_for(self, candidate_id: uuid.UUID) -> list[CredentialOut]:
        return [r for r in self._rows if r.candidate_id == candidate_id]


class MemoryDocumentRepository:
    def __init__(self) -> None:
        self._rows: dict[uuid.UUID, DocumentOut] = {}

    async def add(
        self, candidate_id: uuid.UUID, kind: str, uri: str, sha256: str
    ) -> DocumentOut:
        row = DocumentOut(
            id=uuid.uuid4(), kind=kind, uri=uri, sha256=sha256, status="uploaded"
        )
        self._rows[row.id] = row
        return row

    async def get_by_sha256(self, sha256: str) -> DocumentOut | None:
        return next((r for r in self._rows.values() if r.sha256 == sha256), None)

    async def get_by_id(self, document_id: uuid.UUID) -> DocumentOut | None:
        return self._rows.get(document_id)

    async def set_status(
        self,
        document_id: uuid.UUID,
        status: str,
        *,
        extraction_method: str | None = None,
        error: str | None = None,
    ) -> None:
        row = self._rows[document_id]
        self._rows[document_id] = row.model_copy(
            update={
                "status": status,
                "extraction_method": extraction_method or row.extraction_method,
                "error": error,
            }
        )


class MemoryJobRepository:
    def __init__(self) -> None:
        self._rows: dict[uuid.UUID, JobOut] = {}

    async def add(self, job: JobIn) -> JobOut:
        row = JobOut(id=uuid.uuid4(), **job.model_dump())
        self._rows[row.id] = row
        return row


class MemoryApplicationRepository:
    def __init__(self) -> None:
        self._rows: dict[uuid.UUID, ApplicationOut] = {}
        self.events: dict[uuid.UUID, list[tuple[str, dict[str, Any]]]] = {}

    async def create(
        self, candidate_id: uuid.UUID, job_id: uuid.UUID, status: str
    ) -> ApplicationOut:
        row = ApplicationOut(
            id=uuid.uuid4(), candidate_id=candidate_id, job_id=job_id, status=status
        )
        self._rows[row.id] = row
        self.events[row.id] = []
        return row

    async def get_by_id(self, application_id: uuid.UUID) -> ApplicationOut | None:
        return self._rows.get(application_id)

    async def set_status(self, application_id: uuid.UUID, status: str) -> None:
        row = self._rows[application_id]
        self._rows[application_id] = row.model_copy(update={"status": status})

    async def add_event(
        self, application_id: uuid.UUID, event_type: str, payload: dict[str, Any]
    ) -> None:
        self.events[application_id].append((event_type, payload))


class MemoryProfileRepository:
    def __init__(self) -> None:
        self._rows: dict[tuple[uuid.UUID, str], ProfileFactOut] = {}

    async def set(self, candidate_id: uuid.UUID, key: str, value: str) -> ProfileFactOut:
        existing = self._rows.get((candidate_id, key))
        row = ProfileFactOut(
            id=existing.id if existing else uuid.uuid4(),
            candidate_id=candidate_id,
            key=key,
            value=value,
        )
        self._rows[(candidate_id, key)] = row
        return row

    async def get_all(self, candidate_id: uuid.UUID) -> list[ProfileFactOut]:
        return [row for (cid, _key), row in self._rows.items() if cid == candidate_id]


class MemoryApprovalRepository:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, dict[str, Any]] = {}

    async def create(
        self,
        tool_name: str,
        intent: str,
        args: dict[str, Any],
        sdk_session_id: str | None = None,
    ) -> uuid.UUID:
        approval_id = uuid.uuid4()
        self.rows[approval_id] = {
            "tool_name": tool_name, "intent": intent, "args": args,
            "decision": None, "sdk_session_id": sdk_session_id,
        }
        return approval_id

    async def decide(self, approval_id: uuid.UUID, decision: str) -> bool:
        row = self.rows.get(approval_id)
        if row is None or row["decision"] is not None:
            return False
        row["decision"] = decision
        return True


class MemoryBlobStore:
    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}

    async def put(self, data: bytes, suggested_name: str) -> str:
        uri = f"memory://{uuid.uuid4().hex}/{suggested_name}"
        self._blobs[uri] = data
        return uri

    async def get(self, uri: str) -> bytes:
        return self._blobs[uri]
