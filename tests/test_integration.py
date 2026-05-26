"""Integration tests for amber-agent — verifying all components wire together."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

import pytest

from mdpilot import load_config, ReActLoop
from mdpilot.config.schema import AppConfig
from mdpilot.agent.events import (
    EventEmitter,
    ITERATION_START,
    TOOL_CALL,
    TOOL_RESULT,
    LLM_RESPONSE,
    LOOP_END,
    ERROR,
    Event,
)
from mdpilot.tools.registry import ToolRegistry
from mdpilot.tools.dispatcher import ToolDispatcher
from mdpilot.types import ToolCall, ToolOutput


# ---------------------------------------------------------------------------
# Config → AppConfig wiring
# ---------------------------------------------------------------------------

class TestConfigWiring:
    """Verify load_config returns a properly wired AppConfig."""

    def test_load_config_returns_app_config(self):
        """load_config() returns a valid AppConfig instance."""
        cfg = load_config()
        assert isinstance(cfg, AppConfig)
        assert cfg.provider.model is not None
        assert cfg.agent.max_iterations > 0

    def test_load_config_cli_overrides_apply(self):
        """CLI-style overrides in load_config affect the result."""
        cfg = load_config(
            cli_overrides={
                "provider": {"model": "my-override-model"},
                "agent": {"max_iterations": 5},
            }
        )
        assert cfg.provider.model == "my-override-model"
        assert cfg.agent.max_iterations == 5

    def test_load_config_nested_defaults_preserved(self, tmp_path):
        """Partial overrides do not wipe nested defaults."""
        cfg = load_config(
            cli_overrides={"agent": {"max_iterations": 7}},
            project_dir=tmp_path,
        )
        # These should still come from DEFAULTS
        assert cfg.agent.max_context_tokens == 100_000
        assert cfg.agent.default_mode == "react"


# ---------------------------------------------------------------------------
# Tool registry wiring
# ---------------------------------------------------------------------------

class TestToolRegistryWiring:
    """Verify ToolRegistry discovers and registers builtin tools."""

    def test_auto_discover_finds_builtin_tools(self):
        """auto_discover finds at least one tool."""
        registry = ToolRegistry()
        registry.auto_discover("mdpilot.tools.builtin")
        names = registry.list_tools()
        assert len(names) > 0, "Expected at least one builtin tool"

    def test_schemas_returns_openai_format(self):
        """schemas() returns correctly-shaped OpenAI function schemas."""
        registry = ToolRegistry()
        registry.auto_discover("mdpilot.tools.builtin")
        schemas = registry.schemas()
        assert isinstance(schemas, list)
        for schema in schemas:
            assert schema["type"] == "function"
            assert "function" in schema
            func = schema["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func

    def test_dispatcher_executes_tool(self):
        """ToolDispatcher.execute resolves a ToolCall to a ToolOutput."""
        registry = ToolRegistry()
        registry.auto_discover("mdpilot.tools.builtin")
        dispatcher = ToolDispatcher(registry)

        # The registry must contain at least one tool
        tool_names = registry.list_tools()
        assert len(tool_names) > 0, "Need at least one tool to test dispatch"

        # Dispatch a dummy call for the first registered tool
        dummy_call = ToolCall(
            id="call_test_1",
            name=tool_names[0],
            arguments={},
        )
        output = asyncio.run(dispatcher.execute(dummy_call))
        assert isinstance(output, ToolOutput)


# ---------------------------------------------------------------------------
# ReActLoop wiring — full pipeline with mocks
# ---------------------------------------------------------------------------

class TestReActLoopWiring:
    """Verify ReActLoop initialises all subsystems from AppConfig."""

    def test_loop_initialises_without_error(self):
        """ReActLoop can be instantiated with a valid AppConfig."""
        cfg = load_config(cli_overrides={"agent": {"max_iterations": 3}})
        loop = ReActLoop(cfg)
        assert loop is not None
        assert loop.events is not None
        assert loop.budget is not None

    def test_loop_subsystem_dependencies(self):
        """Loop's LLM, registry, dispatcher, and context are all initialised."""
        cfg = load_config()
        loop = ReActLoop(cfg)
        # Verify internal components are non-None
        assert loop._llm is not None  # noqa: SLF001
        assert loop._registry is not None  # noqa: SLF001
        assert loop._dispatcher is not None  # noqa: SLF001
        assert loop._context is not None  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_mock_run_returns_result(self):
        """With a mocked LLM, the loop returns a result without real API calls."""
        cfg = load_config(cli_overrides={"agent": {"max_iterations": 3}})

        # Patch the LLM chat method on the loop's internal provider
        with patch.object(ReActLoop, "__init__", lambda self, cfg: None):
            loop = ReActLoop.__new__(ReActLoop)
            loop._config = cfg  # noqa: SLF001
            loop._budget = MagicMock()  # noqa: SLF001
            loop._budget.can_continue.return_value = False  # immediately exit
            loop._budget.iteration = 1  # noqa: SLF001
            loop._budget.remaining = {"iterations_left": 0, "cost_remaining": 0.0}  # noqa: SLF001
            loop._context = MagicMock()  # noqa: SLF001
            loop._events = EventEmitter()  # noqa: SLF001
            loop._skills = MagicMock()  # noqa: SLF001
            loop._skills.build_context.return_value = ""  # noqa: SLF001
            loop._use_coordination = False  # noqa: SLF001

            # budget.can_continue False → loop exits immediately with budget summary
            result = await loop.run("test prompt")
            assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_events_emitted_during_mock_run(self):
        """EventEmitter receives events when the loop runs."""
        cfg = load_config(cli_overrides={"agent": {"max_iterations": 1}})

        loop = ReActLoop(cfg)

        emitted: list[Event] = []

        def collector(event: Event) -> None:
            emitted.append(event)

        loop.events.on(ITERATION_START, collector)
        loop.events.on(ERROR, collector)

        # Even a short run should touch the event system
        with patch.object(loop._llm, "chat_once", new_callable=AsyncMock) as mock_chat:
            # Return a "final answer" response (no tool calls)
            mock_response = MagicMock()
            mock_response.content = "42"
            mock_response.tool_calls = []
            mock_response.usage_prompt_tokens = 10
            mock_response.usage_completion_tokens = 5
            mock_chat.return_value = mock_response

            await loop.run("What is 1+1?")

        # At minimum, we should have seen an iteration start
        iteration_events = [e for e in emitted if e.type == ITERATION_START]
        assert len(iteration_events) >= 1


# ---------------------------------------------------------------------------
# End-to-end mock pipeline
# ---------------------------------------------------------------------------

class TestFullPipelineMock:
    """Full pipeline: config → loop → mock run, verifying wiring end-to-end."""

    def test_config_to_loop_to_mock_run(self):
        """A complete config → ReActLoop → mock run pipeline works."""
        cfg = load_config(
            cli_overrides={
                "provider": {"model": "mock-model"},
                "agent": {"max_iterations": 2},
            }
        )
        assert cfg.provider.model == "mock-model"

        loop = ReActLoop(cfg)
        assert loop._config.provider.model == "mock-model"  # noqa: SLF001
        assert loop.budget._max_iterations == 2  # noqa: SLF001

    def test_tools_registry_in_loop_has_tools(self):
        """A ReActLoop's internal registry contains discovered tools."""
        cfg = load_config()
        loop = ReActLoop(cfg)
        tool_names = loop._registry.list_tools()  # noqa: SLF001
        assert len(tool_names) > 0

    def test_event_emitter_in_loop_is_functional(self):
        """The EventEmitter on ReActLoop can register and fire callbacks."""
        cfg = load_config()
        loop = ReActLoop(cfg)

        received: list[Event] = []

        loop.events.on("my_test_event", received.append)
        loop.events.emit("my_test_event", foo="bar")

        assert len(received) == 1
        assert received[0].data["foo"] == "bar"
