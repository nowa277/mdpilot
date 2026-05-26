"""Tool dispatcher — resolves ToolCall to actual function execution."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from mdpilot.types import ToolCall, ToolOutput
from mdpilot.tools.registry import ToolRegistry
from mdpilot.tools.error_classifier import classify_amber_error
from mdpilot.tools.file_context import FileContext, detect_file_type
from mdpilot.tools.skill_loader import SkillLoader

logger = logging.getLogger(__name__)


class ToolValidationError(Exception):
    """Raised when tool arguments fail schema validation."""
    pass


class ToolDispatcher:
    """Dispatches ToolCall objects to registered tool functions.

    Args:
        registry: The ToolRegistry containing tool metadata and callables.
        file_context: Optional file context for tracking output files.
        timeout_manager: Optional timeout manager for enforcing timeouts.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        file_context: FileContext | None = None,
        timeout_manager: Any | None = None
    ) -> None:
        self._registry = registry
        self._file_context = file_context or FileContext()
        self._timeout_manager = timeout_manager
        self._pending_skill_context: dict[str, str] = {}

    async def execute(self, call: ToolCall) -> ToolOutput:
        """Execute a tool call.

        Looks up the tool, validates arguments against its JSON Schema,
        calls the function (async or sync), and wraps the result.

        Args:
            call: The ToolCall request from the LLM.

        Returns:
            ToolOutput with output text or error details.
        """
        logger.debug(f"Executing tool: {call.name} with args: {list(call.arguments.keys())}")

        entry = self._registry.get(call.name)
        if entry is None:
            available_tools = ", ".join(self._registry.list_tools()[:5])
            error_msg = (
                f"Tool '{call.name}' not found. "
                f"Available tools: {available_tools}..."
            )
            logger.error(error_msg)
            return ToolOutput(
                output="",
                success=False,
                error=error_msg,
            )

        meta, fn = entry

        # Load L2 skill instructions before execution (for agent consumption)
        if meta.skill_guide:
            try:
                l2 = SkillLoader.load_l2(meta.skill_guide)
                if l2:
                    self._pending_skill_context[call.name] = l2
            except Exception as exc:
                logger.warning(
                    "Failed to load L2 skill content for '%s' (%s): %s",
                    call.name, meta.skill_guide, exc,
                )

        # Validate arguments against schema
        # Filter streaming artifacts before validation
        call.arguments.pop("__streaming_raw__", None)
        try:
            self._validate_args(call.arguments, meta.parameters)
        except ToolValidationError as exc:
            error_msg = f"Argument validation failed for '{call.name}': {exc}"
            logger.error(error_msg)
            return ToolOutput(
                output="",
                success=False,
                error=error_msg,
            )

        # Execute the function
        try:
            if asyncio.iscoroutinefunction(fn):
                coro = fn(**call.arguments)
            else:
                coro = asyncio.to_thread(fn, **call.arguments)
            
            # Enforce timeout if timeout_manager is configured
            if self._timeout_manager:
                timeout_sec = self._timeout_manager.resolve_timeout(call.name)
                if timeout_sec:
                    result = await self._timeout_manager.enforce_timeout(coro, timeout_sec, call)
                else:
                    result = await coro
            else:
                result = await coro
            
            output_text = str(result) if result is not None else ""

            # Post-classify: many AMBER tools return "Error: ..." strings
            # with success=True (because they catch internally). Detect and
            # re-classify these for structured error reporting.
            if output_text.startswith("Error:"):
                classified = classify_amber_error(output_text)
                logger.warning(f"Tool '{call.name}' returned error: {output_text[:100]}")
                return ToolOutput(
                    output="",
                    success=False,
                    error=output_text,
                    error_code=classified.code if classified else None,
                    error_category=classified.category if classified else None,
                    error_suggestion=classified.suggestion if classified else None,
                )

            # Track output files in file context
            self._register_output_files(call.name, call.arguments, output_text)

            logger.debug(f"Tool '{call.name}' completed successfully")
            return ToolOutput(output=output_text)
        except TimeoutError as exc:
            error_msg = str(exc)
            logger.error(f"Tool '{call.name}' timed out: {error_msg}")
            return ToolOutput(
                output="",
                success=False,
                error=error_msg,
                error_code="TIMEOUT",
                error_category="timeout",
                error_suggestion=f"Consider increasing timeout for '{call.name}' or optimizing the operation"
            )
        except TypeError as exc:
            # TypeError often indicates argument mismatch
            error_msg = (
                f"Argument error calling '{call.name}': {exc}. "
                f"Check that all required parameters are provided."
            )
            logger.error(error_msg)
            return ToolOutput(
                output="",
                success=False,
                error=error_msg,
            )
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            logger.exception(f"Tool '{call.name}' raised exception: {error_msg}")
            classified = classify_amber_error(error_msg)
            return ToolOutput(
                output="",
                success=False,
                error=error_msg,
                error_code=classified.code if classified else None,
                error_category=classified.category if classified else None,
                error_suggestion=classified.suggestion if classified else None,
            )

    def _validate_args(self, args: dict[str, Any], schema: dict[str, Any]) -> None:
        """Validate arguments against a JSON Schema fragment.

        Only checks required fields and basic type correctness.
        Full JSON Schema validation is delegated to the LLM/proxy layer.
        """
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        # Check required fields
        for field_name in required:
            if field_name not in args:
                raise ToolValidationError(f"Missing required argument: {field_name}")

        # Check for unknown fields (lenient — ignore extras)
        # Check type correctness for provided args
        for field_name, value in args.items():
            if field_name not in properties:
                continue
            prop_schema = properties[field_name]
            expected_type = prop_schema.get("type")
            if expected_type is None:
                continue

            # Nullable fields accept None
            if value is None and prop_schema.get("nullable", False):
                continue

            # Type check
            type_map = {
                "string": str,
                "integer": int,
                "number": (int, float),
                "boolean": bool,
                "array": list,
                "object": dict,
            }
            expected_python_type = type_map.get(expected_type)
            if expected_python_type and not isinstance(value, expected_python_type):
                # Allow int for number type
                if expected_type == "number" and isinstance(value, int):
                    continue
                raise ToolValidationError(
                    f"Argument '{field_name}' must be of type {expected_type}, "
                    f"got {type(value).__name__}"
                )

            # For array, check items if schema specifies
            if expected_type == "array" and isinstance(value, list):
                items_schema = prop_schema.get("items")
                if items_schema:
                    item_type = items_schema.get("type")
                    if item_type:
                        item_python_type = type_map.get(item_type)
                        if item_python_type:
                            for i, item in enumerate(value):
                                if not isinstance(item, item_python_type):
                                    if item_type == "number" and isinstance(item, int):
                                        continue
                                    raise ToolValidationError(
                                        f"Array item[{i}] of '{field_name}' must be "
                                        f"{item_type}, got {type(item).__name__}"
                                    )

    def _register_output_files(
        self, tool_name: str, arguments: dict[str, Any], output_text: str
    ) -> None:
        """Register output files produced by a tool into the file context.

        Scans tool arguments for output-like paths and parses output text
        for file references (e.g. "[workdir: ...]", "[trajectory: ...]").
        """
        # From arguments: common output param names
        output_params = {
            "output": "out",
            "trajectory": "nc",
        }
        for param, ftype in output_params.items():
            if param in arguments and arguments[param]:
                path = str(arguments[param])
                self._file_context.add_file(
                    path=path,
                    produced_by=tool_name,
                    step=param,
                    file_type=ftype,
                )

        # From output text: parse workdir, trajectory, restart references
        import re
        for pattern, ftype in [
            (r"\[trajectory:\s*([^\s\]]+)", "nc"),
            (r"\[restart:\s*([^\s\]]+)", "inpcrd"),
            (r"\[workdir:\s*([^\s\]]+)", "other"),
        ]:
            for m in re.finditer(pattern, output_text):
                self._file_context.add_file(
                    path=m.group(1),
                    produced_by=tool_name,
                    step="output",
                    file_type=ftype,
                )

        # For pdb4amber: infer output from input_pdb
        if tool_name == "pdb4amber" and "input_pdb" in arguments:
            input_path = Path(arguments["input_pdb"])
            clean_path = input_path.parent / f"{input_path.stem}_clean.pdb"
            self._file_context.add_file(
                path=str(clean_path),
                produced_by="pdb4amber",
                step="clean_output",
                file_type="pdb",
            )

        # For tleap: infer prmtop/inpcrd from input_script
        if tool_name == "tleap":
            # Default output names from tleap wizard
            workdir = arguments.get("workdir", ".")
            self._file_context.add_file(
                path=f"{workdir}/system.prmtop",
                produced_by="tleap",
                step="topology",
                file_type="prmtop",
            )
            self._file_context.add_file(
                path=f"{workdir}/system.inpcrd",
                produced_by="tleap",
                step="coordinates",
                file_type="inpcrd",
            )

    def pop_skill_context(self, tool_name: str) -> str | None:
        """Retrieve and remove pending L2 skill context for a tool.

        Called by the agent integration (P8) after tool execution to
        inject skill instructions into the conversation context.

        Args:
            tool_name: Name of the tool whose skill context to retrieve.

        Returns:
            L2 body string, or ``None`` if no context was stored.
        """
        return self._pending_skill_context.pop(tool_name, None)
