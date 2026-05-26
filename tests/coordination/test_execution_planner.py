"""Tests for ExecutionPlanner."""

import pytest

from mdpilot.coordination.execution_planner import ExecutionPlanner
from mdpilot.coordination.types import (
    ExecutionPlan,
    PlanStep,
    ResourceEstimate,
)


@pytest.fixture
def planner():
    """Create ExecutionPlanner instance."""
    return ExecutionPlanner()


@pytest.fixture
def simple_plan():
    """Create simple single-step plan."""
    return ExecutionPlan(
        plan_id="test-001",
        task_description="Prepare PDB structure",
        steps=[
            PlanStep(
                step_id="step-1",
                action="prepare_system",
                intent="Clean and prepare PDB file",
                parameters={"input": "1aki.pdb", "output": "1aki_clean.pdb"},
                required_tools=["pdb4amber"],
            )
        ],
        estimated_resources=ResourceEstimate(),
    )


@pytest.fixture
def multi_step_plan():
    """Create multi-step plan."""
    return ExecutionPlan(
        plan_id="test-002",
        task_description="Complete MD workflow",
        steps=[
            PlanStep(
                step_id="step-1",
                action="prepare_system",
                intent="Clean PDB",
                parameters={"input": "1aki.pdb"},
                required_tools=["pdb4amber"],
            ),
            PlanStep(
                step_id="step-2",
                action="build_topology",
                intent="Build system",
                parameters={"input": "1aki_clean.pdb"},
                required_tools=["tleap"],
            ),
            PlanStep(
                step_id="step-3",
                action="minimize",
                intent="Energy minimization",
                parameters={"input": "system.prmtop"},
                required_tools=["sander"],
            ),
        ],
        estimated_resources=ResourceEstimate(),
    )


def test_single_step_to_single_tool_call(planner, simple_plan):
    """Test single step translates to single tool call."""
    sequence = planner.plan_execution(simple_plan)

    assert sequence.plan_id == "test-001"
    assert len(sequence.calls) == 1

    call = sequence.calls[0]
    assert call.tool_name == "pdb4amber"
    assert call.parameters["input_file"] == "1aki.pdb"
    assert call.parameters["output_file"] == "1aki_clean.pdb"
    assert call.metadata["step_id"] == "step-1"
    assert call.metadata["action"] == "prepare_system"


def test_multi_step_to_multiple_tool_calls(planner, multi_step_plan):
    """Test multi-step plan translates to multiple tool calls."""
    sequence = planner.plan_execution(multi_step_plan)

    assert sequence.plan_id == "test-002"
    assert len(sequence.calls) == 3

    # Check each tool call
    assert sequence.calls[0].tool_name == "pdb4amber"
    assert sequence.calls[1].tool_name == "tleap"
    assert sequence.calls[2].tool_name == "sander"


def test_step_with_explicit_required_tools(planner):
    """Test step with explicit required_tools."""
    plan = ExecutionPlan(
        plan_id="test-003",
        task_description="Test explicit tools",
        steps=[
            PlanStep(
                step_id="step-1",
                action="custom_action",
                intent="Custom processing",
                parameters={"param1": "value1"},
                required_tools=["tool_a", "tool_b"],
            )
        ],
        estimated_resources=ResourceEstimate(),
    )

    sequence = planner.plan_execution(plan)

    assert len(sequence.calls) == 2
    assert sequence.calls[0].tool_name == "tool_a"
    assert sequence.calls[1].tool_name == "tool_b"
    assert sequence.calls[0].parameters["param1"] == "value1"
    assert sequence.calls[1].parameters["param1"] == "value1"


def test_step_without_tools_infers_from_action(planner):
    """Test step without tools infers from action name."""
    plan = ExecutionPlan(
        plan_id="test-004",
        task_description="Test inference",
        steps=[
            PlanStep(
                step_id="step-1",
                action="minimize",
                intent="Energy minimization",
                parameters={"input": "system.prmtop"},
                required_tools=[],  # Empty tools list
            )
        ],
        estimated_resources=ResourceEstimate(),
    )

    sequence = planner.plan_execution(plan)

    assert len(sequence.calls) == 1
    assert sequence.calls[0].tool_name == "sander"
    assert sequence.calls[0].metadata["inferred"] is True


def test_parameter_mapping_input_to_input_file(planner):
    """Test parameter mapping from 'input' to 'input_file'."""
    plan = ExecutionPlan(
        plan_id="test-005",
        task_description="Test parameter mapping",
        steps=[
            PlanStep(
                step_id="step-1",
                action="prepare_system",
                intent="Test",
                parameters={"input": "test.pdb"},
                required_tools=["pdb4amber"],
            )
        ],
        estimated_resources=ResourceEstimate(),
    )

    sequence = planner.plan_execution(plan)

    assert "input_file" in sequence.calls[0].parameters
    assert sequence.calls[0].parameters["input_file"] == "test.pdb"


def test_parameter_mapping_output_to_output_file(planner):
    """Test parameter mapping from 'output' to 'output_file'."""
    plan = ExecutionPlan(
        plan_id="test-006",
        task_description="Test output mapping",
        steps=[
            PlanStep(
                step_id="step-1",
                action="prepare_system",
                intent="Test",
                parameters={"output": "result.pdb"},
                required_tools=["pdb4amber"],
            )
        ],
        estimated_resources=ResourceEstimate(),
    )

    sequence = planner.plan_execution(plan)

    assert "output_file" in sequence.calls[0].parameters
    assert sequence.calls[0].parameters["output_file"] == "result.pdb"


def test_metadata_preservation(planner):
    """Test metadata is preserved in tool calls."""
    plan = ExecutionPlan(
        plan_id="test-007",
        task_description="Test metadata",
        steps=[
            PlanStep(
                step_id="step-1",
                action="analyze",
                intent="Analyze trajectory",
                parameters={"traj": "prod.nc"},
                required_tools=["cpptraj"],
            )
        ],
        estimated_resources=ResourceEstimate(),
    )

    sequence = planner.plan_execution(plan)

    metadata = sequence.calls[0].metadata
    assert metadata["step_id"] == "step-1"
    assert metadata["action"] == "analyze"
    assert metadata["intent"] == "Analyze trajectory"


def test_empty_plan_returns_empty_sequence(planner):
    """Test empty plan returns empty sequence."""
    plan = ExecutionPlan(
        plan_id="test-008",
        task_description="Empty plan",
        steps=[],
        estimated_resources=ResourceEstimate(),
    )

    sequence = planner.plan_execution(plan)

    assert sequence.plan_id == "test-008"
    assert len(sequence.calls) == 0


def test_complex_amber_workflow(planner):
    """Test complex AMBER workflow translation."""
    plan = ExecutionPlan(
        plan_id="test-009",
        task_description="Complete AMBER MD simulation",
        steps=[
            PlanStep(
                step_id="step-1",
                action="clean_pdb",
                intent="Clean PDB structure",
                parameters={"input": "protein.pdb"},
                required_tools=[],
            ),
            PlanStep(
                step_id="step-2",
                action="add_hydrogens",
                intent="Add missing hydrogens",
                parameters={"input": "protein_clean.pdb"},
                required_tools=[],
            ),
            PlanStep(
                step_id="step-3",
                action="solvate",
                intent="Add water box",
                parameters={"input": "protein_h.pdb", "box_size": 10.0},
                required_tools=[],
            ),
            PlanStep(
                step_id="step-4",
                action="minimize",
                intent="Energy minimization",
                parameters={"input": "system.prmtop", "steps": 5000},
                required_tools=[],
            ),
            PlanStep(
                step_id="step-5",
                action="equilibrate",
                intent="NVT equilibration",
                parameters={"input": "system.prmtop", "temp": 300},
                required_tools=[],
            ),
            PlanStep(
                step_id="step-6",
                action="production",
                intent="Production MD",
                parameters={"input": "system.prmtop", "time": 100},
                required_tools=[],
            ),
            PlanStep(
                step_id="step-7",
                action="analyze",
                intent="Trajectory analysis",
                parameters={"traj": "prod.nc"},
                required_tools=[],
            ),
        ],
        estimated_resources=ResourceEstimate(cpu_hours=24.0, memory_gb=8.0),
    )

    sequence = planner.plan_execution(plan)

    assert len(sequence.calls) == 7
    assert sequence.calls[0].tool_name == "pdb4amber"
    assert sequence.calls[1].tool_name == "reduce"
    assert sequence.calls[2].tool_name == "tleap"
    assert sequence.calls[3].tool_name == "sander"
    assert sequence.calls[4].tool_name == "sander"
    assert sequence.calls[5].tool_name == "pmdrun"
    assert sequence.calls[6].tool_name == "cpptraj"

    # Verify all are inferred
    for call in sequence.calls:
        assert call.metadata["inferred"] is True


def test_unknown_action_returns_no_tool_call(planner):
    """Test unknown action returns no tool call."""
    plan = ExecutionPlan(
        plan_id="test-010",
        task_description="Unknown action",
        steps=[
            PlanStep(
                step_id="step-1",
                action="unknown_action",
                intent="Unknown",
                parameters={},
                required_tools=[],
            )
        ],
        estimated_resources=ResourceEstimate(),
    )

    sequence = planner.plan_execution(plan)

    assert len(sequence.calls) == 0


def test_mixed_explicit_and_inferred_tools(planner):
    """Test plan with both explicit and inferred tools."""
    plan = ExecutionPlan(
        plan_id="test-011",
        task_description="Mixed tools",
        steps=[
            PlanStep(
                step_id="step-1",
                action="custom",
                intent="Explicit tool",
                parameters={"param": "value"},
                required_tools=["explicit_tool"],
            ),
            PlanStep(
                step_id="step-2",
                action="minimize",
                intent="Inferred tool",
                parameters={"input": "system.prmtop"},
                required_tools=[],
            ),
        ],
        estimated_resources=ResourceEstimate(),
    )

    sequence = planner.plan_execution(plan)

    assert len(sequence.calls) == 2
    assert sequence.calls[0].tool_name == "explicit_tool"
    assert "inferred" not in sequence.calls[0].metadata
    assert sequence.calls[1].tool_name == "sander"
    assert sequence.calls[1].metadata["inferred"] is True


def test_parameter_preservation(planner):
    """Test all parameters are preserved in tool calls."""
    plan = ExecutionPlan(
        plan_id="test-012",
        task_description="Parameter preservation",
        steps=[
            PlanStep(
                step_id="step-1",
                action="minimize",
                intent="Test",
                parameters={
                    "input": "system.prmtop",
                    "steps": 5000,
                    "restraint": True,
                    "force_constant": 10.0,
                },
                required_tools=["sander"],
            )
        ],
        estimated_resources=ResourceEstimate(),
    )

    sequence = planner.plan_execution(plan)

    params = sequence.calls[0].parameters
    assert params["input_file"] == "system.prmtop"
    assert params["steps"] == 5000
    assert params["restraint"] is True
    assert params["force_constant"] == 10.0
