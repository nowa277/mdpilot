"""Tool registry for managing and discovering @tool-decorated functions."""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Any, Callable

from mdpilot.types import ToolMeta
from mdpilot.tools.skill_loader import SkillLoader

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry of all available tools.

    Tools are registered as callables decorated with ``@tool``. The registry
    stores both the ToolMeta metadata and the callable so it can produce
    OpenAI-compatible function-calling schemas on demand.
    """

    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolMeta, Callable]] = {}

    def register(self, fn: Callable) -> None:
        """Register a @tool-decorated function.

        Args:
            fn: A function that has ``_tool_meta`` attached by the @tool decorator.

        Raises:
            ValueError: If the function is not decorated with @tool or has invalid metadata.
        """
        if not callable(fn):
            raise ValueError(f"Cannot register non-callable object: {type(fn).__name__}")

        meta: ToolMeta = getattr(fn, "_tool_meta", None)
        if meta is None:
            raise ValueError(
                f"Function '{fn.__name__}' is not decorated with @tool. "
                f"Use @tool decorator before registering."
            )

        if not meta.name:
            raise ValueError(f"Tool '{fn.__name__}' has empty name in metadata")

        if meta.name in self._tools:
            logger.warning(f"Tool '{meta.name}' is already registered. Overwriting.")

        # Enhance description with L1 metadata from SKILL.md if available
        if meta.skill_guide:
            try:
                l1 = SkillLoader.load_l1(meta.skill_guide)
                if l1:
                    extras: list[str] = []
                    if l1.get("node"):
                        extras.append(f"node={l1['node']}")
                    if l1.get("exec_method"):
                        extras.append(f"exec={l1['exec_method']}")
                    if l1.get("depends_on"):
                        deps = l1["depends_on"]
                        if isinstance(deps, list):
                            extras.append(f"depends_on={','.join(deps)}")
                        else:
                            extras.append(f"depends_on={deps}")
                    if l1.get("triggers"):
                        triggers = l1["triggers"]
                        if isinstance(triggers, list):
                            extras.append(f"triggers={','.join(triggers)}")
                        else:
                            extras.append(f"triggers={triggers}")
                    if extras:
                        meta.description += f" [{', '.join(extras)}]"
            except Exception as exc:
                logger.warning(
                    "Failed to load L1 skill metadata for '%s' (%s): %s",
                    meta.name, meta.skill_guide, exc,
                )

        self._tools[meta.name] = (meta, fn)
        logger.debug(f"Registered tool: {meta.name}")

    def schemas(self) -> list[dict[str, Any]]:
        """Return OpenAI function-calling format schema list.

        Each entry has ``type: "function"`` with a ``function`` key containing
        ``name``, ``description``, and ``parameters``.
        """
        result: list[dict[str, Any]] = []
        for meta, _ in self._tools.values():
            result.append(
                {
                    "type": "function",
                    "function": {
                        "name": meta.name,
                        "description": meta.description,
                        "parameters": meta.parameters,
                    },
                }
            )
        return result

    def get(self, name: str) -> tuple[ToolMeta, Callable] | None:
        """Look up a tool by name.

        Args:
            name: The tool name.

        Returns:
            A ``(ToolMeta, callable)`` tuple, or ``None`` if not found.
        """
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """Return a sorted list of registered tool names."""
        return sorted(self._tools.keys())

    def auto_discover(self, package_path: str) -> None:
        """Auto-discover and register tools from a package.

        Imports all modules found under *package_path* and registers any
        functions that carry the ``_tool_meta`` attribute.

        Args:
            package_path: Dotted package path, e.g. ``"mdpilot.tools.builtin"``.

        Note:
            Import errors and registration errors are logged but do not stop discovery.
            This allows partial tool loading when some modules have issues.
        """
        try:
            package = importlib.import_module(package_path)
        except ImportError as e:
            logger.error(f"Failed to import package '{package_path}': {e}")
            return

        package_dir = getattr(package, "__path__", None)
        if package_dir is None:
            logger.warning(f"Package '{package_path}' has no __path__ attribute. Skipping.")
            return

        discovered_count = 0
        error_count = 0

        for _importer, modname, _ispkg in pkgutil.walk_packages(
            package_dir, prefix=package_path + "."
        ):
            try:
                mod = importlib.import_module(modname)
            except Exception as e:
                logger.warning(f"Failed to import module '{modname}': {e}")
                error_count += 1
                continue

            for attr_name in dir(mod):
                try:
                    obj = getattr(mod, attr_name)
                    if callable(obj) and hasattr(obj, "_tool_meta"):
                        self.register(obj)
                        discovered_count += 1
                except Exception as e:
                    logger.warning(
                        f"Failed to register '{attr_name}' from '{modname}': {e}"
                    )
                    error_count += 1

        logger.info(
            f"Auto-discovery complete: {discovered_count} tools registered "
            f"from '{package_path}' ({error_count} errors)"
        )
