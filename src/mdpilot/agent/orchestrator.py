"""AgentOrchestrator — tool lifecycle management and event transformation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from mdpilot.agent.node_config import NodeConfig, get_node_for_tool


class ToolStatus(str, Enum):
    """Tool execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ToolExecutionState:
    """State of a single tool execution."""

    tool_id: str
    tool_name: str
    status: ToolStatus
    node: NodeConfig
    input_params: dict[str, Any]
    output: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None


class AgentOrchestrator:
    """Manages tool execution lifecycle and emits high-level events."""

    MAX_RETRIES = 3
    RETRYABLE_PATTERNS = ["timeout", "connection_refused", "temporary_failure"]

    def __init__(self) -> None:
        self._tool_states: dict[str, ToolExecutionState] = {}
        self.on_high_level_event: Callable[[dict[str, Any]], None] = lambda e: None

    def get_tool_state(self, tool_id: str) -> Optional[ToolExecutionState]:
        """Get the current state of a tool execution."""
        return self._tool_states.get(tool_id)

    def on_tool_call(
        self,
        tool_name: str,
        tool_id: str,
        arguments: dict[str, Any],
    ) -> None:
        """Handle a TOOL_CALL event from ReActLoop."""
        node = get_node_for_tool(tool_name)
        state = ToolExecutionState(
            tool_id=tool_id,
            tool_name=tool_name,
            status=ToolStatus.RUNNING,
            node=node,
            input_params=arguments if isinstance(arguments, dict) else {},
        )
        self._tool_states[tool_id] = state

        self.on_high_level_event({
            "type": "tool_started",
            "data": {
                "type": "tool_call",
                "tool": tool_name,
                "tool_call_id": tool_id,
                "status": "running",
                "input": state.input_params,
                "backend": {
                    "node": node.node_id,
                    "gpuInfo": node.gpu_info,
                },
            },
        })

    def on_tool_result(
        self,
        tool_id: str,
        output: str,
        success: bool,
    ) -> None:
        """Handle a TOOL_RESULT event from ReActLoop."""
        state = self._tool_states.get(tool_id)
        if state is None:
            return

        state.end_time = time.time()

        if success:
            state.status = ToolStatus.COMPLETED
            state.output = output
            self.on_high_level_event({
                "type": "tool_completed",
                "data": {
                    "type": "tool_call",
                    "tool": state.tool_name,
                    "tool_call_id": tool_id,
                    "status": "completed",
                    "output": output,
                    "backend": {
                        "node": state.node.node_id,
                        "gpuInfo": state.node.gpu_info,
                    },
                },
            })
        else:
            if self._should_retry(output, state.retry_count):
                state.retry_count += 1
                state.status = ToolStatus.RUNNING
                self.on_high_level_event({
                    "type": "tool_retrying",
                    "data": {
                        "type": "tool_call",
                        "tool": state.tool_name,
                        "tool_call_id": tool_id,
                        "status": "running",
                        "error": output,
                        "retryCount": state.retry_count,
                        "backend": {
                            "node": state.node.node_id,
                            "gpuInfo": state.node.gpu_info,
                        },
                    },
                })
            else:
                state.status = ToolStatus.FAILED
                state.error = output
                self.on_high_level_event({
                    "type": "tool_failed",
                    "data": {
                        "type": "tool_call",
                        "tool": state.tool_name,
                        "tool_call_id": tool_id,
                        "status": "failed",
                        "error": output,
                        "backend": {
                            "node": state.node.node_id,
                            "gpuInfo": state.node.gpu_info,
                        },
                    },
                })

    def _should_retry(self, error: str, retry_count: int) -> bool:
        """Determine if a failed tool should be retried."""
        if retry_count >= self.MAX_RETRIES:
            return False
        error_lower = error.lower()
        return any(p in error_lower for p in self.RETRYABLE_PATTERNS)

    def reset(self) -> None:
        """Clear all tool states (for session cleanup)."""
        self._tool_states.clear()
