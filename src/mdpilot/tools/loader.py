"""Auto-discover and register all builtin tools."""

from __future__ import annotations

from mdpilot.tools.registry import ToolRegistry


def load_builtin_tools(registry: ToolRegistry) -> None:
    """Register all @tool functions from the builtin package.

    Args:
        registry: The ToolRegistry to register tools into.
    """
    registry.auto_discover("mdpilot.tools.builtin")
