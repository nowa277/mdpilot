"""Tests for ResourceValidator (E-level)."""

import pytest

from mdpilot.coordination.config import ResourceLimits
from mdpilot.coordination.types import (
    ExecutionPlan,
    PlanStep,
    ResourceEstimate,
    Severity,
)
from mdpilot.coordination.validators.resource_validator import ResourceValidator


@pytest.fixture
def default_limits():
    """Default resource limits."""
    return ResourceLimits(
        max_cpu_hours=10.0,
        max_memory_gb=16.0,
        max_disk_gb=50.0
    )


@pytest.fixture
def validator(default_limits):
    """ResourceValidator with default limits."""
    return ResourceValidator(default_limits)


@pytest.fixture
def valid_plan():
    """Valid plan within all limits."""
    return ExecutionPlan(
        plan_id="test-plan",
        task_description="Test task",
        steps=[
            PlanStep(
                step_id="step1",
                action="test_action",
                intent="Test intent"
            )
        ],
        estimated_resources=ResourceEstimate(
            cpu_hours=5.0,
            memory_gb=8.0,
            disk_gb=25.0
        )
    )


class TestResourceValidator:
    """Test ResourceValidator functionality."""

    def test_validator_level(self, validator):
        """Test validator reports correct level."""
        assert validator.level == "E"

    def test_valid_plan_passes(self, validator, valid_plan):
        """Test valid plan passes validation."""
        result = validator.validate(valid_plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_cpu_hours_exceeds_limit(self, validator):
        """Test CPU hours violation."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="CPU intensive task",
            steps=[PlanStep(step_id="step1", action="compute", intent="Compute")],
            estimated_resources=ResourceEstimate(
                cpu_hours=15.0,  # Exceeds 10.0 limit
                memory_gb=8.0,
                disk_gb=25.0
            )
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.level == "E"
        assert violation.severity == Severity.CRITICAL
        assert "CPU hours" in violation.message
        assert "15.00" in violation.message
        assert "10.00" in violation.message
        assert violation.fixable is False

    def test_memory_exceeds_limit(self, validator):
        """Test memory violation."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Memory intensive task",
            steps=[PlanStep(step_id="step1", action="load", intent="Load data")],
            estimated_resources=ResourceEstimate(
                cpu_hours=5.0,
                memory_gb=20.0,  # Exceeds 16.0 limit
                disk_gb=25.0
            )
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.level == "E"
        assert violation.severity == Severity.CRITICAL
        assert "Memory" in violation.message
        assert "20.00" in violation.message
        assert "16.00" in violation.message
        assert violation.fixable is False

    def test_disk_exceeds_limit(self, validator):
        """Test disk usage violation."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Disk intensive task",
            steps=[PlanStep(step_id="step1", action="write", intent="Write data")],
            estimated_resources=ResourceEstimate(
                cpu_hours=5.0,
                memory_gb=8.0,
                disk_gb=60.0  # Exceeds 50.0 limit
            )
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.level == "E"
        assert violation.severity == Severity.CRITICAL
        assert "Disk usage" in violation.message
        assert "60.00" in violation.message
        assert "50.00" in violation.message
        assert violation.fixable is False

    def test_multiple_violations(self, validator):
        """Test multiple resource violations."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Resource intensive task",
            steps=[PlanStep(step_id="step1", action="process", intent="Process")],
            estimated_resources=ResourceEstimate(
                cpu_hours=15.0,  # Exceeds limit
                memory_gb=20.0,  # Exceeds limit
                disk_gb=60.0     # Exceeds limit
            )
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 3

        # Check all violations are CRITICAL
        for violation in result.violations:
            assert violation.level == "E"
            assert violation.severity == Severity.CRITICAL
            assert violation.fixable is False

    def test_exact_limit_passes(self, validator):
        """Test plan at exact limit passes."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="At limit task",
            steps=[PlanStep(step_id="step1", action="test", intent="Test")],
            estimated_resources=ResourceEstimate(
                cpu_hours=10.0,  # Exactly at limit
                memory_gb=16.0,  # Exactly at limit
                disk_gb=50.0     # Exactly at limit
            )
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_zero_resources_passes(self, validator):
        """Test plan with zero resources passes."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Zero resource task",
            steps=[PlanStep(step_id="step1", action="noop", intent="No-op")],
            estimated_resources=ResourceEstimate(
                cpu_hours=0.0,
                memory_gb=0.0,
                disk_gb=0.0
            )
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_custom_limits(self):
        """Test validator with custom limits."""
        custom_limits = ResourceLimits(
            max_cpu_hours=5.0,
            max_memory_gb=8.0,
            max_disk_gb=20.0
        )
        validator = ResourceValidator(custom_limits)

        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Test task",
            steps=[PlanStep(step_id="step1", action="test", intent="Test")],
            estimated_resources=ResourceEstimate(
                cpu_hours=6.0,  # Exceeds custom limit
                memory_gb=4.0,
                disk_gb=10.0
            )
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1
        assert "6.00" in result.violations[0].message
        assert "5.00" in result.violations[0].message

    def test_just_below_limit_passes(self, validator):
        """Test plan just below limit passes."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Just below limit",
            steps=[PlanStep(step_id="step1", action="test", intent="Test")],
            estimated_resources=ResourceEstimate(
                cpu_hours=9.99,
                memory_gb=15.99,
                disk_gb=49.99
            )
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_just_above_limit_fails(self, validator):
        """Test plan just above limit fails."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Just above limit",
            steps=[PlanStep(step_id="step1", action="test", intent="Test")],
            estimated_resources=ResourceEstimate(
                cpu_hours=10.01,
                memory_gb=8.0,
                disk_gb=25.0
            )
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1
        assert "10.01" in result.violations[0].message

    def test_violation_messages_formatted(self, validator):
        """Test violation messages are properly formatted."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Test formatting",
            steps=[PlanStep(step_id="step1", action="test", intent="Test")],
            estimated_resources=ResourceEstimate(
                cpu_hours=12.5,
                memory_gb=8.0,
                disk_gb=25.0
            )
        )

        result = validator.validate(plan)
        violation = result.violations[0]

        # Check message contains both values with 2 decimal places
        assert "12.50" in violation.message
        assert "10.00" in violation.message
        assert "exceeds limit" in violation.message
