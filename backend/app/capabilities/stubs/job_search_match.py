import uuid
from typing import Any

from claude_agent_sdk import tool

from app.agent.llm import raw_llm
from app.agent.prompts import JOB_MATCH_ASSESSMENT_PROMPT, JOB_SEARCH_MATCH_PROMPT
from app.capabilities.context import get_capability_context
from app.repositories.base import CredentialOut, JobOut


def _credential_line(c: CredentialOut) -> str:
    header = f"- [{c.kind}] {c.title}"
    if c.org:
        header += f" @ {c.org}"
    if c.start_date or c.end_date:
        header += f" ({c.start_date or '?'} to {c.end_date or 'present'})"
    bullets = c.body.get("bullets") if isinstance(c.body, dict) else None
    if bullets:
        header += "\n  " + "\n  ".join(f"- {b}" for b in bullets)
    return header


def _match_prompt_user(job: JobOut, credentials: list[CredentialOut], query: str) -> str:
    creds_text = "\n".join(_credential_line(c) for c in credentials) or "(no credentials on file)"
    parts = [
        f"Job: {job.title} at {job.company}",
        f"Job description:\n{job.jd_text}" if job.jd_text else "",
        f"Extracted details: {job.raw}" if job.raw else "",
        f"Candidate's stored background:\n{creds_text}",
    ]
    if query:
        parts.append(f"Candidate's question: {query}")
    return "\n\n".join(p for p in parts if p)


@tool(
    "job_search_match",
    "Help the user find and match against job opportunities: role archetypes, "
    "target companies, search strategy, and fit against their background. If "
    "job_id is given (a job saved via job_capture or application_track), "
    "assess real fit between that specific posting and the candidate's stored "
    "credentials. Leave job_id empty for general search guidance. Use when "
    "the user asks what jobs to look for or how well they'd match a role.",
    {"query": str, "job_id": str},
)
async def job_search_match(args: dict[str, Any]) -> dict[str, Any]:
    # Promoted (SPEC §15 T12.6): direct LLM comparison of stored Job/Credential
    # text when job_id is given — no pgvector (deferral item 4 stays open).
    # Without job_id, falls back to the original general-guidance behavior.
    ctx = get_capability_context()
    query = str(args.get("query", "")).strip()
    job_id = str(args.get("job_id", "")).strip()

    job: JobOut | None = None
    if job_id:
        try:
            target = uuid.UUID(job_id)
        except ValueError:
            target = None
        if target is not None:
            jobs = await ctx.jobs.list_for(ctx.candidate_id)
            job = next((j for j in jobs if j.id == target), None)

    if job is not None:
        credentials = await ctx.credentials.list_for(ctx.candidate_id)
        text = await raw_llm(
            system=JOB_MATCH_ASSESSMENT_PROMPT,
            user=_match_prompt_user(job, credentials, query),
        )
        return {"content": [{"type": "text", "text": text}]}

    text = await raw_llm(
        system=JOB_SEARCH_MATCH_PROMPT, user=query or "What kinds of jobs should I look for?"
    )
    return {"content": [{"type": "text", "text": text}]}
