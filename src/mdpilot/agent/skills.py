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
    Supports simple key: value, inline lists [a, b], and multi-line
    list-of-dicts blocks (e.g. ``tools:`` with ``  - name: x, node: y``).
    """
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    yaml_text = parts[1].strip()
    content = parts[2].strip()

    meta: dict = {}
    current_list_key: str | None = None
    current_list: list[dict] = []

    for line in yaml_text.splitlines():
        stripped = line.strip()

        # Detect list-of-dicts block header (e.g. "tools:")
        if stripped.endswith(":") and not stripped.startswith("-"):
            if current_list_key and current_list:
                meta[current_list_key] = current_list
            current_list_key = stripped.rstrip(":").strip()
            current_list = []
            continue

        # Parse list item (e.g. "  - name: pdb4amber, node: lab03, exec: ...")
        if stripped.startswith("- ") and current_list_key:
            item_str = stripped[2:].strip()
            item: dict = {}
            if ":" in item_str:
                for part in item_str.split(","):
                    part = part.strip()
                    if ":" in part:
                        k, _, v = part.partition(":")
                        item[k.strip()] = v.strip().strip('"').strip("'")
            if item:
                current_list.append(item)
            continue

        # Non-list line: flush any active list block
        if current_list_key:
            if current_list:
                meta[current_list_key] = current_list
            current_list_key = None
            current_list = []

        # Simple key: value (including inline lists)
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                if value.startswith("[") and value.endswith("]"):
                    items = [v.strip().strip('"').strip("'") for v in value[1:-1].split(",")]
                    meta[key] = [i for i in items if i]
                else:
                    meta[key] = value

    # Flush final list block
    if current_list_key and current_list:
        meta[current_list_key] = current_list

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


@dataclass
class SkillMeta:
    """L1 metadata for a skill — always loaded at startup."""

    name: str
    title: str
    description: str
    tags: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    source: str = "user"
    file_path: Path | None = None
    category: str = ""
    command: str = ""
    tools: list[dict] = field(default_factory=list)
    _l2_cache: str | None = field(default=None, repr=False)

    def matches(self, query: str) -> float:
        """Score relevance using keyword overlap."""
        query_lower = query.lower()
        query_words = set(re.findall(r"\w+", query_lower))

        trigger_words: set[str] = set()
        for t in self.triggers:
            trigger_words.update(re.findall(r"\w+", t.lower()))

        if trigger_words & query_words:
            overlap = len(trigger_words & query_words) / max(len(trigger_words), 1)
            return min(1.0, 0.5 + overlap)

        tag_words: set[str] = set()
        for t in self.tags:
            tag_words.update(re.findall(r"\w+", t.lower()))

        tag_overlap = tag_words & query_words
        if tag_overlap:
            return 0.3 + 0.2 * len(tag_overlap) / max(len(tag_words), 1)

        title_words = set(re.findall(r"\w+", self.title.lower()))
        title_overlap = title_words & query_words
        if title_overlap:
            return 0.2 + 0.1 * len(title_overlap) / max(len(title_words), 1)

        desc_words = set(re.findall(r"\w+", self.description.lower()[:300]))
        desc_overlap = desc_words & query_words
        if desc_overlap:
            return 0.1 * len(desc_overlap) / max(len(desc_words), 1)

        return 0.0


class UnifiedSkillRegistry:
    """Unified skill registry with L1/L2 progressive disclosure.

    Merges builtin skills (from tools/builtin/) and user skills
    (from .mdpilot/skills/). Only loads L1 metadata at startup;
    L2 content is loaded on demand via ``load_l2()``.
    """

    def __init__(self) -> None:
        self._skills: dict[str, SkillMeta] = {}

    def discover_all(self, extra_dirs: list[Path] | None = None) -> int:
        """Scan builtin + user + extra directories for L1 metadata.

        Returns the total number of skills registered.
        """
        count = 0

        # Source 1: builtin directory (same path as SkillLoader)
        builtin_dir = Path(__file__).resolve().parent.parent / "tools" / "builtin"
        if builtin_dir.is_dir():
            count += self._scan_dir(builtin_dir, source="builtin")

        # Source 1.5: src/mdpilot/skills/ (user-facing slash commands)
        skills_dir = Path(__file__).resolve().parent.parent / "skills"
        if skills_dir.is_dir():
            count += self._scan_dir(skills_dir, source="skill")

        # Source 2: project-level .mdpilot/skills/
        project_skills = Path.cwd() / ".mdpilot" / "skills"
        if project_skills.is_dir():
            count += self._scan_dir(project_skills, source="user")

        # Source 3: user-level ~/.mdpilot/skills/
        user_skills = Path.home() / ".mdpilot" / "skills"
        if user_skills.is_dir():
            count += self._scan_dir(user_skills, source="user")

        # Source 4: extra directories (for testing or plugin injection)
        for d in (extra_dirs or []):
            d = Path(d)
            if d.is_dir():
                count += self._scan_dir(d, source="user")

        return count

    def _scan_dir(self, directory: Path, source: str) -> int:
        count = 0
        for md_file in sorted(directory.rglob("*.md")):
            try:
                meta = self._load_l1(md_file, source)
                if meta:
                    # First registration wins (builtin takes priority)
                    if meta.name not in self._skills:
                        self._skills[meta.name] = meta
                    count += 1
            except Exception:
                continue
        return count

    def _load_l1(self, path: Path, source: str) -> SkillMeta | None:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return None

        meta_dict, content = _parse_frontmatter(text)
        title = meta_dict.get("title", "") or _extract_title(content)
        description = meta_dict.get("description", "")
        name = path.stem.lower().replace(" ", "-")

        tags = meta_dict.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]

        triggers = meta_dict.get("triggers", [])
        if isinstance(triggers, str):
            triggers = [t.strip() for t in triggers.split(",")]

        category = meta_dict.get("category", "")
        command = meta_dict.get("command", "")
        tools = meta_dict.get("tools", [])
        if not isinstance(tools, list):
            tools = []

        return SkillMeta(
            name=name,
            title=title,
            description=description,
            tags=tags,
            triggers=triggers,
            source=source,
            file_path=path,
            category=category,
            command=command,
            tools=tools,
        )

    def list_skills(self) -> list[SkillMeta]:
        return sorted(self._skills.values(), key=lambda s: s.name)

    def get(self, name: str) -> SkillMeta | None:
        return self._skills.get(name)

    def load_l2(self, name: str) -> str | None:
        """Load full L2 content for a skill (cached after first load)."""
        meta = self._skills.get(name)
        if meta is None:
            return None
        if meta._l2_cache is not None:
            return meta._l2_cache
        if meta.file_path is None or not meta.file_path.is_file():
            return None
        try:
            text = meta.file_path.read_text(encoding="utf-8")
            _, body = _parse_frontmatter(text)
            meta._l2_cache = body
            return body
        except Exception:
            return None

    def search(self, query: str, top_k: int = 3, min_score: float = 0.1) -> list[tuple[SkillMeta, float]]:
        scored: list[tuple[SkillMeta, float]] = []
        for skill in self._skills.values():
            score = skill.matches(query)
            if score >= min_score:
                scored.append((skill, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def build_context(
        self,
        query: str,
        active_skills: list[str] | None = None,
        max_chars: int = 4000,
    ) -> str:
        """Build context string from active + auto-matched skills."""
        parts: list[str] = []
        total = 0
        active_names = set(active_skills or [])
        loaded_names: set[str] = set()

        # Priority 1: active skills (forced injection)
        if active_names:
            active_parts: list[str] = []
            for name in active_names:
                l2 = self.load_l2(name)
                meta = self.get(name)
                if l2 and meta:
                    section = f"### {meta.title}\n\n{l2}\n\n"
                    if total + len(section) > max_chars:
                        remaining = max_chars - total
                        if remaining > 200:
                            section = section[:remaining] + "\n...(truncated)\n\n"
                        else:
                            break
                    active_parts.append(section)
                    total += len(section)
                    loaded_names.add(name)
            if active_parts:
                parts.append("## Active Skills\n\n" + "".join(active_parts))

        # Priority 2: auto-matched skills (skip already-loaded)
        matches = self.search(query, top_k=3, min_score=0.1)
        auto_parts: list[str] = []
        for skill, score in matches:
            if skill.name in loaded_names:
                continue
            l2 = self.load_l2(skill.name)
            if not l2:
                continue
            section = f"### {skill.title}\n\n{l2}\n\n"
            if total + len(section) > max_chars:
                remaining = max_chars - total
                if remaining > 200:
                    section = section[:remaining] + "\n...(truncated)\n\n"
                else:
                    break
            auto_parts.append(section)
            total += len(section)
            loaded_names.add(skill.name)

        if auto_parts:
            parts.append("## Auto-matched Skills\n\n" + "".join(auto_parts))

        if not parts:
            return ""

        return "# Relevant Knowledge\n\n" + "\n".join(parts)

    @property
    def count(self) -> int:
        return len(self._skills)
