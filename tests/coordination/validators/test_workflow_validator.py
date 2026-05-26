"""Tests for WorkflowValidator (C-level)."""

import pytest

from mdpilot.coordination.config import GuardrailConfig, WorkflowRules
from mdpilot.coordination.types import (
    ExecutionPlan,
    PlanStep,
    ResourceEstimate,
    Severity,
)
from mdpilot.coordination.validators.workflow_validator import WorkflowValidator


@pytest.fixture
def default_config():
    """Default guardrail configuration."""
    return GuardrailConfig(
        workflow_rules=WorkflowRules(
            required_steps=["prepare_system", "minimize", "equilibrate"],
            step_order_constraints={
                "minimize": ["prepare_system"],
                "equilibrate": ["minimize"],
                "production": ["equilibrate"]
            }
        )
    )


@pytest.fixture
def validator(default_config):
    """WorkflowValidator with default config."""
    return WorkflowValidator(default_config)


@pytest.fixture
def valid_plan():
    """Valid plan with all required steps in correct order."""
    return ExecutionPlan(
        plan_id="test-plan",
        task_description="Valid workflow",
        steps=[
            PlanStep(step_id="step1", action="prepare_system", intent="Prepare"),
            PlanStep(step_id="step2", action="minimize", intent="Minimize"),
            PlanStep(step_id="step3", action="equilibrate", intent="Equilibrate")
        ],
        estimated_resources=ResourceEstimate()
    )


class TestWorkflowValidator:
    """Test WorkflowValidator functionality."""

    def test_validator_level(self, validator):
        """Test validator reports correct level."""
        assert validator.level == "C"

    def test_valid_plan_passes(self, validator, valid_plan):
        """Test valid plan passes validation."""
        result = validator.validate(valid_plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_missing_required_step(self, validator):
        """Test missing required step violation."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Missing minimize step",
            steps=[
                PlanStep(step_id="step1", action="prepare_system", intent="Prepare"),
                PlanStep(step_id="step2", action="equilibrate", intent="Equilibrate")
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.level == "C"
        assert violation.severity == Severity.ERROR
        assert "Missing required step: minimize" in violation.message
        assert violation.fixable is True
        assert "Add minimize step" in violation.suggested_fix

    def test_wrong_step_order(self, validator):
        """Test step order constraint violation."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Wrong order",
            steps=[
                PlanStep(step_id="step1", action="minimize", intent="Minimize"),
                PlanStep(step_id="step2", action="prepare_system", intent="Prepare"),
                PlanStep(step_id="step3", action="equilibrate", intent="Equilibrate")
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.level == "C"
        assert violation.severity == Severity.ERROR
        assert "minimize must come after prepare_system" in violation.message
        assert violation.step_id == "minimize"
        assert violation.fixable is True
        assert "prepare_system before minimize" in violation.suggested_fix

    def test_multiple_missing_steps(self, validator):
        """Test multiple missing required steps."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Multiple missing",
            steps=[
                PlanStep(step_id="step1", action="prepare_system", intent="Prepare")
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 2

        # Check both minimize and equilibrate are reported missing
        messages = [v.message for v in result.violations]
        assert any("minimize" in msg for msg in messages)
        assert any("equilibrate" in msg for msg in messages)

        # All violations should be ERROR and fixable
        for violation in result.violations:
            assert violation.level == "C"
            assert violation.severity == Severity.ERROR
            assert violation.fixable is True

    def test_multiple_order_violations(self, validator):
        """Test multiple step order violations."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Multiple order violations",
            steps=[
                PlanStep(step_id="step1", action="production", intent="Production"),
                PlanStep(step_id="step2", action="equilibrate", intent="Equilibrate"),
                PlanStep(step_id="step3", action="minimize", intent="Minimize"),
                PlanStep(step_id="step4", action="prepare_system", intent="Prepare")
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        # Should have violations for production, equilibrate, and minimize order
        assert len(result.violations) >= 3

        for violation in result.violations:
            assert violation.level == "C"
            assert violation.severity == Severity.ERROR
            assert violation.fixable is True

    def test_empty_plan(self, validator):
        """Test empty plan fails validation."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Empty plan",
            steps=[],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        # Should report all required steps as missing
        assert len(result.violations) == 3

    def test_duplicate_steps(self, validator):
        """Test duplicate step detection."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Duplicate steps",
            steps=[
                PlanStep(step_id="step1", action="prepare_system", intent="Prepare"),
                PlanStep(step_id="step2", action="minimize", intent="Minimize"),
                PlanStep(step_id="step3", action="minimize", intent="Minimize again"),
                PlanStep(step_id="step4", action="equilibrate", intent="Equilibrate")
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.level == "C"
        assert violation.severity == Severity.ERROR
        assert "Duplicate step: minimize" in violation.message
        assert violation.fixable is True
        assert "Remove duplicate minimize step" in violation.suggested_fix

    def test_custom_workflow_rules(self):
        """Test validator with custom workflow rules."""
        custom_config = GuardrailConfig(
            workflow_rules=WorkflowRules(
                required_steps=["init", "process"],
                step_order_constraints={
                    "process": ["init"],
                    "finalize": ["process"]
                }
            )
        )
        validator = WorkflowValidator(custom_config)

        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Custom workflow",
            steps=[
                PlanStep(step_id="step1", action="init", intent="Initialize"),
                PlanStep(step_id="step2", action="process", intent="Process")
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_extra_steps_allowed(self, validator):
        """Test that extra steps beyond required are allowed."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Extra steps",
            steps=[
                PlanStep(step_id="step1", action="prepare_system", intent="Prepare"),
                PlanStep(step_id="step2", action="minimize", intent="Minimize"),
                PlanStep(step_id="step3", action="equilibrate", intent="Equilibrate"),
                PlanStep(step_id="step4", action="production", intent="Production"),
                PlanStep(step_id="step5", action="analysis", intent="Analysis")
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_partial_order_constraints(self, validator):
        """Test order constraints only apply to steps present in plan."""
        # Plan without 'production' step should not trigger production constraints
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Partial workflow",
            steps=[
                PlanStep(step_id="step1", action="prepare_system", intent="Prepare"),
                PlanStep(step_id="step2", action="minimize", intent="Minimize"),
                PlanStep(step_id="step3", action="equilibrate", intent="Equilibrate")
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_no_required_steps(self):
        """Test validator with no required steps."""
        config = GuardrailConfig(
            workflow_rules=WorkflowRules(
                required_steps=[],
                step_order_constraints={}
            )
        )
        validator = WorkflowValidator(config)

        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="No requirements",
            steps=[
                PlanStep(step_id="step1", action="anything", intent="Do anything")
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_complex_order_constraints(self):
        """Test complex multi-level order constraints."""
        config = GuardrailConfig(
            workflow_rules=WorkflowRules(
                required_steps=["A", "B", "C"],
                step_order_constraints={
                    "B": ["A"],
                    "C": ["A", "B"],
                    "D": ["C"]
                }
            )
        )
        validator = WorkflowValidator(config)

        # Valid order: A -> B -> C -> D
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Complex order",
            steps=[
                PlanStep(step_id="step1", action="A", intent="Step A"),
                PlanStep(step_id="step2", action="B", intent="Step B"),
                PlanStep(step_id="step3", action="C", intent="Step C"),
                PlanStep(step_id="step4", action="D", intent="Step D")
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_violation_step_id_populated(self, validator):
        """Test that violations include step_id when applicable."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Order violation",
            steps=[
                PlanStep(step_id="step1", action="minimize", intent="Minimize"),
                PlanStep(step_id="step2", action="prepare_system", intent="Prepare"),
                PlanStep(step_id="step3", action="equilibrate", intent="Equilibrate")
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False

        # Order violation should have step_id
        order_violations = [v for v in result.violations if "must come after" in v.message]
        assert len(order_violations) > 0
        assert order_violations[0].step_id == "minimize"

    def test_all_violations_are_fixable(self, validator):
        """Test that all C-level violations are marked as fixable."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Multiple issues",
            steps=[
                PlanStep(step_id="step1", action="equilibrate", intent="Equilibrate"),
                PlanStep(step_id="step2", action="minimize", intent="Minimize")
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False

        # All violations should be fixable
        for violation in result.violations:
            assert violation.fixable is True
            assert violation.suggested_fix is not None
            assert len(violation.suggested_fix) > 0
