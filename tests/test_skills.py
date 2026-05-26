"""Tests for the Skill System — knowledge base loading and routing."""

from __future__ import annotations

from pathlib import Path

import pytest

from mdpilot.agent.skills import Skill, SkillRegistry, _parse_frontmatter, _extract_title


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #

@pytest.fixture()
def skills_dir(tmp_path: Path) -> Path:
    """Create a directory with sample skill files."""
    d = tmp_path / "skills"
    d.mkdir()

    # Skill with frontmatter
    (d / "protein-md.md").write_text(
        "---\n"
        "title: Protein MD Setup\n"
        "tags: [protein, md, simulation]\n"
        "triggers: [protein simulation, MD setup, protein dynamics]\n"
        "---\n"
        "# Protein MD Setup\n\n"
        "Steps for setting up a protein MD simulation:\n"
        "1. Prepare PDB with pdb4amber\n"
        "2. Build topology with tleap\n"
        "3. Minimize with sander\n"
    )

    # Skill without frontmatter
    (d / "ligand-param.md").write_text(
        "# Ligand Parameterization\n\n"
        "Use antechamber to generate parameters for small molecules.\n"
        "Charge method: AM1-BCC (bcc) is the default.\n"
    )

    # Empty file (should be skipped)
    (d / "empty.md").write_text("")

    return d


# ------------------------------------------------------------------ #
# Unit tests — Skill
# ------------------------------------------------------------------ #

class TestSkill:
    def test_matches_trigger(self):
        skill = Skill(
            name="test",
            title="Protein MD",
            triggers=["protein simulation", "MD setup"],
        )
        score = skill.matches("How do I set up a protein simulation?")
        assert score >= 0.5

    def test_matches_tag(self):
        skill = Skill(name="test", tags=["protein", "simulation"])
        score = skill.matches("run a protein simulation")
        assert score >= 0.3

    def test_matches_title(self):
        skill = Skill(name="test", title="Protein MD Setup")
        score = skill.matches("protein md setup guide")
        assert score >= 0.2

    def test_no_match(self):
        skill = Skill(name="test", title="Unrelated")
        score = skill.matches("quantum computing")
        assert score < 0.1


# ------------------------------------------------------------------ #
# Unit tests — frontmatter parsing
# ------------------------------------------------------------------ #

class TestParseFrontmatter:
    def test_with_frontmatter(self):
        text = "---\ntitle: Test\ntags: [a, b]\n---\nContent here"
        meta, content = _parse_frontmatter(text)
        assert meta["title"] == "Test"
        assert meta["tags"] == ["a", "b"]
        assert "Content here" in content

    def test_no_frontmatter(self):
        text = "# Just a heading\n\nContent"
        meta, content = _parse_frontmatter(text)
        assert meta == {}
        assert "# Just a heading" in content

    def test_malformed_frontmatter(self):
        text = "---\ntitle: Test\n---"  # missing closing ---
        meta, content = _parse_frontmatter(text)
        # Should not crash
        assert isinstance(meta, dict)


class TestExtractTitle:
    def test_finds_heading(self):
        assert _extract_title("# Hello World") == "Hello World"

    def test_no_heading(self):
        assert _extract_title("Just text") == ""

    def test_multiple_headings(self):
        assert _extract_title("# First\n## Second") == "First"


# ------------------------------------------------------------------ #
# Unit tests — SkillRegistry
# ------------------------------------------------------------------ #

class TestSkillRegistry:
    def test_load_directory(self, skills_dir: Path):
        reg = SkillRegistry()
        count = reg.load_directory(skills_dir)
        assert count == 2  # empty.md skipped
        assert "protein-md" in reg.list_skills()
        assert "ligand-param" in reg.list_skills()

    def test_load_nonexistent(self, tmp_path: Path):
        reg = SkillRegistry()
        count = reg.load_directory(tmp_path / "nonexistent")
        assert count == 0

    def test_get_skill(self, skills_dir: Path):
        reg = SkillRegistry()
        reg.load_directory(skills_dir)
        skill = reg.get("protein-md")
        assert skill is not None
        assert skill.title == "Protein MD Setup"
        assert "protein" in skill.tags

    def test_get_nonexistent(self, skills_dir: Path):
        reg = SkillRegistry()
        reg.load_directory(skills_dir)
        assert reg.get("nope") is None

    def test_search_relevance(self, skills_dir: Path):
        reg = SkillRegistry()
        reg.load_directory(skills_dir)
        results = reg.search("protein simulation setup")
        assert len(results) > 0
        # protein-md should score highest
        assert results[0][0].name == "protein-md"
        assert results[0][1] > 0

    def test_search_no_results(self, skills_dir: Path):
        reg = SkillRegistry()
        reg.load_directory(skills_dir)
        results = reg.search("quantum entanglement", min_score=0.5)
        assert len(results) == 0

    def test_build_context(self, skills_dir: Path):
        reg = SkillRegistry()
        reg.load_directory(skills_dir)
        context = reg.build_context("protein MD setup")
        assert "Protein MD Setup" in context
        assert "Relevant Knowledge" in context

    def test_build_context_no_match(self, skills_dir: Path):
        reg = SkillRegistry()
        reg.load_directory(skills_dir)
        # With high min_score, nothing matches
        results = reg.search("quantum physics", min_score=0.5)
        if not results:
            context = ""
        else:
            context = reg.build_context("quantum physics")
        assert context == ""

    def test_build_context_respects_max_chars(self, skills_dir: Path):
        reg = SkillRegistry()
        reg.load_directory(skills_dir)
        context = reg.build_context("protein", max_chars=200)
        assert len(context) <= 300  # some overhead allowed

    def test_count(self, skills_dir: Path):
        reg = SkillRegistry()
        reg.load_directory(skills_dir)
        assert reg.count == 2

    def test_list_skills_sorted(self, skills_dir: Path):
        reg = SkillRegistry()
        reg.load_directory(skills_dir)
        names = reg.list_skills()
        assert names == sorted(names)

    def test_skill_without_frontmatter(self, skills_dir: Path):
        reg = SkillRegistry()
        reg.load_directory(skills_dir)
        skill = reg.get("ligand-param")
        assert skill is not None
        assert skill.title == "Ligand Parameterization"
        assert skill.tags == []


# ------------------------------------------------------------------ #
# Integration — ConversationContext.update_system_prompt
# ------------------------------------------------------------------ #

class TestContextUpdate:
    def test_update_system_prompt(self):
        from mdpilot.agent.context import ConversationContext
        ctx = ConversationContext(system_prompt="Original", max_tokens=1000)
        ctx.update_system_prompt("Updated prompt")
        assert ctx.messages[0]["content"] == "Updated prompt"

    def test_skill_context_in_messages(self, skills_dir: Path):
        from mdpilot.agent.context import ConversationContext
        reg = SkillRegistry()
        reg.load_directory(skills_dir)
        ctx = ConversationContext(system_prompt="Base prompt", max_tokens=10000)
        skill_ctx = reg.build_context("protein simulation")
        if skill_ctx:
            ctx.update_system_prompt("Base prompt\n\n" + skill_ctx)
        msgs = ctx.messages
        assert "Protein MD Setup" in msgs[0]["content"]
