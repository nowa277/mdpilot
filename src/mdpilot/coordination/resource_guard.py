"""Runtime resource monitoring and guards."""

from typing import Dict

from mdpilot.coordination.config import ResourceLimits
from mdpilot.coordination.types import ToolCall


class ResourceGuard:
    """Monitors and enforces runtime resource limits."""

    def __init__(self, limits: ResourceLimits):
        """Initialize resource guard.

        Args:
            limits: Resource limits to enforce
        """
        self.limits = limits
        self.current_usage: Dict[str, float] = {
            "cpu_hours": 0.0,
            "memory_gb": 0.0,
            "disk_gb": 0.0
        }

    def check_available(self, tool_call: ToolCall) -> bool:
        """Check if resources available for tool call.

        Args:
            tool_call: Tool call to check resources for

        Returns:
            True if resources available, False otherwise
        """
        estimated = self._estimate_tool_resources(tool_call)

        # Check against limits
        if self.current_usage["memory_gb"] + estimated["memory_gb"] > self.limits.max_memory_gb:
            return False
        if self.current_usage["cpu_hours"] + estimated["cpu_hours"] > self.limits.max_cpu_hours:
            return False
        if self.current_usage["disk_gb"] + estimated["disk_gb"] > self.limits.max_disk_gb:
            return False

        return True

    def record_usage(self, tool_call: ToolCall, actual_usage: Dict[str, float]) -> None:
        """Record actual resource usage.

        Args:
            tool_call: Tool call that was executed
            actual_usage: Actual resource usage
        """
        for key in actual_usage:
            if key in self.current_usage:
                self.current_usage[key] += actual_usage[key]

    def _estimate_tool_resources(self, tool_call: ToolCall) -> Dict[str, float]:
        """Estimate resource needs for tool.

        Args:
            tool_call: Tool call to estimate

        Returns:
            Estimated resource usage
        """
        # Tool-specific estimates
        tool_estimates = {
            "minimize": {"cpu_hours": 0.5, "memory_gb": 2.0, "disk_gb": 1.0},
            "equilibrate": {"cpu_hours": 1.0, "memory_gb": 4.0, "disk_gb": 2.0},
            "production": {"cpu_hours": 5.0, "memory_gb": 8.0, "disk_gb": 5.0},
            "analyze": {"cpu_hours": 0.2, "memory_gb": 1.0, "disk_gb": 0.5},
        }

        # Default estimate
        default = {"cpu_hours": 0.1, "memory_gb": 1.0, "disk_gb": 0.5}

        return tool_estimates.get(tool_call.tool_name, default)

    def get_current_usage(self) -> Dict[str, float]:
        """Get current resource usage.

        Returns:
            Current resource usage
        """
        return self.current_usage.copy()

    def reset_usage(self) -> None:
        """Reset resource usage counters."""
        self.current_usage = {
            "cpu_hours": 0.0,
            "memory_gb": 0.0,
            "disk_gb": 0.0
        }
