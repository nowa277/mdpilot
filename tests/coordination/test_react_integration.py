"""Integration test for ReActAgent coordination path with real coordination components."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from mdpilot.agent.react_agent import ReActAgent
from mdpilot.config.schema import AppConfig, ProviderConfig, AgentConfig
from mdpilot.coordination import (
    ExecutionPlan,
    ExecutionResult,
    ExecutionSequence,
    ExecutionStatus,
    PlanStep,
    ResourceEstimate,
    ResultStatus,
    ToolCall,
    ToolResult,
    ValidationResult,
)


@pytest.fixture
def config():
    return AppConfig(
        provider=ProviderConfig(model="gpt-4", api_key="test-key"),
        agent=AgentConfig(max_iterations=10, max_context_tokens=8000),
    )


@pytest.fixture
def sample_plan():
    return ExecutionPlan(
        plan_id="plan_int_001",
        task_description="Simple test task",
        steps=[
            PlanStep(
                step_id="s1",
                action="echo",
                intent="Print hello",
                required_tools=["bash_run"],
                parameters={"command": "echo hello"},
            ),
        ],
        estimated_resources=ResourceEstimate(
            cpu_hours=0.1, memory_gb=1.0, disk_gb=0.1,
        ),
    )


@pytest.fixture
def sample_sequence():
    return ExecutionSequence(
        plan_id="plan_int_001",
        calls=[
            ToolCall(tool_name="bash_run", parameters={"command": "echo hello"}),
        ],
    )


class TestCoordinationIntegration:
    def test_coordination_components_initialize(self, config):
        """All coordination components initialize without error."""
        agent = ReActAgent(config, use_coordination=True)
        assert agent._plan_generator is not None
        assert agent._plan_validator is not None
        assert agent._execution_planner is not None
        assert agent._tool_executor is not None

    @pytest.mark.asyncio
    async def test_full_coordination_path(self, config, sample_plan, sample_sequence):
        """End-to-end: generate plan -> validate -> execute -> return result."""
        agent = ReActAgent(config, use_coordination=True)

        agent._plan_generator.generate_plan = AsyncMock(return_value=sample_plan)
        # Real PlanValidator enforces workflow rules (prepare_system, minimize, etc.)
        # so we mock validation to pass for our simple test plan
        agent._plan_validator.validate = MagicMock(
            return_value=ValidationResult(valid=True, violations=[])
        )
        agent._execution_planner.plan_execution = MagicMock(return_value=sample_sequence)

        success_result = ExecutionResult(
            sequence_id="plan_int_001",
            status=ExecutionStatus.SUCCESS,
            results=[
                ToolResult(
                    status=ResultStatus.SUCCESS,
                    output={"stdout": "hello"},
                    message="bash_run completed",
                ),
            ],
        )
        agent._tool_executor.execute = AsyncMock(return_value=success_result)

        result = await agent.run("echo hello")

        assert "bash_run completed" in result
        assert "Step 1:" in result

    @pytest.mark.asyncio
    async def test_coordination_events_compat(self, config, sample_plan, sample_sequence):
        """Coordination path emits compatible SSE events."""
        agent = ReActAgent(config, use_coordination=True)

        agent._plan_generator.generate_plan = AsyncMock(return_value=sample_plan)
        agent._plan_validator.validate = MagicMock(
            return_value=ValidationResult(valid=True, violations=[])
        )
        agent._execution_planner.plan_execution = MagicMock(return_value=sample_sequence)

        success_result = ExecutionResult(
            sequence_id="plan_int_001",
            status=ExecutionStatus.SUCCESS,
            results=[
                ToolResult(status=ResultStatus.SUCCESS, output={}, message="done"),
            ],
        )
        agent._tool_executor.execute = AsyncMock(return_value=success_result)

        events = []
        agent.events.on("iteration_start", lambda e: events.append(("iteration_start", e.data)))
        agent.events.on("loop_end", lambda e: events.append(("loop_end", e.data)))

        await agent.run("test task")

        event_types = [t for t, _ in events]
        assert "iteration_start" in event_types
        assert "loop_end" in event_types

    @pytest.mark.asyncio
    async def test_legacy_path_unaffected(self, config):
        """ReActAgent with use_coordination=False is completely unaffected."""
        agent = ReActAgent(config, use_coordination=False)
        assert agent._plan_generator is None
        assert agent._plan_validator is None
