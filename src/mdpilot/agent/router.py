"""AgentRouter — select the appropriate agent paradigm for a task."""

from __future__ import annotations

from typing import Type

from .base import AgentBase
from .react_agent import ReActAgent
from .plan_solve import PlanAndSolveAgent
from .reflection import ReflectionAgent
from .task_classifier import classify_paradigm


class AgentRouter:
    """Routes user prompts to the appropriate agent paradigm.

    Uses TaskClassifier for initial classification, then selects between
    ReActAgent, PlanAndSolveAgent, and ReflectionAgent.
    """

    def select_agent(self, prompt: str) -> Type[AgentBase]:
        """Select the agent class for the given prompt."""
        if not prompt or not prompt.strip():
            return ReActAgent

        paradigm = classify_paradigm(prompt)

        if paradigm == "plan_solve":
            return PlanAndSolveAgent
        elif paradigm == "reflection":
            return ReflectionAgent
        else:
            return ReActAgent
