"""SkillLoader — reads and caches SKILL.md files for progressive disclosure.

SKILL.md files contain YAML frontmatter (L1 metadata) and a Markdown body
(L2 instructions). SkillLoader resolves their paths relative to the
``tools/builtin/`` package directory, parses them via the existing
``_parse_frontmatter`` helper, and caches the results for fast repeated
access.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from mdpilot.agent.skills import _parse_frontmatter

logger = logging.getLogger(__name__)

# Base directory: the ``tools/builtin/`` package folder.
_BUILTIN_DIR = Path(__file__).resolve().parent / "builtin"


class SkillLoader:
    """Reads and caches SKILL.md content for progressive disclosure.

    Class-level cache means all ToolRegistry / ToolDispatcher instances
    share the same parsed data without redundant file reads.
    """

    _cache: dict[str, tuple[dict[str, Any], str]] = {}

    @classmethod
    def _resolve_path(cls, skill_guide: str) -> Path:
        """Resolve a relative skill_guide path to an absolute Path.

        Args:
            skill_guide: Relative path from the ``builtin/`` directory,
                e.g. ``"amber/pmemd_cuda.md"``.

        Returns:
            Absolute ``Path`` to the SKILL.md file.
        """
        return _BUILTIN_DIR / skill_guide

    @classmethod
    def _load(cls, skill_guide: str) -> tuple[dict[str, Any], str] | None:
        """Load and cache a SKILL.md file.

        Returns:
            A ``(frontmatter_dict, body_string)`` tuple, or ``None`` if the
            file cannot be read.
        """
        if skill_guide in cls._cache:
            return cls._cache[skill_guide]

        path = cls._resolve_path(skill_guide)

        if not path.is_file():
            logger.warning("SkillLoader: file not found: %s", path)
            return None

        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("SkillLoader: cannot read %s: %s", path, exc)
            return None

        if not text.strip():
            logger.warning("SkillLoader: empty file: %s", path)
            return None

        frontmatter, body = _parse_frontmatter(text)
        cls._cache[skill_guide] = (frontmatter, body)
        return (frontmatter, body)

    @classmethod
    def load_l1(cls, skill_guide: str) -> dict[str, Any]:
        """Parse and return L1 metadata (YAML frontmatter dict).

        Args:
            skill_guide: Relative path from ``builtin/`` directory.

        Returns:
            Frontmatter dictionary. Empty dict if file is missing or
            unparseable.
        """
        result = cls._load(skill_guide)
        if result is None:
            return {}
        return result[0]

    @classmethod
    def load_l2(cls, skill_guide: str) -> str:
        """Parse and return L2 instructions (Markdown body).

        Args:
            skill_guide: Relative path from ``builtin/`` directory.

        Returns:
            Body string. Empty string if file is missing or unparseable.
        """
        result = cls._load(skill_guide)
        if result is None:
            return ""
        return result[1]

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the class-level cache (useful for testing)."""
        cls._cache.clear()
