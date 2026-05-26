"""Tests for RecoveryValidator (D-level)."""

import pytest

from mdpilot.coordination.config import RecoveryPolicies
from mdpilot.coordination.types import (
    ExecutionPlan,
    PlanStep,
    ResourceEstimate,
    Severity,
)
from mdpilot.coordination.validators.recovery_validator import RecoveryValidator


@pytest.fixture
def default_policies():
    """Default recovery policies."""
    return RecoveryPolicies(
        max_retries=3,
        retry_delay=1.0,
        allowed_strategies=[
            "retry_with_backoff",
            "fallback_tool",
            "skip_step",
            "abort_plan"
        ]
    )


@pytest.fixture
def validator(default_policies):
    """RecoveryValidator with default policies."""
    return RecoveryValidator(default_policies)


@pytest.fixture
def valid_plan():
    """Valid plan with proper error handling."""
    return ExecutionPlan(
        plan_id="test-plan",
        task_description="Valid recovery plan",
        steps=[
            PlanStep(
                step_id="step1",
                action="prepare_system",
                intent="Prepare",
                error_handling="retry_with_backoff",
                parameters={"max_retries": 3}
            ),
            PlanStep(
                step_id="step2",
                action="minimize",
                intent="Minimize",
                error_handling="fallback_tool",
                parameters={"fallback_tool": "alternative_minimizer"}
            ),
            PlanStep(
                step_id="step3",
                action="equilibrate",
                intent="Equilibrate",
                error_handling="skip_step"
            )
        ],
        estimated_resources=ResourceEstimate()
    )


class TestRecoveryValidator:
    """Test RecoveryValidator functionality."""

    def test_validator_level(self, validator):
        """Test validator reports correct level."""
        assert validator.level == "D"

    def test_valid_plan_passes(self, validator, valid_plan):
        """Test valid plan passes validation."""
        result = validator.validate(valid_plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_missing_error_handling(self, validator):
        """Test missing error_handling violation."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Missing error handling",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="prepare_system",
                    intent="Prepare",
                    error_handling=None
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.level == "D"
        assert violation.severity == Severity.ERROR
        assert "missing error_handling strategy" in violation.message
        assert violation.step_id == "step1"
        assert violation.fixable is True
        assert "Add error_handling" in violation.suggested_fix

    def test_invalid_recovery_strategy(self, validator):
        """Test invalid recovery strategy violation."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Invalid strategy",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="prepare_system",
                    intent="Prepare",
                    error_handling="invalid_strategy"
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.level == "D"
        assert violation.severity == Severity.ERROR
        assert "Invalid recovery strategy" in violation.message
        assert "invalid_strategy" in violation.message
        assert violation.step_id == "step1"
        assert violation.fixable is True
        assert "Use one of:" in violation.suggested_fix

    def test_max_retries_exceeded(self, validator):
        """Test max_retries exceeds limit violation."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Too many retries",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="prepare_system",
                    intent="Prepare",
                    error_handling="retry_with_backoff",
                    parameters={"max_retries": 10}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.level == "D"
        assert violation.severity == Severity.ERROR
        assert "max_retries 10 exceeds limit 3" in violation.message
        assert violation.step_id == "step1"
        assert violation.fixable is True
        assert "max_retries <= 3" in violation.suggested_fix

    def test_negative_max_retries(self, validator):
        """Test negative max_retries violation."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Negative retries",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="prepare_system",
                    intent="Prepare",
                    error_handling="retry_with_backoff",
                    parameters={"max_retries": -1}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.level == "D"
        assert violation.severity == Severity.ERROR
        assert "negative max_retries" in violation.message
        assert violation.step_id == "step1"
        assert violation.fixable is True
        assert "non-negative value" in violation.suggested_fix

    def test_missing_fallback_tool(self, validator):
        """Test fallback strategy without fallback_tool violation."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Missing fallback tool",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="minimize",
                    intent="Minimize",
                    error_handling="fallback_tool",
                    parameters={}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.level == "D"
        assert violation.severity == Severity.ERROR
        assert "no fallback_tool specified" in violation.message
        assert violation.step_id == "step1"
        assert violation.fixable is True
        assert "Add fallback_tool parameter" in violation.suggested_fix

    def test_multiple_violations(self, validator):
        """Test multiple recovery violations."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Multiple violations",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="prepare_system",
                    intent="Prepare",
                    error_handling=None
                ),
                PlanStep(
                    step_id="step2",
                    action="minimize",
                    intent="Minimize",
                    error_handling="invalid_strategy"
                ),
                PlanStep(
                    step_id="step3",
                    action="equilibrate",
                    intent="Equilibrate",
                    error_handling="retry_with_backoff",
                    parameters={"max_retries": 10}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 3

        # All violations should be ERROR and fixable
        for violation in result.violations:
            assert violation.level == "D"
            assert violation.severity == Severity.ERROR
            assert violation.fixable is True

    def test_retry_without_max_retries_parameter(self, validator):
        """Test retry strategy without max_retries parameter is valid."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Retry without max_retries",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="prepare_system",
                    intent="Prepare",
                    error_handling="retry_with_backoff",
                    parameters={}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_custom_recovery_policies(self):
        """Test validator with custom recovery policies."""
        custom_policies = RecoveryPolicies(
            max_retries=5,
            retry_delay=2.0,
            allowed_strategies=["retry", "abort"]
        )
        validator = RecoveryValidator(custom_policies)

        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Custom policies",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="prepare_system",
                    intent="Prepare",
                    error_handling="retry",
                    parameters={"max_retries": 4}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_all_allowed_strategies(self, validator):
        """Test all allowed strategies pass validation."""
        strategies = [
            "retry_with_backoff",
            "fallback_tool",
            "skip_step",
            "abort_plan"
        ]

        for strategy in strategies:
            params = {}
            if "fallback" in strategy:
                params["fallback_tool"] = "alternative"

            plan = ExecutionPlan(
                plan_id="test-plan",
                task_description=f"Test {strategy}",
                steps=[
                    PlanStep(
                        step_id="step1",
                        action="test",
                        intent="Test",
                        error_handling=strategy,
                        parameters=params
                    )
                ],
                estimated_resources=ResourceEstimate()
            )

            result = validator.validate(plan)
            assert result.valid is True, f"Strategy {strategy} should be valid"

    def test_zero_max_retries_allowed(self, validator):
        """Test zero max_retries is valid."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Zero retries",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="prepare_system",
                    intent="Prepare",
                    error_handling="retry_with_backoff",
                    parameters={"max_retries": 0}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_exact_max_retries_limit(self, validator):
        """Test max_retries at exact limit is valid."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Exact limit",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="prepare_system",
                    intent="Prepare",
                    error_handling="retry_with_backoff",
                    parameters={"max_retries": 3}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_fallback_with_tool_specified(self, validator):
        """Test fallback strategy with fallback_tool is valid."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Fallback with tool",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="minimize",
                    intent="Minimize",
                    error_handling="fallback_tool",
                    parameters={"fallback_tool": "alternative_minimizer"}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0
