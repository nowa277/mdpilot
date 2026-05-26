"""Tests for ReflectionAgent."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from mdpilot.config.schema import AppConfig, ProviderConfig, AgentConfig


@pytest.fixture
def mock_config():
    return AppConfig(
        provider=ProviderConfig(model="gpt-4", api_key="test-key"),
        agent=AgentConfig(max_iterations=10, max_context_tokens=8000),
    )


class TestReflectionAgentInit:
    def test_inherits_agent_base(self, mock_config):
        from mdpilot.agent.reflection import ReflectionAgent
        from mdpilot.agent.base import AgentBase

        agent = ReflectionAgent(mock_config)
        assert isinstance(agent, AgentBase)

    def test_default_max_reflections(self, mock_config):
        from mdpilot.agent.reflection import ReflectionAgent

        agent = ReflectionAgent(mock_config)
        assert agent._max_reflections == 3

    def test_custom_max_reflections(self, mock_config):
        from mdpilot.agent.reflection import ReflectionAgent

        agent = ReflectionAgent(mock_config, max_reflections=5)
        assert agent._max_reflections == 5


from mdpilot.agent.events import ITERATION_START, LOOP_END
from mdpilot.types import LLMResponse


def _make_response(content: str, tool_calls=None):
    resp = MagicMock(spec=LLMResponse)
    resp.content = content
    resp.tool_calls = tool_calls or []
    return resp


class TestReflectionAgentCritiqueLoop:
    @pytest.mark.asyncio
    async def test_satisfied_on_first_critique(self, mock_config):
        """Agent returns result immediately when critique says satisfied."""
        from mdpilot.agent.reflection import ReflectionAgent

        agent = ReflectionAgent(mock_config, max_reflections=3)

        responses = [
            _make_response("Initial result: RMSD = 2.5 Å"),
            _make_response("SATISFIED. The result looks good."),
        ]
        agent._llm_caller.call = AsyncMock(side_effect=responses)

        collected_events = []
        agent.events.on(LOOP_END, lambda e: collected_events.append(e))

        result = await agent.run("Optimize the RMSD of this structure")

        assert "Initial result" in result
        assert len(collected_events) == 1

    @pytest.mark.asyncio
    async def test_one_revise_cycle(self, mock_config):
        """Agent revises once then is satisfied."""
        from mdpilot.agent.reflection import ReflectionAgent

        agent = ReflectionAgent(mock_config, max_reflections=3)

        responses = [
            _make_response("Initial result: RMSD = 2.5 Å"),
            _make_response("NEEDS_IMPROVEMENT. The cutoff distance is too large."),
            _make_response("Revised result: RMSD = 1.2 Å with shorter cutoff"),
            _make_response("SATISFIED. Improved significantly."),
        ]
        agent._llm_caller.call = AsyncMock(side_effect=responses)

        result = await agent.run("Improve the MD simulation result")

        assert "Revised result" in result

    @pytest.mark.asyncio
    async def test_max_reflections_exhausted(self, mock_config):
        """Agent stops after max_reflections even if not satisfied."""
        from mdpilot.agent.reflection import ReflectionAgent

        agent = ReflectionAgent(mock_config, max_reflections=2)

        responses = [
            _make_response("Initial result"),
            _make_response("NEEDS_IMPROVEMENT. Try again."),
            _make_response("Revised result v1"),
            _make_response("NEEDS_IMPROVEMENT. Still not good."),
            _make_response("Revised result v2"),
            _make_response("NEEDS_IMPROVEMENT. More work needed."),
        ]
        agent._llm_caller.call = AsyncMock(side_effect=responses)

        result = await agent.run("Optimize the parameters")

        assert "Revised result v2" in result

    @pytest.mark.asyncio
    async def test_iteration_events_emitted(self, mock_config):
        """Each execute-critique cycle emits ITERATION_START."""
        from mdpilot.agent.reflection import ReflectionAgent

        agent = ReflectionAgent(mock_config, max_reflections=2)

        responses = [
            _make_response("Result v0"),
            _make_response("SATISFIED."),
        ]
        agent._llm_caller.call = AsyncMock(side_effect=responses)

        iterations = []
        agent.events.on(ITERATION_START, lambda e: iterations.append(e.data["iteration"]))

        await agent.run("Check this result")

        assert len(iterations) >= 1
        assert iterations[0] == 1


from mdpilot.agent.router import AgentRouter


class TestReflectionAgentRouting:
    def test_router_returns_reflection_agent(self):
        router = AgentRouter()
        from mdpilot.agent.reflection import ReflectionAgent

        agent_cls = router.select_agent("帮我优化这个模拟结果")
        assert agent_cls is ReflectionAgent

    def test_router_returns_reflection_for_improve(self):
        router = AgentRouter()
        from mdpilot.agent.reflection import ReflectionAgent

        agent_cls = router.select_agent("改进这个分析报告")
        assert agent_cls is ReflectionAgent

    def test_router_returns_reflection_for_review(self):
        router = AgentRouter()
        from mdpilot.agent.reflection import ReflectionAgent

        agent_cls = router.select_agent("审查这个参数设置是否正确")
        assert agent_cls is ReflectionAgent

    def test_router_importable_from_package(self):
        from mdpilot.agent import ReflectionAgent

        assert ReflectionAgent is not None


from mdpilot.types import ToolCall, ToolOutput


class TestReflectionAgentWithTools:
    @pytest.mark.asyncio
    async def test_execute_with_tool_calls(self, mock_config):
        """Initial execute phase can use tools."""
        from mdpilot.agent.reflection import ReflectionAgent

        agent = ReflectionAgent(mock_config, max_reflections=1)

        tool_call = ToolCall(id="tc_1", name="bash_run", arguments={"command": "echo hello"})
        execute_response = _make_response("Running analysis", tool_calls=[tool_call])
        critique_response = _make_response("SATISFIED. Results are adequate.")

        agent._llm_caller.call = AsyncMock(side_effect=[execute_response, critique_response])

        tool_output = ToolOutput(success=True, output="hello\n")
        agent._dispatcher.execute = AsyncMock(return_value=tool_output)

        result = await agent.run("Analyze this trajectory file")

        assert result is not None

    @pytest.mark.asyncio
    async def test_error_handling(self, mock_config):
        """Exceptions in the loop produce an error message, not a crash."""
        from mdpilot.agent.reflection import ReflectionAgent

        agent = ReflectionAgent(mock_config, max_reflections=2)

        agent._llm_caller.call = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

        result = await agent.run("Optimize this")

        assert "ReflectionAgent error" in result
        assert "LLM unavailable" in result
