"""Skill system — load and route Markdown knowledge bases.

A Skill is a Markdown file (or directory of files) that provides domain-specific
knowledge the agent can inject into its system prompt. Skills are discovered
from a configurable directory, parsed for metadata (title, tags, trigger keywords),
and matched against user queries for automatic routing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Skill:
    """A single skill loaded from a Markdown file.

    Attributes:
        name: Skill identifier (derived from filename).
        title: Human-readable title (from YAML frontmatter or first heading).
        content: Full Markdown content.
        tags: Searchable tags for routing.
        triggers: Keywords that activate this skill.
        file_path: Original file path.
    """

    name: str
    title: str = ""
    content: str = ""
    tags: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    file_path: Path | None = None

    def matches(self, query: str) -> float:
        """Score how well this skill matches a query (0.0 - 1.0).

        Uses simple keyword overlap. Future: embedding similarity.
        """
        query_lower = query.lower()
        query_words = set(re.findall(r"\w+", query_lower))

        # Check triggers first (highest priority)
        trigger_words = set()
        for t in self.triggers:
            trigger_words.update(re.findall(r"\w+", t.lower()))

        if trigger_words & query_words:
            overlap = len(trigger_words & query_words) / max(len(trigger_words), 1)
            return min(1.0, 0.5 + overlap)

        # Check tags
        tag_words = set()
        for t in self.tags:
            tag_words.update(re.findall(r"\w+", t.lower()))

        tag_overlap = tag_words & query_words
        if tag_overlap:
            return 0.3 + 0.2 * len(tag_overlap) / max(len(tag_words), 1)

        # Check title words
        title_words = set(re.findall(r"\w+", self.title.lower()))
        title_overlap = title_words & query_words
        if title_overlap:
            return 0.2 + 0.1 * len(title_overlap) / max(len(title_words), 1)

        # Check content keywords (sample first 500 chars)
        content_sample = self.content[:500].lower()
        content_words = set(re.findall(r"\w+", content_sample))
        content_overlap = content_words & query_words
        if content_overlap:
            return 0.1 * len(content_overlap) / max(len(content_words), 1)

        return 0.0


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from a Markdown string.

    Returns (metadata_dict, remaining_content).
    """
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    yaml_text = parts[1].strip()
    content = parts[2].strip()

    meta: dict = {}
    for line in yaml_text.splitlines():
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                # Handle list values
                if value.startswith("[") and value.endswith("]"):
                    items = [v.strip().strip('"').strip("'") for v in value[1:-1].split(",")]
                    meta[key] = [i for i in items if i]
                else:
                    meta[key] = value

    return meta, content


def _extract_title(content: str) -> str:
    """Extract the first Markdown heading from content."""
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return ""


class SkillRegistry:
    """Manages discovery, loading, and routing of skills.

    Skills are loaded from a directory of Markdown files. Each file
    becomes a Skill with optional YAML frontmatter for metadata.
    """

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def load_directory(self, directory: str | Path) -> int:
        """Load all .md files from a directory as skills.

        Parameters
        ----------
        directory : str or Path
            Path to the skills directory.

        Returns
        -------
        int
            Number of skills loaded.
        """
        dir_path = Path(directory)
        if not dir_path.is_dir():
            return 0

        count = 0
        for md_file in sorted(dir_path.rglob("*.md")):
            try:
                skill = self._load_file(md_file)
                if skill:
                    self._skills[skill.name] = skill
                    count += 1
            except Exception:
                continue  # skip malformed files

        return count

    def _load_file(self, path: Path) -> Skill | None:
        """Load a single Markdown file as a skill."""
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return None

        meta, content = _parse_frontmatter(text)
        title = meta.get("title", "") or _extract_title(content)
        name = path.stem.lower().replace(" ", "-")

        tags = meta.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]

        triggers = meta.get("triggers", [])
        if isinstance(triggers, str):
            triggers = [t.strip() for t in triggers.split(",")]

        return Skill(
            name=name,
            title=title,
            content=content,
            tags=tags,
            triggers=triggers,
            file_path=path,
        )

    def get(self, name: str) -> Skill | None:
        """Look up a skill by name."""
        return self._skills.get(name)

    def list_skills(self) -> list[str]:
        """Return sorted list of skill names."""
        return sorted(self._skills.keys())

    def search(self, query: str, top_k: int = 3, min_score: float = 0.1) -> list[tuple[Skill, float]]:
        """Find skills matching a query.

        Parameters
        ----------
        query : str
            User query to match against.
        top_k : int
            Maximum number of results.
        min_score : float
            Minimum relevance score (0.0 - 1.0).

        Returns
        -------
        list of (Skill, score) tuples, sorted by score descending.
        """
        scored = []
        for skill in self._skills.values():
            score = skill.matches(query)
            if score >= min_score:
                scored.append((skill, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def build_context(self, query: str, max_chars: int = 4000) -> str:
        """Build a context string from relevant skills for a query.

        Selects the most relevant skills and concatenates their content,
        respecting the character budget.
        """
        matches = self.search(query, top_k=3, min_score=0.1)
        if not matches:
            return ""

        parts: list[str] = []
        total = 0

        for skill, score in matches:
            header = f"## Skill: {skill.title or skill.name}\n\n"
            chunk = header + skill.content + "\n\n"
            if total + len(chunk) > max_chars:
                # Truncate this skill
                remaining = max_chars - total - len(header)
                if remaining > 200:
                    chunk = header + skill.content[:remaining] + "\n...(truncated)\n\n"
                else:
                    break
            parts.append(chunk)
            total += len(chunk)

        if not parts:
            return ""

        return "# Relevant Knowledge\n\n" + "".join(parts)

    @property
    def count(self) -> int:
        """Number of loaded skills."""
        return len(self._skills)
