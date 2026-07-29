"""POST /api/chat — streams AgentEvents as SSE.

The error envelope rides the stream as an `error` event; the connection itself always
completes cleanly (SPEC §10: never a hung or dropped stream).
"""

from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sse_starlette import EventSourceResponse, ServerSentEvent

from app.agent.service import AgentService

router = APIRouter()


class ChatRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=8000)


def get_agent_service(request: Request) -> AgentService:
    service: AgentService = request.app.state.agent_service
    return service


@router.post("/api/chat")
async def chat(body: ChatRequest, request: Request) -> EventSourceResponse:
    service = get_agent_service(request)

    async def stream() -> AsyncIterator[ServerSentEvent]:
        async for event in service.chat(body.conversation_id, body.message):
            yield ServerSentEvent(event=event.type.value, data=event.model_dump_json())

    return EventSourceResponse(stream())
