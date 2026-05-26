# tests/agent/test_plan_types.py
"""Tests for PlanAndSolve data types."""

from __future__ import annotations

import pytest

from mdpilot.agent.plan_types import PlanStep, AgentPlan, StepResult


class TestPlanStep:
    def test_create_plan_step(self):
        step = PlanStep(
            step_id="step_1",
            action="Run AlphaFold2 prediction",
            tool_name="alphafold2_predict",
            parameters={"sequence": "MVHL..."},
            expected_output="PDB file with predicted structure",
        )
        assert step.step_id == "step_1"
        assert step.tool_name == "alphafold2_predict"

    def test_plan_step_default_status(self):
        step = PlanStep(step_id="s1", action="test", tool_name="bash")
        assert step.status == "pending"


class TestAgentPlan:
    def test_create_plan(self):
        steps = [
            PlanStep(step_id="s1", action="Prepare", tool_name="pdb4amber"),
            PlanStep(step_id="s2", action="Predict", tool_name="alphafold2_predict"),
        ]
        plan = AgentPlan(task="Protein prediction", steps=steps)
        assert len(plan.steps) == 2
        assert plan.status == "planned"

    def test_plan_step_lookup(self):
        steps = [PlanStep(step_id="s1", action="A", tool_name="bash")]
        plan = AgentPlan(task="test", steps=steps)
        assert plan.get_step("s1").action == "A"

    def test_plan_mark_step_done(self):
        steps = [PlanStep(step_id="s1", action="A", tool_name="bash")]
        plan = AgentPlan(task="test", steps=steps)
        plan.mark_step_done("s1")
        assert plan.get_step("s1").status == "completed"

    def test_plan_has_pending(self):
        steps = [
            PlanStep(step_id="s1", action="A", tool_name="bash"),
            PlanStep(step_id="s2", action="B", tool_name="bash"),
        ]
        plan = AgentPlan(task="test", steps=steps)
        plan.mark_step_done("s1")
        assert plan.has_pending_steps() is True


class TestStepResult:
    def test_step_result_success(self):
        result = StepResult(
            step_id="s1",
            success=True,
            output="Structure predicted",
            tool_call_id="call_1",
        )
        assert result.success is True
        assert result.output == "Structure predicted"

    def test_step_result_failure(self):
        result = StepResult(
            step_id="s1",
            success=False,
            output="",
            error="Timeout",
            tool_call_id="call_1",
        )
        assert result.success is False
        assert result.error == "Timeout"
