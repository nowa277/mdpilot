"""Configuration for coordination layer guardrails."""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ResourceLimits:
    """Resource usage limits (E-level)."""
    max_cpu_hours: float = 10.0
    max_memory_gb: float = 16.0
    max_disk_gb: float = 50.0
    max_cpu: float = 8.0  # Runtime CPU cores
    max_memory: float = 16.0  # Runtime memory GB
    max_disk: float = 50.0  # Runtime disk GB


@dataclass
class RecoveryPolicies:
    """Error recovery policies (D-level)."""
    max_retries: int = 3
    retry_delay: float = 1.0
    allowed_strategies: List[str] = field(default_factory=lambda: [
        "retry_with_backoff",
        "fallback_tool",
        "skip_step",
        "abort_plan"
    ])


@dataclass
class WorkflowRules:
    """Workflow validation rules (C-level)."""
    required_steps: List[str] = field(default_factory=lambda: [
        "prepare_system",
        "minimize",
        "equilibrate"
    ])
    step_order_constraints: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class ToolConstraints:
    """Tool parameter constraints (B-level)."""
    parameter_ranges: Dict[str, Dict[str, any]] = field(default_factory=dict)
    required_parameters: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class FileSystemPermissions:
    """File system access permissions (A-level)."""
    allowed_paths: List[str] = field(default_factory=lambda: [
        "/home/user/obsidian/project/MDPilot",
        "/tmp"
    ])
    forbidden_paths: List[str] = field(default_factory=lambda: [
        "/etc",
        "/sys",
        "/proc"
    ])


@dataclass
class GuardrailConfig:
    """Complete guardrail configuration."""
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    recovery_policies: RecoveryPolicies = field(default_factory=RecoveryPolicies)
    workflow_rules: WorkflowRules = field(default_factory=WorkflowRules)
    tool_constraints: ToolConstraints = field(default_factory=ToolConstraints)
    fs_permissions: FileSystemPermissions = field(default_factory=FileSystemPermissions)
