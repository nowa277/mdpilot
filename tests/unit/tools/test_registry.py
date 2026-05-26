"""Comprehensive tests for ToolRegistry."""

import pytest
import logging
from unittest.mock import Mock, patch
from mdpilot.tools.registry import ToolRegistry
from mdpilot.types import ToolMeta


class TestRegistryInit:
    """Test registry initialization."""
    
    def test_init_empty(self):
        registry = ToolRegistry()
        assert len(registry._tools) == 0
        assert registry.list_tools() == []


class TestRegistryRegister:
    """Test tool registration."""
    
    def test_register_valid_tool(self):
        def my_tool(x: int) -> str:
            return str(x)
        my_tool._tool_meta = ToolMeta(
            name="my_tool",
            description="Test tool",
            parameters={"type": "object", "properties": {"x": {"type": "integer"}}}
        )
        
        registry = ToolRegistry()
        registry.register(my_tool)
        
        assert "my_tool" in registry._tools
        assert registry.get("my_tool") is not None
    
    def test_register_non_callable_raises(self):
        registry = ToolRegistry()
        with pytest.raises(ValueError, match="non-callable"):
            registry.register("not_a_function")
    
    def test_register_without_meta_raises(self):
        def no_meta_tool():
            pass
        
        registry = ToolRegistry()
        with pytest.raises(ValueError, match="not decorated with @tool"):
            registry.register(no_meta_tool)
    
    def test_register_empty_name_raises(self):
        def empty_name_tool():
            pass
        empty_name_tool._tool_meta = ToolMeta(
            name="",
            description="Tool with empty name",
            parameters={}
        )
        
        registry = ToolRegistry()
        with pytest.raises(ValueError, match="empty name"):
            registry.register(empty_name_tool)
    
    def test_register_duplicate_warns(self, caplog):
        def tool1():
            pass
        tool1._tool_meta = ToolMeta(name="duplicate", description="First", parameters={})
        
        def tool2():
            pass
        tool2._tool_meta = ToolMeta(name="duplicate", description="Second", parameters={})
        
        registry = ToolRegistry()
        registry.register(tool1)
        registry.register(tool2)
        
        # Second registration should overwrite
        assert registry.get("duplicate")[0].description == "Second"
        assert "already registered" in caplog.text


class TestRegistryGet:
    """Test tool lookup."""
    
    def test_get_existing_tool(self):
        def my_tool():
            return "result"
        my_tool._tool_meta = ToolMeta(name="my_tool", description="Test", parameters={})
        
        registry = ToolRegistry()
        registry.register(my_tool)
        
        meta, fn = registry.get("my_tool")
        assert meta.name == "my_tool"
        assert fn() == "result"
    
    def test_get_nonexistent_returns_none(self):
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None


class TestRegistryListTools:
    """Test tool listing."""
    
    def test_list_tools_empty(self):
        registry = ToolRegistry()
        assert registry.list_tools() == []
    
    def test_list_tools_sorted(self):
        def tool_c():
            pass
        tool_c._tool_meta = ToolMeta(name="tool_c", description="C", parameters={})
        
        def tool_a():
            pass
        tool_a._tool_meta = ToolMeta(name="tool_a", description="A", parameters={})
        
        def tool_b():
            pass
        tool_b._tool_meta = ToolMeta(name="tool_b", description="B", parameters={})
        
        registry = ToolRegistry()
        registry.register(tool_c)
        registry.register(tool_a)
        registry.register(tool_b)
        
        assert registry.list_tools() == ["tool_a", "tool_b", "tool_c"]


class TestRegistrySchemas:
    """Test OpenAI schema generation."""
    
    def test_schemas_empty(self):
        registry = ToolRegistry()
        assert registry.schemas() == []
    
    def test_schemas_format(self):
        def my_tool(x: int, y: str) -> str:
            return f"{x}-{y}"
        my_tool._tool_meta = ToolMeta(
            name="my_tool",
            description="Test tool",
            parameters={
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "string"}
                },
                "required": ["x", "y"]
            }
        )
        
        registry = ToolRegistry()
        registry.register(my_tool)
        
        schemas = registry.schemas()
        assert len(schemas) == 1
        assert schemas[0]["type"] == "function"
        assert schemas[0]["function"]["name"] == "my_tool"
        assert schemas[0]["function"]["description"] == "Test tool"
        assert "properties" in schemas[0]["function"]["parameters"]
        assert "x" in schemas[0]["function"]["parameters"]["properties"]


class TestRegistryAutoDiscover:
    """Test auto-discovery."""
    
    def test_auto_discover_invalid_package(self, caplog):
        registry = ToolRegistry()
        registry.auto_discover("nonexistent.package")
        
        assert "Failed to import package" in caplog.text
        assert len(registry._tools) == 0
    
    def test_auto_discover_builtin_tools(self):
        registry = ToolRegistry()
        registry.auto_discover("mdpilot.tools.builtin")
        
        # Should discover at least some tools
        tools = registry.list_tools()
        assert len(tools) > 0
        assert any("bash" in t or "file" in t for t in tools)
    
    def test_auto_discover_module_import_error(self, tmp_path, caplog):
        """Test that module import errors are logged but don't stop discovery."""
        module_file = tmp_path / "bad_module.py"
        module_file.write_text("# empty module")
        
        registry = ToolRegistry()
        
        with patch('mdpilot.tools.registry.importlib.import_module') as mock_import:
            mock_package = Mock()
            mock_package.__path__ = [str(tmp_path)]
            
            def import_side_effect(name):
                if name == "test.package":
                    return mock_package
                elif name == "test.package.bad_module":
                    raise ImportError("Module error")
                return Mock()
            
            mock_import.side_effect = import_side_effect
            
            with caplog.at_level(logging.WARNING):
                registry.auto_discover("test.package")
            
            assert "Failed to import module" in caplog.text
            assert "test.package.bad_module" in caplog.text
    
    def test_auto_discover_registration_error(self, tmp_path, caplog):
        """Test that registration errors are logged but don't stop discovery."""
        module_file = tmp_path / "good_module.py"
        module_file.write_text("# empty module")
        
        registry = ToolRegistry()
        
        with patch('mdpilot.tools.registry.importlib.import_module') as mock_import:
            mock_package = Mock()
            mock_package.__path__ = [str(tmp_path)]
            
            mock_tool = Mock()
            mock_tool._tool_meta = ToolMeta(name="", description="Empty name", parameters={})
            
            mock_module = Mock()
            mock_module.bad_tool = mock_tool
            
            def import_side_effect(name):
                if name == "test.package":
                    return mock_package
                elif name == "test.package.good_module":
                    return mock_module
                return Mock()
            
            mock_import.side_effect = import_side_effect
            
            with patch('builtins.dir', return_value=['bad_tool']):
                with caplog.at_level(logging.WARNING):
                    registry.auto_discover("test.package")
                
                assert "Failed to register" in caplog.text
    
    @patch('mdpilot.tools.registry.importlib.import_module')
    def test_auto_discover_no_path_attribute(self, mock_import, caplog):
        # Package without __path__
        mock_package = Mock(spec=[])
        del mock_package.__path__
        mock_import.return_value = mock_package
        
        registry = ToolRegistry()
        registry.auto_discover("test.package")
        
        assert "no __path__" in caplog.text


class TestRegistrySkillEnhancement:
    """Test L1 skill metadata enhancement during registration."""

    def test_description_enhanced_with_l1_metadata(self):
        """Registry should append L1 metadata to description when skill_guide is set."""
        from mdpilot.tools.skill_loader import SkillLoader

        SkillLoader.clear_cache()

        # Seed the cache directly so we don't need a real file
        SkillLoader._cache["amber/pmemd_cuda.md"] = (
            {
                "name": "pmemd_cuda",
                "node": "lab03",
                "exec_method": "local_subprocess",
                "depends_on": ["tleap"],
                "triggers": ["pmemd", "MD simulation"],
            },
            "Body content here",
        )

        def my_tool():
            pass
        my_tool._tool_meta = ToolMeta(
            name="pmemd_cuda",
            description="GPU-accelerated MD simulation",
            parameters={},
            skill_guide="amber/pmemd_cuda.md",
        )

        registry = ToolRegistry()
        registry.register(my_tool)

        meta, _ = registry.get("pmemd_cuda")
        assert "node=lab03" in meta.description
        assert "exec=local_subprocess" in meta.description
        assert "depends_on=tleap" in meta.description
        assert "triggers=pmemd,MD simulation" in meta.description

        SkillLoader.clear_cache()

    def test_description_unchanged_when_no_skill_guide(self):
        """Registry should not modify description when skill_guide is None."""
        def my_tool():
            pass
        my_tool._tool_meta = ToolMeta(
            name="plain_tool",
            description="Plain description",
            parameters={},
        )

        registry = ToolRegistry()
        registry.register(my_tool)

        meta, _ = registry.get("plain_tool")
        assert meta.description == "Plain description"

    def test_description_unchanged_when_skill_file_missing(self):
        """Registry should leave description unchanged if SKILL.md is missing."""
        from mdpilot.tools.skill_loader import SkillLoader

        SkillLoader.clear_cache()

        def my_tool():
            pass
        my_tool._tool_meta = ToolMeta(
            name="missing_skill_tool",
            description="Original description",
            parameters={},
            skill_guide="nonexistent/skill.md",
        )

        registry = ToolRegistry()
        registry.register(my_tool)

        meta, _ = registry.get("missing_skill_tool")
        assert meta.description == "Original description"

        SkillLoader.clear_cache()

    def test_description_unchanged_when_l1_empty(self):
        """Registry should not modify description if L1 frontmatter is empty."""
        from mdpilot.tools.skill_loader import SkillLoader

        SkillLoader.clear_cache()

        SkillLoader._cache["empty.md"] = ({}, "Body only")

        def my_tool():
            pass
        my_tool._tool_meta = ToolMeta(
            name="empty_skill_tool",
            description="Original",
            parameters={},
            skill_guide="empty.md",
        )

        registry = ToolRegistry()
        registry.register(my_tool)

        meta, _ = registry.get("empty_skill_tool")
        assert meta.description == "Original"

        SkillLoader.clear_cache()
