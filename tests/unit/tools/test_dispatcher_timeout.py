"""Tests for ToolDispatcher timeout integration."""

import asyncio

import pytest

from mdpilot.agent.events import EventEmitter
from mdpilot.agent.timeout_manager import TimeoutManager
from mdpilot.config.schema import TimeoutConfig
from mdpilot.tools.decorator import tool
from mdpilot.tools.dispatcher import ToolDispatcher
from mdpilot.tools.registry import ToolRegistry
from mdpilot.types import ToolCall


@pytest.fixture
def registry():
    """Create a tool registry with test tools."""
    reg = ToolRegistry()
    
    @tool(name="fast_tool", description="Fast tool", category="test")
    def fast_tool():
        return "fast"
    
    @tool(name="slow_tool", description="Slow tool", category="test")
    def slow_tool():
        import time
        time.sleep(2)
        return "slow"
    
    @tool(name="async_fast_tool", description="Async fast tool", category="test")
    async def async_fast_tool():
        await asyncio.sleep(0.01)
        return "async_fast"
    
    @tool(name="async_slow_tool", description="Async slow tool", category="test")
    async def async_slow_tool():
        await asyncio.sleep(10)
        return "async_slow"
    
    reg.register(fast_tool)
    reg.register(slow_tool)
    reg.register(async_fast_tool)
    reg.register(async_slow_tool)
    
    return reg


@pytest.fixture
def events():
    return EventEmitter()


class TestDispatcherTimeoutInit:
    """Test ToolDispatcher accepts timeout_manager parameter."""

    def test_dispatcher_accepts_timeout_manager(self, registry, events):
        """Test that ToolDispatcher accepts timeout_manager parameter."""
        config = TimeoutConfig(default_timeout_sec=1)
        timeout_manager = TimeoutManager(config, registry, events)
        
        dispatcher = ToolDispatcher(registry, timeout_manager=timeout_manager)
        
        assert dispatcher._timeout_manager is timeout_manager

    def test_dispatcher_works_without_timeout_manager(self, registry):
        """Test backward compatibility - dispatcher works without timeout_manager."""
        dispatcher = ToolDispatcher(registry)
        
        assert dispatcher._timeout_manager is None


class TestDispatcherTimeoutExecution:
    """Test timeout enforcement for tools."""

    @pytest.mark.asyncio
    async def test_tool_completes_within_timeout(self, registry, events):
        """Test tool completes within timeout."""
        config = TimeoutConfig(default_timeout_sec=5)
        timeout_manager = TimeoutManager(config, registry, events)
        dispatcher = ToolDispatcher(registry, timeout_manager=timeout_manager)
        
        call = ToolCall(id="test1", name="fast_tool", arguments={})
        output = await dispatcher.execute(call)
        
        assert output.success
        assert output.output == "fast"

    @pytest.mark.asyncio
    async def test_tool_exceeds_timeout(self, registry, events):
        """Test tool exceeds timeout."""
        config = TimeoutConfig(by_tool={"slow_tool": 1})
        timeout_manager = TimeoutManager(config, registry, events)
        dispatcher = ToolDispatcher(registry, timeout_manager=timeout_manager)
        
        call = ToolCall(id="test2", name="slow_tool", arguments={})
        output = await dispatcher.execute(call)
        
        assert not output.success
        assert "timeout" in output.error.lower()
        assert output.error_code == "TIMEOUT"
        assert output.error_category == "timeout"

    @pytest.mark.asyncio
    async def test_tool_without_timeout_manager(self, registry):
        """Test tool without timeout manager (backward compat)."""
        dispatcher = ToolDispatcher(registry, timeout_manager=None)
        
        call = ToolCall(id="test3", name="fast_tool", arguments={})
        output = await dispatcher.execute(call)
        
        assert output.success
        assert output.output == "fast"
