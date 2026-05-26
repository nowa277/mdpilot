"""Tests for ProgressTracker."""

import pytest
from datetime import datetime

from mdpilot.agent.dependency_graph import ExecutionWave, ToolNode
from mdpilot.agent.events import (
    PARALLEL_TOOL_COMPLETE,
    PARALLEL_TOOL_ERROR,
    PARALLEL_TOOL_START,
    PARALLEL_WAVE_COMPLETE,
    PARALLEL_WAVE_START,
)
from mdpilot.agent.progress_tracker import ProgressTracker, ToolProgress
from mdpilot.types import ToolCall


@pytest.fixture
def sample_tool_nodes():
    """Create sample tool nodes for testing."""
    return [
        ToolNode(
            tool_id="tool_1",
            tool_call=ToolCall(id="tool_1", name="pdb4amber", arguments={}),
            input_files=set(),
            output_files=set(),
            explicit_deps=[],
        ),
        ToolNode(
            tool_id="tool_2",
            tool_call=ToolCall(id="tool_2", name="tleap", arguments={}),
            input_files=set(),
            output_files=set(),
            explicit_deps=[],
        ),
        ToolNode(
            tool_id="tool_3",
            tool_call=ToolCall(id="tool_3", name="sander", arguments={}),
            input_files=set(),
            output_files=set(),
            explicit_deps=[],
        ),
    ]


@pytest.fixture
def sample_wave(sample_tool_nodes):
    """Create a sample execution wave."""
    return ExecutionWave(wave_id=0, tools=sample_tool_nodes[:2])


def test_progress_tracker_initialization():
    """Test ProgressTracker initialization."""
    tracker = ProgressTracker(total_tools=5)

    assert tracker._total_tools == 5
    assert tracker._completed_tools == 0
    assert tracker._failed_tools == 0
    assert len(tracker._tool_progress) == 0
    assert tracker.get_progress() == 0.0


def test_progress_tracker_initialization_zero_tools():
    """Test ProgressTracker with zero tools."""
    tracker = ProgressTracker(total_tools=0)

    assert tracker.get_progress() == 1.0


def test_progress_tracker_tool_lifecycle():
    """Test complete tool lifecycle: start -> complete."""
    tracker = ProgressTracker(total_tools=3)

    # Start tool
    event = tracker.start_tool("tool_1")
    assert event.type == PARALLEL_TOOL_START
    assert event.data["tool_id"] == "tool_1"
    assert event.data["progress"] == 0.0
    assert "tool_1" in tracker._tool_progress
    assert tracker._tool_progress["tool_1"].status == "running"
    assert tracker._tool_progress["tool_1"].start_time is not None

    # Complete tool
    event = tracker.complete_tool("tool_1")
    assert event.type == PARALLEL_TOOL_COMPLETE
    assert event.data["tool_id"] == "tool_1"
    assert event.data["progress"] == pytest.approx(1 / 3)
    assert tracker._tool_progress["tool_1"].status == "completed"
    assert tracker._tool_progress["tool_1"].end_time is not None
    assert tracker._completed_tools == 1


def test_progress_tracker_tool_failure():
    """Test tool failure: start -> fail."""
    tracker = ProgressTracker(total_tools=2)

    # Start tool
    event = tracker.start_tool("tool_1")
    assert event.type == PARALLEL_TOOL_START
    assert tracker._tool_progress["tool_1"].status == "running"

    # Fail tool
    error_msg = "File not found"
    event = tracker.fail_tool("tool_1", error_msg)
    assert event.type == PARALLEL_TOOL_ERROR
    assert event.data["tool_id"] == "tool_1"
    assert event.data["error"] == error_msg
    assert event.data["progress"] == 0.5
    assert tracker._tool_progress["tool_1"].status == "failed"
    assert tracker._tool_progress["tool_1"].error == error_msg
    assert tracker._tool_progress["tool_1"].end_time is not None
    assert tracker._failed_tools == 1


def test_progress_tracker_wave_events(sample_wave):
    """Test wave start and complete events."""
    tracker = ProgressTracker(total_tools=2)

    # Start wave
    event = tracker.start_wave(sample_wave)
    assert event.type == PARALLEL_WAVE_START
    assert event.data["wave_id"] == 0
    assert event.data["tool_count"] == 2
    assert event.data["tool_ids"] == ["tool_1", "tool_2"]

    # Complete wave
    event = tracker.complete_wave(sample_wave)
    assert event.type == PARALLEL_WAVE_COMPLETE
    assert event.data["wave_id"] == 0
    assert event.data["tool_count"] == 2
    assert "progress" in event.data


def test_progress_tracker_progress_calculation():
    """Test progress percentage calculation."""
    tracker = ProgressTracker(total_tools=4)

    # Initial progress
    assert tracker.get_progress() == 0.0

    # Complete one tool
    tracker.start_tool("tool_1")
    tracker.complete_tool("tool_1")
    assert tracker.get_progress() == 0.25

    # Complete another tool
    tracker.start_tool("tool_2")
    tracker.complete_tool("tool_2")
    assert tracker.get_progress() == 0.5

    # Fail one tool
    tracker.start_tool("tool_3")
    tracker.fail_tool("tool_3", "error")
    assert tracker.get_progress() == 0.75

    # Complete last tool
    tracker.start_tool("tool_4")
    tracker.complete_tool("tool_4")
    assert tracker.get_progress() == 1.0


def test_progress_tracker_multiple_tools_parallel():
    """Test tracking multiple tools executing in parallel."""
    tracker = ProgressTracker(total_tools=3)

    # Start all tools
    tracker.start_tool("tool_1")
    tracker.start_tool("tool_2")
    tracker.start_tool("tool_3")

    assert len(tracker._tool_progress) == 3
    assert tracker.get_progress() == 0.0

    # Complete in different order
    tracker.complete_tool("tool_2")
    assert tracker.get_progress() == pytest.approx(1 / 3)

    tracker.complete_tool("tool_1")
    assert tracker.get_progress() == pytest.approx(2 / 3)

    tracker.complete_tool("tool_3")
    assert tracker.get_progress() == 1.0


def test_progress_tracker_mixed_success_failure():
    """Test progress with mix of successful and failed tools."""
    tracker = ProgressTracker(total_tools=4)

    # Complete two tools successfully
    tracker.start_tool("tool_1")
    tracker.complete_tool("tool_1")
    tracker.start_tool("tool_2")
    tracker.complete_tool("tool_2")

    assert tracker._completed_tools == 2
    assert tracker._failed_tools == 0
    assert tracker.get_progress() == 0.5

    # Fail two tools
    tracker.start_tool("tool_3")
    tracker.fail_tool("tool_3", "error 1")
    tracker.start_tool("tool_4")
    tracker.fail_tool("tool_4", "error 2")

    assert tracker._completed_tools == 2
    assert tracker._failed_tools == 2
    assert tracker.get_progress() == 1.0


def test_progress_tracker_complete_without_start():
    """Test completing a tool that was never started."""
    tracker = ProgressTracker(total_tools=2)

    # Complete tool without starting it
    event = tracker.complete_tool("tool_1")

    assert event.type == PARALLEL_TOOL_COMPLETE
    assert tracker._completed_tools == 1
    # Tool should not be in progress dict since it was never started
    assert "tool_1" not in tracker._tool_progress


def test_progress_tracker_fail_without_start():
    """Test failing a tool that was never started."""
    tracker = ProgressTracker(total_tools=2)

    # Fail tool without starting it
    event = tracker.fail_tool("tool_1", "error")

    assert event.type == PARALLEL_TOOL_ERROR
    assert tracker._failed_tools == 1
    # Tool should not be in progress dict since it was never started
    assert "tool_1" not in tracker._tool_progress


def test_progress_tracker_thread_safety():
    """Test that ProgressTracker is thread-safe."""
    import threading

    tracker = ProgressTracker(total_tools=10)

    def complete_tool(tool_id: str):
        tracker.start_tool(tool_id)
        tracker.complete_tool(tool_id)

    # Start multiple threads
    threads = []
    for i in range(10):
        thread = threading.Thread(target=complete_tool, args=(f"tool_{i}",))
        threads.append(thread)
        thread.start()

    # Wait for all threads
    for thread in threads:
        thread.join()

    # Verify all tools completed
    assert tracker._completed_tools == 10
    assert tracker.get_progress() == 1.0
