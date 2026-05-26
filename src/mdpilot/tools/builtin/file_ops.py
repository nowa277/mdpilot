"""File operations tools for mdpilot."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from mdpilot.agent.file_policy import FileAccessPolicy
from mdpilot.tools.decorator import tool

logger = logging.getLogger(__name__)

_policy = FileAccessPolicy("lab03")


@tool(
    name="file_read",
    description="Read the contents of a text file. Sensitive files (keys, tokens, etc.) are blocked.",
    category="file",
)
def file_read(path: str, offset: int = 1, limit: int = 500) -> str:
    """Read a file with optional line range.

    Args:
        path: Path to the file to read.
        offset: Starting line number (1-indexed). Default 1.
        limit: Maximum number of lines to read. Default 500.

    Returns:
        The file contents as a string, or an error message.
    """
    try:
        if not _policy.can_read(path):
            logger.warning(f"FileAccessPolicy blocked read: {path}")
            return f"Error: Access denied by policy: {path}"
        p = Path(path).resolve()
        if not p.exists():
         return f"Error: File not found: {path}"
        if not p.is_file():
          return f"Error: Not a regular file: {path}"

        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        start = max(0, offset - 1)
        end = start + limit
        selected = lines[start:end]

        result = "".join(selected)
        if end < len(lines):
            result += f"\n... (showing lines {offset}-{end} of {len(lines)})"
        return result
    except Exception as exc:
        return f"Error reading {path}: {exc}"


@tool(
    category="file",
    name="file_write",
    description="Write content to a file, creating directories as needed. Restricted to changshengjie directory.",
)
def file_write(path: str, content: str) -> str:
    """Write content to a file.

    Args:
      path: Destination file path (must be within changshengjie directory).
      content: The text content to write.

    Returns:
        Success message or error description.
    """
    try:
        if not _policy.can_write(path):
            logger.warning(f"FileAccessPolicy blocked write: {path}")
            return f"Error: Write access denied by policy: {path}"
        p = Path(path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} bytes to {path}"
    except Exception as exc:
        return f"Error writing {path}: {exc}"


@tool(
    name="file_search",
    description="Search for files matching a glob pattern.",
    category="file",
)
def file_search(pattern: str, directory: str = ".") -> str:
    """Search for files matching a glob pattern.

    Args:
        pattern: Glob pattern to match (e.g., '*.pdb', '**/*.py').
        directory: Directory to search in. Default is current directory.

    Returns:
        Newline-separated list of matching file paths.
    """
    try:
        base = Path(directory).resolve()
        if not base.exists():
            return f"Error: Directory not found: {directory}"

        matches = sorted(str(p) for p in base.glob(pattern))
        if not matches:
            return f"No files matching '{pattern}' in {directory}"
        return "\n".join(matches[:100])
    except Exception as exc:
        return f"Error searching: {exc}"
