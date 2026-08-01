"""GET /api/conversations/{id}/messages — chat history rehydration on reload
(SPEC §14 T11.1). {id} is the client-generated sdk_session_id, the same value
POST /api/chat takes as conversation_id — never the internal DB primary key.

An id with no history yet (a brand-new client id) is a valid state, not a 404:
the repository contract already returns [] for an unseen session.
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.repositories.base import ConversationRepository, MessageOut

router = APIRouter()


class MessagesResponse(BaseModel):
    messages: list[MessageOut]


def get_conversations(request: Request) -> ConversationRepository:
    repo: ConversationRepository = request.app.state.conversations
    return repo


@router.get("/api/conversations/{conversation_id}/messages")
async def conversation_messages(conversation_id: str, request: Request) -> MessagesResponse:
    conversations = get_conversations(request)
    messages = await conversations.get_messages(conversation_id)
    return MessagesResponse(messages=messages)
