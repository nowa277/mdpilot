"""Tests for PlanValidator coordinator."""

import pytest

from mdpilot.coordination.config import (
    FileSystemPermissions,
    GuardrailConfig,
    RecoveryPolicies,
    ResourceLimits,
    ToolConstraints,
    WorkflowRules,
)
from mdpilot.coordination.plan_validator import PlanValidator
from mdpilot.coordination.types import (
    ExecutionPlan,
    PlanStep,
    ResourceEstimate,
    Severity,
)


@pytest.fixture
def default_config():
    """Create default guardrail configuration."""
    return GuardrailConfig(
        resource_limits=ResourceLimits(
            max_cpu_hours=10.0,
            max_memory_gb=16.0,
            max_disk_gb=50.0
        ),
        recovery_policies=RecoveryPolicies(
            max_retries=3,
            allowed_strategies=["retry_with_backoff", "fallback_tool", "skip_step", "abort_plan"]
        ),
        workflow_rules=WorkflowRules(
            required_steps=["prepare_system", "minimize", "equilibrate"],
            step_order_constraints={"minimize": ["prepare_system"]}
        ),
        tool_constraints=ToolConstraints(
            required_parameters={"pmemd": ["input_file", "topology"]},
            parameter_ranges={"pmemd": {"steps": {"min": 1, "max": 1000000}}}
        ),
        fs_permissions=FileSystemPermissions(
            allowed_paths=["/home/user/obsidian/project/amber-agent", "/tmp"],
            forbidden_paths=["/etc", "/sys", "/proc"]
        )
    )


@pytest.fixture
def valid_plan():
    """Create a valid execution plan."""
    return ExecutionPlan(
        plan_id="test_plan_001",
        task_description="Test simulation",
        steps=[
            PlanStep(
                step_id="step1",
                action="prepare_system",
                intent="Prepare system",
                parameters={},
                required_tools=["tleap"],
                error_handling="retry_with_backoff"
            ),
            PlanStep(
                step_id="step2",
                action="minimize",
                intent="Minimize energy",
                parameters={
                    "input_file": "/tmp/min.in",
                    "topology": "/tmp/system.prmtop",
                    "fallback_tool": "sander"  # Required for fallback_tool strategy
                },
                required_tools=["pmemd"],
                error_handling="fallback_tool"
            ),
            PlanStep(
                step_id="step3",
                action="equilibrate",
                intent="Equilibrate system",
                parameters={
                    "input_file": "/tmp/eq.in",
                    "topology": "/tmp/system.prmtop"
                },
                required_tools=["pmemd"],
                error_handling="skip_step"
            ),
        ],
        estimated_resources=ResourceEstimate(
            cpu_hours=5.0,
            memory_gb=8.0,
            disk_gb=20.0
        )
    )


class TestPlanValidatorInit:
    """Test PlanValidator initialization."""

    def test_init_with_config(self, default_config):
        """Test validator initializes with config."""
        validator = PlanValidator(default_config)
        assert validator.config == default_config
        assert len(validator.validators) == 5

    def test_validators_order(self, default_config):
        """Test validators are in correct order (E→D→C→B→A)."""
        validator = PlanValidator(default_config)
        levels = [v.level for v in validator.validators]
        assert levels == ["E", "D", "C", "B", "A"]


class TestPlanValidatorValidate:
    """Test plan validation."""

    def test_valid_plan_passes(self, default_config, valid_plan):
        """Test valid plan passes all validators."""
        validator = PlanValidator(default_config)
        result = validator.validate(valid_plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_critical_violation_stops_early(self, default_config):
        """Test CRITICAL violation stops validation early."""
        # Create plan that exceeds resource limits (E-level CRITICAL)
        plan = ExecutionPlan(
            plan_id="test_plan_002",
            task_description="Resource-heavy task",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="prepare_system",
                    intent="Prepare",
                    parameters={},
                    required_tools=[],
                    error_handling=None  # This would trigger D-level ERROR
                )
            ],
            estimated_resources=ResourceEstimate(
                cpu_hours=100.0,  # Exceeds limit of 10.0
                memory_gb=8.0,
                disk_gb=20.0
            )
        )

        validator = PlanValidator(default_config)
        result = validator.validate(plan)

        assert result.valid is False
        # Should only have E-level violations (stopped early)
        assert all(v.level == "E" for v in result.violations)
        assert all(v.severity == Severity.CRITICAL for v in result.violations)

    def test_multiple_level_violations(self, default_config):
        """Test aggregates violations from multiple levels."""
        # Create plan with D, C, B, A violations (no E-level to avoid early stop)
        plan = ExecutionPlan(
            plan_id="test_plan_003",
            task_description="Multi-violation plan",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="minimize",  # Missing prepare_system (C-level)
                    intent="Minimize",
                    parameters={"input_file": "/etc/passwd"},  # Forbidden path (A-level)
                    required_tools=["pmemd"],
                    error_handling=None  # Missing error handling (D-level)
                )
            ],
            estimated_resources=ResourceEstimate(
                cpu_hours=5.0,
                memory_gb=8.0,
                disk_gb=20.0
            )
        )

        validator = PlanValidator(default_config)
        result = validator.validate(plan)

        assert result.valid is False
        # Should have violations from D, C, A levels
        levels = {v.level for v in result.violations}
        assert "D" in levels  # Missing error_handling
        assert "C" in levels  # Missing required step
        assert "A" in levels  # Forbidden path

    def test_empty_plan_violations(self, default_config):
        """Test empty plan triggers violations."""
        # Empty plan will fail validation at ExecutionPlan.validate()
        # but we test with minimal invalid plan
        plan = ExecutionPlan(
            plan_id="test_plan_004",
            task_description="Empty plan",
            steps=[],  # No steps
            estimated_resources=ResourceEstimate()
        )

        validator = PlanValidator(default_config)
        # This will raise ValueError from plan.validate()
        with pytest.raises(ValueError, match="plan must have at least one step"):
            plan.validate()

    def test_workflow_violations_only(self, default_config):
        """Test plan with only workflow violations."""
        plan = ExecutionPlan(
            plan_id="test_plan_005",
            task_description="Workflow violation",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="minimize",  # Missing prepare_system prerequisite
                    intent="Minimize",
                    parameters={},
                    required_tools=[],
                    error_handling="retry_with_backoff"
                ),
                PlanStep(
                    step_id="step2",
                    action="prepare_system",  # Should come before minimize
                    intent="Prepare",
                    parameters={},
                    required_tools=[],
                    error_handling="skip_step"
                ),
                PlanStep(
                    step_id="step3",
                    action="equilibrate",
                    intent="Equilibrate",
                    parameters={},
                    required_tools=[],
                    error_handling="abort_plan"
                ),
            ],
            estimated_resources=ResourceEstimate(
                cpu_hours=5.0,
                memory_gb=8.0,
                disk_gb=20.0
            )
        )

        validator = PlanValidator(default_config)
        result = validator.validate(plan)

        assert result.valid is False
        assert all(v.level == "C" for v in result.violations)
        assert all(v.severity == Severity.ERROR for v in result.violations)


class TestPlanValidatorSuggestFixes:
    """Test fix suggestion generation."""

    def test_suggest_fixes_for_fixable_violations(self, default_config):
        """Test generates fixes for fixable violations."""
        plan = ExecutionPlan(
            plan_id="test_plan_006",
            task_description="Fixable violations",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="prepare_system",
                    intent="Prepare",
                    parameters={},
                    required_tools=[],
                    error_handling=None  # Fixable D-level violation
                )
            ],
            estimated_resources=ResourceEstimate(
                cpu_hours=5.0,
                memory_gb=8.0,
                disk_gb=20.0
            )
        )

        validator = PlanValidator(default_config)
        result = validator.validate(plan)

        assert result.valid is False
        fixes = validator.suggest_fixes(result.violations)

        assert len(fixes) > 0
        for fix in fixes:
            assert "level" in fix
            assert "message" in fix
            assert "fix" in fix
            assert "step_id" in fix

    def test_no_fixes_for_critical_violations(self, default_config):
        """Test no fixes generated for CRITICAL violations."""
        plan = ExecutionPlan(
            plan_id="test_plan_007",
            task_description="Critical violation",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="prepare_system",
                    intent="Prepare",
                    parameters={},
                    required_tools=[],
                    error_handling="retry_with_backoff"
                )
            ],
            estimated_resources=ResourceEstimate(
                cpu_hours=100.0,  # CRITICAL violation
                memory_gb=8.0,
                disk_gb=20.0
            )
        )

        validator = PlanValidator(default_config)
        result = validator.validate(plan)

        assert result.valid is False
        fixes = validator.suggest_fixes(result.violations)

        # CRITICAL violations are not fixable
        assert len(fixes) == 0

    def test_suggest_fixes_empty_violations(self, default_config):
        """Test suggest_fixes with empty violations list."""
        validator = PlanValidator(default_config)
        fixes = validator.suggest_fixes([])
        assert fixes == []

    def test_suggest_fixes_mixed_violations(self, default_config):
        """Test suggest_fixes with mix of fixable and non-fixable."""
        plan = ExecutionPlan(
            plan_id="test_plan_008",
            task_description="Mixed violations",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="prepare_system",
                    intent="Prepare",
                    parameters={},
                    required_tools=[],
                    error_handling=None  # Fixable
                )
            ],
            estimated_resources=ResourceEstimate(
                cpu_hours=100.0,  # Not fixable (CRITICAL)
                memory_gb=8.0,
                disk_gb=20.0
            )
        )

        validator = PlanValidator(default_config)
        result = validator.validate(plan)

        # Should stop at E-level, so only CRITICAL violations
        fixes = validator.suggest_fixes(result.violations)
        assert len(fixes) == 0


class TestPlanValidatorComplexScenarios:
    """Test complex multi-violation scenarios."""

    def test_all_validators_triggered(self, default_config):
        """Test plan that triggers all 5 validators."""
        plan = ExecutionPlan(
            plan_id="test_plan_009",
            task_description="All validators",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="minimize",  # Wrong order (C)
                    intent="Minimize",
                    parameters={
                        "input_file": "/etc/passwd",  # Forbidden (A)
                        "steps": 2000000  # Exceeds max (B)
                    },
                    required_tools=["pmemd"],
                    error_handling="invalid_strategy"  # Invalid (D)
                )
            ],
            estimated_resources=ResourceEstimate(
                cpu_hours=5.0,  # Within limits (E passes)
                memory_gb=8.0,
                disk_gb=20.0
            )
        )

        validator = PlanValidator(default_config)
        result = validator.validate(plan)

        assert result.valid is False
        # Should have violations from D, C, B, A (E passes)
        levels = {v.level for v in result.violations}
        assert "D" in levels
        assert "C" in levels
        assert "B" in levels
        assert "A" in levels

    def test_duplicate_steps_and_missing_required(self, default_config):
        """Test duplicate steps and missing required steps."""
        plan = ExecutionPlan(
            plan_id="test_plan_010",
            task_description="Duplicate and missing",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="prepare_system",
                    intent="Prepare",
                    parameters={},
                    required_tools=[],
                    error_handling="retry_with_backoff"
                ),
                PlanStep(
                    step_id="step2",
                    action="prepare_system",  # Duplicate
                    intent="Prepare again",
                    parameters={},
                    required_tools=[],
                    error_handling="skip_step"
                ),
                # Missing: minimize, equilibrate
            ],
            estimated_resources=ResourceEstimate(
                cpu_hours=5.0,
                memory_gb=8.0,
                disk_gb=20.0
            )
        )

        validator = PlanValidator(default_config)
        result = validator.validate(plan)

        assert result.valid is False
        # Should have C-level violations for duplicate and missing steps
        c_violations = [v for v in result.violations if v.level == "C"]
        assert len(c_violations) >= 2  # At least duplicate + missing steps

    def test_parameter_validation_comprehensive(self, default_config):
        """Test comprehensive parameter validation."""
        plan = ExecutionPlan(
            plan_id="test_plan_011",
            task_description="Parameter validation",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="prepare_system",
                    intent="Prepare",
                    parameters={},
                    required_tools=[],
                    error_handling="retry_with_backoff"
                ),
                PlanStep(
                    step_id="step2",
                    action="minimize",
                    intent="Minimize",
                    parameters={
                        # Missing required: input_file, topology
                        "steps": 0  # Below minimum
                    },
                    required_tools=["pmemd"],
                    error_handling="fallback_tool"
                ),
                PlanStep(
                    step_id="step3",
                    action="equilibrate",
                    intent="Equilibrate",
                    parameters={},
                    required_tools=[],
                    error_handling="skip_step"
                ),
            ],
            estimated_resources=ResourceEstimate(
                cpu_hours=5.0,
                memory_gb=8.0,
                disk_gb=20.0
            )
        )

        validator = PlanValidator(default_config)
        result = validator.validate(plan)

        assert result.valid is False
        # Should have B-level violations for missing params and range
        b_violations = [v for v in result.violations if v.level == "B"]
        assert len(b_violations) >= 3  # Missing input_file, topology, steps < min
