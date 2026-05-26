"""Plan data models for the Plan-then-Execute engine."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    """A single executable step within a plan.

    Attributes
    ----------
    id : int
        Unique step identifier, assigned during plan creation.
    description : str
        Human-readable description of what this step does.
    tool : str
        Name of the tool to invoke.
    arguments : dict
        Keyword arguments to pass to the tool.
    depends_on : list[int]
        Step IDs that must complete before this step runs.
    status : str
        Execution status: ``pending``, ``running``, ``completed``, ``failed``, ``skipped``.
    """

    id: int
    description: str
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[int] = Field(default_factory=list)
    status: str = "pending"


class Plan(BaseModel):
    """A multi-step execution plan.

    Attributes
    ----------
    goal : str
        The high-level user goal this plan addresses.
    steps : list[PlanStep]
        Ordered list of steps to execute.
    estimated_time : str | None
        Optional human-readable time estimate.
    """

    goal: str
    steps: list[PlanStep] = Field(default_factory=list)
    estimated_time: str | None = None


class PlanResult(BaseModel):
    """Result of executing a plan.

    Attributes
    ----------
    plan : Plan
        The original plan that was executed.
    results : dict[int, ToolOutput]
        Mapping from step ID to tool execution result.
    success : bool
        Whether all steps completed successfully.
    error : str | None
        Error message if execution failed.
    """

    plan: Plan
    results: dict[int, Any] = Field(default_factory=dict)
    success: bool = True
    error: str | None = None
