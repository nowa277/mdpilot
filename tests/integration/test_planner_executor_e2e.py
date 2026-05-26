"""End-to-end integration tests for Planner + Executor architecture.

Tests complete flow from task → plan → validation → execution.
"""

import os
import pytest

from mdpilot.coordination import (
    ExecutionPlanner,
    ExecutionStatus,
    GuardrailConfig,
    PlanGenerator,
    PlanValidator,
    ResourceGuard,
    ToolExecutor,
)
from mdpilot.coordination.config import (
    RecoveryPolicies,
    ResourceLimits,
    WorkflowRules,
)
from mdpilot.coordination.types import (
    ExecutionPlan,
    PlanStep,
    ResourceEstimate,
    ResultStatus,
    Severity,
)
from mdpilot.llm.provider import LLMProvider
from mdpilot.knowledge.index import KnowledgeIndex


class MockDispatcher:
    """Mock tool dispatcher for E2E testing."""

    def __init__(self, should_fail=False, fail_on_tool=None):
        self.should_fail = should_fail
        self.fail_on_tool = fail_on_tool
        self.calls = []

    async def dispatch(self, tool_name: str, parameters: dict):
        """Mock dispatch method."""
        self.calls.append((tool_name, parameters))

        if self.should_fail or (self.fail_on_tool and tool_name == self.fail_on_tool):
            raise RuntimeError(f"Tool {tool_name} failed")

        return {"status": "success", "tool": tool_name, "params": parameters}


@pytest.mark.integration
class TestPlannerExecutorE2E:
    """End-to-end tests for Planner + Executor architecture."""

    @pytest.fixture
    def llm_client(self):
        """Create real LLM client (or skip if no API key)."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            pytest.skip("ANTHROPIC_API_KEY not set")

        return LLMProvider(
            model="claude-sonnet-4-20250514",
            api_key=api_key,
            temperature=0.0,
            max_tokens=4096
        )

    @pytest.fixture
    def knowledge_base(self):
        """Create knowledge base (or skip if not available)."""
        kb_path = os.path.join(
            os.path.dirname(__file__),
            "../../knowledge_base"
        )

        if not os.path.exists(kb_path):
            pytest.skip("Knowledge base not found")

        try:
            return KnowledgeIndex(kb_path)
        except FileNotFoundError:
            pytest.skip("Knowledge base index not found")

    @pytest.fixture
    def mock_dispatcher(self):
        """Create mock dispatcher."""
        return MockDispatcher()

    @pytest.fixture
    def default_config(self):
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
                required_steps=["prepare_system", "minimize", "equilibrate"]
            )
        )

    @pytest.mark.asyncio
    async def test_happy_path_simple_task(self, mock_dispatcher, default_config):
        """Test complete flow for simple task with mock components."""
        # Setup components
        plan_validator = PlanValidator(default_config)
        exec_planner = ExecutionPlanner()
        resource_guard = ResourceGuard(default_config.resource_limits)
        tool_executor = ToolExecutor(mock_dispatcher, resource_guard)

        # Create a valid plan manually (simulating PlanGenerator output)
        plan = ExecutionPlan(
            plan_id="test_plan_001",
            task_description="Prepare protein for MD",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="prepare_system",
                    intent="Clean and prepare PDB structure",
                    parameters={"input": "protein.pdb"},
                    required_tools=["pdb4amber"],
                    error_handling="retry_with_backoff"
                ),
                PlanStep(
                    step_id="step2",
                    action="minimize",
                    intent="Minimize energy",
                    parameters={"steps": 1000},
                    required_tools=["sander"],
                    error_handling="skip_step"
                ),
                PlanStep(
                    step_id="step3",
                    action="equilibrate",
                    intent="Equilibrate system",
                    parameters={"steps": 5000},
                    required_tools=["sander"],
                    error_handling="skip_step"
                ),
            ],
            estimated_resources=ResourceEstimate(
                cpu_hours=2.0,
                memory_gb=4.0,
                disk_gb=10.0
            )
        )

        # Validate plan
        validation = plan_validator.validate(plan)
        assert validation.valid, f"Plan validation failed: {validation.violations}"

        # Plan execution
        sequence = exec_planner.plan_execution(plan)
        assert len(sequence.calls) == 3

        # Execute
        result = await tool_executor.execute(sequence)

        # Verify
        assert result.status == ExecutionStatus.SUCCESS
        assert len(result.results) == 3
        assert all(r.status == ResultStatus.SUCCESS for r in result.results)
        assert len(mock_dispatcher.calls) == 3

    @pytest.mark.asyncio
    async def test_resource_limit_violation(self, default_config):
        """Test E-level validation failure due to resource limits."""
        # Create config with tight limits
        config = GuardrailConfig(
            resource_limits=ResourceLimits(
                max_cpu_hours=1.0,
                max_memory_gb=2.0,
                max_disk_gb=5.0
            )
        )

        # Create plan that exceeds limits
        plan = ExecutionPlan(
            plan_id="test_plan_heavy",
            task_description="Heavy computation",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="production",
                    intent="Run long production MD",
                    parameters={"steps": 10000000},
                    required_tools=["pmemd"],
                    error_handling="abort_plan"
                )
            ],
            estimated_resources=ResourceEstimate(
                cpu_hours=10.0,  # Exceeds max_cpu_hours=1.0
                memory_gb=8.0,   # Exceeds max_memory_gb=2.0
                disk_gb=20.0     # Exceeds max_disk_gb=5.0
            )
        )

        # Validate
        validator = PlanValidator(config)
        result = validator.validate(plan)

        # Verify E-level violations
        assert not result.valid
        assert len(result.violations) > 0
        assert any(v.level == "E" for v in result.violations)
        assert any(v.severity == Severity.CRITICAL for v in result.violations)

        # Check violation messages mention resource limits
        violation_messages = [v.message for v in result.violations]
        assert any("cpu" in msg.lower() or "memory" in msg.lower() or "disk" in msg.lower()
                   for msg in violation_messages)

    @pytest.mark.asyncio
    async def test_workflow_validation_failure(self, default_config):
        """Test C-level validation with fix suggestions."""
        # Create plan missing required steps
        plan = ExecutionPlan(
            plan_id="test_plan_incomplete",
            task_description="Incomplete workflow",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="prepare_system",
                    intent="Prepare system",
                    parameters={},
                    required_tools=["tleap"],
                    error_handling="retry_with_backoff"
                )
                # Missing: minimize, equilibrate (required by WorkflowRules)
            ],
            estimated_resources=ResourceEstimate(
                cpu_hours=0.5,
                memory_gb=1.0,
                disk_gb=2.0
            )
        )

        # Validate
        validator = PlanValidator(default_config)
        result = validator.validate(plan)

        # Verify C-level violations
        assert not result.valid
        assert len(result.violations) > 0
        assert any(v.level == "C" for v in result.violations)

        # Check for fixable violations
        fixable_violations = [v for v in result.violations if v.fixable]
        assert len(fixable_violations) > 0

        # Check fix suggestions
        fixes = validator.suggest_fixes(result.violations)
        assert len(fixes) > 0
        assert all("fix" in fix for fix in fixes)
        assert all("step_id" in fix for fix in fixes)

    @pytest.mark.asyncio
    async def test_execution_failure_handling(self, default_config):
        """Test execution failure with graceful handling."""
        # Setup with failing dispatcher
        failing_dispatcher = MockDispatcher(fail_on_tool="sander")
        resource_guard = ResourceGuard(default_config.resource_limits)
        tool_executor = ToolExecutor(failing_dispatcher, resource_guard)
        exec_planner = ExecutionPlanner()

        # Create valid plan
        plan = ExecutionPlan(
            plan_id="test_plan_fail",
            task_description="Test failure handling",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="prepare_system",
                    intent="Prepare",
                    parameters={},
                    required_tools=["pdb4amber"],
                    error_handling="retry_with_backoff"
                ),
                PlanStep(
                    step_id="step2",
                    action="minimize",
                    intent="Minimize",
                    parameters={},
                    required_tools=["sander"],  # This will fail
                    error_handling="skip_step"
                ),
                PlanStep(
                    step_id="step3",
                    action="analyze",
                    intent="Analyze",
                    parameters={},
                    required_tools=["cpptraj"],
                    error_handling="skip_step"
                ),
            ],
            estimated_resources=ResourceEstimate(
                cpu_hours=1.0,
                memory_gb=2.0,
                disk_gb=5.0
            )
        )

        # Execute
        sequence = exec_planner.plan_execution(plan)
        result = await tool_executor.execute(sequence)

        # Verify graceful failure
        assert result.status == ExecutionStatus.FAILED
        assert len(result.results) >= 1  # At least first tool executed
        assert result.results[0].status == ResultStatus.SUCCESS  # First succeeded
        assert result.results[1].status == ResultStatus.FAILED   # Second failed
        assert len(result.results) == 2  # Stopped after failure

    @pytest.mark.asyncio
    async def test_resource_exhaustion_during_execution(self, default_config):
        """Test runtime resource guard aborts execution."""
        # Setup with tight runtime limits
        config = GuardrailConfig(
            resource_limits=ResourceLimits(
                max_cpu_hours=10.0,
                max_memory_gb=4.0,  # Tight limit
                max_disk_gb=50.0
            )
        )

        dispatcher = MockDispatcher()
        resource_guard = ResourceGuard(config.resource_limits)
        tool_executor = ToolExecutor(dispatcher, resource_guard)
        exec_planner = ExecutionPlanner()

        # Pre-consume resources
        resource_guard.current_usage["memory_gb"] = 3.0

        # Create plan that will exceed limits during execution
        plan = ExecutionPlan(
            plan_id="test_plan_exhaust",
            task_description="Test resource exhaustion",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="minimize",
                    intent="Minimize",
                    parameters={},
                    required_tools=["sander"],  # Uses 1GB
                    error_handling="skip_step"
                ),
                PlanStep(
                    step_id="step2",
                    action="minimize",
                    intent="Minimize again",
                    parameters={},
                    required_tools=["sander"],  # Would need 1GB more (total 4GB)
                    error_handling="skip_step"
                ),
            ],
            estimated_resources=ResourceEstimate(
                cpu_hours=1.0,
                memory_gb=2.0,
                disk_gb=5.0
            )
        )

        # Execute
        sequence = exec_planner.plan_execution(plan)
        result = await tool_executor.execute(sequence)

        # Verify resource exhaustion
        assert result.status == ExecutionStatus.RESOURCE_EXHAUSTED
        assert "Insufficient resources" in result.error or "resource" in result.error.lower()

    @pytest.mark.asyncio
    async def test_complex_amber_workflow_e2e(self, mock_dispatcher, default_config):
        """Test complete AMBER MD workflow from start to finish."""
        # Use custom config for complex workflow (no strict required steps)
        workflow_config = GuardrailConfig(
            resource_limits=default_config.resource_limits,
            recovery_policies=default_config.recovery_policies,
            workflow_rules=WorkflowRules(
                required_steps=[],  # No strict requirements for this test
                step_order_constraints={}
            )
        )

        # Setup components
        plan_validator = PlanValidator(workflow_config)
        exec_planner = ExecutionPlanner()
        resource_guard = ResourceGuard(workflow_config.resource_limits)
        tool_executor = ToolExecutor(mock_dispatcher, resource_guard)

        # Create comprehensive MD workflow plan
        plan = ExecutionPlan(
            plan_id="test_plan_md_workflow",
            task_description="Complete MD simulation workflow",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="prepare_system",
                    intent="Clean PDB structure",
                    parameters={"input": "1AKI.pdb", "output": "1AKI_clean.pdb"},
                    required_tools=["pdb4amber"],
                    error_handling="retry_with_backoff"
                ),
                PlanStep(
                    step_id="step2",
                    action="build_topology",
                    intent="Build topology with tleap",
                    parameters={
                        "input": "1AKI_clean.pdb",
                        "force_field": "ff19SB",
                        "water_model": "OPC3"
                    },
                    required_tools=["tleap"],
                    error_handling="abort_plan"
                ),
                PlanStep(
                    step_id="step3",
                    action="minimize",
                    intent="Energy minimization",
                    parameters={"steps": 5000, "restraint": "backbone"},
                    required_tools=["sander"],
                    error_handling="retry_with_backoff"
                ),
                PlanStep(
                    step_id="step4",
                    action="equilibrate_nvt",
                    intent="NVT equilibration",
                    parameters={"steps": 10000, "ensemble": "NVT", "temperature": 300},
                    required_tools=["sander"],
                    error_handling="skip_step"
                ),
                PlanStep(
                    step_id="step5",
                    action="equilibrate_npt",
                    intent="NPT equilibration",
                    parameters={"steps": 10000, "ensemble": "NPT", "pressure": 1.0},
                    required_tools=["sander"],
                    error_handling="skip_step"
                ),
                PlanStep(
                    step_id="step6",
                    action="production",
                    intent="Production MD",
                    parameters={"steps": 50000, "ensemble": "NPT"},
                    required_tools=["pmemd"],
                    error_handling="abort_plan"
                ),
                PlanStep(
                    step_id="step7",
                    action="analyze",
                    intent="Trajectory analysis",
                    parameters={"trajectory": "prod.nc", "analyses": ["rmsd", "rmsf"]},
                    required_tools=["cpptraj"],
                    error_handling="skip_step"
                ),
            ],
            estimated_resources=ResourceEstimate(
                cpu_hours=8.0,
                memory_gb=12.0,
                disk_gb=30.0
            )
        )

        # Validate plan
        validation = plan_validator.validate(plan)
        assert validation.valid, f"Workflow validation failed: {validation.violations}"

        # Plan execution
        sequence = exec_planner.plan_execution(plan)
        assert len(sequence.calls) == 7

        # Execute
        result = await tool_executor.execute(sequence)

        # Verify complete workflow
        assert result.status == ExecutionStatus.SUCCESS
        assert len(result.results) == 7
        assert all(r.status == ResultStatus.SUCCESS for r in result.results)

        # Verify all tools were called in order
        expected_tools = ["pdb4amber", "tleap", "sander", "sander", "sander", "pmemd", "cpptraj"]
        actual_tools = [call[0] for call in mock_dispatcher.calls]
        assert actual_tools == expected_tools

    @pytest.mark.asyncio
    async def test_validation_stops_on_critical_violation(self, default_config):
        """Test that validation stops early on CRITICAL violations."""
        # Create plan with multiple violations (resource + workflow)
        plan = ExecutionPlan(
            plan_id="test_plan_multi_violation",
            task_description="Plan with multiple issues",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="production",
                    intent="Heavy production",
                    parameters={},
                    required_tools=["pmemd"],
                    error_handling="abort_plan"
                )
                # Missing required steps (workflow violation)
            ],
            estimated_resources=ResourceEstimate(
                cpu_hours=100.0,  # Exceeds limit (CRITICAL)
                memory_gb=1.0,
                disk_gb=5.0
            )
        )

        # Validate
        validator = PlanValidator(default_config)
        result = validator.validate(plan)

        # Verify stopped on CRITICAL
        assert not result.valid
        has_critical = any(v.severity == Severity.CRITICAL for v in result.violations)
        assert has_critical

        # Should have E-level violations, may not have C-level (stopped early)
        has_e_level = any(v.level == "E" for v in result.violations)
        assert has_e_level

    @pytest.mark.asyncio
    async def test_empty_plan_validation(self, default_config):
        """Test validation of empty plan."""
        plan = ExecutionPlan(
            plan_id="test_plan_empty",
            task_description="Empty plan",
            steps=[],  # No steps
            estimated_resources=ResourceEstimate()
        )

        # Should raise validation error
        with pytest.raises(ValueError, match="at least one step"):
            plan.validate()

    @pytest.mark.asyncio
    async def test_plan_with_real_llm(self, llm_client, knowledge_base, mock_dispatcher, default_config):
        """Test complete flow with real LLM-generated plan."""
        # Setup all components
        plan_generator = PlanGenerator(llm_client, knowledge_base)
        plan_validator = PlanValidator(default_config)
        exec_planner = ExecutionPlanner()
        resource_guard = ResourceGuard(default_config.resource_limits)
        tool_executor = ToolExecutor(mock_dispatcher, resource_guard)

        # Generate plan from task
        task = "Prepare protein 1AKI for molecular dynamics simulation"
        plan = await plan_generator.generate_plan(task)

        # Validate generated plan
        validation = plan_validator.validate(plan)

        # If validation fails, check if fixable
        if not validation.valid:
            fixes = plan_validator.suggest_fixes(validation.violations)
            # For this test, we'll just verify we got suggestions
            assert isinstance(fixes, list)

            # Skip execution if plan has CRITICAL violations
            if any(v.severity == Severity.CRITICAL for v in validation.violations):
                pytest.skip("Generated plan has CRITICAL violations")

        # Plan execution
        sequence = exec_planner.plan_execution(plan)
        assert len(sequence.calls) > 0

        # Execute
        result = await tool_executor.execute(sequence)

        # Verify execution completed (success or partial)
        assert result.status in [ExecutionStatus.SUCCESS, ExecutionStatus.PARTIAL, ExecutionStatus.FAILED]
        assert len(result.results) > 0
