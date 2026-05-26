"""Tests for AMBER workflow templates."""

from __future__ import annotations

import pytest

from mdpilot.workflows import (
    WorkflowStep,
    WorkflowTemplate,
    PROTEIN_MD,
    LIGAND_PARAMETERIZE,
    TRAJECTORY_ANALYSIS,
    BUILTIN_TEMPLATES,
    list_templates,
    get_template,
)


class TestWorkflowStep:
    def test_create_step(self):
        step = WorkflowStep(name="test", description="Test step", tool="bash_run")
        assert step.name == "test"
        assert step.tool == "bash_run"
        assert step.arguments == {}

    def test_step_with_dependencies(self):
        step = WorkflowStep(name="step2", description="Depends on 1", tool="sander", depends_on=[1])
        assert step.depends_on == [1]


class TestWorkflowTemplate:
    def test_to_plan_dict(self):
        tmpl = WorkflowTemplate(
            name="test",
            description="Test workflow",
            steps=[
                WorkflowStep(name="s1", description="Step 1", tool="bash_run"),
                WorkflowStep(name="s2", description="Step 2", tool="sander", depends_on=[1]),
            ],
        )
        plan = tmpl.to_plan_dict()
        assert plan["goal"] == "Test workflow"
        assert len(plan["steps"]) == 2
        assert plan["steps"][0]["id"] == 1
        assert plan["steps"][1]["depends_on"] == [1]


class TestBuiltinTemplates:
    def test_protein_md(self):
        assert PROTEIN_MD.name == "protein_md"
        assert len(PROTEIN_MD.steps) == 6
        assert PROTEIN_MD.category == "protein"
        assert PROTEIN_MD.steps[0].tool == "pdb4amber"
        assert PROTEIN_MD.steps[1].tool == "tleap"

    def test_protein_md_dependencies(self):
        """Each step depends on the previous one."""
        for i, step in enumerate(PROTEIN_MD.steps):
            if i > 0:
                assert i in step.depends_on, f"Step {i+1} should depend on step {i}"

    def test_ligand_parameterize(self):
        assert LIGAND_PARAMETERIZE.name == "ligand_parameterize"
        assert len(LIGAND_PARAMETERIZE.steps) == 2
        assert LIGAND_PARAMETERIZE.category == "ligand"

    def test_trajectory_analysis(self):
        assert TRAJECTORY_ANALYSIS.name == "trajectory_analysis"
        assert len(TRAJECTORY_ANALYSIS.steps) == 3
        assert TRAJECTORY_ANALYSIS.category == "analysis"

    def test_all_templates_have_required_fields(self):
        for name, tmpl in BUILTIN_TEMPLATES.items():
            assert tmpl.name
            assert tmpl.description
            assert tmpl.category
            assert len(tmpl.steps) > 0
            for step in tmpl.steps:
                assert step.tool
                assert step.description

    def test_all_tools_are_registered(self):
        """All workflow tools should be discoverable."""
        from mdpilot.tools.registry import ToolRegistry
        reg = ToolRegistry()
        reg.auto_discover("mdpilot.tools.builtin")
        available = reg.list_tools()
        for name, tmpl in BUILTIN_TEMPLATES.items():
            for step in tmpl.steps:
                assert step.tool in available, f"Tool '{step.tool}' in {name} not registered"


class TestRegistry:
    def test_list_templates(self):
        templates = list_templates()
        assert len(templates) == 3
        names = {t["name"] for t in templates}
        assert "protein_md" in names

    def test_list_templates_by_category(self):
        protein = list_templates(category="protein")
        assert len(protein) == 1
        assert protein[0]["name"] == "protein_md"

    def test_list_templates_empty_category(self):
        membrane = list_templates(category="membrane")
        assert len(membrane) == 0

    def test_get_template(self):
        tmpl = get_template("protein_md")
        assert tmpl is not None
        assert tmpl.name == "protein_md"

    def test_get_template_nonexistent(self):
        assert get_template("nonexistent") is None
