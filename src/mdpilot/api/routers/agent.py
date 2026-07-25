"""Agent execution router"""
import json
import logging
import re
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from mdpilot.api.services.agent_service import AgentService
from mdpilot.api.services.chat_service import ChatService
from mdpilot.api.auth import verify_token
from mdpilot.database import get_session_dependency

router = APIRouter(
    prefix="/api/v1/agent",
    tags=["agent"],
    dependencies=[Depends(verify_token)]
)

agent_service = AgentService()
logger = logging.getLogger(__name__)
AGENT_STREAM_ERROR = "agent execution failed"


def clean_llm_response(content: str) -> str:
    if not content or not isinstance(content, str):
        return content if isinstance(content, str) else ""
    cleaned = re.sub(r'<think[\s\S]*?</think\s*>', '', content, flags=re.IGNORECASE)
    cleaned = re.sub(r'</?think>', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned)
    return cleaned.strip()


_MAX_PERSISTED_TOOL_OUTPUT = 2000


def _classify_llm_content(content: str) -> list[dict]:
    """Classify LLM content into thinking and response blocks."""
    if not content or not content.strip():
        return []
    blocks = []
    pattern = re.compile(r'<think(?:ing)?[^>]*>([\s\S]*?)</think(?:ing)?\s*>', re.IGNORECASE)
    last_end = 0
    for match in pattern.finditer(content):
        before = content[last_end:match.start()].strip()
        if before:
            blocks.append({"type": "response", "content": before})
        thinking = match.group(1).strip()
        if thinking:
            blocks.append({"type": "thinking", "content": thinking})
        last_end = match.end()
    remaining = content[last_end:].strip()
    remaining = re.sub(r'</?think(?:ing)?\s*>', '', remaining, flags=re.IGNORECASE).strip()
    if remaining:
        blocks.append({"type": "response", "content": remaining})
    if not blocks and content.strip():
        blocks.append({"type": "response", "content": content.strip()})
    return blocks


def _convert_tool_event(event: dict) -> dict | None:
    event_type = event.get("type", "")
    data = event.get("data", {})
    tc_id = str(data.get("tool_call_id", ""))
    name = str(data.get("tool", ""))
    backend_info = data.get("backend")
    has_backend = isinstance(backend_info, dict) and backend_info.get("node")

    if event_type == "tool_started":
        block: dict[str, Any] = {
            "type": "tool_call",
            "tool_call_id": tc_id,
            "name": name,
            "status": "running",
        }
        if data.get("input"):
            block["input"] = data["input"]
        if has_backend:
            block["backend"] = backend_info
        return block

    if event_type == "tool_completed":
        block = {
            "type": "tool_call",
            "tool_call_id": tc_id,
            "name": name,
            "status": "completed",
        }
        output = str(data.get("output", ""))
        if len(output) > _MAX_PERSISTED_TOOL_OUTPUT:
            output = output[:_MAX_PERSISTED_TOOL_OUTPUT] + "\n... [truncated]"
        block["result"] = output
        if has_backend:
            block["backend"] = backend_info
        return block

    if event_type == "tool_failed":
        return {
            "type": "tool_call",
            "tool_call_id": tc_id,
            "name": name,
            "status": "failed",
            "error": str(data.get("error", "")),
        }

    if event_type == "tool_retrying":
        block = {
            "type": "tool_call",
            "tool_call_id": tc_id,
            "name": name,
            "status": "running",
        }
        if has_backend:
            block["backend"] = backend_info
        return block

    return None


class _BlockCollector:
    def __init__(self):
        self.blocks: list[dict] = []
        self._pending_chunks: str = ""
        self._last_flushed: list[dict] = []

    def _flush_pending_chunks(self) -> None:
        if not self._pending_chunks:
            return
        classified = _classify_llm_content(self._pending_chunks)
        for block in classified:
            if self.blocks and self.blocks[-1].get("type") == block["type"]:
                self.blocks[-1]["content"] += "\n" + block["content"]
            else:
                self.blocks.append(block)
        self._pending_chunks = ""

    def feed(self, event: dict) -> None:
        event_type = event.get("type", "")
        if event_type == "llm_response":
            chunk = str(event.get("data", {}).get("content", ""))
            if chunk.strip():
                self._pending_chunks += chunk
            return
        if event_type in ("iteration_start", "progress_update"):
            return
        self._flush_pending_chunks()
        if event_type in ("loop_end", "complete"):
            return
        if event_type == "error":
            self.blocks.append({"type": "error", "message": str(event.get("data", {}).get("error", ""))})
            return
        block = _convert_tool_event(event)
        if block and block.get("tool_call_id"):
            self._upsert_tool_block(block)
        elif block:
            self.blocks.append(block)

    def flush_events(self) -> list[dict]:
        """Flush pending chunks and return newly classified blocks as SSE events."""
        if not self._pending_chunks:
            return []
        classified = _classify_llm_content(self._pending_chunks)
        self._pending_chunks = ""
        if not classified:
            return []
        events = []
        for block in classified:
            if self.blocks and self.blocks[-1].get("type") == block["type"]:
                self.blocks[-1]["content"] += "\n" + block["content"]
            else:
                self.blocks.append(block)
            events.append(block)
        return events

    def finalize(self) -> list[dict]:
        self._flush_pending_chunks()
        return self.blocks

    def reset(self) -> list[dict]:
        blocks = self.finalize()
        self.blocks = []
        self._pending_chunks = ""
        return blocks

    def _upsert_tool_block(self, block: dict):
        tc_id = block.get("tool_call_id", "")
        for i, existing in enumerate(self.blocks):
            if existing.get("type") == "tool_call" and existing.get("tool_call_id") == tc_id:
                self.blocks[i] = {**existing, **block}
                return
        self.blocks.append(block)


class AgentExecuteRequest(BaseModel):
    session_id: str
    prompt: str


class AgentExecuteResponse(BaseModel):
    session_id: str
    result: str


class ManualQueueItem(BaseModel):
    tool: str
    order: int
    enabled: bool = True
    constraints: dict[str, Any] = Field(default_factory=dict)


class AgentStreamRequest(BaseModel):
    session_id: str
    prompt: str
    mode: str = "agent"
    manual_queue: list[ManualQueueItem] = Field(default_factory=list)
    enabled_tools: list[str] = Field(default_factory=list)
    active_skills: list[str] = Field(default_factory=list)


def _sse(event_type: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event_type}\ndata: {payload}\n\n"


@router.post("/stream")
async def stream_agent_task(
    request: AgentStreamRequest,
    db_session: AsyncSession = Depends(get_session_dependency),
) -> StreamingResponse:
    """Stream LLM-driven task events as server-sent events."""

    collector = _BlockCollector()

    async def event_stream():
        result_text = ""
        has_result = False
        chat_service = ChatService(db_session)
        iteration_count = 0
        try:
            display_content = request.prompt
            if request.active_skills:
                display_content = f"/{request.active_skills[0]} {request.prompt}".strip()
            await chat_service.add_message(
                session_id=request.session_id,
                content=display_content,
                role="user",
            )
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            yield _sse("error", {"error": AGENT_STREAM_ERROR})
            return

        complete_data = None
        try:
            async for event in agent_service.execute_with_stream(
                session_id=request.session_id,
                prompt=request.prompt,
                mode=request.mode,
                manual_queue=[item.model_dump() for item in request.manual_queue],
                enabled_tools=request.enabled_tools,
                active_skills=request.active_skills,
            ):
                event_type = event.get("type", "message")
                data = event.get("data", {})

                if event_type == "iteration_start":
                    iteration_count += 1
                    if iteration_count > 1:
                        iteration_blocks = collector.reset()
                        if iteration_blocks:
                            try:
                                await chat_service.add_message(
                                    session_id=request.session_id,
                                    content="",
                                    role="assistant",
                                    extra_data={"agentBlocks": iteration_blocks},
                                )
                                await db_session.commit()
                            except Exception:
                                await db_session.rollback()
                        yield _sse("message_split", {})
                    yield _sse(event_type, data)
                    continue

                collector.feed(event)
                if event_type == "complete" and "result" in data:
                    result_text = clean_llm_response(data["result"])
                    has_result = True
                    complete_data = {**data, "result": result_text}
                    continue
                yield _sse(event_type, data)
                # After tool events, flush classified thinking/response blocks
                if event_type in ("tool_started", "tool_completed", "tool_failed"):
                    for block in collector.flush_events():
                        yield _sse(f"{block['type']}_block", block)
        except Exception as e:
            logger.error(f"Agent execution failed: {type(e).__name__}: {str(e)}", exc_info=True)
            yield _sse("error", {"error": AGENT_STREAM_ERROR})
            return

        collected_blocks = collector.finalize()
        # Emit final thinking/response blocks
        for block in collected_blocks:
            if block.get("type") in ("thinking", "response"):
                yield _sse(f"{block['type']}_block", block)
        try:
            if has_result or collected_blocks:
                extra: dict[str, Any] = {}
                if collected_blocks:
                    extra["agentBlocks"] = collected_blocks
                await chat_service.add_message(
                    session_id=request.session_id,
                    content=result_text if has_result else "",
                    role="assistant",
                    extra_data=extra if extra else None,
                )
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            yield _sse("error", {"error": AGENT_STREAM_ERROR})
            return

        if complete_data is not None:
            yield _sse("complete", complete_data)

    async def event_stream_with_cleanup():
        interrupted = False
        try:
            async for event in event_stream():
                yield event
        except GeneratorExit:
            interrupted = True
        except Exception:
            interrupted = True
        finally:
            if interrupted:
                try:
                    blocks = collector.finalize()
                    if blocks:
                        from mdpilot.database.session import get_session as get_db_session
                        async with get_db_session() as db:
                            from sqlalchemy import select, desc
                            from mdpilot.database.models.message import Message as DBMessage
                            from mdpilot.database.repositories.message import MessageRepository
                            result = await db.execute(
                                select(DBMessage)
                                .where(DBMessage.chat_id == UUID(request.session_id))
                                .where(DBMessage.role == "assistant")
                                .order_by(desc(DBMessage.created_at))
                                .limit(1)
                            )
                            latest = result.scalar_one_or_none()
                            if latest:
                                existing = latest.extra_data or {}
                                existing["interrupted"] = True
                                existing["agentBlocks"] = blocks
                                latest.extra_data = existing
                            else:
                                msg_repo = MessageRepository(db)
                                await msg_repo.create({
                                    "chat_id": UUID(request.session_id),
                                    "content": "",
                                    "role": "assistant",
                                    "extra_data": {"interrupted": True, "agentBlocks": blocks},
                                })
                            await db.commit()
                except Exception as e:
                    logger.error(f"Failed to persist interrupted state: {e}")
                # save agent state on interrupt too
                try:
                    await agent_service.save_agent_state(request.session_id)
                except Exception as e:
                    logger.error(f"Failed to save agent state on interrupt: {e}")
            else:
                try:
                    await agent_service.save_agent_state(request.session_id)
                except Exception as e:
                    logger.error(f"Failed to save agent state for session {request.session_id}: {e}")
            agent_service.cleanup_agent(request.session_id)

    return StreamingResponse(event_stream_with_cleanup(), media_type="text/event-stream")


@router.post("/execute", response_model=AgentExecuteResponse)
async def execute_agent_task(
    request: AgentExecuteRequest,
    db_session: AsyncSession = Depends(get_session_dependency),
) -> AgentExecuteResponse:
    """Execute LLM-driven task (non-streaming)"""
    chat_service = ChatService(db_session)
    result_text = ""

    try:
        await chat_service.add_message(
            session_id=request.session_id,
            content=request.prompt,
            role="user",
        )
        await db_session.commit()
    except Exception:
        await db_session.rollback()
        raise HTTPException(status_code=500, detail=AGENT_STREAM_ERROR)

    try:
        async for event in agent_service.execute_with_stream(
            session_id=request.session_id,
            prompt=request.prompt,
        ):
            if event["type"] == "complete":
                result_text = clean_llm_response(event["data"]["result"])
    except Exception:
        raise HTTPException(status_code=500, detail=AGENT_STREAM_ERROR)
    finally:
        try:
            await agent_service.save_agent_state(request.session_id)
        except Exception as e:
            logger.error(f"Failed to save agent state for session {request.session_id}: {e}")
        agent_service.cleanup_agent(request.session_id)

    try:
        await chat_service.add_message(
            session_id=request.session_id,
            content=result_text,
            role="assistant",
        )
        await db_session.commit()
    except Exception:
        await db_session.rollback()
        raise HTTPException(status_code=500, detail=AGENT_STREAM_ERROR)

    return AgentExecuteResponse(
        session_id=request.session_id,
        result=result_text,
    )
