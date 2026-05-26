# tests/agent/test_react_agent.py
"""Regression tests: ReActAgent behaves identically to ReActLoop."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mdpilot.agent import AgentBase
from mdpilot.agent.react_agent import ReActAgent, ReActLoop
from mdpilot.config.schema import AgentConfig, AppConfig, ProviderConfig
from mdpilot.types import LLMChunk, LLMResponse, ToolCall, ToolOutput


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
) -> LLMResponse:
    return LLMResponse(
        content=content,
        tool_calls=tool_calls or [],
        usage_prompt_tokens=10,
        usage_completion_tokens=10,
    )


class TestReActAgentIsAgentBase:
    """ReActAgent is a proper subclass of AgentBase."""

    def test_inherits_agent_base(self):
        agent = ReActAgent(_make_app_config())
        assert isinstance(agent, AgentBase)

    def test_reactloop_alias(self):
        """ReActLoop is an alias for ReActAgent."""
        assert ReActLoop is ReActAgent


class TestReActAgentSimpleResponse:
    """ReActAgent returns final answer when LLM doesn't request tools."""

    @pytest.mark.asyncio
    async def test_returns_final_answer(self):
        agent = ReActAgent(_make_app_config(max_iterations=5))
        mock_resp = _mock_response(content="The answer is 42.")

        async def mock_chat_once(*args, **kwargs):
            return mock_resp

        with patch.object(agent._llm, "chat_once", side_effect=mock_chat_once):
            result = await agent.run("What is 6 * 7?")

        assert result == "The answer is 42."

    @pytest.mark.asyncio
    async def test_context_receives_user_and_assistant_messages(self):
        agent = ReActAgent(_make_app_config(max_iterations=5))
        mock_resp = _mock_response(content="Done.")

        async def mock_chat_once(*args, **kwargs):
            return mock_resp

        with patch.object(agent._llm, "chat_once", side_effect=mock_chat_once):
            await agent.run("Hello")

        msgs = agent._context.messages
        assert msgs[1]["role"] == "user"
        assert msgs[2]["role"] == "assistant"


class TestReActAgentToolCalls:
    """ReActAgent executes tools and continues."""

    @pytest.mark.asyncio
    async def test_one_tool_call_then_response(self):
        agent = ReActAgent(_make_app_config(max_iterations=10))
        tool_call = ToolCall(id="call_1", name="bash", arguments={"cmd": "pwd"})
        first_response = _mock_response(content="Running...", tool_calls=[tool_call])
        second_response = _mock_response(content="Directory: /home")

        call_count = 0
        async def mock_chat_once(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return first_response if call_count == 1 else second_response

        async def mock_execute(call):
            return ToolOutput(output="/home")

        with patch.object(agent._llm, "chat_once", side_effect=mock_chat_once), \
             patch.object(agent._dispatcher, "execute", side_effect=mock_execute):
            result = await agent.run("Show directory")

        assert "Directory" in result
        assert call_count == 2


class TestReActAgentBudget:
    """ReActAgent stops at budget limit."""

    @pytest.mark.asyncio
    async def test_stops_at_max_iterations(self):
        agent = ReActAgent(_make_app_config(max_iterations=2))
        tool_call = ToolCall(id="call_1", name="bash", arguments={"cmd": "ls"})
        mock_resp = _mock_response(content="Running...", tool_calls=[tool_call])

        async def mock_chat_once(*args, **kwargs):
            return mock_resp

        async def mock_execute(call):
            return ToolOutput(output="files")

        with patch.object(agent._llm, "chat_once", side_effect=mock_chat_once), \
             patch.object(agent._dispatcher, "execute", side_effect=mock_execute):
            result = await agent.run("Keep calling tools")

        assert "Budget exceeded" in result
        assert agent._budget.iteration == 2


class TestReActAgentEvents:
    """ReActAgent emits events correctly."""

    @pytest.mark.asyncio
    async def test_iteration_start_event(self):
        from mdpilot.agent.events import ITERATION_START, Event

        agent = ReActAgent(_make_app_config(max_iterations=3))
        mock_resp = _mock_response(content="Done.")
        events_received: list[Event] = []
        agent.events.on(ITERATION_START, lambda e: events_received.append(e))

        async def mock_chat_once(*args, **kwargs):
            return mock_resp

        with patch.object(agent._llm, "chat_once", side_effect=mock_chat_once):
            await agent.run("Test")

        assert len(events_received) >= 1
        assert events_received[0].data.get("iteration") == 1

    @pytest.mark.asyncio
    async def test_loop_end_event(self):
        from mdpilot.agent.events import LOOP_END, Event

        agent = ReActAgent(_make_app_config(max_iterations=3))
        mock_resp = _mock_response(content="Final answer.")
        events_received: list[Event] = []
        agent.events.on(LOOP_END, lambda e: events_received.append(e))

        async def mock_chat_once(*args, **kwargs):
            return mock_resp

        with patch.object(agent._llm, "chat_once", side_effect=mock_chat_once):
            await agent.run("Test")

        assert len(events_received) == 1
        assert events_received[0].data.get("reason") == "final_answer"


class TestReActAgentStreaming:
    """ReActAgent streaming mode works."""

    @pytest.mark.asyncio
    async def test_streaming_returns_content(self):
        agent = ReActAgent(_make_app_config(max_iterations=3))

        async def mock_stream(*args, **kwargs):
            yield LLMChunk(content="Hello", finish_reason=None)
            yield LLMChunk(content=" world", finish_reason="stop")

        with patch.object(agent._llm, "chat", side_effect=mock_stream):
            result = await agent.run("Say hello", stream=True)

        assert result == "Hello world"


class TestReActAgentSkillContext:
    """ReActAgent injects skill context."""

    @pytest.mark.asyncio
    async def test_skill_context_injection(self):
        agent = ReActAgent(_make_app_config(max_iterations=3))
        mock_resp = _mock_response(content="Done.")

        async def mock_chat_once(*args, **kwargs):
            return mock_resp

        with patch.object(agent._skills, "build_context", return_value="## Skill Context\nTest skill info"), \
             patch.object(agent._llm, "chat_once", side_effect=mock_chat_once):
            await agent.run("Test with skills")

        system_msg = agent._context.messages[0]
        assert "Skill Context" in system_msg["content"]


class TestReActAgentCoordination:
    """ReActAgent coordination mode initializes correctly."""

    def test_coordination_mode_init(self):
        config = _make_app_config()
        agent = ReActAgent(config, use_coordination=True)
        assert agent._plan_generator is not None
        assert agent._execution_planner is not None
        assert agent._tool_executor is not None

    def test_no_coordination_by_default(self):
        agent = ReActAgent(_make_app_config())
        assert agent._plan_generator is None
        assert agent._tool_executor is None


class TestReActAgentToolSkillInjection:
    """ReActAgent injects tool skill L2 content into system prompt."""

    @pytest.mark.asyncio
    async def test_legacy_injects_tool_skills_into_system(self):
        agent = ReActAgent(_make_app_config(max_iterations=3))
        mock_resp = _mock_response(content="Done.")

        async def mock_chat_once(*args, **kwargs):
            return mock_resp

        with patch.object(agent._skills, "build_context", return_value=""), \
             patch.object(agent, "_inject_tool_skills", return_value="## Tool Guide: sander\nUse pmemd.cuda for standard MD.") as mock_inject, \
             patch.object(agent._llm, "chat_once", side_effect=mock_chat_once):
            await agent.run("run MD simulation with sander")

        mock_inject.assert_called_once_with("run MD simulation with sander")
        system_msg = agent._context.messages[0]
        assert "Tool Guide: sander" in system_msg["content"]

    @pytest.mark.asyncio
    async def test_legacy_injects_both_context_and_skills(self):
        agent = ReActAgent(_make_app_config(max_iterations=3))
        mock_resp = _mock_response(content="Done.")

        async def mock_chat_once(*args, **kwargs):
            return mock_resp

        with patch.object(agent._skills, "build_context", return_value="## Skill: AMBER"), \
             patch.object(agent, "_inject_tool_skills", return_value="## Tool Guide: tleap\nBuild topology.") as mock_inject, \
             patch.object(agent._llm, "chat_once", side_effect=mock_chat_once):
            await agent.run("build topology for protein")

        system_msg = agent._context.messages[0]
        assert "Skill: AMBER" in system_msg["content"]
        assert "Tool Guide: tleap" in system_msg["content"]

    @pytest.mark.asyncio
    async def test_coordination_injects_tool_skills(self):
        agent = ReActAgent(_make_app_config(max_iterations=3), use_coordination=True)
        mock_resp = _mock_response(content="Done.")

        async def mock_chat_once(*args, **kwargs):
            return mock_resp

        with patch.object(agent._skills, "build_context", return_value=""), \
             patch.object(agent, "_inject_tool_skills", return_value="## Tool Guide: sander\nUse pmemd.cuda.") as mock_inject, \
             patch.object(agent._llm, "chat_once", side_effect=mock_chat_once):
            await agent.run("run MD simulation")

        mock_inject.assert_called_once_with("run MD simulation")

    @pytest.mark.asyncio
    async def test_no_skill_injection_when_empty(self):
        agent = ReActAgent(_make_app_config(max_iterations=3))
        mock_resp = _mock_response(content="Done.")

        async def mock_chat_once(*args, **kwargs):
            return mock_resp

        original_prompt = agent._build_system_prompt()

        with patch.object(agent._skills, "build_context", return_value=""), \
             patch.object(agent, "_inject_tool_skills", return_value=""), \
             patch.object(agent._llm, "chat_once", side_effect=mock_chat_once):
            await agent.run("casual chat")

        system_msg = agent._context.messages[0]
        assert system_msg["content"] == original_prompt
