"""profile_save / profile_recall — generic personal-fact store (SPEC §15 T12.2).

profile_save is the one write; the whole batch of facts in a single call sits
behind ONE approval, same batching rule as resume_store (SPEC §11).
profile_recall is read-only — no approval gate.
"""

from typing import Any

from claude_agent_sdk import tool

from app.capabilities.context import get_capability_context


@tool(
    "profile_save",
    "Save one or more personal facts to the user's profile: preferences, goals, "
    "constraints, or anything else about them worth remembering beyond their "
    "resume credentials (e.g. 'only wants remote roles', 'targeting fintech'). "
    "Use when the user shares something about themselves they want remembered "
    "for later. Pass facts as key/value pairs with short, stable keys.",
    {"facts": dict},
)
async def profile_save(args: dict[str, Any]) -> dict[str, Any]:
    ctx = get_capability_context()
    facts = args.get("facts")
    if not isinstance(facts, dict) or not facts:
        return {"content": [{"type": "text", "text": "No facts to save."}]}
    saved: list[str] = []
    for key, value in facts.items():
        await ctx.profile.set(ctx.candidate_id, str(key), str(value))
        saved.append(str(key))
    return {"content": [{"type": "text", "text": f"Saved to your profile: {', '.join(saved)}."}]}


@tool(
    "profile_recall",
    "Look up personal facts previously saved to the user's profile: preferences, "
    "goals, constraints. Use when the user asks what you know or remember about "
    "them, or when a saved preference would help answer their question.",
    {},
)
async def profile_recall(_args: dict[str, Any]) -> dict[str, Any]:
    ctx = get_capability_context()
    facts = await ctx.profile.get_all(ctx.candidate_id)
    if not facts:
        return {"content": [{"type": "text", "text": "Nothing saved to your profile yet."}]}
    lines = "\n".join(f"- {f.key}: {f.value}" for f in facts)
    return {"content": [{"type": "text", "text": f"Here's what I have on your profile:\n{lines}"}]}
