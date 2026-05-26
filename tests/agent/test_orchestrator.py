"""Tests for AgentOrchestrator."""
import pytest

from mdpilot.agent.events import (
    TOOL_STARTED, TOOL_RUNNING, TOOL_COMPLETED, TOOL_FAILED,
)


def test_high_level_event_constants_exist():
    """Verify new event type constants are defined."""
    assert TOOL_STARTED == "tool_started"
    assert TOOL_RUNNING == "tool_running"
    assert TOOL_COMPLETED == "tool_completed"
    assert TOOL_FAILED == "tool_failed"


from mdpilot.agent.node_config import NodeConfig, get_node_for_tool


def test_get_node_for_known_tool():
    """Known tools map to their designated nodes."""
    node = get_node_for_tool("alphafold2_predict")
    assert node.node_id == "lab02"
    assert node.gpu_info == "9× TITAN V"


def test_get_node_for_unknown_tool():
    """Unknown tools default to lab03."""
    node = get_node_for_tool("some_random_tool")
    assert node.node_id == "lab03"
    assert node.gpu_info == "4× GTX 1080Ti"


def test_node_config_has_writable_dir():
    """Each node config includes writable directory."""
    node = get_node_for_tool("bioreason_annotate")
    assert node.node_id == "lab06"
    assert node.writable_dir == "/home/6-FF/changshengjie"


import asyncio
from unittest.mock import MagicMock

from mdpilot.agent.orchestrator import AgentOrchestrator, ToolStatus


def test_orchestrator_on_tool_call_creates_running_state():
    """When a tool_call event arrives, orchestrator creates a running state."""
    orch = AgentOrchestrator()
    orch.on_tool_call(tool_name="bash_run", tool_id="tc_1", arguments={"command": "ls"})

    state = orch.get_tool_state("tc_1")
    assert state is not None
    assert state.status == ToolStatus.RUNNING
    assert state.tool_name == "bash_run"
    assert state.node.node_id == "lab03"
    assert state.input_params == {"command": "ls"}


def test_orchestrator_on_tool_result_marks_completed():
    """When a tool_result event arrives, state transitions to completed."""
    orch = AgentOrchestrator()
    orch.on_tool_call(tool_name="bash_run", tool_id="tc_1", arguments={"command": "ls"})
    orch.on_tool_result(tool_id="tc_1", output="file1.txt\nfile2.txt", success=True)

    state = orch.get_tool_state("tc_1")
    assert state.status == ToolStatus.COMPLETED
    assert state.output == "file1.txt\nfile2.txt"


def test_orchestrator_on_tool_result_failure_marks_failed():
    """When a tool_result with success=False arrives, state transitions to failed."""
    orch = AgentOrchestrator()
    orch.on_tool_call(tool_name="bash_run", tool_id="tc_1", arguments={"command": "bad"})
    orch.on_tool_result(tool_id="tc_1", output="command not found", success=False)

    state = orch.get_tool_state("tc_1")
    assert state.status == ToolStatus.FAILED
    assert state.error == "command not found"


def test_orchestrator_emits_tool_started_event():
    """Orchestrator emits TOOL_STARTED when tool_call arrives."""
    orch = AgentOrchestrator()
    events = []
    orch.on_high_level_event = lambda e: events.append(e)

    orch.on_tool_call(tool_name="alphafold2_predict", tool_id="tc_2", arguments={"seq": "MKTAY"})

    assert len(events) == 1
    assert events[0]["type"] == "tool_started"
    assert events[0]["data"]["tool"] == "alphafold2_predict"
    assert events[0]["data"]["status"] == "running"
    assert events[0]["data"]["backend"]["node"] == "lab02"
    assert events[0]["data"]["backend"]["gpuInfo"] == "9× TITAN V"
    assert events[0]["data"]["input"] == {"seq": "MKTAY"}


def test_orchestrator_emits_tool_completed_event():
    """Orchestrator emits TOOL_COMPLETED when tool_result arrives."""
    orch = AgentOrchestrator()
    events = []
    orch.on_high_level_event = lambda e: events.append(e)

    orch.on_tool_call(tool_name="bash_run", tool_id="tc_3", arguments={"command": "ls"})
    orch.on_tool_result(tool_id="tc_3", output="done", success=True)

    assert len(events) == 2
    assert events[1]["type"] == "tool_completed"
    assert events[1]["data"]["tool"] == "bash_run"
    assert events[1]["data"]["status"] == "completed"
    assert events[1]["data"]["output"] == "done"


def test_orchestrator_retries_on_timeout():
    """Orchestrator retries when error contains 'timeout'."""
    orch = AgentOrchestrator()
    events = []
    orch.on_high_level_event = lambda e: events.append(e)

    orch.on_tool_call(tool_name="pmemd.cuda", tool_id="tc_4", arguments={"steps": 1000})
    orch.on_tool_result(tool_id="tc_4", output="Error: timeout waiting for GPU", success=False)

    state = orch.get_tool_state("tc_4")
    assert state.status == ToolStatus.RUNNING  # Still running (retrying)
    assert state.retry_count == 1

    # Verify retrying event emitted
    assert events[1]["type"] == "tool_retrying"
    assert events[1]["data"]["retryCount"] == 1


def test_orchestrator_fails_after_max_retries():
    """Orchestrator marks failed after MAX_RETRIES attempts."""
    orch = AgentOrchestrator()
    events = []
    orch.on_high_level_event = lambda e: events.append(e)

    orch.on_tool_call(tool_name="pmemd.cuda", tool_id="tc_5", arguments={})
    # Fail 4 times with retryable error (1 initial + 3 retries)
    for _ in range(4):
        orch.on_tool_result(tool_id="tc_5", output="timeout", success=False)

    state = orch.get_tool_state("tc_5")
    assert state.status == ToolStatus.FAILED
    assert state.retry_count == 3


def test_orchestrator_no_retry_on_fatal_error():
    """Orchestrator does not retry on non-retryable errors."""
    orch = AgentOrchestrator()
    events = []
    orch.on_high_level_event = lambda e: events.append(e)

    orch.on_tool_call(tool_name="bash_run", tool_id="tc_6", arguments={"command": "rm -rf /"})
    orch.on_tool_result(tool_id="tc_6", output="Permission denied: dangerous command blocked", success=False)

    state = orch.get_tool_state("tc_6")
    assert state.status == ToolStatus.FAILED
    assert state.retry_count == 0
