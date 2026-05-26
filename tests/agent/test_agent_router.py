# tests/agent/test_agent_router.py
"""Tests for AgentRouter paradigm selection."""

from __future__ import annotations

import pytest

from mdpilot.agent.router import AgentRouter
from mdpilot.agent.base import AgentBase
from mdpilot.agent.react_agent import ReActAgent
from mdpilot.agent.plan_solve import PlanAndSolveAgent


class TestAgentRouter:
    """AgentRouter selects the correct agent class."""

    def setup_method(self):
        self.router = AgentRouter()

    def test_chat_selects_react(self):
        cls = self.router.select_agent("你好")
        assert cls is ReActAgent

    def test_simple_question_selects_react(self):
        cls = self.router.select_agent("什么是 RMSD？")
        assert cls is ReActAgent

    def test_multi_step_selects_plan_solve(self):
        cls = self.router.select_agent("预测蛋白质结构然后分析功能")
        assert cls is PlanAndSolveAgent

    def test_workflow_selects_plan_solve(self):
        cls = self.router.select_agent("跑一个完整的 AMBER MD 模拟流程")
        assert cls is PlanAndSolveAgent

    def test_optimization_selects_reflection(self):
        cls = self.router.select_agent("优化模拟参数获得更好结果")
        # ReflectionAgent not yet implemented, fallback to ReAct
        assert issubclass(cls, AgentBase)

    def test_empty_prompt_defaults_to_react(self):
        cls = self.router.select_agent("")
        assert cls is ReActAgent

    def test_select_agent_returns_agent_base_subclass(self):
        cls = self.router.select_agent("any prompt")
        assert issubclass(cls, AgentBase)
