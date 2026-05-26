"""Tests for ToolMeta extensions: dependency and resource fields."""

from mdpilot.types import ToolMeta


def test_tool_meta_has_depends_on_field():
    """ToolMeta should have depends_on field with default empty list."""
    meta = ToolMeta(
        name="test_tool",
        description="Test",
        parameters={}
    )
    assert hasattr(meta, 'depends_on')
    assert meta.depends_on == []


def test_tool_meta_has_resource_requirements_field():
    """ToolMeta should have resource_requirements field with default empty dict."""
    meta = ToolMeta(
        name="test_tool",
        description="Test",
        parameters={}
    )
    assert hasattr(meta, 'resource_requirements')
    assert meta.resource_requirements == {}


def test_tool_meta_has_estimated_duration_field():
    """ToolMeta should have estimated_duration_sec field with default None."""
    meta = ToolMeta(
        name="test_tool",
        description="Test",
        parameters={}
    )
    assert hasattr(meta, 'estimated_duration_sec')
    assert meta.estimated_duration_sec is None


def test_tool_meta_with_all_new_fields():
    """ToolMeta should accept all new fields."""
    meta = ToolMeta(
        name="sander",
        description="Run sander",
        parameters={},
        depends_on=["tleap"],
        resource_requirements={"cpu_cores": 4, "memory_mb": 2048, "gpu": False},
        estimated_duration_sec=300
    )
    assert meta.depends_on == ["tleap"]
    assert meta.resource_requirements == {"cpu_cores": 4, "memory_mb": 2048, "gpu": False}
    assert meta.estimated_duration_sec == 300


def test_tool_meta_has_skill_guide_field():
    """ToolMeta should have skill_guide field with default None."""
    meta = ToolMeta(
        name="test_tool",
        description="Test",
        parameters={}
    )
    assert hasattr(meta, 'skill_guide')
    assert meta.skill_guide is None


def test_tool_meta_skill_guide_accepts_string():
    """ToolMeta should accept skill_guide as a string path."""
    meta = ToolMeta(
        name="pmemd_cuda",
        description="GPU MD",
        parameters={},
        skill_guide="amber/pmemd_cuda.md"
    )
    assert meta.skill_guide == "amber/pmemd_cuda.md"


def test_tool_meta_skill_guide_with_all_fields():
    """ToolMeta should accept skill_guide alongside all other fields."""
    meta = ToolMeta(
        name="sander",
        description="Run sander",
        parameters={},
        depends_on=["tleap"],
        resource_requirements={"cpu_cores": 4},
        estimated_duration_sec=300,
        skill_guide="amber/sander.md"
    )
    assert meta.skill_guide == "amber/sander.md"
    assert meta.depends_on == ["tleap"]
    assert meta.resource_requirements == {"cpu_cores": 4}
    assert meta.estimated_duration_sec == 300
