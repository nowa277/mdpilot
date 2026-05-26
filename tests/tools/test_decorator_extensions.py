"""Tests for @tool decorator extensions (depends_on, resource_requirements, estimated_duration_sec)."""

from mdpilot.tools.decorator import tool
from mdpilot.types import ToolMeta


def test_tool_decorator_accepts_depends_on():
    """@tool decorator should accept depends_on parameter."""
    @tool(
        name="test_tool",
        description="Test",
        depends_on=["other_tool"]
    )
    def my_tool():
        return "result"

    meta: ToolMeta = my_tool._tool_meta
    assert meta.depends_on == ["other_tool"]


def test_tool_decorator_accepts_resource_requirements():
    """@tool decorator should accept resource_requirements parameter."""
    @tool(
        name="test_tool",
        description="Test",
        resource_requirements={"cpu_cores": 4, "memory_mb": 2048, "gpu": False}
    )
    def my_tool():
        return "result"

    meta: ToolMeta = my_tool._tool_meta
    assert meta.resource_requirements == {"cpu_cores": 4, "memory_mb": 2048, "gpu": False}


def test_tool_decorator_accepts_estimated_duration():
    """@tool decorator should accept estimated_duration_sec parameter."""
    @tool(
        name="test_tool",
        description="Test",
        estimated_duration_sec=300
    )
    def my_tool():
        return "result"

    meta: ToolMeta = my_tool._tool_meta
    assert meta.estimated_duration_sec == 300


def test_tool_decorator_defaults_for_new_fields():
    """@tool decorator should use defaults for new fields when not provided."""
    @tool(
        name="test_tool",
        description="Test"
    )
    def my_tool():
        return "result"

    meta: ToolMeta = my_tool._tool_meta
    assert meta.depends_on == []
    assert meta.resource_requirements == {}
    assert meta.estimated_duration_sec is None


def test_tool_decorator_accepts_skill_guide():
    """@tool decorator should accept skill_guide parameter."""
    @tool(
        name="test_tool",
        description="Test",
        skill_guide="amber/pmemd_cuda.md"
    )
    def my_tool():
        return "result"

    meta: ToolMeta = my_tool._tool_meta
    assert meta.skill_guide == "amber/pmemd_cuda.md"


def test_tool_decorator_skill_guide_default_none():
    """@tool decorator should default skill_guide to None."""
    @tool(
        name="test_tool",
        description="Test"
    )
    def my_tool():
        return "result"

    meta: ToolMeta = my_tool._tool_meta
    assert meta.skill_guide is None


def test_tool_decorator_skill_guide_with_all_params():
    """@tool decorator should accept skill_guide alongside all other parameters."""
    @tool(
        name="pmemd_cuda",
        description="GPU MD simulation",
        category="amber",
        depends_on=["tleap"],
        resource_requirements={"gpu": True},
        estimated_duration_sec=3600,
        skill_guide="amber/pmemd_cuda.md"
    )
    def run_md(input_file: str) -> str:
        return input_file

    meta: ToolMeta = run_md._tool_meta
    assert meta.skill_guide == "amber/pmemd_cuda.md"
    assert meta.category == "amber"
    assert meta.depends_on == ["tleap"]
    assert meta.resource_requirements == {"gpu": True}
    assert meta.estimated_duration_sec == 3600
