"""Tests for plan/generator.py"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from mdpilot.llm.provider import LLMProvider
from mdpilot.plan_legacy.generator import PlanGenerationError, PlanGenerator
from mdpilot.plan_legacy.schema import Plan, PlanStep
from mdpilot.tools.registry import ToolRegistry
from mdpilot.types import LLMResponse


@pytest.fixture
def mock_provider():
    """Create mock LLMProvider."""
    provider = MagicMock(spec=LLMProvider)
    provider.chat_once = AsyncMock()
    return provider


@pytest.fixture
def mock_registry():
    """Create mock ToolRegistry."""
    registry = MagicMock(spec=ToolRegistry)
    registry.list_tools = MagicMock(return_value=["bash_run", "file_read", "file_write"])
    registry.schemas = MagicMock(return_value=[
        {
            "function": {
                "name": "bash_run",
                "description": "Execute shell commands"
            }
        },
        {
            "function": {
                "name": "file_read",
                "description": "Read file contents"
            }
        },
        {
            "function": {
                "name": "file_write",
                "description": "Write file contents"
            }
        }
    ])
    return registry


@pytest.fixture
def generator(mock_provider, mock_registry):
    """Create PlanGenerator instance."""
    return PlanGenerator(mock_provider, mock_registry)


def test_generator_init(generator, mock_provider, mock_registry):
    """Test PlanGenerator initialization."""
    assert generator._provider == mock_provider
    assert generator._registry == mock_registry


@pytest.mark.asyncio
async def test_generate_valid_plan(generator, mock_provider):
    """Test generating a valid plan."""
    plan_json = {
        "goal": "Read and process a file",
        "steps": [
            {
                "description": "Read input file",
                "tool": "file_read",
                "arguments": {"path": "input.txt"},
                "depends_on": []
            },
            {
                "description": "Process data",
                "tool": "bash_run",
                "arguments": {"command": "process.sh"},
                "depends_on": [1]
            }
        ],
        "estimated_time": "5 seconds"
    }
    
    mock_provider.chat_once.return_value = LLMResponse(
        content=json.dumps(plan_json),
        tool_calls=None
    )
    
    plan = await generator.generate("Read and process a file")
    
    assert isinstance(plan, Plan)
    assert plan.goal == "Read and process a file"
    assert len(plan.steps) == 2
    assert plan.steps[0].id == 1
    assert plan.steps[0].tool == "file_read"
    assert plan.steps[0].depends_on == []
    assert plan.steps[1].id == 2
    assert plan.steps[1].tool == "bash_run"
    assert plan.steps[1].depends_on == [1]
    assert plan.estimated_time == "5 seconds"


@pytest.mark.asyncio
async def test_generate_with_code_fences(generator, mock_provider):
    """Test generating plan with markdown code fences."""
    plan_json = {
        "goal": "Test goal",
        "steps": [
            {
                "description": "Step 1",
                "tool": "bash_run",
                "arguments": {},
                "depends_on": []
            }
        ]
    }
    
    # LLM returns JSON wrapped in markdown code fences
    mock_provider.chat_once.return_value = LLMResponse(
        content=f"```json\n{json.dumps(plan_json)}\n```",
        tool_calls=None
    )
    
    plan = await generator.generate("Test goal")
    
    assert isinstance(plan, Plan)
    assert plan.goal == "Test goal"
    assert len(plan.steps) == 1


@pytest.mark.asyncio
async def test_generate_with_trailing_text(generator, mock_provider):
    """Test generating plan with trailing explanatory text."""
    plan_json = {
        "goal": "Test goal",
        "steps": [
            {
                "description": "Step 1",
                "tool": "file_read",
                "arguments": {"path": "test.txt"},
                "depends_on": []
            }
        ]
    }
    
    # LLM returns JSON followed by explanatory text
    response_text = json.dumps(plan_json) + "\n\nThis plan will read the file first."
    mock_provider.chat_once.return_value = LLMResponse(
        content=response_text,
        tool_calls=None
    )
    
    plan = await generator.generate("Test goal")
    
    assert isinstance(plan, Plan)
    assert len(plan.steps) == 1


@pytest.mark.asyncio
async def test_generate_invalid_json(generator, mock_provider):
    """Test handling invalid JSON response."""
    mock_provider.chat_once.return_value = LLMResponse(
        content="This is not valid JSON {incomplete",
        tool_calls=None
    )
    
    with pytest.raises(PlanGenerationError, match="invalid JSON"):
        await generator.generate("Test goal")


@pytest.mark.asyncio
async def test_generate_unknown_tool(generator, mock_provider):
    """Test handling unknown tool reference."""
    plan_json = {
        "goal": "Test goal",
        "steps": [
            {
                "description": "Use unknown tool",
                "tool": "unknown_tool",
                "arguments": {},
                "depends_on": []
            }
        ]
    }
    
    mock_provider.chat_once.return_value = LLMResponse(
        content=json.dumps(plan_json),
        tool_calls=None
    )
    
    with pytest.raises(PlanGenerationError, match="unknown tool"):
        await generator.generate("Test goal")


@pytest.mark.asyncio
async def test_generate_invalid_dependency(generator, mock_provider):
    """Test handling invalid dependency reference."""
    plan_json = {
        "goal": "Test goal",
        "steps": [
            {
                "description": "Step 1",
                "tool": "bash_run",
                "arguments": {},
                "depends_on": [99]  # Non-existent step ID
            }
        ]
    }
    
    mock_provider.chat_once.return_value = LLMResponse(
        content=json.dumps(plan_json),
        tool_calls=None
    )
    
    with pytest.raises(PlanGenerationError, match="non-existent step ID"):
        await generator.generate("Test goal")


@pytest.mark.asyncio
async def test_generate_steps_not_list(generator, mock_provider):
    """Test handling non-list steps field."""
    plan_json = {
        "goal": "Test goal",
        "steps": "not a list"
    }
    
    mock_provider.chat_once.return_value = LLMResponse(
        content=json.dumps(plan_json),
        tool_calls=None
    )
    
    with pytest.raises(PlanGenerationError, match="must be a list"):
        await generator.generate("Test goal")


@pytest.mark.asyncio
async def test_generate_missing_goal(generator, mock_provider):
    """Test handling missing goal field (uses original goal)."""
    plan_json = {
        "steps": [
            {
                "description": "Step 1",
                "tool": "bash_run",
                "arguments": {},
                "depends_on": []
            }
        ]
    }
    
    mock_provider.chat_once.return_value = LLMResponse(
        content=json.dumps(plan_json),
        tool_calls=None
    )
    
    plan = await generator.generate("Original goal")
    
    assert plan.goal == "Original goal"


@pytest.mark.asyncio
async def test_generate_empty_steps(generator, mock_provider):
    """Test generating plan with empty steps list."""
    plan_json = {
        "goal": "Test goal",
        "steps": []
    }
    
    mock_provider.chat_once.return_value = LLMResponse(
        content=json.dumps(plan_json),
        tool_calls=None
    )
    
    plan = await generator.generate("Test goal")
    
    assert isinstance(plan, Plan)
    assert len(plan.steps) == 0


def test_strip_code_fences_json():
    """Test stripping JSON code fences."""
    text = "```json\n{\"key\": \"value\"}\n```"
    result = PlanGenerator._strip_code_fences(text)
    assert result == "{\"key\": \"value\"}"


def test_strip_code_fences_plain():
    """Test stripping plain code fences."""
    text = "```\n{\"key\": \"value\"}\n```"
    result = PlanGenerator._strip_code_fences(text)
    assert result == "{\"key\": \"value\"}"


def test_strip_code_fences_no_fences():
    """Test text without code fences."""
    text = "{\"key\": \"value\"}"
    result = PlanGenerator._strip_code_fences(text)
    assert result == "{\"key\": \"value\"}"


def test_extract_json_object_simple():
    """Test extracting simple JSON object."""
    text = '{"key": "value"} extra text'
    result = PlanGenerator._extract_json_object(text)
    assert result == '{"key": "value"}'


def test_extract_json_object_nested():
    """Test extracting nested JSON object."""
    text = '{"outer": {"inner": "value"}} extra'
    result = PlanGenerator._extract_json_object(text)
    assert result == '{"outer": {"inner": "value"}}'


def test_extract_json_object_with_string_braces():
    """Test extracting JSON with braces in strings."""
    text = '{"key": "value with } brace"} extra'
    result = PlanGenerator._extract_json_object(text)
    assert result == '{"key": "value with } brace"}'


def test_extract_json_object_with_escaped_quotes():
    """Test extracting JSON with escaped quotes."""
    text = '{"key": "value with \\" quote"} extra'
    result = PlanGenerator._extract_json_object(text)
    assert result == '{"key": "value with \\" quote"}'


def test_extract_json_object_no_json():
    """Test text without JSON object."""
    text = "No JSON here"
    result = PlanGenerator._extract_json_object(text)
    assert result == "No JSON here"


def test_extract_json_object_incomplete():
    """Test incomplete JSON object."""
    text = '{"key": "value"'
    result = PlanGenerator._extract_json_object(text)
    assert result == '{"key": "value"'


def test_build_system_prompt(generator):
    """Test system prompt construction."""
    prompt = generator._build_system_prompt()
    
    assert "planning agent" in prompt.lower()
    assert "bash_run" in prompt
    assert "file_read" in prompt
    assert "file_write" in prompt
    assert "depends_on" in prompt
    assert "JSON" in prompt


def test_build_system_prompt_no_tools(generator, mock_registry):
    """Test system prompt with no tools registered."""
    mock_registry.list_tools.return_value = []
    mock_registry.schemas.return_value = []
    
    prompt = generator._build_system_prompt()
    
    assert "no tools registered" in prompt


def test_build_user_message(generator):
    """Test user message construction."""
    message = generator._build_user_message("Test goal")
    
    assert "Test goal" in message
    assert "Generate a plan" in message


@pytest.mark.asyncio
async def test_generate_step_with_defaults(generator, mock_provider):
    """Test generating step with missing optional fields."""
    plan_json = {
        "goal": "Test goal",
        "steps": [
            {
                "tool": "bash_run"
                # Missing description, arguments, depends_on
            }
        ]
    }
    
    mock_provider.chat_once.return_value = LLMResponse(
        content=json.dumps(plan_json),
        tool_calls=None
    )
    
    plan = await generator.generate("Test goal")
    
    assert len(plan.steps) == 1
    assert plan.steps[0].description == ""
    assert plan.steps[0].arguments == {}
    assert plan.steps[0].depends_on == []
    assert plan.steps[0].status == "pending"


@pytest.mark.asyncio
async def test_generate_complex_dependencies(generator, mock_provider):
    """Test generating plan with complex dependency graph."""
    plan_json = {
        "goal": "Complex workflow",
        "steps": [
            {"description": "Step 1", "tool": "file_read", "arguments": {}, "depends_on": []},
            {"description": "Step 2", "tool": "bash_run", "arguments": {}, "depends_on": []},
            {"description": "Step 3", "tool": "file_write", "arguments": {}, "depends_on": [1, 2]},
            {"description": "Step 4", "tool": "bash_run", "arguments": {}, "depends_on": [3]}
        ]
    }
    
    mock_provider.chat_once.return_value = LLMResponse(
        content=json.dumps(plan_json),
        tool_calls=None
    )
    
    plan = await generator.generate("Complex workflow")
    
    assert len(plan.steps) == 4
    assert plan.steps[2].depends_on == [1, 2]
    assert plan.steps[3].depends_on == [3]


@pytest.mark.asyncio
async def test_generate_with_nested_json_in_string(generator, mock_provider):
    """Test extracting JSON when response contains nested JSON in strings."""
    plan_json = {
        "goal": "Test goal",
        "steps": [
            {
                "description": "Step with JSON string: {\"nested\": \"value\"}",
                "tool": "bash_run",
                "arguments": {"config": "{\"key\": \"value\"}"},
                "depends_on": []
            }
        ]
    }
    
    mock_provider.chat_once.return_value = LLMResponse(
        content=json.dumps(plan_json) + " Extra text after",
        tool_calls=None
    )
    
    plan = await generator.generate("Test goal")
    
    assert len(plan.steps) == 1
    assert "{\"nested\": \"value\"}" in plan.steps[0].description


def test_plan_generation_error():
    """Test PlanGenerationError exception."""
    error = PlanGenerationError("Test error message")
    assert str(error) == "Test error message"
    assert isinstance(error, Exception)
