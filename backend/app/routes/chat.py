"""POST /api/chat — streams AgentEvents as SSE.

The error envelope rides the stream as an `error` event; the connection itself always
completes cleanly (SPEC §10: never a hung or dropped stream). History persists per
turn: the user message before the agent runs, the assistant text after. A DB outage
before the turn starts is a 503 (SPEC §10 reliability row 3); one after the stream is
open becomes an `error` event.
"""

import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sse_starlette import EventSourceResponse, ServerSentEvent

from app.agent.events import AgentEventType
from app.agent.service import AgentService
from app.repositories.base import ConversationRepository

logger = logging.getLogger("app.chat")

router = APIRouter()


class ChatRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=8000)


def get_agent_service(request: Request) -> AgentService:
    service: AgentService = request.app.state.agent_service
    return service


def get_conversations(request: Request) -> ConversationRepository:
    repo: ConversationRepository = request.app.state.conversations
    return repo


@router.post("/api/chat")
async def chat(body: ChatRequest, request: Request) -> EventSourceResponse:
    service = get_agent_service(request)
    conversations = get_conversations(request)

    try:
        conversation_pk = await conversations.ensure_conversation(body.conversation_id)
        await conversations.add_message(conversation_pk, "user", {"text": body.message})
    except Exception as exc:
        logger.exception("chat persistence unavailable")
        raise HTTPException(
            status_code=503,
            detail="The database is unavailable; your message was not saved. "
            "Please try again shortly.",
        ) from exc

    async def stream() -> AsyncIterator[ServerSentEvent]:
        assistant_parts: list[str] = []
        async for event in service.chat(body.conversation_id, body.message):
            if event.type == AgentEventType.TEXT and event.text:
                assistant_parts.append(event.text)
            yield ServerSentEvent(event=event.type.value, data=event.model_dump_json())
        if assistant_parts:
            try:
                await conversations.add_message(
                    conversation_pk, "assistant", {"text": "".join(assistant_parts)}
                )
            except Exception:
                logger.exception("failed to persist assistant message")

    return EventSourceResponse(stream())
