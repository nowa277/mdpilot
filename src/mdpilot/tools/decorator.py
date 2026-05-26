"""@tool decorator for registering AMBER agent tools.

Auto-generates JSON Schema from type hints and docstrings,
attaching ToolMeta metadata to the decorated function.
"""

from __future__ import annotations

import inspect
import re
import types
from typing import Any, Optional, Union, get_type_hints

from mdpilot.types import ToolMeta


def _parse_args_section(docstring: str) -> dict[str, str]:
    """Parse Google-style Args: section from a docstring.

    Returns a mapping of parameter name -> description string.
    """
    args_desc: dict[str, str] = {}
    in_args = False
    for line in docstring.split("\n"):
        stripped = line.strip()
        if stripped.startswith("Args:"):
            in_args = True
            continue
        if in_args:
            # A new section starts (e.g. Returns:, Raises:)
            if stripped.endswith(":") and not stripped.startswith(" "):
                break
            # Match "name: description" or "name (type): description"
            match = re.match(r"^\s*(\w+)\s*(?:\([^)]*\))?\s*:\s*(.*)", line)
            if match:
                args_desc[match.group(1)] = match.group(2).strip()
    return args_desc


def _type_to_schema(py_type: Any) -> dict[str, Any]:
    """Convert a Python type hint to a JSON Schema fragment."""
    origin = getattr(py_type, "__origin__", None)

    # Handle types.UnionType (str | None syntax, Python 3.10+)
    if isinstance(py_type, types.UnionType):
        args = py_type.__args__
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1 and type(None) in args:
            schema = _type_to_schema(non_none[0])
            return {**schema, "nullable": True}
        elif non_none:
            return _type_to_schema(non_none[0])
        return {}

    # Handle Union (including Optional)
    if hasattr(py_type, "__args__") and origin is not None:
        args = getattr(py_type, "__args__", ())
        # Optional[X] is Union[X, None]
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1 and type(None) in args:
            # It's Optional[X]
            schema = _type_to_schema(non_none[0])
            return {**schema, "nullable": True}
        else:
            # General Union — pick first non-None type
            if non_none:
                return _type_to_schema(non_none[0])
            return {}

    # Simple types
    type_map: dict[type, str] = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
    }

    if py_type in type_map:
        return {"type": type_map[py_type]}

    # list -> array
    if py_type is list or origin is list:
        schema: dict[str, Any] = {"type": "array"}
        args = getattr(py_type, "__args__", None)
        if args:
            schema["items"] = _type_to_schema(args[0])
        return schema

    # dict -> object
    if py_type is dict or origin is dict:
        schema = {"type": "object"}
        args = getattr(py_type, "__args__", None)
        if args and len(args) >= 2:
            schema["additionalProperties"] = _type_to_schema(args[1])
        return schema

    # Fallback
    return {"type": "string"}


def tool(
    name: str,
    description: str,
    category: str = "general",
    depends_on: list[str] | None = None,
    resource_requirements: dict[str, Any] | None = None,
    estimated_duration_sec: int | None = None,
    exclude: list[str] | None = None,
    skill_guide: str | None = None,
):
    """Decorator that marks a function as a tool and generates its metadata.

    Usage::

        @tool(name="my_tool", description="Does something useful")
        def my_func(arg1: str, arg2: int = 0) -> str:
            '''Function description.

            Args:
                arg1: First argument
                arg2: Second argument
            '''
            ...

    Parameters:
        name: The tool name exposed to the LLM.
        description: Human-readable description of the tool.
        category: Tool category for grouping (e.g. "amber", "file", "general").
        depends_on: List of tool names this tool depends on.
        resource_requirements: Resource requirements (cpu_cores, memory_mb, gpu).
        estimated_duration_sec: Estimated execution duration in seconds.
        exclude: List of parameter names to exclude from the tool schema.
    """

    def decorator(fn):
        # Build parameter schema from type hints
        hints = get_type_hints(fn)
        sig = inspect.signature(fn)
        args_desc = _parse_args_section(fn.__doc__) if fn.__doc__ else {}

        properties: dict[str, Any] = {}
        required: list[str] = []

        for param_name, param in sig.parameters.items():
            # Skip excluded parameters
            if exclude and param_name in exclude:
                continue

            hint = hints.get(param_name)
            if hint is None:
                # No type hint — default to string
                prop_schema: dict[str, Any] = {"type": "string"}
            else:
                prop_schema = _type_to_schema(hint)

            # If parameter has a default, add it to schema
            if param.default is not inspect.Parameter.empty:
                prop_schema["default"] = param.default
            else:
                required.append(param_name)

            # Add description from docstring if available
            if param_name in args_desc:
                prop_schema["description"] = args_desc[param_name]

            properties[param_name] = prop_schema

        parameters_schema = {
            "type": "object",
            "properties": properties,
        }
        if required:
            parameters_schema["required"] = required

        meta = ToolMeta(
            name=name,
            description=description,
            parameters=parameters_schema,
            category=category,
            depends_on=depends_on or [],
            resource_requirements=resource_requirements or {},
            estimated_duration_sec=estimated_duration_sec,
            skill_guide=skill_guide,
        )
        fn._tool_meta = meta  # type: ignore[attr-defined]
        return fn

    return decorator
