"""Core types for the coordination layer."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Severity(str, Enum):
    """Violation severity levels."""
    CRITICAL = "critical"  # Immediate rejection
    ERROR = "error"        # Fixable error
    WARNING = "warning"    # Suggestion


class ExecutionStatus(str, Enum):
    """Execution result status."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    RESOURCE_EXHAUSTED = "resource_exhausted"


class ResultStatus(str, Enum):
    """Individual tool result status."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class RecoveryAction(str, Enum):
    """Error recovery actions."""
    RETRY = "retry"
    SKIP = "skip"
    ABORT = "abort"
    FALLBACK = "fallback"


@dataclass
class ResourceEstimate:
    """Resource usage estimate."""
    cpu_hours: float = 0.0
    memory_gb: float = 0.0
    disk_gb: float = 0.0


@dataclass
class PlanStep:
    """Single step in execution plan."""
    step_id: str
    action: str
    intent: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    required_tools: List[str] = field(default_factory=list)
    expected_output: str = ""
    error_handling: Optional[str] = None


@dataclass
class ExecutionPlan:
    """High-level execution plan from LLM."""
    plan_id: str
    task_description: str
    steps: List[PlanStep]
    estimated_resources: ResourceEstimate
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> bool:
        """Validate plan structure."""
        if not self.plan_id:
            raise ValueError("plan_id is required")
        if not self.task_description:
            raise ValueError("task_description is required")
        if not self.steps:
            raise ValueError("plan must have at least one step")
        for step in self.steps:
            if not step.step_id:
                raise ValueError("step missing step_id")
            if not step.action:
                raise ValueError(f"step {step.step_id} missing action")
        return True


@dataclass
class Violation:
    """Guardrail violation."""
    level: str  # E, D, C, B, A
    severity: Severity
    message: str
    step_id: str
    fixable: bool = False
    suggested_fix: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of plan validation."""
    valid: bool
    violations: List[Violation] = field(default_factory=list)


@dataclass
class ToolCall:
    """Single tool invocation."""
    tool_name: str
    parameters: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionSequence:
    """Sequence of tool calls."""
    plan_id: str
    calls: List[ToolCall]


@dataclass
class ToolResult:
    """Result of tool execution."""
    status: ResultStatus
    output: Any = None
    error: Optional[str] = None
    message: str = ""


@dataclass
class ExecutionResult:
    """Result of executing a sequence."""
    sequence_id: str
    status: ExecutionStatus
    results: List[ToolResult] = field(default_factory=list)
    error: Optional[str] = None
