"""Comprehensive tests for @tool decorator."""

import pytest
from typing import Optional
from mdpilot.tools.decorator import tool, _parse_args_section, _type_to_schema


class TestParseArgsSection:
    """Test docstring Args: section parsing."""
    
    def test_parse_simple_args(self):
        docstring = """
        Function description.
        
        Args:
            arg1: First argument
            arg2: Second argument
        """
        result = _parse_args_section(docstring)
        assert result == {"arg1": "First argument", "arg2": "Second argument"}
    
    def test_parse_args_with_types(self):
        docstring = """
        Args:
            arg1 (str): First argument
            arg2 (int): Second argument
        """
        result = _parse_args_section(docstring)
        assert result == {"arg1": "First argument", "arg2": "Second argument"}
    
    def test_parse_no_args_section(self):
        docstring = "Just a description"
        result = _parse_args_section(docstring)
        assert result == {}
    
    def test_parse_stops_at_returns(self):
        docstring = """
        Args:
            arg1: First argument
        
        Returns:
            Something
        """
        result = _parse_args_section(docstring)
        assert result == {"arg1": "First argument"}


class TestTypeToSchema:
    """Test Python type to JSON Schema conversion."""
    
    def test_simple_types(self):
        assert _type_to_schema(str) == {"type": "string"}
        assert _type_to_schema(int) == {"type": "integer"}
        assert _type_to_schema(float) == {"type": "number"}
        assert _type_to_schema(bool) == {"type": "boolean"}
    
    def test_optional_type(self):
        schema = _type_to_schema(Optional[str])
        assert schema["type"] == "string"
        assert schema["nullable"] is True
    
    def test_union_type_python310(self):
        # Test str | None syntax (Python 3.10+)
        import sys
        if sys.version_info >= (3, 10):
            schema = _type_to_schema(str | None)
            assert schema["type"] == "string"
            assert schema.get("nullable") is True
    
    def test_list_type(self):
        schema = _type_to_schema(list)
        assert schema["type"] == "array"
    
    
    def test_dict_type(self):
        schema = _type_to_schema(dict)
        assert schema["type"] == "object"
    
    
    def test_unknown_type_fallback(self):
        class CustomType:
            pass
        schema = _type_to_schema(CustomType)
        assert schema["type"] == "string"


class TestToolDecorator:
    """Test @tool decorator."""
    
    def test_basic_decoration(self):
        @tool(name="test_tool", description="Test tool")
        def my_func(arg1: str) -> str:
            return arg1
        
        assert hasattr(my_func, "_tool_meta")
        meta = my_func._tool_meta
        assert meta.name == "test_tool"
        assert meta.description == "Test tool"
    
    def test_parameters_from_type_hints(self):
        @tool(name="test_tool", description="Test")
        def my_func(arg1: str, arg2: int) -> str:
            return f"{arg1}-{arg2}"
        
        meta = my_func._tool_meta
        assert "arg1" in meta.parameters["properties"]
        assert "arg2" in meta.parameters["properties"]
        assert meta.parameters["properties"]["arg1"]["type"] == "string"
        assert meta.parameters["properties"]["arg2"]["type"] == "integer"
    
    def test_required_parameters(self):
        @tool(name="test_tool", description="Test")
        def my_func(required: str, optional: int = 0) -> str:
            return f"{required}-{optional}"
        
        meta = my_func._tool_meta
        assert "required" in meta.parameters["required"]
        assert "optional" not in meta.parameters["required"]
        assert meta.parameters["properties"]["optional"]["default"] == 0
    
    def test_description_from_docstring(self):
        @tool(name="test_tool", description="Test")
        def my_func(arg1: str) -> str:
            """Function description.
            
            Args:
                arg1: First argument description
            """
            return arg1
        
        meta = my_func._tool_meta
        assert meta.parameters["properties"]["arg1"]["description"] == "First argument description"
    
    def test_no_type_hint_defaults_to_string(self):
        @tool(name="test_tool", description="Test")
        def my_func(arg1):
            return arg1
        
        meta = my_func._tool_meta
        assert meta.parameters["properties"]["arg1"]["type"] == "string"
    
    def test_category_parameter(self):
        @tool(name="test_tool", description="Test", category="amber")
        def my_func() -> str:
            return "result"
        
        meta = my_func._tool_meta
        assert meta.category == "amber"
    
    def test_depends_on_parameter(self):
        @tool(name="test_tool", description="Test", depends_on=["tool1", "tool2"])
        def my_func() -> str:
            return "result"
        
        meta = my_func._tool_meta
        assert meta.depends_on == ["tool1", "tool2"]
    
    def test_resource_requirements(self):
        @tool(
            name="test_tool",
            description="Test",
            resource_requirements={"cpu_cores": 4, "memory_mb": 1024}
        )
        def my_func() -> str:
            return "result"
        
        meta = my_func._tool_meta
        assert meta.resource_requirements == {"cpu_cores": 4, "memory_mb": 1024}
    
    def test_estimated_duration(self):
        @tool(name="test_tool", description="Test", estimated_duration_sec=60)
        def my_func() -> str:
            return "result"
        
        meta = my_func._tool_meta
        assert meta.estimated_duration_sec == 60
    
    def test_function_still_callable(self):
        @tool(name="test_tool", description="Test")
        def my_func(x: int) -> int:
            return x * 2
        
        result = my_func(5)
        assert result == 10
    
    def test_no_docstring(self):
        @tool(name="test_tool", description="Test")
        def my_func(arg1: str):
            return arg1
        
        meta = my_func._tool_meta
        assert "arg1" in meta.parameters["properties"]
