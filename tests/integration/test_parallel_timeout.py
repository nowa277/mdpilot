"""Integration tests for timeout in parallel execution."""

import asyncio

import pytest

from mdpilot.agent.events import EventEmitter
from mdpilot.agent.parallel_executor import ExecutionConfig, ParallelExecutor
from mdpilot.agent.timeout_manager import TimeoutManager
from mdpilot.config.schema import TimeoutConfig
from mdpilot.tools.decorator import tool
from mdpilot.tools.dispatcher import ToolDispatcher
from mdpilot.tools.registry import ToolRegistry


@pytest.fixture
def registry():
    """Create a tool registry with test tools."""
    reg = ToolRegistry()
    
    @tool(name="fast_tool_1", description="Fast tool 1", category="test")
    async def fast_tool_1():
        await asyncio.sleep(0.01)
        return "fast_1"
    
    @tool(name="fast_tool_2", description="Fast tool 2", category="test")
    async def fast_tool_2():
        await asyncio.sleep(0.01)
        return "fast_2"
    
    @tool(name="slow_tool", description="Slow tool", category="test")
    async def slow_tool():
        await asyncio.sleep(10)
        return "slow"
    
    reg.register(fast_tool_1)
    reg.register(fast_tool_2)
    reg.register(slow_tool)
    
    return reg


@pytest.fixture
def events():
    return EventEmitter()


class TestParallelTimeout:
    """Test timeout behavior in parallel execution."""

    @pytest.mark.asyncio
    async def test_independent_tools_timeout_independently(self, registry, events):
        """Test that independent tools timeout independently."""
        config = TimeoutConfig(
            by_tool={"slow_tool": 1, "fast_tool_1": 5, "fast_tool_2": 5}
        )
        timeout_manager = TimeoutManager(config, registry, events)
        dispatcher = ToolDispatcher(registry, timeout_manager=timeout_manager)
        
        exec_config = ExecutionConfig(max_concurrent_tools=3, enable_parallel=True)
        executor = ParallelExecutor(dispatcher, registry, exec_config, events)
        
        tools = [
            ("fast_tool_1", "Fast 1", {}),
            ("slow_tool", "Slow", {}),
            ("fast_tool_2", "Fast 2", {})
        ]
        
        results = await executor.execute_parallel(tools)

        assert len(results) == 3
        
        # Find results by tool name
        results_by_name = {r.tool_call.name: r for r in results}
        
        assert results_by_name["fast_tool_1"].output.success
        assert results_by_name["fast_tool_1"].output.output == "fast_1"
        assert not results_by_name["slow_tool"].output.success
        assert "timeout" in results_by_name["slow_tool"].output.error.lower()
        assert results_by_name["fast_tool_2"].output.success
        assert results_by_name["fast_tool_2"].output.output == "fast_2"

    @pytest.mark.asyncio
    async def test_timeout_in_one_tool_doesnt_affect_others(self, registry, events):
        """Test that timeout in one tool doesn't affect others."""
        config = TimeoutConfig(by_tool={"slow_tool": 1})
        timeout_manager = TimeoutManager(config, registry, events)
        dispatcher = ToolDispatcher(registry, timeout_manager=timeout_manager)
        
        exec_config = ExecutionConfig(max_concurrent_tools=3, enable_parallel=True)
        executor = ParallelExecutor(dispatcher, registry, exec_config, events)
        
        tools = [
            ("fast_tool_1", "Fast 1", {}),
            ("slow_tool", "Slow", {}),
            ("fast_tool_2", "Fast 2", {})
        ]
        
        results = await executor.execute_parallel(tools)
        
        success_count = sum(1 for r in results if r.output.success)
        assert success_count == 2

    @pytest.mark.asyncio
    async def test_wave_continues_after_timeout(self, registry, events):
        """Test that wave continues execution after a timeout."""
        config = TimeoutConfig(by_tool={"slow_tool": 1})
        timeout_manager = TimeoutManager(config, registry, events)
        dispatcher = ToolDispatcher(registry, timeout_manager=timeout_manager)
        
        exec_config = ExecutionConfig(max_concurrent_tools=3, enable_parallel=True)
        executor = ParallelExecutor(dispatcher, registry, exec_config, events)
        
        tools = [
            ("slow_tool", "Slow", {}),
            ("fast_tool_1", "Fast 1", {}),
            ("fast_tool_2", "Fast 2", {})
        ]
        
        results = await executor.execute_parallel(tools)
        
        assert len(results) == 3
        assert any(r.output.success for r in results)

    @pytest.mark.asyncio
    async def test_timeout_errors_included_in_results(self, registry, events):
        """Test that timeout errors are properly included in results."""
        config = TimeoutConfig(by_tool={"slow_tool": 1})
        timeout_manager = TimeoutManager(config, registry, events)
        dispatcher = ToolDispatcher(registry, timeout_manager=timeout_manager)
        
        exec_config = ExecutionConfig(max_concurrent_tools=2, enable_parallel=True)
        executor = ParallelExecutor(dispatcher, registry, exec_config, events)
        
        tools = [("slow_tool", "Slow", {})]
        
        results = await executor.execute_parallel(tools)
        
        assert len(results) == 1
        assert not results[0].output.success
        assert results[0].output.error_code == "TIMEOUT"
        assert results[0].output.error_category == "timeout"

    @pytest.mark.asyncio
    async def test_multiple_timeouts_in_same_wave(self, registry, events):
        """Test multiple timeouts in the same wave."""
        config = TimeoutConfig(default_timeout_sec=1)
        timeout_manager = TimeoutManager(config, registry, events)
        dispatcher = ToolDispatcher(registry, timeout_manager=timeout_manager)
        
        exec_config = ExecutionConfig(max_concurrent_tools=3, enable_parallel=True)
        executor = ParallelExecutor(dispatcher, registry, exec_config, events)
        
        # Register another slow tool
        @tool(name="slow_tool_2", description="Slow tool 2", category="test")
        async def slow_tool_2():
            await asyncio.sleep(10)
            return "slow_2"
        
        registry.register(slow_tool_2)
        
        tools = [
            ("slow_tool", "Slow 1", {}),
            ("slow_tool_2", "Slow 2", {}),
            ("fast_tool_1", "Fast", {})
        ]
        
        results = await executor.execute_parallel(tools)
        
        assert len(results) == 3
        timeout_count = sum(1 for r in results if not r.output.success and "timeout" in r.output.error.lower())
        assert timeout_count == 2
        success_count = sum(1 for r in results if r.output.success)
        assert success_count == 1
