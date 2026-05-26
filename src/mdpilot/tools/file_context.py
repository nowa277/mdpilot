"""File chain context — tracks files produced by wizard/tool execution steps.

Provides the "pipeline awareness" that lets a wizard's file_picker step
recommend outputs from a previous step (e.g. pdb4amber → tleap).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FileEntry:
    """A file produced or consumed during a wizard/tool execution."""

    path: str
    produced_by: str  # tool name that created it
    step: str         # step name within the wizard
    file_type: str    # pdb / prmtop / inpcrd / mol2 / frcmod / nc / out / rst / dat / other
    size_bytes: int = 0

    @property
    def name(self) -> str:
        return Path(self.path).name

    @property
    def exists(self) -> bool:
        return Path(self.path).exists()


class FileContext:
    """Tracks the chain of files produced by tool executions.

    Used by the wizard system to recommend the most likely input file
    for a file_picker step based on what the previous tool produced.
    """

    def __init__(self) -> None:
        self._files: list[FileEntry] = []

    def add_file(
        self,
        path: str,
        produced_by: str,
        step: str,
        file_type: str = "other",
    ) -> None:
        """Register a file as produced by a tool step."""
        size = 0
        p = Path(path)
        if p.exists():
            size = p.stat().st_size

        self._files.append(FileEntry(
            path=str(p.resolve()),
            produced_by=produced_by,
            step=step,
            file_type=file_type,
            size_bytes=size,
        ))

    def get_recommended_files(
        self,
        file_type: str | None = None,
        filter_ext: str | None = None,
        after_step: str | None = None,
    ) -> list[FileEntry]:
        """Get files matching criteria, sorted by recency (newest first).

        Args:
            file_type: Filter by file type category (pdb, prmtop, etc.)
            filter_ext: Filter by extension (e.g. ".prmtop")
            after_step: Only files produced after this step
        """
        results = []
        seen_steps = after_step is None
        for entry in reversed(self._files):
            if after_step and entry.step == after_step:
                seen_steps = True
                continue
            if not seen_steps:
                continue

            if file_type and entry.file_type != file_type:
                continue
            if filter_ext and not entry.path.endswith(filter_ext):
                continue
            results.append(entry)

        return results

    def get_latest(self, file_type: str | None = None, filter_ext: str | None = None) -> FileEntry | None:
        """Get the most recent file matching criteria."""
        files = self.get_recommended_files(file_type=file_type, filter_ext=filter_ext)
        return files[0] if files else None

    def get_pipeline_summary(self) -> str:
        """Human-readable summary of the file pipeline."""
        if not self._files:
            return "(no files in pipeline)"

        lines = ["File pipeline:"]
        for i, f in enumerate(self._files, 1):
            size_str = f"{f.size_bytes / 1024:.1f} KB" if f.size_bytes else "N/A"
            lines.append(f"  {i}. [{f.produced_by}] {f.name} ({f.file_type}, {size_str})")
        return "\n".join(lines)

    @property
    def files(self) -> list[FileEntry]:
        return list(self._files)

    def clear(self) -> None:
        self._files.clear()


# ------------------------------------------------------------------ #
# File type detection from extension
# ------------------------------------------------------------------ #

_EXTENSION_MAP: dict[str, str] = {
    ".pdb": "pdb",
    ".prmtop": "prmtop",
    ".top": "prmtop",
    ".inpcrd": "inpcrd",
    ".rst": "inpcrd",
    ".rst7": "inpcrd",
    ".mol2": "mol2",
    ".frcmod": "frcmod",
    ".nc": "nc",
    ".mdcrd": "nc",
    ".out": "out",
    ".dat": "dat",
    ".crd": "inpcrd",
}

def detect_file_type(path: str) -> str:
    """Detect file type from extension."""
    suffix = Path(path).suffix.lower()
    return _EXTENSION_MAP.get(suffix, "other")
