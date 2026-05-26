"""Command injection protection and input validation.

This module provides comprehensive security validation for all subprocess calls
and user inputs to prevent command injection attacks.
"""

from __future__ import annotations

import logging
import os
import re
import shlex
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when input validation fails."""

    pass


# Shell metacharacters that could enable command injection
SHELL_METACHARACTERS = {
    ";",  # Command separator
    "&",  # Background execution / command chaining
    "|",  # Pipe
    ">",  # Redirect output
    "<",  # Redirect input
    "`",  # Command substitution
    "$",  # Variable expansion
    "(",  # Subshell
    ")",  # Subshell
    "{",  # Brace expansion
    "}",  # Brace expansion
    "\n",  # Newline (command separator)
    "\r",  # Carriage return
    "\\",  # Escape character (can be used for injection)
}

# Dangerous command patterns (for shell execution validation)
DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\s+/",  # rm -rf /
    r"\b(sudo|su)\b",  # privilege escalation
    r">\s*/dev/sd[a-z]",  # writing to disk devices
    r"\bcurl\b.*\|\s*(bash|sh)",  # curl | bash
    r"\bwget\b.*\|\s*(bash|sh)",  # wget | bash
    r";\s*rm\s+-rf",  # command chaining with rm -rf
    r"\&\&\s*rm\s+-rf",  # command chaining with rm -rf
    r"\|\s*rm\s+-rf",  # piping to rm -rf
    r"\$\(.*\)",  # command substitution $(...)
    r"`.*`",  # command substitution `...`
    r"\beval\b",  # eval command
    r"\bexec\b",  # exec command
]

# Whitelist of allowed AMBER tools (extensible)
ALLOWED_TOOLS = {
    # AMBER suite
    "tleap",
    "sander",
    "pmemd",
    "pmemd.cuda",
    "pmemd.MPI",
    "pmemd.cuda.MPI",
    "antechamber",
    "parmchk2",
    "cpptraj",
    "pdb4amber",
    "reduce",
    "propka3",
    "parmed",
    # Standard utilities
    "bash",
    "sh",
    "python",
    "python3",
    "mpirun",
    "mpiexec",
    # Analysis tools
    "vmd",
    "pymol",
}


class CommandValidator:
    """Validates commands and inputs for security."""

    def __init__(self, additional_tools: set[str] | None = None):
        """Initialize validator.

        Args:
            additional_tools: Additional tool names to whitelist.
        """
        self.allowed_tools = ALLOWED_TOOLS.copy()
        if additional_tools:
            self.allowed_tools.update(additional_tools)
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in DANGEROUS_PATTERNS
        ]

    def validate_command(self, tool: str, args: list[str]) -> None:
        """Validate a command is safe to execute.

        Args:
            tool: Tool/executable name.
            args: Command arguments as list.

        Raises:
            ValidationError: If command is unsafe.
        """
        # Validate tool name
        if not self.is_whitelisted_tool(tool):
            logger.warning(f"Blocked non-whitelisted tool: {tool}")
            raise ValidationError(
                f"Tool '{tool}' is not in the whitelist. "
                f"Allowed tools: {sorted(self.allowed_tools)}"
            )

        # Validate each argument
        for i, arg in enumerate(args):
            try:
                self.sanitize_argument(arg, allow_paths=True)
            except ValidationError as e:
                logger.warning(f"Blocked unsafe argument at position {i}: {arg}")
                raise ValidationError(f"Unsafe argument at position {i}: {e}") from e

        logger.debug(f"Command validated: {tool} {args}")

    def validate_shell_command(self, command: str) -> None:
        """Validate a shell command string for dangerous patterns.

        This is for cases where shell=True is necessary (like bash_run tool).

        Args:
            command: Shell command string.

        Raises:
            ValidationError: If command contains dangerous patterns.
        """
        for pattern in self._compiled_patterns:
            if pattern.search(command):
                logger.warning(f"Blocked dangerous shell pattern: {pattern.pattern}")
                raise ValidationError(
                    f"Command blocked: contains dangerous pattern '{pattern.pattern}'. "
                    f"Command: {command[:100]}"
                )

        logger.debug(f"Shell command validated: {command[:100]}")

    def sanitize_path(self, path: str, must_exist: bool = False) -> Path:
        """Sanitize and validate a file path.

        Args:
            path: File path to sanitize.
            must_exist: If True, path must exist.

        Returns:
            Validated Path object.

        Raises:
            ValidationError: If path is invalid or unsafe.
        """
        if not path or not isinstance(path, str):
            raise ValidationError(f"Invalid path: {path!r}")

        # Check for null bytes
        if "\x00" in path:
            raise ValidationError("Path contains null byte")

        # Convert to Path object
        try:
            path_obj = Path(path)
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid path format: {e}") from e

        # Resolve to absolute path to detect traversal
        try:
            resolved = path_obj.resolve()
        except (OSError, RuntimeError) as e:
            raise ValidationError(f"Cannot resolve path: {e}") from e

        # Check for path traversal attempts
        # If the resolved path doesn't start with the original path's anchor,
        # it might be trying to escape
        if ".." in path:
            # Allow .. only if it doesn't escape the working directory
            cwd = Path.cwd().resolve()

            # Check if resolved path is under cwd
            try:
                resolved.relative_to(cwd)
                # Path is under cwd, allow it
                logger.debug(f"Path within working directory: {resolved}")
            except ValueError:
                # Path is not under cwd, check if it's under AMBERHOME
                amber_home = os.environ.get("AMBERHOME")
                if amber_home:
                    amber_path = Path(amber_home).resolve()
                    try:
                        resolved.relative_to(amber_path)
                        # Path is under AMBERHOME, allow it
                        logger.debug(f"Path under AMBERHOME allowed: {resolved}")
                    except ValueError:
                        # Path is neither under cwd nor AMBERHOME
                        logger.warning(f"Blocked path traversal attempt: {path} -> {resolved}")
                        raise ValidationError(
                            f"Path traversal detected: {path} resolves outside working directory"
                        )
                else:
                    # No AMBERHOME, path must be under cwd
                    logger.warning(f"Blocked path traversal attempt: {path} -> {resolved}")
                    raise ValidationError(
                        f"Path traversal detected: {path} resolves outside working directory"
                    )

        # Check existence if required
        if must_exist and not resolved.exists():
            raise ValidationError(f"Path does not exist: {resolved}")

        logger.debug(f"Path validated: {path} -> {resolved}")
        return resolved

    def sanitize_argument(self, arg: str, allow_paths: bool = False) -> str:
        """Sanitize a command argument.

        Args:
            arg: Argument to sanitize.
            allow_paths: If True, allow path-like arguments (but still block dangerous chars).

        Returns:
            Sanitized argument (may be quoted).

        Raises:
            ValidationError: If argument contains dangerous characters.
        """
        if not isinstance(arg, str):
            raise ValidationError(f"Argument must be string, got {type(arg)}")

        # Check for null bytes
        if "\x00" in arg:
            raise ValidationError("Argument contains null byte")

        # Check for shell metacharacters
        dangerous_chars = SHELL_METACHARACTERS & set(arg)
        if dangerous_chars:
            # If allow_paths, only / is allowed (Unix path separator)
            # Backslash is still dangerous as it's an escape character
            if allow_paths and dangerous_chars == {"/"}:
                # Only has forward slash, likely a path
                try:
                    self.sanitize_path(arg, must_exist=False)
                    # If valid path, quote it for safety
                    return shlex.quote(arg)
                except ValidationError:
                    # Not a valid path, but only has forward slash - allow it
                    return shlex.quote(arg)

            logger.warning(f"Blocked argument with shell metacharacters: {arg}")
            raise ValidationError(
                f"Argument contains dangerous characters: {dangerous_chars}. "
                f"Argument: {arg[:100]}"
            )

        return arg

    def is_whitelisted_tool(self, tool: str) -> bool:
        """Check if a tool is in the whitelist.

        Args:
            tool: Tool name or path.

        Returns:
            True if tool is whitelisted.
        """
        # Extract basename if it's a path
        tool_name = Path(tool).name

        # Check exact match
        if tool_name in self.allowed_tools:
            return True

        # Check without extension
        tool_base = tool_name.split(".")[0]
        if tool_base in self.allowed_tools:
            return True

        return False


# Module-level convenience functions
_default_validator = CommandValidator()


def validate_command(tool: str, args: list[str]) -> None:
    """Validate a command using the default validator.

    Args:
        tool: Tool/executable name.
        args: Command arguments as list.

    Raises:
        ValidationError: If command is unsafe.
    """
    _default_validator.validate_command(tool, args)


def validate_shell_command(command: str) -> None:
    """Validate a shell command using the default validator.

    Args:
        command: Shell command string.

    Raises:
        ValidationError: If command contains dangerous patterns.
    """
    _default_validator.validate_shell_command(command)


def sanitize_path(path: str, must_exist: bool = False) -> Path:
    """Sanitize a file path using the default validator.

    Args:
        path: File path to sanitize.
        must_exist: If True, path must exist.

    Returns:
        Validated Path object.

    Raises:
        ValidationError: If path is invalid or unsafe.
    """
    return _default_validator.sanitize_path(path, must_exist=must_exist)


def sanitize_argument(arg: str, allow_paths: bool = False) -> str:
    """Sanitize a command argument using the default validator.

    Args:
        arg: Argument to sanitize.
        allow_paths: If True, allow path-like arguments.

    Returns:
        Sanitized argument.

    Raises:
        ValidationError: If argument contains dangerous characters.
    """
    return _default_validator.sanitize_argument(arg, allow_paths=allow_paths)


def validate_tool_name(tool: str) -> bool:
    """Check if a tool is whitelisted using the default validator.

    Args:
        tool: Tool name or path.

    Returns:
        True if tool is whitelisted.
    """
    return _default_validator.is_whitelisted_tool(tool)


__all__ = [
    "CommandValidator",
    "ValidationError",
    "sanitize_argument",
    "sanitize_path",
    "validate_command",
    "validate_shell_command",
    "validate_tool_name",
]
