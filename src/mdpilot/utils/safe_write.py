"""Safe concurrent write utilities for multi-agent environments.

Prevents race conditions when multiple agents write to the same
__init__.py or other shared files simultaneously.
"""

from __future__ import annotations

import fcntl
import tempfile
from pathlib import Path
from typing import Any


def safe_write_init_py(
    init_path: Path,
    imports: list[str] | None = None,
    all_exports: list[str] | None = None,
    extra_content: str = "",
) -> None:
    """Safely write or update an ``__init__.py`` file with file locking.

    Uses ``fcntl.flock`` for process-level mutual exclusion. Reads the
    existing content, merges imports and ``__all__`` lists, then writes
    back atomically via a temp file + rename.

    Args:
        init_path: Path to the __init__.py file.
        imports: List of import lines to ensure are present.
        all_exports: List of names to ensure in ``__all__``.
        extra_content: Additional content to append (deduped).
    """
    init_path = Path(init_path)
    init_path.parent.mkdir(parents=True, exist_ok=True)

    # Build desired imports set
    desired_imports = set(imports or [])
    desired_all = set(all_exports or [])

    # Read existing content under lock
    existing_imports: set[str] = set()
    existing_all: set[str] = set()
    existing_lines: list[str] = []
    header_lines: list[str] = []
    in_header = True
    in_docstring = False

    lock_path = init_path.with_suffix(".lock")

    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            if init_path.exists():
                content = init_path.read_text()
                for line in content.splitlines():
                    stripped = line.strip()

                    # Track docstrings (only at file start)
                    if in_header and not in_docstring:
                        if stripped.startswith('"""'):
                            header_lines.append(line)
                            if stripped.count('"""') >= 2 and len(stripped) > 3:
                                # Single-line docstring: """text"""
                                in_header = False
                            else:
                                in_docstring = True
                            continue
                        elif stripped.startswith("'''"):
                            header_lines.append(line)
                            if stripped.count("'''") >= 2 and len(stripped) > 3:
                                in_header = False
                            else:
                                in_docstring = True
                            continue
                        elif stripped == "" or stripped.startswith("#"):
                            header_lines.append(line)
                            continue
                        else:
                            # Not a docstring/comment — end header
                            in_header = False

                    if in_docstring:
                        header_lines.append(line)
                        if '"""' in stripped or "'''" in stripped:
                            in_docstring = False
                            in_header = False
                        continue

                    # Parse import lines
                    if stripped.startswith("from ") or stripped.startswith("import "):
                        existing_imports.add(stripped)
                        continue

                    # Parse __all__
                    if stripped.startswith("__all__"):
                        # Extract names from __all__ = ["...", "..."]
                        names = _parse_all_list(stripped)
                        existing_all.update(names)
                        continue

                    existing_lines.append(line)

            # Merge
            merged_imports = existing_imports | desired_imports
            merged_all = existing_all | desired_all

            # Build output
            parts: list[str] = []

            # Header (docstring/comments)
            if header_lines:
                parts.extend(header_lines)
                parts.append("")

            # Imports (sorted for determinism)
            for imp in sorted(merged_imports):
                parts.append(imp)
            if merged_imports:
                parts.append("")

            # __all__
            if merged_all:
                names_str = ", ".join(f'"{n}"' for n in sorted(merged_all))
                parts.append(f"__all__ = [{names_str}]")
                parts.append("")

            # Extra content
            if extra_content and extra_content.strip():
                parts.append(extra_content.strip())
                parts.append("")

            # Remaining existing content (cleaned up)
            # Remove trailing blank lines
            while existing_lines and not existing_lines[-1].strip():
                existing_lines.pop()
            if existing_lines:
                parts.extend(existing_lines)
                parts.append("")

            # Write atomically via temp file
            output = "\n".join(parts)
            if not output.endswith("\n"):
                output += "\n"

            fd, tmp_path = tempfile.mkstemp(
                dir=str(init_path.parent),
                prefix=".init_",
                suffix=".tmp",
            )
            try:
                with open(fd, "w") as f:
                    f.write(output)
                Path(tmp_path).rename(init_path)
            except Exception:
                Path(tmp_path).unlink(missing_ok=True)
                raise

        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    # Clean up lock file
    try:
        lock_path.unlink()
    except OSError:
        pass


def _parse_all_list(line: str) -> set[str]:
    """Extract names from a ``__all__ = [...]`` line."""
    names: set[str] = set()
    # Find content between [ and ]
    start = line.find("[")
    end = line.rfind("]")
    if start == -1 or end == -1:
        return names
    inner = line[start + 1:end]
    for item in inner.split(","):
        item = item.strip().strip("\"'")
        if item:
            names.add(item)
    return names
