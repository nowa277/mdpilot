"""Shared type definitions for mdpilot.

All subsystems (config, tools, llm, agent) reference these types
to maintain a consistent internal contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Events — yielded by the ReAct loop, consumed by TUI / CLI
# ---------------------------------------------------------------------------

class EventKind(str, Enum):
    USER_MSG = "user_msg"
    ASSISTANT_MSG = "assistant_msg"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    PLAN_READY = "plan_ready"
    STEP_START = "step_start"
    STEP_RESULT = "step_result"
    DONE = "done"
    ERROR = "error"
    BUDGET_WARNING = "budget_warning"


@dataclass
class UserMsg:
    kind: EventKind = field(default=EventKind.USER_MSG, init=False)
    content: str = ""


@dataclass
class AssistantMsg:
    kind: EventKind = field(default=EventKind.ASSISTANT_MSG, init=False)
    content: str = ""


@dataclass
class ToolCallEvent:
    kind: EventKind = field(default=EventKind.TOOL_CALL, init=False)
    name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResultEvent:
    kind: EventKind = field(default=EventKind.TOOL_RESULT, init=False)
    name: str = ""
    output: str = ""
    success: bool = True


@dataclass
class Done:
    kind: EventKind = field(default=EventKind.DONE, init=False)
    reason: str = ""


@dataclass
class Error:
    kind: EventKind = field(default=EventKind.ERROR, init=False)
    message: str = ""


@dataclass
class BudgetWarning:
    kind: EventKind = field(default=EventKind.BUDGET_WARNING, init=False)
    remaining: int = 0


# Union type for event dispatch
Event = UserMsg | AssistantMsg | ToolCallEvent | ToolResultEvent | Done | Error | BudgetWarning


# ---------------------------------------------------------------------------
# Tool types — used by tools/ and agent/ subsystems
# ---------------------------------------------------------------------------

@dataclass
class ToolMeta:
    """Metadata attached to each @tool-decorated function."""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    category: str = "general"
    depends_on: list[str] = field(default_factory=list)
    resource_requirements: dict[str, Any] = field(default_factory=dict)
    estimated_duration_sec: int | None = None
    skill_guide: str | None = None


@dataclass
class ToolCall:
    """A single tool invocation request from the LLM."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolOutput:
    """Result of executing a tool."""
    output: str
    success: bool = True
    error: str | None = None
    # Structured error fields (P1-4)
    error_code: str | None = None
    error_category: str | None = None  # missing_file / amber_config / pdb_format / memory / gpu / timeout / unknown
    error_suggestion: str | None = None


# ---------------------------------------------------------------------------
# LLM types — used by llm/ and agent/ subsystems
# ---------------------------------------------------------------------------

@dataclass
class LLMChunk:
    """A single chunk from a streaming LLM response."""
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None


@dataclass
class LLMResponse:
    """A complete (non-streaming) LLM response."""
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    usage_prompt_tokens: int = 0
    usage_completion_tokens: int = 0


# ---------------------------------------------------------------------------
# Progress types — used by BioReason integration for real-time progress tracking
# ---------------------------------------------------------------------------

class ProgressStage(str, Enum):
    """Progress stages for remote tasks (BioReason + AlphaFold2)"""
    QUEUED = "queued"          # Task queued/preparing
    PREPARING = "preparing"    # 25%
    RUNNING = "running"        # Task running
    EXECUTING = "executing"    # 50%
    PROCESSING = "processing"  # Post-processing
    PARSING = "parsing"        # 75%
    COMPLETED = "completed"    # 100%
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class TaskProgress:
    """任务进度"""
    task_id: str
    stage: ProgressStage
    current_step: int
    total_steps: int
    percent: int
    message: str
    timestamp: datetime
    error: str | None = None
    
    def to_dict(self) -> dict:
        """转换为字典"""
        data = asdict(self)
        data["stage"] = self.stage.value
        data["timestamp"] = self.timestamp.isoformat()
        return data
