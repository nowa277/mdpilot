"""Tests for ReAct coordination layer integration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mdpilot.agent.react import ReActLoop
from mdpilot.config.schema import AppConfig, ProviderConfig, AgentConfig
from mdpilot.coordination import (
    ExecutionPlan,
    ExecutionResult,
    ExecutionSequence,
    ExecutionStatus,
    PlanStep,
    ResourceEstimate,
    ResultStatus,
    Severity,
    ToolCall,
    ToolResult,
    ValidationResult,
    Violation,
)


@pytest.fixture
def mock_config():
    """Create mock AppConfig."""
    return AppConfig(
        provider=ProviderConfig(
            model="gpt-4",
            api_key="test-key",
        ),
        agent=AgentConfig(
            max_iterations=10,
            max_context_tokens=8000,
        ),
    )


@pytest.fixture
def mock_llm_response():
    """Create mock LLM response."""
    response = MagicMock()
    response.content = "Test response"
    response.tool_calls = []
    response.usage_prompt_tokens = 100
    response.usage_completion_tokens = 50
    return response


@pytest.fixture
def sample_plan():
    """Create sample execution plan."""
    return ExecutionPlan(
        plan_id="plan_0001",
        task_description="Minimize protein structure",
        steps=[
            PlanStep(
                step_id="step_1",
                action="prepare_system",
                intent="Clean PDB file",
                required_tools=["pdb4amber"],
                parameters={"input": "protein.pdb"},
            ),
            PlanStep(
                step_id="step_2",
                action="minimize",
                intent="Energy minimization",
                required_tools=["sander"],
                parameters={"maxcyc": 1000},
            ),
        ],
        estimated_resources=ResourceEstimate(
            cpu_hours=1.0,
            memory_gb=4.0,
            disk_gb=2.0,
        ),
    )


@pytest.fixture
def sample_sequence():
    """Create sample execution sequence."""
    return ExecutionSequence(
        plan_id="plan_0001",
        calls=[
            ToolCall(
                tool_name="pdb4amber",
                parameters={"input": "protein.pdb"},
            ),
            ToolCall(
                tool_name="sander",
                parameters={"maxcyc": 1000},
            ),
        ],
    )


class TestReActCoordinationIntegration:
    """Test ReAct coordination layer integration."""

    def test_init_without_coordination(self, mock_config):
        """Test initialization without coordination layer."""
        loop = ReActLoop(mock_config, use_coordination=False)

        assert not loop.use_coordination
        assert loop._plan_generator is None
        assert loop._plan_validator is None
        assert loop._execution_planner is None
        assert loop._tool_executor is None

    def test_init_with_coordination(self, mock_config):
        """Test initialization with coordination layer."""
        loop = ReActLoop(mock_config, use_coordination=True)

        assert loop.use_coordination
        assert loop._plan_generator is not None
        assert loop._plan_validator is not None
        assert loop._execution_planner is not None
        assert loop._tool_executor is not None

    @pytest.mark.asyncio
    async def test_legacy_path_still_works(self, mock_config, mock_llm_response):
        """Test that legacy ReAct path still works."""
        loop = ReActLoop(mock_config, use_coordination=False)

        # Mock LLM to return final answer
        with patch.object(loop._llm, "chat_once", return_value=mock_llm_response):
            result = await loop.run("What is AMBER?")

        assert result == "Test response"
        assert not loop.use_coordination

    @pytest.mark.asyncio
    async def test_coordination_path_success(
        self, mock_config, sample_plan, sample_sequence
    ):
        """Test successful coordination path execution."""
        loop = ReActLoop(mock_config, use_coordination=True)

        # Mock plan generation
        loop._plan_generator.generate_plan = AsyncMock(return_value=sample_plan)

        # Mock validation (pass)
        loop._plan_validator.validate = MagicMock(
            return_value=ValidationResult(valid=True, violations=[])
        )

        # Mock execution planning
        loop._execution_planner.plan_execution = MagicMock(return_value=sample_sequence)

        # Mock tool execution (success)
        success_result = ExecutionResult(
            sequence_id="plan_0001",
            status=ExecutionStatus.SUCCESS,
            results=[
                ToolResult(
                    status=ResultStatus.SUCCESS,
                    output={"cleaned": True},
                    message="Tool pdb4amber completed successfully",
                ),
                ToolResult(
                    status=ResultStatus.SUCCESS,
                    output={"minimized": True},
                    message="Tool sander completed successfully",
                ),
            ],
        )
        loop._tool_executor.execute = AsyncMock(return_value=success_result)

        result = await loop.run("Minimize protein structure")

        assert "Step 1:" in result
        assert "Step 2:" in result
        assert "completed successfully" in result

    @pytest.mark.asyncio
    async def test_coordination_validation_failure(self, mock_config, sample_plan):
        """Test coordination path with validation failure."""
        loop = ReActLoop(mock_config, use_coordination=True)

        # Mock plan generation
        loop._plan_generator.generate_plan = AsyncMock(return_value=sample_plan)

        # Mock validation (fail)
        violations = [
            Violation(
                level="E",
                severity=Severity.CRITICAL,
                message="Exceeds memory limit",
                step_id="step_2",
                fixable=True,
                suggested_fix="Reduce system size",
            )
        ]
        loop._plan_validator.validate = MagicMock(
            return_value=ValidationResult(valid=False, violations=violations)
        )
        loop._plan_validator.suggest_fixes = MagicMock(
            return_value=[
                {
                    "level": "E",
                    "message": "Exceeds memory limit",
                    "fix": "Reduce system size",
                    "step_id": "step_2",
                }
            ]
        )

        result = await loop.run("Minimize protein structure")

        assert "Plan validation failed" in result
        assert "Exceeds memory limit" in result
        assert "Suggested fixes" in result
        assert "Reduce system size" in result

    @pytest.mark.asyncio
    async def test_coordination_execution_failure(
        self, mock_config, sample_plan, sample_sequence
    ):
        """Test coordination path with execution failure."""
        loop = ReActLoop(mock_config, use_coordination=True)

        # Mock plan generation
        loop._plan_generator.generate_plan = AsyncMock(return_value=sample_plan)

        # Mock validation (pass)
        loop._plan_validator.validate = MagicMock(
            return_value=ValidationResult(valid=True, violations=[])
        )

        # Mock execution planning
        loop._execution_planner.plan_execution = MagicMock(return_value=sample_sequence)

        # Mock tool execution (failure)
        failure_result = ExecutionResult(
            sequence_id="plan_0001",
            status=ExecutionStatus.FAILED,
            results=[
                ToolResult(
                    status=ResultStatus.SUCCESS,
                    output={"cleaned": True},
                    message="Tool pdb4amber completed successfully",
                ),
                ToolResult(
                    status=ResultStatus.FAILED,
                    error="File not found",
                    message="Tool sander failed: File not found",
                ),
            ],
            error="File not found",
        )
        loop._tool_executor.execute = AsyncMock(return_value=failure_result)

        result = await loop.run("Minimize protein structure")

        assert "Execution failed" in result
        assert "File not found" in result

    @pytest.mark.asyncio
    async def test_coordination_resource_exhausted(
        self, mock_config, sample_plan, sample_sequence
    ):
        """Test coordination path with resource exhaustion."""
        loop = ReActLoop(mock_config, use_coordination=True)

        # Mock plan generation
        loop._plan_generator.generate_plan = AsyncMock(return_value=sample_plan)

        # Mock validation (pass)
        loop._plan_validator.validate = MagicMock(
            return_value=ValidationResult(valid=True, violations=[])
        )

        # Mock execution planning
        loop._execution_planner.plan_execution = MagicMock(return_value=sample_sequence)

        # Mock tool execution (resource exhausted)
        exhausted_result = ExecutionResult(
            sequence_id="plan_0001",
            status=ExecutionStatus.RESOURCE_EXHAUSTED,
            results=[],
            error="Insufficient resources for tool execution",
        )
        loop._tool_executor.execute = AsyncMock(return_value=exhausted_result)

        result = await loop.run("Minimize protein structure")

        assert "Resource exhausted" in result
        assert "Insufficient resources" in result

    @pytest.mark.asyncio
    async def test_coordination_exception_handling(self, mock_config):
        """Test coordination path exception handling."""
        loop = ReActLoop(mock_config, use_coordination=True)

        # Mock plan generation to raise exception
        loop._plan_generator.generate_plan = AsyncMock(
            side_effect=Exception("LLM error")
        )

        result = await loop.run("Minimize protein structure")

        assert "Coordination error" in result
        assert "LLM error" in result

    @pytest.mark.asyncio
    async def test_backward_compatibility_default(self, mock_config, mock_llm_response):
        """Test backward compatibility - default is legacy path."""
        loop = ReActLoop(mock_config)  # No use_coordination parameter

        assert not loop.use_coordination

        # Mock LLM
        with patch.object(loop._llm, "chat_once", return_value=mock_llm_response):
            result = await loop.run("Test query")

        assert result == "Test response"

    def test_coordination_components_initialized(self, mock_config):
        """Test that all coordination components are properly initialized."""
        loop = ReActLoop(mock_config, use_coordination=True)

        # Check all components exist
        assert hasattr(loop, "_plan_generator")
        assert hasattr(loop, "_plan_validator")
        assert hasattr(loop, "_execution_planner")
        assert hasattr(loop, "_tool_executor")

        # Check they are not None
        assert loop._plan_generator is not None
        assert loop._plan_validator is not None
        assert loop._execution_planner is not None
        assert loop._tool_executor is not None

    @pytest.mark.asyncio
    async def test_coordination_with_skill_context(
        self, mock_config, sample_plan, sample_sequence
    ):
        """Test coordination path with skill context injection."""
        loop = ReActLoop(mock_config, use_coordination=True)

        # Mock skill context
        loop._skills.build_context = MagicMock(return_value="Skill context")

        # Mock plan generation
        loop._plan_generator.generate_plan = AsyncMock(return_value=sample_plan)

        # Mock validation (pass)
        loop._plan_validator.validate = MagicMock(
            return_value=ValidationResult(valid=True, violations=[])
        )

        # Mock execution planning
        loop._execution_planner.plan_execution = MagicMock(return_value=sample_sequence)

        # Mock tool execution (success)
        success_result = ExecutionResult(
            sequence_id="plan_0001",
            status=ExecutionStatus.SUCCESS,
            results=[
                ToolResult(
                    status=ResultStatus.SUCCESS,
                    output={"result": "ok"},
                    message="Tool completed successfully",
                )
            ],
        )
        loop._tool_executor.execute = AsyncMock(return_value=success_result)

        result = await loop.run("Test with skills")

        assert "completed successfully" in result

    @pytest.mark.asyncio
    async def test_coordination_partial_execution(
        self, mock_config, sample_plan, sample_sequence
    ):
        """Test coordination path with partial execution status."""
        loop = ReActLoop(mock_config, use_coordination=True)

        # Mock plan generation
        loop._plan_generator.generate_plan = AsyncMock(return_value=sample_plan)

        # Mock validation (pass)
        loop._plan_validator.validate = MagicMock(
            return_value=ValidationResult(valid=True, violations=[])
        )

        # Mock execution planning
        loop._execution_planner.plan_execution = MagicMock(return_value=sample_sequence)

        # Mock tool execution (partial)
        partial_result = ExecutionResult(
            sequence_id="plan_0001",
            status=ExecutionStatus.PARTIAL,
            results=[
                ToolResult(
                    status=ResultStatus.SUCCESS,
                    output={"result": "ok"},
                    message="Tool completed",
                ),
                ToolResult(
                    status=ResultStatus.SKIPPED,
                    message="Tool skipped",
                ),
            ],
            error="Some steps skipped",
        )
        loop._tool_executor.execute = AsyncMock(return_value=partial_result)

        result = await loop.run("Test partial execution")

        assert "Execution failed" in result
        assert "Some steps skipped" in result


class TestReActCoordinationProperties:
    """Test ReAct coordination properties."""

    def test_use_coordination_property(self, mock_config):
        """Test use_coordination property."""
        loop_legacy = ReActLoop(mock_config, use_coordination=False)
        loop_coord = ReActLoop(mock_config, use_coordination=True)

        assert not loop_legacy.use_coordination
        assert loop_coord.use_coordination

    def test_existing_properties_still_work(self, mock_config):
        """Test that existing properties still work with coordination."""
        loop = ReActLoop(mock_config, use_coordination=True)

        assert loop.config == mock_config
        assert loop.iteration == 0
        assert loop.max_iterations == 10
        assert loop.events is not None
        assert loop.budget is not None
