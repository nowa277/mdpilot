"""End-to-end integration tests for timeout system."""

import asyncio

import pytest

from mdpilot.agent.events import EventEmitter
from mdpilot.agent.timeout_manager import TimeoutManager
from mdpilot.config.schema import TimeoutConfig
from mdpilot.tools.decorator import tool
from mdpilot.tools.dispatcher import ToolDispatcher
from mdpilot.tools.registry import ToolRegistry


@pytest.fixture
def registry():
    """Create a tool registry with test tools."""
    reg = ToolRegistry()
    
    @tool(name="fast_tool", description="Fast tool", category="test")
    def fast_tool():
        return "fast"
    
    @tool(name="medium_tool", description="Medium tool", category="medium_category")
    async def medium_tool():
        await asyncio.sleep(0.5)
        return "medium"
    
    @tool(name="slow_tool", description="Slow tool", category="slow_category")
    async def slow_tool():
        await asyncio.sleep(10)
        return "slow"
    
    reg.register(fast_tool)
    reg.register(medium_tool)
    reg.register(slow_tool)
    
    return reg


@pytest.fixture
def events():
    return EventEmitter()


class TestTimeoutE2E:
    """End-to-end tests for the complete timeout system."""

    @pytest.mark.asyncio
    async def test_tool_specific_overrides_category(self, registry, events):
        """Test that tool-specific timeout overrides category timeout."""
        config = TimeoutConfig(
            default_timeout_sec=100,
            by_category={"slow_category": 50},
            by_tool={"slow_tool": 1}
        )
        
        timeout_manager = TimeoutManager(config, registry, events)
        dispatcher = ToolDispatcher(registry, timeout_manager=timeout_manager)
        
        from mdpilot.types import ToolCall
        call = ToolCall(id="test1", name="slow_tool", arguments={})
        output = await dispatcher.execute(call)
        
        assert not output.success
        assert output.error_code == "TIMEOUT"

    @pytest.mark.asyncio
    async def test_category_overrides_global_default(self, registry, events):
        """Test that category timeout overrides global default."""
        config = TimeoutConfig(
            default_timeout_sec=100,
            by_category={"slow_category": 1}
        )
        
        timeout_manager = TimeoutManager(config, registry, events)
        dispatcher = ToolDispatcher(registry, timeout_manager=timeout_manager)
        
        from mdpilot.types import ToolCall
        call = ToolCall(id="test2", name="slow_tool", arguments={})
        output = await dispatcher.execute(call)
        
        assert not output.success
        assert output.error_code == "TIMEOUT"

    @pytest.mark.asyncio
    async def test_global_default_used_as_fallback(self, registry, events):
        """Test that global default is used when no specific config."""
        config = TimeoutConfig(default_timeout_sec=1)
        
        timeout_manager = TimeoutManager(config, registry, events)
        dispatcher = ToolDispatcher(registry, timeout_manager=timeout_manager)
        
        from mdpilot.types import ToolCall
        call = ToolCall(id="test3", name="slow_tool", arguments={})
        output = await dispatcher.execute(call)
        
        assert not output.success
        assert output.error_code == "TIMEOUT"

    @pytest.mark.asyncio
    async def test_no_timeout_when_unconfigured(self, registry, events):
        """Test that no timeout is applied when unconfigured."""
        config = TimeoutConfig()
        
        timeout_manager = TimeoutManager(config, registry, events)
        dispatcher = ToolDispatcher(registry, timeout_manager=timeout_manager)
        
        from mdpilot.types import ToolCall
        call = ToolCall(id="test4", name="fast_tool", arguments={})
        output = await dispatcher.execute(call)
        
        assert output.success
        assert output.output == "fast"

    @pytest.mark.asyncio
    async def test_warning_event_emitted(self, registry, events):
        """Test that warning event is emitted at threshold."""
        config = TimeoutConfig(
            by_tool={"medium_tool": 1},
            warning_threshold=0.3
        )
        
        warning_events = []
        events.on("tool.timeout_warning", lambda event: warning_events.append(event.data))
        
        timeout_manager = TimeoutManager(config, registry, events)
        dispatcher = ToolDispatcher(registry, timeout_manager=timeout_manager)
        
        from mdpilot.types import ToolCall
        call = ToolCall(id="test5", name="medium_tool", arguments={})
        output = await dispatcher.execute(call)
        
        assert output.success
        assert len(warning_events) == 1
        assert warning_events[0]["tool_name"] == "medium_tool"

    @pytest.mark.asyncio
    async def test_timeout_event_emitted(self, registry, events):
        """Test that timeout event is emitted on timeout."""
        config = TimeoutConfig(by_tool={"slow_tool": 1})
        
        timeout_events = []
        events.on("tool.timeout", lambda event: timeout_events.append(event.data))
        
        timeout_manager = TimeoutManager(config, registry, events)
        dispatcher = ToolDispatcher(registry, timeout_manager=timeout_manager)
        
        from mdpilot.types import ToolCall
        call = ToolCall(id="test6", name="slow_tool", arguments={})
        output = await dispatcher.execute(call)
        
        assert not output.success
        assert len(timeout_events) == 1
        assert timeout_events[0]["tool_name"] == "slow_tool"
        assert timeout_events[0]["timeout_sec"] == 1

    @pytest.mark.asyncio
    async def test_backward_compatibility_no_timeout_manager(self, registry):
        """Test backward compatibility - dispatcher works without timeout_manager."""
        dispatcher = ToolDispatcher(registry, timeout_manager=None)
        
        from mdpilot.types import ToolCall
        call = ToolCall(id="test7", name="fast_tool", arguments={})
        output = await dispatcher.execute(call)
        
        assert output.success
        assert output.output == "fast"

    @pytest.mark.asyncio
    async def test_multiple_tools_different_timeouts(self, registry, events):
        """Test multiple tools with different timeout configurations."""
        config = TimeoutConfig(
            default_timeout_sec=100,
            by_category={"medium_category": 2},
            by_tool={"slow_tool": 1}
        )
        
        timeout_manager = TimeoutManager(config, registry, events)
        dispatcher = ToolDispatcher(registry, timeout_manager=timeout_manager)
        
        from mdpilot.types import ToolCall
        
        # Fast tool - no timeout
        call1 = ToolCall(id="t1", name="fast_tool", arguments={})
        output1 = await dispatcher.execute(call1)
        assert output1.success
        
        # Medium tool - category timeout (2s, should pass)
        call2 = ToolCall(id="t2", name="medium_tool", arguments={})
        output2 = await dispatcher.execute(call2)
        assert output2.success
        
        # Slow tool - tool-specific timeout (1s, should fail)
        call3 = ToolCall(id="t3", name="slow_tool", arguments={})
        output3 = await dispatcher.execute(call3)
        assert not output3.success
        assert output3.error_code == "TIMEOUT"
