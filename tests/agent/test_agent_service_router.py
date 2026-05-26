# tests/agent/test_agent_service_router.py
"""Tests for AgentService routing to different agent paradigms."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from mdpilot.agent.base import AgentBase
from mdpilot.agent.plan_solve import PlanAndSolveAgent
from mdpilot.agent.react_agent import ReActAgent
from mdpilot.api.services.agent_service import AgentService


@asynccontextmanager
async def _mock_session():
    """Yield a mock async session that returns no saved state."""
    db = AsyncMock()
    repo = AsyncMock()
    repo.load_session = AsyncMock(return_value=None)
    # Patch SessionRepository to return our mock repo
    with patch(
        "mdpilot.api.services.agent_service.SessionRepository",
        return_value=repo,
    ):
        yield db


class TestAgentServiceRouting:
    """AgentService creates the right agent type based on prompt."""

    @pytest.mark.asyncio
    async def test_default_without_prompt_is_react(self):
        service = AgentService()
        with patch("mdpilot.api.services.agent_service.get_session", _mock_session):
            agent = await service.get_or_create_agent("session_default")
        assert isinstance(agent, ReActAgent)

    @pytest.mark.asyncio
    async def test_with_prompt_routes_correctly(self):
        service = AgentService()
        with patch("mdpilot.api.services.agent_service.get_session", _mock_session):
            agent = await service.get_or_create_agent("session_chat", prompt="你好")
        assert isinstance(agent, ReActAgent)

    @pytest.mark.asyncio
    async def test_multi_step_creates_plan_solve(self):
        service = AgentService()
        with patch("mdpilot.api.services.agent_service.get_session", _mock_session):
            agent = await service.get_or_create_agent("session_plan", prompt="预测结构然后分析功能")
        assert isinstance(agent, PlanAndSolveAgent)

    @pytest.mark.asyncio
    async def test_same_session_reuses_agent_even_if_type_differs(self):
        """Session reuse: once an agent is created, it's reused regardless of type."""
        service = AgentService()
        with patch("mdpilot.api.services.agent_service.get_session", _mock_session):
            agent1 = await service.get_or_create_agent("session_reuse", prompt="你好")
            agent2 = await service.get_or_create_agent("session_reuse", prompt="预测结构然后分析功能")
        assert agent1 is agent2
        assert isinstance(agent1, ReActAgent)
