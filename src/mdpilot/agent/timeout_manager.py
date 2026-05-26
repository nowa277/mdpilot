"""Timeout management for tool execution."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Coroutine

from mdpilot.agent.events import EventEmitter
from mdpilot.config.schema import TimeoutConfig
from mdpilot.tools.registry import ToolRegistry
from mdpilot.types import ToolCall


class TimeoutManager:
    """Manages timeout resolution and enforcement for tool execution."""

    def __init__(
        self,
        config: TimeoutConfig,
        registry: ToolRegistry,
        events: EventEmitter
    ):
        """Initialize timeout manager.
        
        Args:
            config: Timeout configuration
            registry: Tool registry for metadata lookup
            events: Event emitter for monitoring
        """
        self._config = config
        self._registry = registry
        self._events = events
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._task_start_times: dict[str, float] = {}

    def resolve_timeout(self, tool_name: str) -> int | None:
        """Resolve timeout for a tool using three-tier inheritance hierarchy.
        
        Resolution order:
        1. Tool-specific timeout (highest priority)
        2. Category-level timeout
        3. Global default timeout
        4. None (no timeout)
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Timeout in seconds, or None if no timeout configured
        """
        if tool_name in self._config.by_tool:
            return self._config.by_tool[tool_name]
        
        tool_entry = self._registry.get(tool_name)
        if tool_entry:
            meta, _ = tool_entry
            category = meta.category
            if category in self._config.by_category:
                return self._config.by_category[category]
        
        return self._config.default_timeout_sec

    async def enforce_timeout(
        self,
        coro: Coroutine,
        timeout_sec: int | None,
        tool_call: ToolCall
    ) -> Any:
        """Enforce timeout on a coroutine execution.
        
        Args:
            coro: Coroutine to execute
            timeout_sec: Timeout in seconds (None = no timeout)
            tool_call: Tool call context for error reporting
            
        Returns:
            Result of the coroutine
            
        Raises:
            TimeoutError: If execution exceeds timeout
        """
        if timeout_sec is None:
            return await coro
        
        task = asyncio.create_task(coro)
        self._active_tasks[tool_call.id] = task
        self._task_start_times[tool_call.id] = time.time()
        
        try:
            warning_time = timeout_sec * self._config.warning_threshold
            warning_task = asyncio.create_task(
                self._emit_warning_after(tool_call, warning_time)
            )
            
            result = await asyncio.wait_for(task, timeout=timeout_sec)
            warning_task.cancel()
            return result
            
        except asyncio.TimeoutError:
            self._events.emit("tool.timeout",
                tool_name=tool_call.name,
                tool_id=tool_call.id,
                timeout_sec=timeout_sec
            )
            
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            
            raise TimeoutError(
                f"Tool '{tool_call.name}' exceeded timeout of {timeout_sec}s"
            )
        finally:
            self._active_tasks.pop(tool_call.id, None)
            self._task_start_times.pop(tool_call.id, None)

    async def _emit_warning_after(
        self,
        tool_call: ToolCall,
        delay: float
    ) -> None:
        """Emit warning event after delay.
        
        Args:
            tool_call: Tool call context
            delay: Delay in seconds before emitting warning
        """
        try:
            await asyncio.sleep(delay)
            self._events.emit("tool.timeout_warning",
                tool_name=tool_call.name,
                tool_id=tool_call.id,
                elapsed_sec=delay
            )
        except asyncio.CancelledError:
            pass

    def get_active_timeouts(self) -> dict[str, float]:
        """Get currently active tool executions with elapsed times.
        
        Returns:
            Dictionary mapping tool_id to elapsed time in seconds
        """
        result = {}
        current_time = time.time()
        for tool_id, task in self._active_tasks.items():
            if not task.done():
                start_time = self._task_start_times.get(tool_id)
                if start_time:
                    result[tool_id] = current_time - start_time
        return result
