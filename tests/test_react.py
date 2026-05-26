"""Tests for the agent sub-package: context, budget, events, and ReActLoop."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mdpilot.agent import (
    BudgetTracker,
    ConversationContext,
    ERROR,
    ITERATION_START,
    LOOP_END,
    LLM_RESPONSE,
    Event,
    EventEmitter,
    ReActLoop,
    TOOL_CALL,
    TOOL_RESULT,
)
from mdpilot.config.schema import AgentConfig, AppConfig, ProviderConfig
from mdpilot.types import LLMChunk, LLMResponse, ToolCall, ToolOutput


# ----------------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------------

def _make_app_config(
    max_iterations: int = 10,
    max_context_tokens: int = 100_000,
) -> AppConfig:
    return AppConfig(
        provider=ProviderConfig(model="test-model"),
        agent=AgentConfig(
            max_iterations=max_iterations,
            max_context_tokens=max_context_tokens,
        ),
    )


def _mock_response(
    content: str = "",
    tool_calls: list[ToolCall] | None = None,
    prompt_tokens: int = 10,
    completion_tokens: int = 10,
) -> LLMResponse:
    return LLMResponse(
        content=content,
        tool_calls=tool_calls or [],
        usage_prompt_tokens=prompt_tokens,
        usage_completion_tokens=completion_tokens,
    )


# ----------------------------------------------------------------------------------
# ConversationContext
# ----------------------------------------------------------------------------------

class TestConversationContext:
    def test_add_user_message(self):
        ctx = ConversationContext(system_prompt="You are a helpful assistant.")
        ctx.add(role="user", content="Hello")
        assert len(ctx.messages) == 2  # system + user
        assert ctx.messages[0]["role"] == "system"
        assert ctx.messages[1]["role"] == "user"
        assert ctx.messages[1]["content"] == "Hello"

    def test_add_assistant_message_with_tool_calls(self):
        ctx = ConversationContext(system_prompt="You are helpful.")
        tool_calls = [
            {
                "id": "call_abc",
                "type": "function",
                "function": {
                    "name": "run_bash",
                    "arguments": '{"cmd": "ls"}',
                },
            }
        ]
        ctx.add(role="assistant", content="Running ls...", tool_calls=tool_calls)
        assert ctx.messages[1]["tool_calls"] == tool_calls

    def test_add_tool_result(self):
        ctx = ConversationContext(system_prompt="You are helpful.")
        ctx.add(role="tool", content="file1.txt\nfile2.txt", tool_call_id="call_abc")
        assert ctx.messages[1]["role"] == "tool"
        assert ctx.messages[1]["tool_call_id"] == "call_abc"

    def test_token_count_property(self):
        ctx = ConversationContext(system_prompt="Hello world", max_tokens=100_000)
        ctx.add(role="user", content="Test message here")
        assert ctx.token_count >= 1

    def test_estimate_tokens(self):
        text = "Hello world"
        est = ConversationContext.estimate_tokens(text)
        assert est == max(1, len(text) // 4)

    def test_truncate_preserves_system(self):
        ctx = ConversationContext(system_prompt="System prompt", max_tokens=100)
        for i in range(10):
            ctx.add(role="user", content=f"Message number {i} " * 100)
        initial_count = len(ctx.messages)
        ctx.truncate(keep_system=True)
        assert ctx.messages[0]["role"] == "system"
        assert len(ctx.messages) <= initial_count

    def test_truncate_without_system(self):
        ctx = ConversationContext(system_prompt="System", max_tokens=100)
        ctx.add(role="user", content="Hello")
        ctx.truncate(keep_system=False)
        assert ctx.messages[0]["content"] == ""


# ----------------------------------------------------------------------------------
# BudgetTracker
# ----------------------------------------------------------------------------------

class TestBudgetTracker:
    def test_iteration_starts_at_zero(self):
        b = BudgetTracker(max_iterations=10)
        assert b.iteration == 0

    def test_increment(self):
        b = BudgetTracker(max_iterations=10)
        b.increment()
        assert b.iteration == 1
        b.increment()
        assert b.iteration == 2

    def test_can_continue_initially_true(self):
        b = BudgetTracker(max_iterations=10)
        assert b.can_continue() is True

    def test_can_continue_false_after_max_iterations(self):
        b = BudgetTracker(max_iterations=2)
        b.increment()
        b.increment()
        assert b.can_continue() is False

    def test_can_continue_false_after_max_cost(self):
        b = BudgetTracker(max_iterations=100, max_cost_usd=0.0001)
        b.add_usage(prompt_tokens=100, completion_tokens=100)  # adds cost
        assert b.can_continue() is False

    def test_add_usage_tracks_tokens(self):
        b = BudgetTracker(max_iterations=10)
        b.add_usage(prompt_tokens=100, completion_tokens=50, cost_usd=0.001)
        assert b.cost_usd == 0.001

    def test_add_usage_estimates_cost_without_explicit(self):
        b = BudgetTracker(max_iterations=10, max_cost_usd=100.0)
        # 1M prompt tokens @ $1.5/1M = $1.5, 1M completion @ $7.5/1M = $7.5
        b.add_usage(prompt_tokens=1_000_000, completion_tokens=1_000_000)
        assert b.cost_usd == pytest.approx(9.0, rel=0.1)

    def test_remaining_property(self):
        b = BudgetTracker(max_iterations=10, max_cost_usd=1.0)
        b.increment()
        b.add_usage(prompt_tokens=100, completion_tokens=50, cost_usd=0.1)
        rem = b.remaining
        assert rem["iterations_left"] == 9
        assert rem["cost_remaining"] == pytest.approx(0.9, rel=0.01)


# ----------------------------------------------------------------------------------
# EventEmitter
# ----------------------------------------------------------------------------------

class TestEventEmitter:
    def test_on_and_emit(self):
        emitter = EventEmitter()
        received: list[Event] = []

        def handler(e: Event) -> None:
            received.append(e)

        emitter.on("test_event", handler)
        emitter.emit("test_event", foo="bar")

        assert len(received) == 1
        assert received[0].type == "test_event"
        assert received[0].data == {"foo": "bar"}

    def test_off_removes_callback(self):
        emitter = EventEmitter()
        called = False

        def handler(_: Event) -> None:
            nonlocal called
            called = True

        emitter.on("test_event", handler)
        emitter.off("test_event", handler)
        emitter.emit("test_event")
        assert called is False

    def test_multiple_listeners(self):
        emitter = EventEmitter()
        count = 0

        def handler1(_: Event) -> None:
            nonlocal count
            count += 1

        def handler2(_: Event) -> None:
            nonlocal count
            count += 2

        emitter.on("test_event", handler1)
        emitter.on("test_event", handler2)
        emitter.emit("test_event")
        assert count == 3

    def test_emit_returns_deregister_function(self):
        emitter = EventEmitter()
        called = False

        def handler(_: Event) -> None:
            nonlocal called
            called = True

        deregister = emitter.on("test_event", handler)
        deregister()
        emitter.emit("test_event")
        assert called is False

    def test_emit_unknown_event_noops(self):
        emitter = EventEmitter()
        emitter.emit("never_registered", foo="bar")  # should not raise

    def test_predefined_event_types_exist(self):
        assert ITERATION_START == "iteration_start"
        assert TOOL_CALL == "tool_call"
        assert TOOL_RESULT == "tool_result"
        assert LLM_RESPONSE == "llm_response"
        assert LOOP_END == "loop_end"
        assert ERROR == "error"


# ----------------------------------------------------------------------------------
# ReActLoop — mocked integration tests
# ----------------------------------------------------------------------------------

class TestReActLoopSimpleResponse:
    """ReActLoop returns final answer when LLM doesn't request tools."""

    @pytest.mark.asyncio
    async def test_returns_final_answer(self):
        config = _make_app_config(max_iterations=5)
        loop = ReActLoop(config)

        mock_resp = _mock_response(content="The answer is 42.")

        async def mock_chat_once(*args, **kwargs):
            return mock_resp

        with patch.object(loop._llm, "chat_once", side_effect=mock_chat_once):
            result = await loop.run("What is 6 * 7?")

        assert result == "The answer is 42."

    @pytest.mark.asyncio
    async def test_context_receives_user_and_assistant_messages(self):
        config = _make_app_config(max_iterations=5)
        loop = ReActLoop(config)

        mock_resp = _mock_response(content="Done.")

        async def mock_chat_once(*args, **kwargs):
            return mock_resp

        with patch.object(loop._llm, "chat_once", side_effect=mock_chat_once):
            await loop.run("Hello")

        msgs = loop._context.messages
        assert msgs[1]["role"] == "user"
        assert msgs[2]["role"] == "assistant"


class TestReActLoopToolCalls:
    """ReActLoop executes tools and continues when LLM requests them."""

    @pytest.mark.asyncio
    async def test_one_tool_call_then_response(self):
        config = _make_app_config(max_iterations=10)
        loop = ReActLoop(config)

        tool_call = ToolCall(id="call_1", name="bash", arguments={"cmd": "pwd"})
        first_response = _mock_response(content="Running command...", tool_calls=[tool_call])
        second_response = _mock_response(content="Current directory is /home/user.")

        call_count = 0

        async def mock_chat_once(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return first_response
            return second_response

        tool_output = ToolOutput(output="/home/user")

        async def mock_execute(call):
            return tool_output

        with patch.object(loop._llm, "chat_once", side_effect=mock_chat_once), \
             patch.object(loop._dispatcher, "execute", side_effect=mock_execute):
            result = await loop.run("Show me current directory")

        assert "Current directory" in result
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_in_one_turn(self):
        config = _make_app_config(max_iterations=10)
        loop = ReActLoop(config)

        tool_calls_list = [
            ToolCall(id="call_1", name="bash", arguments={"cmd": "ls"}),
            ToolCall(id="call_2", name="bash", arguments={"cmd": "pwd"}),
        ]
        first_response = _mock_response(content="Listing files...", tool_calls=tool_calls_list)
        second_response = _mock_response(content="All done.")

        call_count = 0

        async def mock_chat_once(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return first_response
            return second_response

        tool_output = ToolOutput(output="result")
        dispatch_count = 0

        async def mock_execute(call):
            nonlocal dispatch_count
            dispatch_count += 1
            return tool_output

        with patch.object(loop._llm, "chat_once", side_effect=mock_chat_once), \
             patch.object(loop._dispatcher, "execute", side_effect=mock_execute):
            result = await loop.run("Run two commands")

        assert dispatch_count == 2
        assert "done" in result


class TestReActLoopBudgetExceeded:
    """ReActLoop stops when budget is exhausted."""

    @pytest.mark.asyncio
    async def test_stops_at_max_iterations(self):
        config = _make_app_config(max_iterations=2)
        loop = ReActLoop(config)

        tool_call = ToolCall(id="call_1", name="bash", arguments={"cmd": "ls"})
        mock_response = _mock_response(content="Running...", tool_calls=[tool_call])

        async def mock_chat_once(*args, **kwargs):
            return mock_response

        tool_output = ToolOutput(output="files")

        async def mock_execute(call):
            return tool_output

        with patch.object(loop._llm, "chat_once", side_effect=mock_chat_once), \
             patch.object(loop._dispatcher, "execute", side_effect=mock_execute):
            result = await loop.run("Keep calling tools")

        assert "Budget exceeded" in result
        assert loop._budget.iteration == 2


class TestReActLoopEvents:
    """ReActLoop emits appropriate events during execution."""

    @pytest.mark.asyncio
    async def test_events_property_returns_emitter(self):
        config = _make_app_config()
        loop = ReActLoop(config)
        assert isinstance(loop.events, EventEmitter)

    @pytest.mark.asyncio
    async def test_error_event_on_exception(self):
        config = _make_app_config(max_iterations=3)
        loop = ReActLoop(config)

        async def mock_chat_once(*args, **kwargs):
            raise RuntimeError("LLM failure")

        events_received: list[Event] = []
        loop.events.on(ERROR, lambda e: events_received.append(e))

        with patch.object(loop._llm, "chat_once", side_effect=mock_chat_once):
            result = await loop.run("This will fail")

        assert len(events_received) >= 1
        assert "LLM failure" in events_received[0].data.get("message", "")

    @pytest.mark.asyncio
    async def test_iteration_start_event_emitted(self):
        config = _make_app_config(max_iterations=3)
        loop = ReActLoop(config)

        mock_resp = _mock_response(content="Done.")
        events_received: list[Event] = []
        loop.events.on(ITERATION_START, lambda e: events_received.append(e))

        async def mock_chat_once(*args, **kwargs):
            return mock_resp

        with patch.object(loop._llm, "chat_once", side_effect=mock_chat_once):
            await loop.run("Test")

        assert len(events_received) >= 1
        assert events_received[0].data.get("iteration") == 1

    @pytest.mark.asyncio
    async def test_loop_end_event_emitted(self):
        config = _make_app_config(max_iterations=3)
        loop = ReActLoop(config)

        mock_resp = _mock_response(content="Final answer.")
        events_received: list[Event] = []
        loop.events.on(LOOP_END, lambda e: events_received.append(e))

        async def mock_chat_once(*args, **kwargs):
            return mock_resp

        with patch.object(loop._llm, "chat_once", side_effect=mock_chat_once):
            await loop.run("Test")

        assert len(events_received) == 1
        assert events_received[0].data.get("reason") == "final_answer"


# ----------------------------------------------------------------------------------
# ReActLoop streaming
# ----------------------------------------------------------------------------------

class TestReActLoopStreaming:
    @pytest.mark.asyncio
    async def test_streaming_returns_empty(self):
        config = _make_app_config(max_iterations=3)
        loop = ReActLoop(config)

        async def mock_stream(*args, **kwargs):
            yield LLMChunk(content="Hello", finish_reason=None)
            yield LLMChunk(content=" world", finish_reason="stop")

        with patch.object(loop._llm, "chat", side_effect=mock_stream):
            result = await loop.run("Say hello", stream=True)

        # Streaming mode returns empty string
        assert result == ""

    @pytest.mark.asyncio
    async def test_streaming_with_final_response(self):
        config = _make_app_config(max_iterations=3)
        loop = ReActLoop(config)

        async def mock_stream(*args, **kwargs):
            yield LLMChunk(content="Hello world", finish_reason="stop")

        with patch.object(loop._llm, "chat", side_effect=mock_stream):
            result = await loop.run("Say hello", stream=True)

        assert result == ""

    @pytest.mark.asyncio
    async def test_streaming_with_tool_calls(self):
        config = _make_app_config(max_iterations=3)
        loop = ReActLoop(config)

        tool_call = ToolCall(id="call_1", name="bash", arguments={"cmd": "ls"})

        call_count = 0
        async def mock_stream(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: stream with tool calls
                yield LLMChunk(content="Running command", finish_reason=None, tool_calls=[tool_call])
            else:
                # Second call: final response
                yield LLMChunk(content="Done", finish_reason="stop")

        tool_output = ToolOutput(output="file1.txt")

        async def mock_execute(call):
            return tool_output

        with patch.object(loop._llm, "chat", side_effect=mock_stream), \
             patch.object(loop._dispatcher, "execute", side_effect=mock_execute):
            result = await loop.run("List files", stream=True)

        assert result == ""
        assert call_count == 2


# ----------------------------------------------------------------------------------
# ReActLoop properties
# ----------------------------------------------------------------------------------

class TestReActLoopProperties:
    """Test ReActLoop property accessors."""

    @pytest.mark.asyncio
    async def test_budget_property(self):
        config = _make_app_config(max_iterations=5)
        loop = ReActLoop(config)
        assert isinstance(loop.budget, BudgetTracker)
        assert loop.budget.iteration == 0

    @pytest.mark.asyncio
    async def test_iteration_property(self):
        config = _make_app_config(max_iterations=5)
        loop = ReActLoop(config)
        assert loop.iteration == 0

        mock_resp = _mock_response(content="Done.")
        async def mock_chat_once(*args, **kwargs):
            return mock_resp

        with patch.object(loop._llm, "chat_once", side_effect=mock_chat_once):
            await loop.run("Test")

        assert loop.iteration == 1

    @pytest.mark.asyncio
    async def test_max_iterations_property(self):
        config = _make_app_config(max_iterations=7)
        loop = ReActLoop(config)
        assert loop.max_iterations == 7

    @pytest.mark.asyncio
    async def test_config_property(self):
        config = _make_app_config(max_iterations=5)
        loop = ReActLoop(config)
        assert loop.config == config
        assert loop.config.agent.max_iterations == 5


# ----------------------------------------------------------------------------------
# ReActLoop skill context injection
# ----------------------------------------------------------------------------------

class TestReActLoopSkillContext:
    """Test skill context injection into system prompt."""

    @pytest.mark.asyncio
    async def test_skill_context_injection(self):
        config = _make_app_config(max_iterations=3)
        loop = ReActLoop(config)

        # Mock skill registry to return context
        with patch.object(loop._skills, "build_context", return_value="## Skill Context\nTest skill info"):
            mock_resp = _mock_response(content="Done.")

            async def mock_chat_once(*args, **kwargs):
                return mock_resp

            with patch.object(loop._llm, "chat_once", side_effect=mock_chat_once):
                await loop.run("Test with skills")

            # Verify system prompt was updated
            system_msg = loop._context.messages[0]
            assert "Skill Context" in system_msg["content"]

    @pytest.mark.asyncio
    async def test_load_skills_from_user_directory(self):
        """Test that user-level skills directory is checked during initialization."""
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            # Mock Path.home() to return our temp directory
            user_skills_dir = Path(tmpdir) / ".mdpilot" / "skills"
            user_skills_dir.mkdir(parents=True, exist_ok=True)

            # Create a dummy skill file
            (user_skills_dir / "test_skill.py").write_text("# test skill")

            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                config = _make_app_config(max_iterations=3)
                loop = ReActLoop(config)

                # The _load_skills method should have been called during __init__
                # and should have attempted to load from the user skills directory
                assert loop._skills is not None


# ----------------------------------------------------------------------------------
# ReActLoop context truncation
# ----------------------------------------------------------------------------------

class TestReActLoopContextTruncation:
    """Test context truncation when token limit is reached."""

    @pytest.mark.asyncio
    async def test_context_truncation_on_overflow(self):
        # Set very low max_context_tokens to trigger truncation
        config = _make_app_config(max_iterations=5, max_context_tokens=100)
        loop = ReActLoop(config)

        # Add a lot of content to exceed token limit
        for i in range(10):
            loop._context.add(role="user", content="x" * 100)

        mock_resp = _mock_response(content="Done.")

        async def mock_chat_once(*args, **kwargs):
            return mock_resp

        with patch.object(loop._llm, "chat_once", side_effect=mock_chat_once):
            result = await loop.run("Test truncation")

        # Should complete without error
        assert "Done" in result


# ----------------------------------------------------------------------------------
# ReActLoop tool error handling
# ----------------------------------------------------------------------------------

class TestReActLoopToolErrors:
    """Test tool execution error handling."""

    @pytest.mark.asyncio
    async def test_tool_error_with_suggestion(self):
        config = _make_app_config(max_iterations=5)
        loop = ReActLoop(config)

        tool_call = ToolCall(id="call_1", name="bash", arguments={"cmd": "invalid"})
        first_response = _mock_response(content="Running...", tool_calls=[tool_call])
        second_response = _mock_response(content="I see the error.")

        call_count = 0
        async def mock_chat_once(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return first_response
            return second_response

        # Tool returns error with suggestion
        tool_output = ToolOutput(
            output="",
            success=False,
            error="Command failed",
            error_suggestion="Try using a valid command"
        )

        async def mock_execute(call):
            return tool_output

        with patch.object(loop._llm, "chat_once", side_effect=mock_chat_once), \
             patch.object(loop._dispatcher, "execute", side_effect=mock_execute):
            result = await loop.run("Run invalid command")

        # Should handle error and continue
        assert call_count == 2
        assert "error" in result.lower() or "see" in result.lower()

    @pytest.mark.asyncio
    async def test_tool_error_without_suggestion(self):
        config = _make_app_config(max_iterations=5)
        loop = ReActLoop(config)

        tool_call = ToolCall(id="call_1", name="bash", arguments={"cmd": "fail"})
        first_response = _mock_response(content="Trying...", tool_calls=[tool_call])
        second_response = _mock_response(content="Understood.")

        call_count = 0
        async def mock_chat_once(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return first_response
            return second_response

        # Tool returns error without suggestion
        tool_output = ToolOutput(output="", success=False, error="Generic error")

        async def mock_execute(call):
            return tool_output

        with patch.object(loop._llm, "chat_once", side_effect=mock_chat_once), \
             patch.object(loop._dispatcher, "execute", side_effect=mock_execute):
            result = await loop.run("Run failing command")

        assert call_count == 2
