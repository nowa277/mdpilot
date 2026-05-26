"""Agent service - Bridge between API and ReActLoop"""
import asyncio
import itertools
import logging
from contextlib import suppress
from typing import AsyncGenerator, Dict

from mdpilot.agent.base import AgentBase
from mdpilot.agent.react_agent import ReActAgent
from mdpilot.agent.router import AgentRouter
from mdpilot.agent.orchestrator import AgentOrchestrator
from mdpilot.config.loader import load_config
from mdpilot.agent.events import (
    ITERATION_START, LLM_RESPONSE, TOOL_CALL,
    TOOL_RESULT, LOOP_END, ERROR, PROGRESS_UPDATE
)
from mdpilot.database.session import get_session
from mdpilot.database.repositories.session import SessionRepository

logger = logging.getLogger(__name__)


def _sanitize_messages(messages: list[dict]) -> list[dict]:
    """Remove incomplete tool_call sequences from restored context.

    After an interrupt, the saved context may contain assistant messages with
    tool_calls but no corresponding tool role result messages.  Sending these
    to the LLM API causes a BadRequestError (code 2013).  This function strips
    any trailing incomplete tool sequences and their corresponding tool results.

    Rules:
    - Every assistant tool_calls message must be followed by tool results for
      ALL call IDs before the next user/assistant (non-tool) message.
    - If an incomplete sequence is found, remove the dangling assistant
      tool_calls message and any partial tool results that follow it.
    """
    if not messages:
        return messages

    # Pass 1: collect all tool_call_ids from assistant messages
    all_call_ids = set()
    for msg in messages:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                tc_id = tc.get("id")
                if tc_id:
                    all_call_ids.add(tc_id)

    # Pass 2: collect all tool_call_ids that have results
    answered_ids = set()
    for msg in messages:
        if msg.get("role") == "tool" and msg.get("tool_call_id"):
            answered_ids.add(msg["tool_call_id"])

    # If all calls have results, nothing to strip
    unanswered = all_call_ids - answered_ids
    if not unanswered:
        return messages

    # Pass 3: strip from the first unanswered tool_call onward
    # Find the assistant message that contains the first unanswered call
    strip_from = len(messages)
    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                if tc.get("id") in unanswered:
                    strip_from = i
                    break
        if strip_from < len(messages):
            break

    if strip_from >= len(messages):
        return messages

    result = messages[:strip_from]
    # Strip trailing user messages to avoid consecutive user msgs on restore
    while result and result[-1].get("role") == "user":
        result.pop()

    logger.info(
        "Sanitizing context: %d → %d messages (%d unanswered tool calls)",
        len(messages), len(result), len(unanswered),
    )
    return result


class AgentService:
    """Manage ReActLoop instances and handle event streaming"""

    def __init__(self, max_concurrent: int = 5):
        self.config = load_config()
        self._agents: Dict[str, AgentBase] = {}
        self._router = AgentRouter()
        self._concurrent_limit = asyncio.Semaphore(max_concurrent)
        self._tool_id_counter = itertools.count()

    async def get_or_create_agent(self, session_id: str, prompt: str = "") -> AgentBase:
        """Get or create agent instance for session with DB persistence"""
        if session_id in self._agents:
            agent = self._agents[session_id]
            clean = _sanitize_messages(agent._context._messages)
            if len(clean) == len(agent._context._messages):
                return agent
            # Corrupted (interrupt race condition), force fresh from DB
            del self._agents[session_id]

        agent_cls = self._router.select_agent(prompt) if prompt else ReActAgent
        use_coordination = self.config.agent.use_coordination
        if agent_cls is ReActAgent:
            agent = agent_cls(self.config, use_coordination=use_coordination)
        else:
            agent = agent_cls(self.config)

        async with get_session() as db:
            repo = SessionRepository(db)
            saved = await repo.load_session(session_id)
            if saved:
                agent._context._system_prompt = saved.system_prompt
                agent._context._messages = _sanitize_messages(saved.context_messages)
                agent._budget._iteration = saved.iteration_count
                agent._budget._max_iterations = saved.max_iterations

        self._agents[session_id] = agent
        return agent

    async def save_agent_state(self, session_id: str):
        """Persist agent state to database"""
        if session_id not in self._agents:
            return

        agent = self._agents[session_id]
        clean_messages = _sanitize_messages(agent._context._messages)
        async with get_session() as db:
            repo = SessionRepository(db)
            await repo.save_session(
                session_id=session_id,
                context_messages=clean_messages,
                system_prompt=agent._context._system_prompt,
                iteration_count=agent._budget._iteration,
                max_iterations=agent._budget._max_iterations
            )

    async def execute_with_stream(
        self,
        session_id: str,
        prompt: str,
        mode: str = "agent",
        manual_queue: list[dict] | None = None,
        enabled_tools: list[str] | None = None,
    ) -> AsyncGenerator[Dict, None]:
        """Execute task and stream events in real-time with concurrency control"""
        async with self._concurrent_limit:
            agent = await self.get_or_create_agent(session_id, prompt=prompt)
            event_queue = asyncio.Queue()

            # Per-session orchestrator — no shared state between sessions
            orchestrator = AgentOrchestrator()
            orchestrator.on_high_level_event = event_queue.put_nowait

            # Track tool_call_id from ReActLoop (LLM-native id) -> synthetic id
            _pending_tool_ids: Dict[str, str] = {}

            def on_tool_call(e):
                data = e.data or {}
                tool_name = data.get("name", "unknown")
                llm_tool_id = data.get("id", "")
                tool_id = f"tool-{next(self._tool_id_counter)}"
                # Use LLM-native id as key to avoid same-name-tool collisions
                _pending_tool_ids[llm_tool_id] = tool_id
                arguments = data.get("arguments", {})
                orchestrator.on_tool_call(tool_name, tool_id, arguments)

            def on_tool_result(e):
                data = e.data or {}
                llm_tool_id = data.get("tool_call_id", "")
                tool_id = _pending_tool_ids.pop(llm_tool_id, None)
                if tool_id is None:
                    return
                output = data.get("output", "")
                success = data.get("success", True)
                orchestrator.on_tool_result(tool_id, str(output), success)

            def on_passthrough(event_type: str, e):
                event_queue.put_nowait({"type": event_type, "data": e.data})

            agent.events.on(TOOL_CALL, on_tool_call)
            agent.events.on(TOOL_RESULT, on_tool_result)
            agent.events.on(ITERATION_START, lambda e: on_passthrough("iteration_start", e))
            agent.events.on(LLM_RESPONSE, lambda e: on_passthrough("llm_response", e))
            agent.events.on(LOOP_END, lambda e: on_passthrough("loop_end", e))
            agent.events.on(ERROR, lambda e: on_passthrough("error", e))
            agent.events.on(PROGRESS_UPDATE, lambda e: on_passthrough("progress_update", e))

            task = asyncio.create_task(
                agent.run(prompt, stream=True, mode=mode,
                          manual_queue=manual_queue, enabled_tools=enabled_tools)
            )
            try:
                while not task.done():
                    try:
                        event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                        yield event
                    except asyncio.TimeoutError:
                        continue

                # Drain remaining events queued before task.done() was set
                while not event_queue.empty():
                    yield event_queue.get_nowait()

                result = await task
                yield {"type": "complete", "data": {"result": result}}
            finally:
                if not task.done():
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task

    def cleanup_agent(self, session_id: str):
        """Clean up agent instance"""
        if session_id in self._agents:
            del self._agents[session_id]
