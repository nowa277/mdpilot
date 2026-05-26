"""Tests for coordination types."""

import pytest
from mdpilot.coordination.types import (
    Severity,
    ExecutionStatus,
    ResultStatus,
    RecoveryAction,
    ResourceEstimate,
    PlanStep,
    ExecutionPlan,
    Violation,
    ValidationResult,
    ToolCall,
    ExecutionSequence,
    ToolResult,
    ExecutionResult,
)


class TestEnums:
    """Test enum types."""

    def test_severity_values(self):
        assert Severity.CRITICAL == "critical"
        assert Severity.ERROR == "error"
        assert Severity.WARNING == "warning"

    def test_execution_status_values(self):
        assert ExecutionStatus.SUCCESS == "success"
        assert ExecutionStatus.FAILED == "failed"
        assert ExecutionStatus.PARTIAL == "partial"
        assert ExecutionStatus.RESOURCE_EXHAUSTED == "resource_exhausted"

    def test_result_status_values(self):
        assert ResultStatus.SUCCESS == "success"
        assert ResultStatus.FAILED == "failed"
        assert ResultStatus.SKIPPED == "skipped"

    def test_recovery_action_values(self):
        assert RecoveryAction.RETRY == "retry"
        assert RecoveryAction.SKIP == "skip"
        assert RecoveryAction.ABORT == "abort"
        assert RecoveryAction.FALLBACK == "fallback"


class TestResourceEstimate:
    """Test ResourceEstimate dataclass."""

    def test_default_values(self):
        estimate = ResourceEstimate()
        assert estimate.cpu_hours == 0.0
        assert estimate.memory_gb == 0.0
        assert estimate.disk_gb == 0.0

    def test_custom_values(self):
        estimate = ResourceEstimate(cpu_hours=2.5, memory_gb=8.0, disk_gb=20.0)
        assert estimate.cpu_hours == 2.5
        assert estimate.memory_gb == 8.0
        assert estimate.disk_gb == 20.0


class TestPlanStep:
    """Test PlanStep dataclass."""

    def test_required_fields(self):
        step = PlanStep(step_id="step1", action="minimize", intent="Energy minimization")
        assert step.step_id == "step1"
        assert step.action == "minimize"
        assert step.intent == "Energy minimization"

    def test_default_fields(self):
        step = PlanStep(step_id="step1", action="minimize", intent="Energy minimization")
        assert step.parameters == {}
        assert step.required_tools == []
        assert step.expected_output == ""
        assert step.error_handling is None

    def test_all_fields(self):
        step = PlanStep(
            step_id="step1",
            action="minimize",
            intent="Energy minimization",
            parameters={"maxcyc": 1000},
            required_tools=["sander"],
            expected_output="min.out",
            error_handling="retry"
        )
        assert step.parameters == {"maxcyc": 1000}
        assert step.required_tools == ["sander"]
        assert step.expected_output == "min.out"
        assert step.error_handling == "retry"


class TestExecutionPlan:
    """Test ExecutionPlan dataclass."""

    def test_minimal_plan(self):
        plan = ExecutionPlan(
            plan_id="plan1",
            task_description="Run MD simulation",
            steps=[PlanStep(step_id="step1", action="minimize", intent="Minimize")],
            estimated_resources=ResourceEstimate()
        )
        assert plan.plan_id == "plan1"
        assert plan.task_description == "Run MD simulation"
        assert len(plan.steps) == 1
        assert plan.dependencies == []
        assert plan.metadata == {}

    def test_validate_success(self):
        plan = ExecutionPlan(
            plan_id="plan1",
            task_description="Run MD simulation",
            steps=[PlanStep(step_id="step1", action="minimize", intent="Minimize")],
            estimated_resources=ResourceEstimate()
        )
        assert plan.validate() is True

    def test_validate_missing_plan_id(self):
        plan = ExecutionPlan(
            plan_id="",
            task_description="Run MD simulation",
            steps=[PlanStep(step_id="step1", action="minimize", intent="Minimize")],
            estimated_resources=ResourceEstimate()
        )
        with pytest.raises(ValueError, match="plan_id is required"):
            plan.validate()

    def test_validate_missing_task_description(self):
        plan = ExecutionPlan(
            plan_id="plan1",
            task_description="",
            steps=[PlanStep(step_id="step1", action="minimize", intent="Minimize")],
            estimated_resources=ResourceEstimate()
        )
        with pytest.raises(ValueError, match="task_description is required"):
            plan.validate()

    def test_validate_no_steps(self):
        plan = ExecutionPlan(
            plan_id="plan1",
            task_description="Run MD simulation",
            steps=[],
            estimated_resources=ResourceEstimate()
        )
        with pytest.raises(ValueError, match="plan must have at least one step"):
            plan.validate()

    def test_validate_step_missing_step_id(self):
        plan = ExecutionPlan(
            plan_id="plan1",
            task_description="Run MD simulation",
            steps=[PlanStep(step_id="", action="minimize", intent="Minimize")],
            estimated_resources=ResourceEstimate()
        )
        with pytest.raises(ValueError, match="step missing step_id"):
            plan.validate()

    def test_validate_step_missing_action(self):
        plan = ExecutionPlan(
            plan_id="plan1",
            task_description="Run MD simulation",
            steps=[PlanStep(step_id="step1", action="", intent="Minimize")],
            estimated_resources=ResourceEstimate()
        )
        with pytest.raises(ValueError, match="step step1 missing action"):
            plan.validate()


class TestViolation:
    """Test Violation dataclass."""

    def test_minimal_violation(self):
        violation = Violation(
            level="E",
            severity=Severity.CRITICAL,
            message="Resource limit exceeded",
            step_id="step1"
        )
        assert violation.level == "E"
        assert violation.severity == Severity.CRITICAL
        assert violation.message == "Resource limit exceeded"
        assert violation.step_id == "step1"
        assert violation.fixable is False
        assert violation.suggested_fix is None

    def test_fixable_violation(self):
        violation = Violation(
            level="B",
            severity=Severity.ERROR,
            message="Invalid parameter",
            step_id="step2",
            fixable=True,
            suggested_fix="Use maxcyc=1000"
        )
        assert violation.fixable is True
        assert violation.suggested_fix == "Use maxcyc=1000"


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_valid_result(self):
        result = ValidationResult(valid=True)
        assert result.valid is True
        assert result.violations == []

    def test_invalid_result(self):
        violation = Violation(
            level="E",
            severity=Severity.CRITICAL,
            message="Resource limit exceeded",
            step_id="step1"
        )
        result = ValidationResult(valid=False, violations=[violation])
        assert result.valid is False
        assert len(result.violations) == 1
        assert result.violations[0].message == "Resource limit exceeded"


class TestToolCall:
    """Test ToolCall dataclass."""

    def test_minimal_tool_call(self):
        call = ToolCall(tool_name="sander", parameters={"input": "min.in"})
        assert call.tool_name == "sander"
        assert call.parameters == {"input": "min.in"}
        assert call.metadata == {}

    def test_tool_call_with_metadata(self):
        call = ToolCall(
            tool_name="sander",
            parameters={"input": "min.in"},
            metadata={"timeout": 300}
        )
        assert call.metadata == {"timeout": 300}


class TestExecutionSequence:
    """Test ExecutionSequence dataclass."""

    def test_execution_sequence(self):
        calls = [
            ToolCall(tool_name="tleap", parameters={"input": "leap.in"}),
            ToolCall(tool_name="sander", parameters={"input": "min.in"})
        ]
        sequence = ExecutionSequence(plan_id="plan1", calls=calls)
        assert sequence.plan_id == "plan1"
        assert len(sequence.calls) == 2
        assert sequence.calls[0].tool_name == "tleap"
        assert sequence.calls[1].tool_name == "sander"


class TestToolResult:
    """Test ToolResult dataclass."""

    def test_success_result(self):
        result = ToolResult(status=ResultStatus.SUCCESS, output="Minimization complete")
        assert result.status == ResultStatus.SUCCESS
        assert result.output == "Minimization complete"
        assert result.error is None
        assert result.message == ""

    def test_failed_result(self):
        result = ToolResult(
            status=ResultStatus.FAILED,
            error="File not found",
            message="Input file missing"
        )
        assert result.status == ResultStatus.FAILED
        assert result.error == "File not found"
        assert result.message == "Input file missing"

    def test_skipped_result(self):
        result = ToolResult(status=ResultStatus.SKIPPED, message="Step skipped due to error")
        assert result.status == ResultStatus.SKIPPED
        assert result.message == "Step skipped due to error"


class TestExecutionResult:
    """Test ExecutionResult dataclass."""

    def test_success_execution(self):
        results = [
            ToolResult(status=ResultStatus.SUCCESS, output="Step 1 complete"),
            ToolResult(status=ResultStatus.SUCCESS, output="Step 2 complete")
        ]
        execution = ExecutionResult(
            sequence_id="seq1",
            status=ExecutionStatus.SUCCESS,
            results=results
        )
        assert execution.sequence_id == "seq1"
        assert execution.status == ExecutionStatus.SUCCESS
        assert len(execution.results) == 2
        assert execution.error is None

    def test_failed_execution(self):
        execution = ExecutionResult(
            sequence_id="seq1",
            status=ExecutionStatus.FAILED,
            error="Execution failed"
        )
        assert execution.status == ExecutionStatus.FAILED
        assert execution.error == "Execution failed"
        assert execution.results == []
