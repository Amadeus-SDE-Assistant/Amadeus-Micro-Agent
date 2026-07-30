"""LLM decomposition: extracted resume text → typed credentials (SPEC §4).

Strict contract: the model must return a JSON array validating against
list[CredentialIn]; any parse/validation failure fails the document with a reason
(SPEC §10 reliability row 5) — no partial writes.
"""

import json

from pydantic import TypeAdapter, ValidationError

from app.agent.llm import raw_llm
from app.agent.prompts import DECOMPOSE_PROMPT
from app.repositories.base import CredentialIn

_adapter = TypeAdapter(list[CredentialIn])


class DecompositionError(Exception):
    pass


def parse_credentials(raw: str) -> list[CredentialIn]:
    """Parse + validate model output. Separated from the LLM call for cheap tests.

    Kind validity is enforced by CredentialIn.kind's Literal type — invalid kinds
    fail Pydantic validation directly (SPEC §8: Pydantic at I/O boundaries).
    """
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    try:
        credentials = _adapter.validate_python(json.loads(cleaned))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise DecompositionError(f"model output failed validation: {exc}") from exc
    if not credentials:
        raise DecompositionError("no credentials found in resume text")
    return credentials


async def decompose(resume_text: str) -> list[CredentialIn]:
    raw = await raw_llm(system=DECOMPOSE_PROMPT, user=resume_text)
    return parse_credentials(raw)
