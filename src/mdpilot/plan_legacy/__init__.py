"""
DEPRECATED: This module is marked for removal in v1.0.0.
Use the new coordination layer (mdpilot.coordination) instead.

Legacy plan module - will be replaced by Planner + Executor architecture.
Kept temporarily for backward compatibility.
"""
import warnings

warnings.warn(
    "mdpilot.plan_legacy is deprecated and will be removed in v1.0.0. "
    "Use mdpilot.coordination instead.",
    DeprecationWarning,
    stacklevel=2
)

from mdpilot.plan_legacy.executor import PlanExecutor
from mdpilot.plan_legacy.generator import PlanGenerationError, PlanGenerator
from mdpilot.plan_legacy.schema import Plan, PlanResult, PlanStep

__all__ = [
    "Plan",
    "PlanExecutor",
    "PlanGenerationError",
    "PlanGenerator",
    "PlanResult",
    "PlanStep",
]
