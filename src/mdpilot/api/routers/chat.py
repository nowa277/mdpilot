"""Chat management router."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mdpilot.api.models.chat import (
    ChatSession,
    ChatSessionCreate,
    Message,
    MessageCreate,
    MessageHistory,
)
from mdpilot.api.services.chat_service import ChatService
from mdpilot.api.auth import verify_token
from mdpilot.database import get_session_dependency

router = APIRouter(
    prefix="/api/v1/chat",
    tags=["chat"],
    dependencies=[Depends(verify_token)]
)


@router.post("/sessions", response_model=ChatSession)
async def create_session(
    session_data: ChatSessionCreate,
    db_session: AsyncSession = Depends(get_session_dependency),
) -> ChatSession:
    """Create a new chat session."""
    service = ChatService(db_session)
    chat_session = await service.create_session(
        user_id=session_data.user_id,
        metadata=session_data.metadata,
    )
    await db_session.commit()
    return chat_session


@router.post("/sessions/{session_id}/messages", response_model=Message)
async def send_message(
    session_id: str,
    message_data: MessageCreate,
    db_session: AsyncSession = Depends(get_session_dependency),
) -> Message:
    """Send a message to a chat session."""
    service = ChatService(db_session)
    message = await service.add_message(
        session_id=session_id,
        content=message_data.content,
        role=message_data.role,
    )
    if message is None:
        raise HTTPException(status_code=404, detail="Session not found")
    await db_session.commit()
    return message


@router.get("/sessions/{session_id}/messages", response_model=MessageHistory)
async def get_messages(
    session_id: str,
    limit: int = 100,
    offset: int = 0,
    db_session: AsyncSession = Depends(get_session_dependency),
) -> MessageHistory:
    """Get message history for a session."""
    service = ChatService(db_session)
    result = await service.get_messages(session_id, limit=limit, offset=offset)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")

    messages, total = result
    return MessageHistory(
        messages=messages,
        total=total,
        limit=limit,
        offset=offset,
    )
