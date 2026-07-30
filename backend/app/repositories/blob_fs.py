"""Filesystem BlobStore — swaps to S3/MinIO by replacing this one class (SPEC §3)."""

import re
import uuid
from pathlib import Path

import anyio


class FsBlobStore:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    async def put(self, data: bytes, suggested_name: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", suggested_name)[-100:] or "blob"
        path = self._root / uuid.uuid4().hex / safe
        path.parent.mkdir(parents=True)
        await anyio.Path(path).write_bytes(data)
        return path.as_posix()

    async def get(self, uri: str) -> bytes:
        path = _resolve_within(self._root, uri)
        return await anyio.Path(path).read_bytes()


def _resolve_within(root: Path, uri: str) -> Path:
    path = Path(uri).resolve()
    if not path.is_relative_to(root):
        raise ValueError("blob uri escapes the store root")
    return path
