"""Comprehensive tests for ToolDispatcher."""

import pytest
from unittest.mock import AsyncMock, Mock
from mdpilot.tools.dispatcher import ToolDispatcher, ToolValidationError
from mdpilot.tools.registry import ToolRegistry
from mdpilot.tools.file_context import FileContext
from mdpilot.types import ToolCall, ToolMeta


@pytest.fixture
def registry():
    """Create a registry with test tools."""
    reg = ToolRegistry()
    
    # Simple sync tool
    def simple_tool(text: str) -> str:
        return f"Result: {text}"
    simple_tool._tool_meta = ToolMeta(
        name="simple_tool",
        description="A simple test tool",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"]
        }
    )
    reg.register(simple_tool)
    
    # Async tool
    async def async_tool(value: int) -> str:
        return f"Async result: {value}"
    async_tool._tool_meta = ToolMeta(
        name="async_tool",
        description="An async test tool",
        parameters={
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"]
        }
    )
    reg.register(async_tool)
    
    # Tool that returns error string
    def error_tool() -> str:
        return "Error: Something went wrong"
    error_tool._tool_meta = ToolMeta(
        name="error_tool",
        description="Tool that returns error",
        parameters={"type": "object", "properties": {}}
    )
    reg.register(error_tool)
    
    # Tool with optional params
    def optional_tool(required: str, optional: str = "default") -> str:
        return f"{required}-{optional}"
    optional_tool._tool_meta = ToolMeta(
        name="optional_tool",
        description="Tool with optional params",
        parameters={
            "type": "object",
            "properties": {
                "required": {"type": "string"},
                "optional": {"type": "string"}
            },
            "required": ["required"]
        }
    )
    reg.register(optional_tool)
    
    # Tool with array parameter
    def array_tool(items: list) -> str:
        return f"Items: {len(items)}"
    array_tool._tool_meta = ToolMeta(
        name="array_tool",
        description="Tool with array param",
        parameters={
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["items"]
        }
    )
    reg.register(array_tool)
    
    return reg


@pytest.fixture
def dispatcher(registry):
    """Create a dispatcher with test registry."""
    return ToolDispatcher(registry)


class TestDispatcherInit:
    """Test dispatcher initialization."""
    
    def test_init_with_registry(self, registry):
        dispatcher = ToolDispatcher(registry)
        assert dispatcher._registry is registry
        assert isinstance(dispatcher._file_context, FileContext)
        assert dispatcher._timeout_manager is None
    
    def test_init_with_file_context(self, registry):
        ctx = FileContext()
        dispatcher = ToolDispatcher(registry, file_context=ctx)
        assert dispatcher._file_context is ctx
    
    def test_init_with_timeout_manager(self, registry):
        timeout_mgr = Mock()
        dispatcher = ToolDispatcher(registry, timeout_manager=timeout_mgr)
        assert dispatcher._timeout_manager is timeout_mgr


class TestDispatcherExecuteBasic:
    """Test basic tool execution."""
    
    @pytest.mark.asyncio
    async def test_execute_sync_tool(self, dispatcher):
        call = ToolCall(id="1", name="simple_tool", arguments={"text": "hello"})
        output = await dispatcher.execute(call)
        
        assert output.success is True
        assert output.output == "Result: hello"
        assert output.error is None
    
    @pytest.mark.asyncio
    async def test_execute_async_tool(self, dispatcher):
        call = ToolCall(id="2", name="async_tool", arguments={"value": 42})
        output = await dispatcher.execute(call)
        
        assert output.success is True
        assert output.output == "Async result: 42"
    
    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self, dispatcher):
        call = ToolCall(id="3", name="nonexistent", arguments={})
        output = await dispatcher.execute(call)
        
        assert output.success is False
        assert "not found" in output.error
        assert "Available tools:" in output.error


class TestDispatcherValidation:
    """Test argument validation."""
    
    @pytest.mark.asyncio
    async def test_missing_required_argument(self, dispatcher):
        call = ToolCall(id="4", name="simple_tool", arguments={})
        output = await dispatcher.execute(call)
        
        assert output.success is False
        assert "Missing required argument: text" in output.error
    
    @pytest.mark.asyncio
    async def test_wrong_argument_type(self, dispatcher):
        call = ToolCall(id="5", name="async_tool", arguments={"value": "not_an_int"})
        output = await dispatcher.execute(call)
        
        assert output.success is False
        assert "must be of type integer" in output.error
    
    @pytest.mark.asyncio
    async def test_optional_argument_omitted(self, dispatcher):
        call = ToolCall(id="6", name="optional_tool", arguments={"required": "test"})
        output = await dispatcher.execute(call)
        
        assert output.success is True
        assert output.output == "test-default"
    
    @pytest.mark.asyncio
    async def test_optional_argument_provided(self, dispatcher):
        call = ToolCall(id="7", name="optional_tool", arguments={"required": "test", "optional": "custom"})
        output = await dispatcher.execute(call)
        
        assert output.success is True
        assert output.output == "test-custom"
    
    @pytest.mark.asyncio
    async def test_array_validation_correct_type(self, dispatcher):
        call = ToolCall(id="8", name="array_tool", arguments={"items": ["a", "b", "c"]})
        output = await dispatcher.execute(call)
        
        assert output.success is True
        assert output.output == "Items: 3"
    
    @pytest.mark.asyncio
    async def test_array_validation_wrong_item_type(self, dispatcher):
        call = ToolCall(id="9", name="array_tool", arguments={"items": ["a", 123, "c"]})
        output = await dispatcher.execute(call)
        
        assert output.success is False
        assert "Array item[1]" in output.error


class TestDispatcherErrorHandling:
    """Test error handling and classification."""
    
    @pytest.mark.asyncio
    async def test_tool_returns_error_string(self, dispatcher):
        call = ToolCall(id="10", name="error_tool", arguments={})
        output = await dispatcher.execute(call)
        
        assert output.success is False
        assert "Error: Something went wrong" in output.error
    
    @pytest.mark.asyncio
    async def test_tool_raises_exception(self, registry):
        def failing_tool() -> str:
            raise ValueError("Tool failed")
        failing_tool._tool_meta = ToolMeta(
            name="failing_tool",
            description="Tool that raises",
            parameters={"type": "object", "properties": {}}
        )
        registry.register(failing_tool)
        
        dispatcher = ToolDispatcher(registry)
        call = ToolCall(id="11", name="failing_tool", arguments={})
        output = await dispatcher.execute(call)
        
        assert output.success is False
        assert "ValueError: Tool failed" in output.error


class TestDispatcherFileContext:
    """Test file context tracking."""
    
    @pytest.mark.asyncio
    async def test_tracks_trajectory_from_output_text(self, registry):
        def traj_tool() -> str:
            return "Simulation complete [trajectory: output.nc]"
        traj_tool._tool_meta = ToolMeta(
            name="traj_tool",
            description="Tool that outputs trajectory",
            parameters={"type": "object", "properties": {}}
        )
        registry.register(traj_tool)
        
        ctx = FileContext()
        dispatcher = ToolDispatcher(registry, file_context=ctx)
        
        call = ToolCall(id="12", name="traj_tool", arguments={})
        await dispatcher.execute(call)
        
        # Check internal file tracking (path may be absolute)
        assert len(ctx._files) > 0
        assert any("output.nc" in f.path for f in ctx._files)
    
    @pytest.mark.asyncio
    async def test_pdb4amber_infers_output(self, registry):
        def pdb4amber(input_pdb: str) -> str:
            return "Cleaned PDB"
        pdb4amber._tool_meta = ToolMeta(
            name="pdb4amber",
            description="PDB cleaner",
            parameters={
                "type": "object",
                "properties": {"input_pdb": {"type": "string"}},
                "required": ["input_pdb"]
            }
        )
        registry.register(pdb4amber)
        
        ctx = FileContext()
        dispatcher = ToolDispatcher(registry, file_context=ctx)
        
        call = ToolCall(id="13", name="pdb4amber", arguments={"input_pdb": "protein.pdb"})
        await dispatcher.execute(call)
        
        assert len(ctx._files) > 0
        assert any("protein_clean.pdb" in f.path for f in ctx._files)
    
    @pytest.mark.asyncio
    async def test_tleap_infers_topology_files(self, registry):
        def tleap(workdir: str = ".") -> str:
            return "Topology created"
        tleap._tool_meta = ToolMeta(
            name="tleap",
            description="Topology builder",
            parameters={
                "type": "object",
                "properties": {"workdir": {"type": "string"}},
            }
        )
        registry.register(tleap)
        
        ctx = FileContext()
        dispatcher = ToolDispatcher(registry, file_context=ctx)
        
        call = ToolCall(id="14", name="tleap", arguments={"workdir": "/tmp"})
        await dispatcher.execute(call)
        
        assert len(ctx._files) >= 2
        assert any("system.prmtop" in f.path for f in ctx._files)
        assert any("system.inpcrd" in f.path for f in ctx._files)


class TestDispatcherTimeout:
    """Test timeout handling."""
    
    @pytest.mark.asyncio
    async def test_timeout_enforced(self, registry):
        async def slow_tool() -> str:
            import asyncio
            await asyncio.sleep(10)
            return "Done"
        slow_tool._tool_meta = ToolMeta(
            name="slow_tool",
            description="Slow tool",
            parameters={"type": "object", "properties": {}}
        )
        registry.register(slow_tool)
        
        timeout_mgr = Mock()
        timeout_mgr.resolve_timeout.return_value = 0.1
        timeout_mgr.enforce_timeout = AsyncMock(side_effect=TimeoutError("Tool timed out after 0.1s"))
        
        dispatcher = ToolDispatcher(registry, timeout_manager=timeout_mgr)
        call = ToolCall(id="15", name="slow_tool", arguments={})
        output = await dispatcher.execute(call)
        
        assert output.success is False
        assert "timed out" in output.error
        assert output.error_code == "TIMEOUT"
        assert output.error_category == "timeout"
    
    @pytest.mark.asyncio
    async def test_no_timeout_when_none_configured(self, registry):
        async def fast_tool() -> str:
            return "Quick"
        fast_tool._tool_meta = ToolMeta(
            name="fast_tool",
            description="Fast tool",
            parameters={"type": "object", "properties": {}}
        )
        registry.register(fast_tool)
        
        timeout_mgr = Mock()
        timeout_mgr.resolve_timeout.return_value = None
        
        dispatcher = ToolDispatcher(registry, timeout_manager=timeout_mgr)
        call = ToolCall(id="16", name="fast_tool", arguments={})
        output = await dispatcher.execute(call)
        
        assert output.success is True
        assert output.output == "Quick"


class TestDispatcherSkillContext:
    """Test L2 skill context storage and retrieval."""

    @pytest.mark.asyncio
    async def test_stores_l2_context_on_execute(self, registry):
        """Dispatcher should store L2 content in _pending_skill_context."""
        from mdpilot.tools.skill_loader import SkillLoader

        SkillLoader.clear_cache()
        SkillLoader._cache["test/tool.md"] = (
            {"name": "skill_tool"},
            "## Detailed instructions\n\nStep 1: Do X\nStep 2: Do Y",
        )

        def skill_tool(msg: str) -> str:
            return f"done: {msg}"

        skill_tool._tool_meta = ToolMeta(
            name="skill_tool",
            description="A tool with skill guide",
            parameters={
                "type": "object",
                "properties": {"msg": {"type": "string"}},
                "required": ["msg"],
            },
            skill_guide="test/tool.md",
        )
        registry.register(skill_tool)

        dispatcher = ToolDispatcher(registry)
        call = ToolCall(id="s1", name="skill_tool", arguments={"msg": "hello"})
        output = await dispatcher.execute(call)

        assert output.success is True
        assert output.output == "done: hello"

        # L2 should be stored and retrievable via pop_skill_context
        l2 = dispatcher.pop_skill_context("skill_tool")
        assert l2 is not None
        assert "## Detailed instructions" in l2
        assert "Step 1: Do X" in l2

        # pop should remove it
        assert dispatcher.pop_skill_context("skill_tool") is None

        SkillLoader.clear_cache()

    @pytest.mark.asyncio
    async def test_no_context_when_no_skill_guide(self, registry):
        """Dispatcher should not store context for tools without skill_guide."""
        dispatcher = ToolDispatcher(registry)
        call = ToolCall(id="s2", name="simple_tool", arguments={"text": "hello"})
        await dispatcher.execute(call)

        assert dispatcher.pop_skill_context("simple_tool") is None

    @pytest.mark.asyncio
    async def test_no_context_when_skill_file_missing(self, registry):
        """Dispatcher should not crash when skill file is missing."""
        from mdpilot.tools.skill_loader import SkillLoader

        SkillLoader.clear_cache()

        def missing_skill_tool(msg: str) -> str:
            return f"ok: {msg}"

        missing_skill_tool._tool_meta = ToolMeta(
            name="missing_skill_tool",
            description="Tool with missing skill guide",
            parameters={
                "type": "object",
                "properties": {"msg": {"type": "string"}},
                "required": ["msg"],
            },
            skill_guide="nonexistent.md",
        )
        registry.register(missing_skill_tool)

        dispatcher = ToolDispatcher(registry)
        call = ToolCall(id="s3", name="missing_skill_tool", arguments={"msg": "test"})
        output = await dispatcher.execute(call)

        assert output.success is True
        assert output.output == "ok: test"
        assert dispatcher.pop_skill_context("missing_skill_tool") is None

        SkillLoader.clear_cache()
