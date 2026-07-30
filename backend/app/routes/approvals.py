"""POST /api/approvals/{id} — resolve a pending approval (SPEC §11)."""

import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.agent.approvals import APPROVED, DENIED, ApprovalGate

router = APIRouter()


class ApprovalDecision(BaseModel):
    decision: Literal["approved", "denied"]


@router.post("/api/approvals/{approval_id}")
async def resolve_approval(
    approval_id: uuid.UUID, body: ApprovalDecision, request: Request
) -> dict[str, str]:
    gate: ApprovalGate = request.app.state.approval_gate
    decision = APPROVED if body.decision == "approved" else DENIED
    outcome = gate.resolve(approval_id, decision)
    if outcome == "unknown":
        raise HTTPException(status_code=404, detail="no pending approval with this id")
    if outcome == "already_decided":
        raise HTTPException(status_code=409, detail="approval already decided")
    return {"status": "ok", "decision": body.decision}
