"""LLM extraction: pasted job-posting text → structured JobIn (SPEC §15 T12.3).

Same shape as ingestion/decompose.py: strict JSON contract, parsing separated from
the LLM call for cheap tests, malformed/non-job-like input raises a typed error
rather than propagating a crash.
"""

import json

from pydantic import TypeAdapter, ValidationError

from app.agent.llm import raw_llm
from app.agent.prompts import JOB_EXTRACT_PROMPT
from app.repositories.base import JobIn

_adapter = TypeAdapter(JobIn)


class JobExtractionError(Exception):
    pass


def parse_job(raw: str) -> JobIn:
    """Parse + validate model output. Separated from the LLM call for cheap tests."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    try:
        job = _adapter.validate_python(json.loads(cleaned))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise JobExtractionError(f"model output failed validation: {exc}") from exc
    if not job.title.strip() or not job.company.strip():
        raise JobExtractionError("couldn't identify a title and company in that text")
    return job


async def extract_job(posting_text: str) -> JobIn:
    raw = await raw_llm(system=JOB_EXTRACT_PROMPT, user=posting_text)
    return parse_job(raw)
