"""Repository conformance suite.

The same behavioral assertions run against the in-memory implementations here and
against Postgres in tests/integration/test_repositories_pg.py — that symmetry is
what makes the fakes trustworthy stand-ins (SPEC §9).
"""

import uuid

from app.repositories.base import (
    BlobStore,
    ConversationRepository,
    CredentialIn,
    CredentialRepository,
    DocumentRepository,
)
from app.repositories.memory import (
    MemoryBlobStore,
    MemoryConversationRepository,
    MemoryCredentialRepository,
    MemoryDocumentRepository,
)


async def assert_conversation_contract(repo: ConversationRepository) -> None:
    sid = f"s-{uuid.uuid4().hex[:8]}"
    cid = await repo.ensure_conversation(sid)
    assert await repo.ensure_conversation(sid) == cid  # idempotent get-or-create

    await repo.add_message(cid, "user", {"text": "hello"})
    await repo.add_message(cid, "assistant", {"text": "hi there"})
    messages = await repo.get_messages(sid)
    assert [(m.role, m.content["text"]) for m in messages] == [
        ("user", "hello"),
        ("assistant", "hi there"),
    ]
    assert await repo.get_messages("never-seen") == []


async def assert_credential_contract(
    repo: CredentialRepository, candidate_id: uuid.UUID
) -> None:
    ids = await repo.add_many(
        candidate_id,
        [
            CredentialIn(kind="experience", title="Software Engineer", org="Acme",
                         start_date="2021-01", end_date="2023-06",
                         body={"bullets": ["built things"]}),
            CredentialIn(kind="skill", title="Python"),
        ],
    )
    assert len(ids) == 2
    rows = await repo.list_for(candidate_id)
    assert {r.kind for r in rows} == {"experience", "skill"}
    assert rows[0].candidate_id == candidate_id
    assert await repo.list_for(uuid.uuid4()) == []


async def assert_document_contract(repo: DocumentRepository, candidate_id: uuid.UUID) -> None:
    sha = uuid.uuid4().hex + uuid.uuid4().hex  # 64 chars
    doc = await repo.add(candidate_id, "resume", "file:///x.pdf", sha)
    assert doc.status == "uploaded"

    found = await repo.get_by_sha256(sha)
    assert found is not None and found.id == doc.id  # dedupe lookup
    assert await repo.get_by_sha256("0" * 64) is None

    await repo.set_status(doc.id, "extracted", extraction_method="text_layer")
    updated = await repo.get_by_sha256(sha)
    assert updated is not None
    assert updated.status == "extracted"
    assert updated.extraction_method == "text_layer"

    await repo.set_status(doc.id, "failed", error="boom")
    failed = await repo.get_by_sha256(sha)
    assert failed is not None and failed.status == "failed" and failed.error == "boom"


async def assert_blob_contract(store: BlobStore) -> None:
    uri = await store.put(b"pdf bytes", "resume.pdf")
    assert await store.get(uri) == b"pdf bytes"


async def test_memory_conversation_contract() -> None:
    await assert_conversation_contract(MemoryConversationRepository())


async def test_memory_credential_contract() -> None:
    await assert_credential_contract(MemoryCredentialRepository(), uuid.uuid4())


async def test_memory_document_contract() -> None:
    await assert_document_contract(MemoryDocumentRepository(), uuid.uuid4())


async def test_memory_blob_contract() -> None:
    await assert_blob_contract(MemoryBlobStore())
