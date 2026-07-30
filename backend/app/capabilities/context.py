"""Capability dependency context.

Tool functions are module-level (the @tool decorator registers them), so their
dependencies arrive through this holder, set once at app startup. Capabilities
still depend only on repository protocols (SPEC §11).
"""

import uuid
from dataclasses import dataclass

from app.repositories.base import CredentialRepository


@dataclass
class CapabilityContext:
    credentials: CredentialRepository
    candidate_id: uuid.UUID


_context: CapabilityContext | None = None


def set_capability_context(context: CapabilityContext) -> None:
    global _context
    _context = context


def get_capability_context() -> CapabilityContext:
    if _context is None:
        raise RuntimeError("capability context not initialised (app startup missing)")
    return _context
