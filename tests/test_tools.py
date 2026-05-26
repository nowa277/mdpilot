"""Tests for the tools subsystem."""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from mdpilot.types import ToolCall, ToolOutput
from mdpilot.tools.decorator import tool
from mdpilot.tools.dispatcher import ToolDispatcher
from mdpilot.tools.registry import ToolRegistry
from mdpilot.tools.loader import load_builtin_tools


# ---------------------------------------------------------------------------
# Decorator tests
# ---------------------------------------------------------------------------

def test_tool_decorator_attaches_meta():
    """@tool decorator must attach _tool_meta to the function."""

    @tool(name="test_tool", description="A test tool")
    def test_fn(arg1: str, arg2: int = 0) -> str:
        """Test function.

        Args:
            arg1: First argument.
            arg2: Second argument.
        """
        return arg1

    assert hasattr(test_fn, "_tool_meta")
    assert test_fn._tool_meta.name == "test_tool"
    assert test_fn._tool_meta.description == "A test tool"
    assert "arg1" in test_fn._tool_meta.parameters["properties"]
    assert "arg2" in test_fn._tool_meta.parameters["properties"]


def test_tool_decorator_generates_defaults():
    """Parameters with defaults must have defaults in the schema."""

    @tool(name="with_defaults", description="Defaults test")
    def with_defaults(arg1: str, arg2: int = 42) -> str:
        return arg1

    props = with_defaults._tool_meta.parameters["properties"]
    assert props["arg2"]["default"] == 42
    # Parameters with defaults are NOT required
    assert "arg2" not in with_defaults._tool_meta.parameters.get("required", [])
    # Only arg1 (no default) should be required
    assert "arg1" in with_defaults._tool_meta.parameters.get("required", [])


def test_tool_decorator_required_params():
    """Parameters without defaults must be marked required."""

    @tool(name="required_test", description="Required test")
    def required_fn(required_arg: str, optional_arg: int = 10) -> str:
        return required_arg

    params = required_fn._tool_meta.parameters
    assert "required_arg" in params["required"]
    assert "optional_arg" not in params.get("required", [])


def test_tool_decorator_parsed_docstring_args():
    """Docstring Args: section should populate parameter descriptions."""

    @tool(name="docstring_test", description="Docstring test")
    def docstring_fn(foo: str, bar: int) -> str:
        """Do something.

        Args:
            foo: The foo parameter.
            bar: The bar parameter.
        """
        return foo

    props = docstring_fn._tool_meta.parameters["properties"]
    assert props["foo"]["description"] == "The foo parameter."
    assert props["bar"]["description"] == "The bar parameter."


def test_tool_decorator_optional_type():
    """Optional types should produce nullable schema."""

    @tool(name="optional_test", description="Optional test")
    def optional_fn(arg1: str | None = None) -> str:
        return arg1 or ""

    props = optional_fn._tool_meta.parameters["properties"]
    assert props["arg1"]["type"] == "string"
    assert props["arg1"].get("nullable") is True


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

def test_registry_register_and_get():
    """Registry should store and retrieve tools."""

    @tool(name="reg_test", description="Registry test")
    def reg_test_fn(x: int) -> int:
        return x * 2

    registry = ToolRegistry()
    registry.register(reg_test_fn)

    result = registry.get("reg_test")
    assert result is not None
    meta, fn = result
    assert meta.name == "reg_test"
    assert fn(5) == 10


def test_registry_register_requires_decorator():
    """Registering a non-@tool function must raise ValueError."""
    registry = ToolRegistry()
    with pytest.raises(ValueError, match="not decorated with @tool"):
        registry.register(lambda x: x)


def test_registry_schemas_format():
    """schemas() must return OpenAI function-calling format."""

    @tool(name="schema_test", description="Schema format test")
    def schema_fn(a: str) -> str:
        return a

    registry = ToolRegistry()
    registry.register(schema_fn)

    schemas = registry.schemas()
    assert len(schemas) == 1
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "schema_test"


def test_registry_list_tools():
    """list_tools() returns sorted tool names."""

    @tool(name="zz_last", description="Last")
    def fn1() -> str:
        return ""

    @tool(name="aa_first", description="First")
    def fn2() -> str:
        return ""

    registry = ToolRegistry()
    registry.register(fn1)
    registry.register(fn2)

    assert registry.list_tools() == ["aa_first", "zz_last"]


# ---------------------------------------------------------------------------
# Dispatcher tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatcher_executes_sync_tool():
    """Dispatcher should execute sync tool functions."""

    @tool(name="sync_tool", description="Sync tool")
    def sync_add(x: int, y: int) -> int:
        return x + y

    registry = ToolRegistry()
    registry.register(sync_add)
    dispatcher = ToolDispatcher(registry)

    call = ToolCall(id="call_1", name="sync_tool", arguments={"x": 3, "y": 4})
    result = await dispatcher.execute(call)

    assert result.success is True
    assert result.output == "7"


@pytest.mark.asyncio
async def test_dispatcher_executes_async_tool():
    """Dispatcher should await async tool functions."""

    @tool(name="async_tool", description="Async tool")
    async def async_multiply(x: int, y: int) -> int:
        await asyncio.sleep(0.01)
        return x * y

    registry = ToolRegistry()
    registry.register(async_multiply)
    dispatcher = ToolDispatcher(registry)

    call = ToolCall(id="call_2", name="async_tool", arguments={"x": 3, "y": 7})
    result = await dispatcher.execute(call)

    assert result.success is True
    assert result.output == "21"


@pytest.mark.asyncio
async def test_dispatcher_unknown_tool():
    """Dispatcher returns error for unknown tool names."""
    registry = ToolRegistry()
    dispatcher = ToolDispatcher(registry)

    call = ToolCall(id="call_3", name="nonexistent_tool", arguments={})
    result = await dispatcher.execute(call)

    assert result.success is False
    assert "not found" in result.error


@pytest.mark.asyncio
async def test_dispatcher_missing_required_arg():
    """Dispatcher returns error for missing required arguments."""
    @tool(name="required_tool", description="Required args")
    def required_fn(x: int, y: int) -> int:
        return x + y

    registry = ToolRegistry()
    registry.register(required_fn)
    dispatcher = ToolDispatcher(registry)

    call = ToolCall(id="call_4", name="required_tool", arguments={"x": 1})
    result = await dispatcher.execute(call)

    assert result.success is False
    assert "Missing required" in result.error


@pytest.mark.asyncio
async def test_dispatcher_wrong_type_arg():
    """Dispatcher returns error for arguments with wrong type."""
    @tool(name="typed_tool", description="Typed tool")
    def typed_fn(x: int) -> int:
        return x

    registry = ToolRegistry()
    registry.register(typed_fn)
    dispatcher = ToolDispatcher(registry)

    call = ToolCall(id="call_5", name="typed_tool", arguments={"x": "not_an_int"})
    result = await dispatcher.execute(call)

    assert result.success is False
    assert "must be of type" in result.error


@pytest.mark.asyncio
async def test_dispatcher_tool_exception():
    """Dispatcher catches and returns tool exceptions."""

    @tool(name="raising_tool", description="Raises error")
    def raising_fn() -> str:
        raise ValueError("deliberate error")

    registry = ToolRegistry()
    registry.register(raising_fn)
    dispatcher = ToolDispatcher(registry)

    call = ToolCall(id="call_6", name="raising_tool", arguments={})
    result = await dispatcher.execute(call)

    assert result.success is False
    assert "ValueError" in result.error


# ---------------------------------------------------------------------------
# Builtin tool tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bash_run_echo():
    """bash_run should execute echo and return output."""
    from mdpilot.tools.builtin.bash import bash_run

    registry = ToolRegistry()
    registry.register(bash_run)
    dispatcher = ToolDispatcher(registry)

    call = ToolCall(id="call_bash", name="bash_run", arguments={"command": "echo hello"})
    result = await dispatcher.execute(call)

    assert result.success is True
    assert "hello" in result.output.strip()


@pytest.mark.asyncio
async def test_bash_run_with_timeout():
    """bash_run should respect timeout parameter."""
    from mdpilot.tools.builtin.bash import bash_run

    registry = ToolRegistry()
    registry.register(bash_run)
    dispatcher = ToolDispatcher(registry)

    call = ToolCall(
        id="call_bash_timeout",
        name="bash_run",
        arguments={"command": "sleep 0.1", "timeout": 5},
    )
    result = await dispatcher.execute(call)

    assert result.success is True


@pytest.mark.asyncio
async def test_bash_run_timeout_expires():
    """bash_run should raise TimeoutError when command exceeds timeout."""
    from mdpilot.tools.builtin.bash import bash_run

    registry = ToolRegistry()
    registry.register(bash_run)
    dispatcher = ToolDispatcher(registry)

    call = ToolCall(
        id="call_bash_slow",
        name="bash_run",
        arguments={"command": "sleep 10", "timeout": 1},
    )
    result = await dispatcher.execute(call)

    assert result.success is False
    assert "timed out" in result.error.lower()


@pytest.mark.asyncio
async def test_file_write_and_read_roundtrip():
    """file_write and file_read should form a working roundtrip."""
    from mdpilot.tools.builtin.file_ops import file_read, file_write

    registry = ToolRegistry()
    registry.register(file_read)
    registry.register(file_write)
    dispatcher = ToolDispatcher(registry)

    # Use a path within the working directory
    test_file = "test_roundtrip_temp.txt"
    content = "Hello, file roundtrip!\nLine 2\nLine 3"

    try:
        # Write
        write_call = ToolCall(
            id="call_write",
            name="file_write",
            arguments={"path": test_file, "content": content},
        )
        write_result = await dispatcher.execute(write_call)
        assert write_result.success is True

        # Read
        read_call = ToolCall(
            id="call_read",
            name="file_read",
            arguments={"path": test_file},
        )
        read_result = await dispatcher.execute(read_call)
        assert read_result.success is True
        assert content in read_result.output
    finally:
        # Clean up
        if Path(test_file).exists():
            Path(test_file).unlink()


@pytest.mark.asyncio
async def test_file_read_nonexistent():
    """file_read returns error for missing file."""
    from mdpilot.tools.builtin.file_ops import file_read

    registry = ToolRegistry()
    registry.register(file_read)
    dispatcher = ToolDispatcher(registry)

    call = ToolCall(
        id="call_read_missing",
        name="file_read",
        arguments={"path": "nonexistent_file_that_does_not_exist.txt"},
    )
    result = await dispatcher.execute(call)

    assert result.success is False  # Tool execution fails for missing file
    assert "Error" in result.error  # Error message in error field


@pytest.mark.asyncio
async def test_file_search_finds_file():
    """file_search should locate files by pattern."""
    from mdpilot.tools.builtin.file_ops import file_search

    registry = ToolRegistry()
    registry.register(file_search)
    dispatcher = ToolDispatcher(registry)

    # Create test files in working directory
    test_dir = Path("test_search_temp")
    test_dir.mkdir(exist_ok=True)

    try:
        (test_dir / "alpha.py").touch()
        (test_dir / "beta.py").touch()
        (test_dir / "gamma.txt").touch()

        call = ToolCall(
            id="call_search",
            name="file_search",
            arguments={"pattern": ".py", "path": str(test_dir)},
        )
        result = await dispatcher.execute(call)

        assert result.success is True
        assert "alpha.py" in result.output
        assert "beta.py" in result.output
        assert "gamma.txt" not in result.output
    finally:
        # Clean up
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir)


@pytest.mark.asyncio
async def test_file_search_no_matches():
    """file_search returns message when no files match."""
    from mdpilot.tools.builtin.file_ops import file_search

    registry = ToolRegistry()
    registry.register(file_search)
    dispatcher = ToolDispatcher(registry)

    # Create empty test directory in working directory
    test_dir = Path("test_search_empty_temp")
    test_dir.mkdir(exist_ok=True)

    try:
        call = ToolCall(
            id="call_search_empty",
            name="file_search",
            arguments={"pattern": "nonexistent", "path": str(test_dir)},
        )
        result = await dispatcher.execute(call)

        assert result.success is True
        assert "No files found" in result.output
    finally:
        # Clean up
        if test_dir.exists():
            test_dir.rmdir()


def test_amber_env_check_skip_if_no_amber():
    """amber_env_check runs even without AMBER, returning diagnostic info."""
    from mdpilot.tools.builtin.amber_env import amber_env_check

    registry = ToolRegistry()
    registry.register(amber_env_check)
    dispatcher = ToolDispatcher(registry)

    # Run synchronously since amber_env_check is sync
    call = ToolCall(id="call_amber", name="amber_env_check", arguments={})
    result = asyncio.run(dispatcher.execute(call))

    assert result.success is True
    assert "AMBER" in result.output or "AMBERHOME" in result.output


# ---------------------------------------------------------------------------
# Loader tests
# ---------------------------------------------------------------------------

def test_loader_registers_all_builtin_tools():
    """load_builtin_tools should register bash, file_ops, and amber_env tools."""
    registry = ToolRegistry()
    load_builtin_tools(registry)

    tool_names = registry.list_tools()
    assert "bash_run" in tool_names
    assert "file_read" in tool_names
    assert "file_write" in tool_names
    assert "file_search" in tool_names
    assert "amber_env_check" in tool_names


def test_auto_discover_finds_builtin_tools():
    """auto_discover should find tools in the builtin package."""
    registry = ToolRegistry()
    registry.auto_discover("mdpilot.tools.builtin")

    tool_names = registry.list_tools()
    assert "bash_run" in tool_names
    assert "file_read" in tool_names
    assert "amber_env_check" in tool_names


# ---------------------------------------------------------------------------
# End-to-end tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_end_to_end_tool_chain():
    """Full flow: register tools, create dispatcher, execute call."""
    registry = ToolRegistry()
    load_builtin_tools(registry)
    dispatcher = ToolDispatcher(registry)

    # Verify schemas can be generated (needed for LLM function-calling)
    schemas = registry.schemas()
    assert len(schemas) >= 5
    assert all(s["type"] == "function" for s in schemas)

    # Execute a bash call
    call = ToolCall(
        id="call_e2e",
        name="bash_run",
        arguments={"command": "echo 'end to end'"},
    )
    result = await dispatcher.execute(call)
    assert result.success is True
