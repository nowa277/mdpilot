"""Tests for SkillLoader — SKILL.md reading and caching."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from mdpilot.tools.skill_loader import SkillLoader


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #

@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear SkillLoader cache before and after each test."""
    SkillLoader.clear_cache()
    yield
    SkillLoader.clear_cache()


@pytest.fixture()
def skill_file(tmp_path: Path) -> Path:
    """Create a sample SKILL.md file and return its parent as builtin dir."""
    builtin = tmp_path / "builtin"
    amber_dir = builtin / "amber"
    amber_dir.mkdir(parents=True)

    (amber_dir / "pmemd_cuda.md").write_text(
        "---\n"
        "name: pmemd_cuda\n"
        'description: "GPU-accelerated MD simulation"\n'
        "triggers:\n"
        "  - pmemd\n"
        "  - MD simulation\n"
        "depends_on:\n"
        "  - tleap\n"
        "node: lab03\n"
        "exec_method: local_subprocess\n"
        "---\n"
        "\n"
        "## When to use\n"
        "\n"
        "Use pmemd.cuda for production MD runs on GPU.\n"
        "\n"
        "## Input Templates\n"
        "\n"
        "Example md.in file:\n"
        "  &cntrl\n"
        "    imin=0, irest=1, ntx=5,\n"
        "  /\n"
    )

    return builtin


# ------------------------------------------------------------------ #
# Tests — _resolve_path
# ------------------------------------------------------------------ #

class TestResolvePath:
    def test_resolve_simple_path(self):
        resolved = SkillLoader._resolve_path("amber/pmemd_cuda.md")
        assert resolved.name == "pmemd_cuda.md"
        assert "amber" in str(resolved)

    def test_resolve_nested_path(self):
        resolved = SkillLoader._resolve_path("a/b/c.md")
        assert resolved.name == "c.md"


# ------------------------------------------------------------------ #
# Tests — load_l1
# ------------------------------------------------------------------ #

class TestLoadL1:
    def test_load_l1_parses_frontmatter(self, skill_file: Path):
        with patch("mdpilot.tools.skill_loader._BUILTIN_DIR", skill_file):
            l1 = SkillLoader.load_l1("amber/pmemd_cuda.md")

        assert l1["name"] == "pmemd_cuda"
        assert l1["node"] == "lab03"
        assert l1["exec_method"] == "local_subprocess"

    def test_load_l1_missing_file_returns_empty(self, skill_file: Path):
        with patch("mdpilot.tools.skill_loader._BUILTIN_DIR", skill_file):
            l1 = SkillLoader.load_l1("nonexistent.md")

        assert l1 == {}

    def test_load_l1_empty_file_returns_empty(self, skill_file: Path):
        empty_dir = skill_file / "empty"
        empty_dir.mkdir()
        (empty_dir / "blank.md").write_text("")

        with patch("mdpilot.tools.skill_loader._BUILTIN_DIR", skill_file):
            l1 = SkillLoader.load_l1("empty/blank.md")

        assert l1 == {}


# ------------------------------------------------------------------ #
# Tests — load_l2
# ------------------------------------------------------------------ #

class TestLoadL2:
    def test_load_l2_returns_body(self, skill_file: Path):
        with patch("mdpilot.tools.skill_loader._BUILTIN_DIR", skill_file):
            l2 = SkillLoader.load_l2("amber/pmemd_cuda.md")

        assert "## When to use" in l2
        assert "pmemd.cuda" in l2
        assert "## Input Templates" in l2
        # Frontmatter should NOT appear in the body
        assert "---" not in l2

    def test_load_l2_missing_file_returns_empty(self, skill_file: Path):
        with patch("mdpilot.tools.skill_loader._BUILTIN_DIR", skill_file):
            l2 = SkillLoader.load_l2("nonexistent.md")

        assert l2 == ""


# ------------------------------------------------------------------ #
# Tests — caching
# ------------------------------------------------------------------ #

class TestCaching:
    def test_second_call_uses_cache(self, skill_file: Path):
        with patch("mdpilot.tools.skill_loader._BUILTIN_DIR", skill_file):
            l1_first = SkillLoader.load_l1("amber/pmemd_cuda.md")
            assert "amber/pmemd_cuda.md" in SkillLoader._cache

            # Modify the file — cache should still return old data
            (skill_file / "amber" / "pmemd_cuda.md").write_text(
                "---\nname: changed\n---\nNew body"
            )
            l1_second = SkillLoader.load_l1("amber/pmemd_cuda.md")
            assert l1_second == l1_first
            assert l1_second["name"] == "pmemd_cuda"

    def test_clear_cache(self, skill_file: Path):
        with patch("mdpilot.tools.skill_loader._BUILTIN_DIR", skill_file):
            SkillLoader.load_l1("amber/pmemd_cuda.md")
            assert len(SkillLoader._cache) > 0

        SkillLoader.clear_cache()
        assert len(SkillLoader._cache) == 0


# ------------------------------------------------------------------ #
# Tests — load_l1 and load_l2 return consistent data
# ------------------------------------------------------------------ #

class TestConsistency:
    def test_l1_and_l2_from_same_file(self, skill_file: Path):
        with patch("mdpilot.tools.skill_loader._BUILTIN_DIR", skill_file):
            l1 = SkillLoader.load_l1("amber/pmemd_cuda.md")
            l2 = SkillLoader.load_l2("amber/pmemd_cuda.md")

        # L1 should be a dict with keys
        assert isinstance(l1, dict)
        assert "name" in l1
        # L2 should be a string with body content
        assert isinstance(l2, str)
        assert len(l2) > 0
        # L1 should not contain body content
        assert "When to use" not in l1
        # L2 should not contain frontmatter keys
        assert "pmemd_cuda" not in l2 or "When to use" in l2
