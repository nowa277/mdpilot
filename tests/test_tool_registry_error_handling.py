"""Tests for tool registry and dispatcher error handling."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from mdpilot.tools.decorator import tool
from mdpilot.tools.dispatcher import ToolDispatcher, ToolValidationError
from mdpilot.tools.registry import ToolRegistry
from mdpilot.types import ToolCall, ToolMeta


class TestToolRegistryErrors:
    """Test error handling in ToolRegistry."""

    def test_register_non_callable(self):
        """Registering non-callable should raise ValueError."""
        registry = ToolRegistry()

        with pytest.raises(ValueError) as exc_info:
            registry.register("not_a_function")

        assert "non-callable" in str(exc_info.value)

    def test_register_without_decorator(self):
        """Registering function without @tool should raise ValueError."""
        registry = ToolRegistry()

        def plain_function():
            pass

        with pytest.raises(ValueError) as exc_info:
            registry.register(plain_function)

        assert "not decorated with @tool" in str(exc_info.value)
        assert "plain_function" in str(exc_info.value)

    def test_register_with_empty_name(self):
        """Tool with empty name should raise ValueError."""
        registry = ToolRegistry()

        def bad_tool():
            pass

        # Manually attach invalid metadata
        bad_tool._tool_meta = ToolMeta(name="", description="test", parameters={})

        with pytest.raises(ValueError) as exc_info:
            registry.register(bad_tool)

        assert "empty name" in str(exc_info.value)

    def test_register_duplicate_tool_logs_warning(self, caplog):
        """Registering duplicate tool should log warning."""
        registry = ToolRegistry()

        @tool(name="duplicate", description="First")
        def tool1():
            pass

        @tool(name="duplicate", description="Second")
        def tool2():
            pass

        registry.register(tool1)

        with caplog.at_level(logging.WARNING):
            registry.register(tool2)

        assert "already registered" in caplog.text
        assert "duplicate" in caplog.text

    def test_register_success_logs_debug(self, caplog):
        """Successful registration should log at DEBUG level."""
        registry = ToolRegistry()

        @tool(name="test_tool", description="Test")
        def my_tool():
            pass

        with caplog.at_level(logging.DEBUG):
            registry.register(my_tool)

        assert "Registered tool: test_tool" in caplog.text


class TestAutoDiscoveryErrors:
    """Test error handling in auto_discover."""

    def test_auto_discover_invalid_package(self, caplog):
        """Invalid package path should log error and return gracefully."""
        registry = ToolRegistry()

        with caplog.at_level(logging.ERROR):
            registry.auto_discover("nonexistent.package.path")

        assert "Failed to import package" in caplog.text
        assert "nonexistent.package.path" in caplog.text

    def test_auto_discover_package_without_path(self, caplog):
        """Package without __path__ should log warning."""
        registry = ToolRegistry()

        # Use a built-in module (not a package)
        with caplog.at_level(logging.INFO):
            registry.auto_discover("os")

        # Should either warn about no __path__ or complete with 0 tools
        assert "has no __path__" in caplog.text or "0 tools registered" in caplog.text

    def test_auto_discover_logs_summary(self, caplog):
        """Auto-discovery should log summary with counts."""
        registry = ToolRegistry()

        with caplog.at_level(logging.INFO):
            registry.auto_discover("mdpilot.tools.builtin")

        assert "Auto-discovery complete" in caplog.text
        assert "tools registered" in caplog.text


class TestDispatcherErrors:
    """Test error handling in ToolDispatcher."""

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self, caplog):
        """Executing non-existent tool should return error with suggestions."""
        registry = ToolRegistry()

        @tool(name="existing_tool", description="Test")
        def my_tool():
            return "ok"

        registry.register(my_tool)
        dispatcher = ToolDispatcher(registry)

        call = ToolCall(id="1", name="nonexistent_tool", arguments={})

        with caplog.at_level(logging.ERROR):
            result = await dispatcher.execute(call)

        assert not result.success
        assert "not found" in result.error
        assert "Available tools" in result.error
        assert "nonexistent_tool" in caplog.text

    @pytest.mark.asyncio
    async def test_execute_missing_required_argument(self, caplog):
        """Missing required argument should return validation error."""
        registry = ToolRegistry()

        @tool(name="test_tool", description="Test")
        def my_tool(required_arg: str):
            """Test tool.

            Args:
                required_arg: A required argument
            """
            return f"Got: {required_arg}"

        registry.register(my_tool)
        dispatcher = ToolDispatcher(registry)

        call = ToolCall(id="1", name="test_tool", arguments={})

        with caplog.at_level(logging.ERROR):
            result = await dispatcher.execute(call)

        assert not result.success
        assert "validation failed" in result.error.lower()
        assert "required_arg" in result.error

    @pytest.mark.asyncio
    async def test_execute_wrong_argument_type(self, caplog):
        """Wrong argument type should return validation error."""
        registry = ToolRegistry()

        @tool(name="test_tool", description="Test")
        def my_tool(count: int):
            """Test tool.

            Args:
                count: An integer count
            """
            return f"Count: {count}"

        registry.register(my_tool)
        dispatcher = ToolDispatcher(registry)

        call = ToolCall(id="1", name="test_tool", arguments={"count": "not_a_number"})

        with caplog.at_level(logging.ERROR):
            result = await dispatcher.execute(call)

        assert not result.success
        assert "validation failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_tool_raises_exception(self, caplog):
        """Tool raising exception should be caught and logged."""
        registry = ToolRegistry()

        @tool(name="failing_tool", description="Test")
        def failing_tool():
            raise RuntimeError("Something went wrong")

        registry.register(failing_tool)
        dispatcher = ToolDispatcher(registry)

        call = ToolCall(id="1", name="failing_tool", arguments={})

        with caplog.at_level(logging.ERROR):
            result = await dispatcher.execute(call)

        assert not result.success
        assert "RuntimeError" in result.error
        assert "Something went wrong" in result.error
        assert "raised exception" in caplog.text

    @pytest.mark.asyncio
    async def test_execute_tool_type_error(self, caplog):
        """TypeError (argument mismatch) should have helpful error message."""
        registry = ToolRegistry()

        @tool(name="test_tool", description="Test")
        def my_tool(arg1: str, unexpected_arg: str):
            """Test tool.

            Args:
                arg1: First argument
                unexpected_arg: Second argument
            """
            # This will cause TypeError if unexpected_arg is not provided
            return f"{arg1} {unexpected_arg}"

        registry.register(my_tool)
        dispatcher = ToolDispatcher(registry)

        call = ToolCall(id="1", name="test_tool", arguments={"arg1": "value"})

        with caplog.at_level(logging.ERROR):
            result = await dispatcher.execute(call)

        assert not result.success
        # Validation catches missing required arg before TypeError
        assert "validation failed" in result.error.lower()
        assert "unexpected_arg" in result.error

    @pytest.mark.asyncio
    async def test_execute_logs_debug_on_success(self, caplog):
        """Successful execution should log at DEBUG level."""
        registry = ToolRegistry()

        @tool(name="test_tool", description="Test")
        def my_tool():
            return "success"

        registry.register(my_tool)
        dispatcher = ToolDispatcher(registry)

        call = ToolCall(id="1", name="test_tool", arguments={})

        with caplog.at_level(logging.DEBUG):
            result = await dispatcher.execute(call)

        assert result.success
        assert "Executing tool: test_tool" in caplog.text
        assert "completed successfully" in caplog.text

    @pytest.mark.asyncio
    async def test_execute_tool_returns_error_string(self, caplog):
        """Tool returning 'Error:' string should be classified as failure."""
        registry = ToolRegistry()

        @tool(name="test_tool", description="Test")
        def my_tool():
            return "Error: File not found"

        registry.register(my_tool)
        dispatcher = ToolDispatcher(registry)

        call = ToolCall(id="1", name="test_tool", arguments={})

        with caplog.at_level(logging.WARNING):
            result = await dispatcher.execute(call)

        assert not result.success
        assert "Error: File not found" in result.error
        assert "returned error" in caplog.text


class TestValidationErrorDetails:
    """Test detailed validation error messages."""

    @pytest.mark.asyncio
    async def test_array_item_type_validation(self):
        """Array items with wrong type should give detailed error."""
        registry = ToolRegistry()

        @tool(name="test_tool", description="Test")
        def my_tool(numbers: list[int]):
            """Test tool.

            Args:
                numbers: List of integers
            """
            return str(numbers)

        registry.register(my_tool)
        dispatcher = ToolDispatcher(registry)

        call = ToolCall(
            id="1", name="test_tool", arguments={"numbers": [1, 2, "three", 4]}
        )

        result = await dispatcher.execute(call)

        assert not result.success
        # The validation detects type mismatch at array level
        assert "validation failed" in result.error.lower()
        assert "numbers" in result.error
