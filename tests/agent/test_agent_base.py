# tests/agent/test_agent_base.py
"""Tests for AgentBase abstract base class."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from mdpilot.agent.base import AgentBase
from mdpilot.config.schema import AgentConfig, AppConfig, ProviderConfig


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


class ConcreteAgent(AgentBase):
    """Concrete subclass for testing AgentBase."""
    async def run(self, prompt: str, stream: bool = False) -> str:
        return "test"


class TestAgentBaseInit:
    """AgentBase initializes all shared subsystems from AppConfig."""

    def test_init_creates_llm_provider(self):
        agent = ConcreteAgent(_make_app_config())
        assert agent._llm is not None

    def test_init_creates_tool_registry(self):
        agent = ConcreteAgent(_make_app_config())
        assert agent._registry is not None
        assert len(agent._registry.list_tools()) > 0

    def test_init_creates_dispatcher(self):
        agent = ConcreteAgent(_make_app_config())
        assert agent._dispatcher is not None

    def test_init_creates_llm_caller(self):
        agent = ConcreteAgent(_make_app_config())
        assert agent._llm_caller is not None

    def test_init_creates_skill_registry(self):
        agent = ConcreteAgent(_make_app_config())
        assert agent._skills is not None

    def test_init_creates_conversation_context(self):
        agent = ConcreteAgent(_make_app_config())
        assert agent._context is not None
        assert agent._context._system_prompt != ""

    def test_init_creates_budget_tracker(self):
        agent = ConcreteAgent(_make_app_config(max_iterations=5))
        assert agent._budget is not None
        assert agent._budget._max_iterations == 5

    def test_init_creates_event_emitter(self):
        agent = ConcreteAgent(_make_app_config())
        assert agent._events is not None


class TestAgentBaseProperties:
    """AgentBase property accessors work correctly."""

    def test_events_property(self):
        agent = ConcreteAgent(_make_app_config())
        from mdpilot.agent.events import EventEmitter
        assert isinstance(agent.events, EventEmitter)

    def test_budget_property(self):
        agent = ConcreteAgent(_make_app_config())
        from mdpilot.agent.budget import BudgetTracker
        assert isinstance(agent.budget, BudgetTracker)

    def test_config_property(self):
        config = _make_app_config()
        agent = ConcreteAgent(config)
        assert agent.config == config


class TestAgentBaseSystemPrompt:
    """AgentBase builds system prompt correctly."""

    def test_build_system_prompt_returns_string(self):
        agent = ConcreteAgent(_make_app_config())
        prompt = agent._build_system_prompt()
        assert isinstance(prompt, str)
        assert "MDPilot" in prompt
        assert "Knowledge Base" in prompt

    def test_build_system_prompt_includes_knowledge_summary(self):
        agent = ConcreteAgent(_make_app_config())
        prompt = agent._build_system_prompt()
        assert "Knowledge" in prompt


class TestAgentBaseCannotInstantiate:
    """AgentBase cannot be instantiated directly."""

    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            AgentBase(_make_app_config())


class TestAgentBaseKnowledgeInjection:
    """AgentBase._inject_context builds knowledge context."""

    def test_inject_context_returns_string(self):
        agent = ConcreteAgent(_make_app_config())
        result = agent._inject_context("test prompt")
        assert isinstance(result, str)

    def test_inject_context_includes_skill(self):
        agent = ConcreteAgent(_make_app_config())
        with patch.object(agent._skills, "build_context", return_value="## Skill: Test"):
            result = agent._inject_context("test")
        assert "Skill" in result


class TestAgentBaseToolSkillInjection:
    """AgentBase._inject_tool_skills matches triggers and returns L2 content."""

    def test_returns_empty_when_no_skills(self):
        """No skill_guide on any tool -> empty string."""
        agent = ConcreteAgent(_make_app_config())
        result = agent._inject_tool_skills("run MD simulation")
        assert result == ""

    def test_returns_content_when_trigger_matches(self):
        """Tool with skill_guide whose trigger matches prompt returns L2."""
        agent = ConcreteAgent(_make_app_config())

        from mdpilot.types import ToolMeta

        def fake_tool(text: str) -> str:
            return text
        fake_tool._tool_meta = ToolMeta(
            name="sander",
            description="MD engine",
            parameters={"type": "object", "properties": {"text": {"type": "string"}}},
            skill_guide="amber/skills/sander.md",
        )
        agent._registry.register(fake_tool)

        with patch("mdpilot.tools.skill_loader.SkillLoader.load_l1", return_value={
                "triggers": ["sander", "energy minimization", "MD simulation"],
            }), \
             patch("mdpilot.tools.skill_loader.SkillLoader.load_l2", return_value="## Sander Guide\nUse pmemd.cuda instead for standard MD."):
            result = agent._inject_tool_skills("run MD simulation with sander")

        assert "Sander Guide" in result
        assert "sander" in result

    def test_returns_empty_when_no_trigger_match(self):
        """Tool with skill_guide whose triggers do NOT match prompt -> empty."""
        agent = ConcreteAgent(_make_app_config())

        from mdpilot.types import ToolMeta

        def fake_tool(text: str) -> str:
            return text
        fake_tool._tool_meta = ToolMeta(
            name="sander",
            description="MD engine",
            parameters={"type": "object", "properties": {"text": {"type": "string"}}},
            skill_guide="amber/skills/sander.md",
        )
        agent._registry.register(fake_tool)

        with patch("mdpilot.tools.skill_loader.SkillLoader.load_l1", return_value={
                "triggers": ["sander", "energy minimization"],
            }):
            result = agent._inject_tool_skills("What is the meaning of life?")

        assert result == ""

    def test_respects_char_budget(self):
        """Multiple matching tools are truncated to max_chars budget."""
        agent = ConcreteAgent(_make_app_config())

        from mdpilot.types import ToolMeta

        def tool_a(text: str) -> str:
            return text
        tool_a._tool_meta = ToolMeta(
            name="sander",
            description="MD engine",
            parameters={"type": "object", "properties": {}},
            skill_guide="amber/skills/sander.md",
        )
        agent._registry.register(tool_a)

        def tool_b(text: str) -> str:
            return text
        tool_b._tool_meta = ToolMeta(
            name="pmemd_cuda",
            description="GPU MD",
            parameters={"type": "object", "properties": {}},
            skill_guide="amber/skills/pmemd_cuda.md",
        )
        agent._registry.register(tool_b)

        with patch("mdpilot.tools.skill_loader.SkillLoader.load_l1", return_value={"triggers": ["sander", "pmemd", "MD simulation"]}), \
             patch("mdpilot.tools.skill_loader.SkillLoader.load_l2", return_value="X" * 5000):
            result = agent._inject_tool_skills("run MD simulation")

        assert len(result) <= 5000

    def test_graceful_on_skill_load_error(self):
        """SkillLoader.load_l1 raising exception -> tool skipped, not crash."""
        agent = ConcreteAgent(_make_app_config())

        from mdpilot.types import ToolMeta

        def fake_tool(text: str) -> str:
            return text
        fake_tool._tool_meta = ToolMeta(
            name="broken_tool",
            description="Broken",
            parameters={"type": "object", "properties": {}},
            skill_guide="nonexistent.md",
        )
        agent._registry.register(fake_tool)

        with patch("mdpilot.tools.skill_loader.SkillLoader.load_l1", side_effect=FileNotFoundError("nope")):
            result = agent._inject_tool_skills("use broken_tool")

        assert result == ""
