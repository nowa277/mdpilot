"""Tests for ToolValidator (B-level)."""

import pytest

from mdpilot.coordination.config import ToolConstraints
from mdpilot.coordination.types import (
    ExecutionPlan,
    PlanStep,
    ResourceEstimate,
    Severity,
)
from mdpilot.coordination.validators.tool_validator import ToolValidator


@pytest.fixture
def default_constraints():
    """Default tool constraints."""
    return ToolConstraints(
        required_parameters={
            "tleap": ["input_file", "output_file"],
            "pmemd": ["topology", "coordinates", "config"],
            "cpptraj": ["topology", "trajectory"]
        },
        parameter_ranges={
            "pmemd": {
                "nsteps": {"min": 1, "max": 1000000},
                "temperature": {"min": 0, "max": 500},
                "pressure": {"min": 0, "max": 10}
            },
            "cpptraj": {
                "stride": {"min": 1, "max": 1000},
                "format": {"allowed": ["pdb", "dcd", "netcdf", "xtc"]}
            }
        }
    )


@pytest.fixture
def validator(default_constraints):
    """ToolValidator with default constraints."""
    return ToolValidator(default_constraints)


@pytest.fixture
def valid_plan():
    """Valid plan with proper tool parameters."""
    return ExecutionPlan(
        plan_id="test-plan",
        task_description="Valid tool plan",
        steps=[
            PlanStep(
                step_id="step1",
                action="prepare_system",
                intent="Prepare",
                required_tools=["tleap"],
                parameters={
                    "input_file": "system.in",
                    "output_file": "system.prmtop"
                }
            ),
            PlanStep(
                step_id="step2",
                action="minimize",
                intent="Minimize",
                required_tools=["pmemd"],
                parameters={
                    "topology": "system.prmtop",
                    "coordinates": "system.inpcrd",
                    "config": "min.in",
                    "nsteps": 5000,
                    "temperature": 300
                }
            )
        ],
        estimated_resources=ResourceEstimate()
    )


class TestToolValidator:
    """Test ToolValidator functionality."""

    def test_validator_level(self, validator):
        """Test validator reports correct level."""
        assert validator.level == "B"

    def test_valid_plan_passes(self, validator, valid_plan):
        """Test valid plan passes validation."""
        result = validator.validate(valid_plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_missing_required_parameter(self, validator):
        """Test missing required parameter violation."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Missing parameter",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="prepare_system",
                    intent="Prepare",
                    required_tools=["tleap"],
                    parameters={"input_file": "system.in"}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.level == "B"
        assert violation.severity == Severity.WARNING
        assert "missing required parameter 'output_file'" in violation.message
        assert violation.step_id == "step1"
        assert violation.fixable is True
        assert "Add 'output_file' parameter" in violation.suggested_fix

    def test_parameter_below_minimum(self, validator):
        """Test parameter below minimum value violation."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Below minimum",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="minimize",
                    intent="Minimize",
                    required_tools=["pmemd"],
                    parameters={
                        "topology": "system.prmtop",
                        "coordinates": "system.inpcrd",
                        "config": "min.in",
                        "nsteps": 0
                    }
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.level == "B"
        assert violation.severity == Severity.WARNING
        assert "below minimum" in violation.message
        assert "nsteps" in violation.message
        assert violation.step_id == "step1"
        assert violation.fixable is True

    def test_parameter_above_maximum(self, validator):
        """Test parameter above maximum value violation."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Above maximum",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="minimize",
                    intent="Minimize",
                    required_tools=["pmemd"],
                    parameters={
                        "topology": "system.prmtop",
                        "coordinates": "system.inpcrd",
                        "config": "min.in",
                        "temperature": 600
                    }
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.level == "B"
        assert violation.severity == Severity.WARNING
        assert "exceeds maximum" in violation.message
        assert "temperature" in violation.message
        assert violation.step_id == "step1"
        assert violation.fixable is True

    def test_parameter_not_in_allowed_values(self, validator):
        """Test parameter not in allowed values violation."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Invalid value",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="analyze",
                    intent="Analyze",
                    required_tools=["cpptraj"],
                    parameters={
                        "topology": "system.prmtop",
                        "trajectory": "prod.nc",
                        "format": "xyz"
                    }
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.level == "B"
        assert violation.severity == Severity.WARNING
        assert "not in allowed values" in violation.message
        assert "format" in violation.message
        assert "xyz" in violation.message
        assert violation.step_id == "step1"
        assert violation.fixable is True
        assert "Use one of:" in violation.suggested_fix

    def test_multiple_missing_parameters(self, validator):
        """Test multiple missing required parameters."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Multiple missing",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="minimize",
                    intent="Minimize",
                    required_tools=["pmemd"],
                    parameters={"topology": "system.prmtop"}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 2

        # Check both coordinates and config are reported missing
        messages = [v.message for v in result.violations]
        assert any("coordinates" in msg for msg in messages)
        assert any("config" in msg for msg in messages)

        # All violations should be WARNING and fixable
        for violation in result.violations:
            assert violation.level == "B"
            assert violation.severity == Severity.WARNING
            assert violation.fixable is True

    def test_multiple_range_violations(self, validator):
        """Test multiple parameter range violations."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Multiple range violations",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="minimize",
                    intent="Minimize",
                    required_tools=["pmemd"],
                    parameters={
                        "topology": "system.prmtop",
                        "coordinates": "system.inpcrd",
                        "config": "min.in",
                        "nsteps": 2000000,
                        "temperature": -10
                    }
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 2

        # All violations should be WARNING and fixable
        for violation in result.violations:
            assert violation.level == "B"
            assert violation.severity == Severity.WARNING
            assert violation.fixable is True

    def test_tool_without_constraints(self, validator):
        """Test tool without defined constraints passes."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Unconstrained tool",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="custom",
                    intent="Custom",
                    required_tools=["custom_tool"],
                    parameters={"any_param": "any_value"}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_step_without_required_tools(self, validator):
        """Test step without required_tools passes."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="No tools",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="prepare",
                    intent="Prepare",
                    required_tools=[],
                    parameters={"some_param": "value"}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_parameter_at_exact_minimum(self, validator):
        """Test parameter at exact minimum is valid."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Exact minimum",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="minimize",
                    intent="Minimize",
                    required_tools=["pmemd"],
                    parameters={
                        "topology": "system.prmtop",
                        "coordinates": "system.inpcrd",
                        "config": "min.in",
                        "nsteps": 1
                    }
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_parameter_at_exact_maximum(self, validator):
        """Test parameter at exact maximum is valid."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Exact maximum",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="minimize",
                    intent="Minimize",
                    required_tools=["pmemd"],
                    parameters={
                        "topology": "system.prmtop",
                        "coordinates": "system.inpcrd",
                        "config": "min.in",
                        "temperature": 500
                    }
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_custom_tool_constraints(self):
        """Test validator with custom tool constraints."""
        custom_constraints = ToolConstraints(
            required_parameters={
                "custom_tool": ["input", "output"]
            },
            parameter_ranges={
                "custom_tool": {
                    "level": {"allowed": ["low", "medium", "high"]}
                }
            }
        )
        validator = ToolValidator(custom_constraints)

        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Custom constraints",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="custom",
                    intent="Custom",
                    required_tools=["custom_tool"],
                    parameters={
                        "input": "data.in",
                        "output": "data.out",
                        "level": "medium"
                    }
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_extra_parameters_allowed(self, validator):
        """Test that extra parameters beyond required are allowed."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Extra parameters",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="prepare_system",
                    intent="Prepare",
                    required_tools=["tleap"],
                    parameters={
                        "input_file": "system.in",
                        "output_file": "system.prmtop",
                        "extra_param": "extra_value",
                        "another_param": 123
                    }
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_all_allowed_format_values(self, validator):
        """Test all allowed format values pass validation."""
        formats = ["pdb", "dcd", "netcdf", "xtc"]

        for fmt in formats:
            plan = ExecutionPlan(
                plan_id="test-plan",
                task_description=f"Test {fmt}",
                steps=[
                    PlanStep(
                        step_id="step1",
                        action="analyze",
                        intent="Analyze",
                        required_tools=["cpptraj"],
                        parameters={
                            "topology": "system.prmtop",
                            "trajectory": "prod.nc",
                            "format": fmt
                        }
                    )
                ],
                estimated_resources=ResourceEstimate()
            )

            result = validator.validate(plan)
            assert result.valid is True, f"Format {fmt} should be valid"

    def test_multiple_tools_in_step(self, validator):
        """Test step with multiple required tools."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Multiple tools",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="complex",
                    intent="Complex",
                    required_tools=["tleap", "pmemd"],
                    parameters={
                        "input_file": "system.in",
                        "output_file": "system.prmtop",
                        "topology": "system.prmtop",
                        "coordinates": "system.inpcrd",
                        "config": "min.in"
                    }
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_parameter_range_only_min(self):
        """Test parameter range with only minimum constraint."""
        constraints = ToolConstraints(
            parameter_ranges={
                "tool": {
                    "value": {"min": 10}
                }
            }
        )
        validator = ToolValidator(constraints)

        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Min only",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="test",
                    intent="Test",
                    required_tools=["tool"],
                    parameters={"value": 100}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True

    def test_parameter_range_only_max(self):
        """Test parameter range with only maximum constraint."""
        constraints = ToolConstraints(
            parameter_ranges={
                "tool": {
                    "value": {"max": 100}
                }
            }
        )
        validator = ToolValidator(constraints)

        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Max only",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="test",
                    intent="Test",
                    required_tools=["tool"],
                    parameters={"value": 50}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
