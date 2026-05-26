# src/mdpilot/agent/plan_types.py
"""Data types for PlanAndSolve agent paradigm."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PlanStep:
    """A single step in an execution plan."""

    step_id: str
    action: str
    tool_name: str
    parameters: dict[str, Any] = field(default_factory=dict)
    expected_output: str = ""
    status: str = "pending"  # pending | running | completed | failed
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action": self.action,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "expected_output": self.expected_output,
            "status": self.status,
        }


@dataclass
class StepResult:
    """Result from executing a single plan step."""

    step_id: str
    success: bool
    output: str
    tool_call_id: str = ""
    error: Optional[str] = None
    is_async_job: bool = False
    job_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "success": self.success,
            "output": self.output,
            "error": self.error,
        }


@dataclass
class AgentPlan:
    """An execution plan with ordered steps."""

    task: str
    steps: list[PlanStep] = field(default_factory=list)
    status: str = "planned"  # planned | executing | completed | failed | replanning

    def get_step(self, step_id: str) -> PlanStep:
        for s in self.steps:
            if s.step_id == step_id:
                return s
        raise KeyError(f"Step {step_id} not found")

    def mark_step_done(self, step_id: str) -> None:
        self.get_step(step_id).status = "completed"

    def mark_step_failed(self, step_id: str, error: str) -> None:
        step = self.get_step(step_id)
        step.status = "failed"
        step.error = error

    def has_pending_steps(self) -> bool:
        return any(s.status == "pending" for s in self.steps)

    def get_pending_steps(self) -> list[PlanStep]:
        return [s for s in self.steps if s.status == "pending"]

    def get_completed_results_text(self) -> str:
        parts = []
        for s in self.steps:
            if s.status == "completed":
                parts.append(f"- {s.action}: completed")
            elif s.status == "failed":
                parts.append(f"- {s.action}: failed ({s.error})")
        return "\n".join(parts)

    def to_prompt_text(self) -> str:
        lines = [f"Task: {self.task}", "", "Steps:"]
        for i, s in enumerate(self.steps, 1):
            lines.append(f"  {i}. [{s.status}] {s.action} (tool: {s.tool_name})")
        return "\n".join(lines)
