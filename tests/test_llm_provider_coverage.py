"""Additional tests for LLM provider to improve coverage to 90%."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import litellm

from mdpilot.llm.provider import LLMProvider
from mdpilot.types import LLMChunk, LLMResponse, ToolCall


class TestToolCallExtraction:
    """Test _extract_tool_calls edge cases."""

    def test_extract_tool_calls_empty_list(self):
        """Empty list returns empty result."""
        result = LLMProvider._extract_tool_calls([])
        assert result == []

    def test_extract_tool_calls_none(self):
        """None returns empty result."""
        result = LLMProvider._extract_tool_calls(None)
        assert result == []

    def test_extract_tool_calls_no_function(self):
        """Tool call without function attribute is skipped."""
        tc = MagicMock()
        tc.function = None

        result = LLMProvider._extract_tool_calls([tc])
        assert result == []

    def test_extract_tool_calls_dict_arguments(self):
        """Tool call with dict arguments."""
        tc = MagicMock()
        tc.id = "call_123"
        tc.function = MagicMock()
        tc.function.name = "test_func"
        tc.function.arguments = {"key": "value"}

        result = LLMProvider._extract_tool_calls([tc])

        assert len(result) == 1
        assert result[0].id == "call_123"
        assert result[0].name == "test_func"
        assert result[0].arguments == {"key": "value"}

    def test_extract_tool_calls_string_arguments_valid_json(self):
        """Tool call with valid JSON string arguments."""
        tc = MagicMock()
        tc.id = "call_456"
        tc.function = MagicMock()
        tc.function.name = "another_func"
        tc.function.arguments = '{"param": "test"}'

        result = LLMProvider._extract_tool_calls([tc])

        assert len(result) == 1
        assert result[0].arguments == {"param": "test"}

    def test_extract_tool_calls_string_arguments_invalid_json(self):
        """Tool call with invalid JSON string returns empty dict."""
        tc = MagicMock()
        tc.id = "call_789"
        tc.function = MagicMock()
        tc.function.name = "bad_func"
        tc.function.arguments = "not valid json"

        result = LLMProvider._extract_tool_calls([tc])

        assert len(result) == 1
        assert result[0].arguments == {}

    def test_extract_tool_calls_no_arguments_attribute(self):
        """Tool call without arguments attribute."""
        tc = MagicMock()
        tc.id = "call_000"
        tc.function = MagicMock(spec=['name'])  # Only has 'name', no 'arguments'
        tc.function.name = "minimal_func"

        result = LLMProvider._extract_tool_calls([tc])

        assert len(result) == 1
        assert result[0].arguments == {}

    def test_extract_tool_calls_multiple(self):
        """Multiple tool calls are all extracted."""
        tc1 = MagicMock()
        tc1.id = "call_1"
        tc1.function = MagicMock()
        tc1.function.name = "func1"
        tc1.function.arguments = {"a": 1}

        tc2 = MagicMock()
        tc2.id = "call_2"
        tc2.function = MagicMock()
        tc2.function.name = "func2"
        tc2.function.arguments = '{"b": 2}'

        result = LLMProvider._extract_tool_calls([tc1, tc2])

        assert len(result) == 2
        assert result[0].name == "func1"
        assert result[1].name == "func2"


class TestBuildKwargs:
    """Test _build_kwargs method."""

    def test_build_kwargs_minimal(self):
        """Minimal kwargs with no optional parameters."""
        provider = LLMProvider(model="test-model")

        kwargs = provider._build_kwargs(
            messages=[{"role": "user", "content": "test"}],
            tools=None,
            stream=False
        )

        assert kwargs["model"] == "test-model"
        assert kwargs["messages"] == [{"role": "user", "content": "test"}]
        assert kwargs["temperature"] == 0.0
        assert kwargs["max_tokens"] == 8192
        assert kwargs["stream"] is False
        assert "api_key" not in kwargs
        assert "api_base" not in kwargs
        assert "tools" not in kwargs

    def test_build_kwargs_with_api_key(self):
        """API key is included when set."""
        provider = LLMProvider(model="test-model", api_key="sk-test")

        kwargs = provider._build_kwargs([], None, False)

        assert kwargs["api_key"] == "sk-test"

    def test_build_kwargs_with_base_url(self):
        """Base URL is included when set."""
        provider = LLMProvider(model="test-model", base_url="https://test.com")

        kwargs = provider._build_kwargs([], None, False)

        assert kwargs["api_base"] == "https://test.com"

    def test_build_kwargs_with_tools(self):
        """Tools are included when provided."""
        provider = LLMProvider(model="test-model")
        tools = [{"type": "function", "function": {"name": "test"}}]

        kwargs = provider._build_kwargs([], tools, False)

        assert kwargs["tools"] == tools

    def test_build_kwargs_with_custom_provider(self):
        """Custom LLM provider is included when set."""
        provider = LLMProvider(
            model="test-model",
            custom_llm_provider="openai"
        )

        kwargs = provider._build_kwargs([], None, False)

        assert kwargs["custom_llm_provider"] == "openai"

    def test_build_kwargs_stream_true(self):
        """Stream parameter is set correctly."""
        provider = LLMProvider(model="test-model")

        kwargs = provider._build_kwargs([], None, True)

        assert kwargs["stream"] is True


class TestModelPrefixing:
    """Test custom_llm_provider model prefixing."""

    def test_model_prefix_added_when_custom_provider_set(self):
        """Model gets prefixed with custom provider."""
        provider = LLMProvider(
            model="gpt-4",
            custom_llm_provider="openai"
        )

        assert provider.model == "openai/gpt-4"

    def test_model_prefix_not_added_when_already_present(self):
        """Model with existing prefix is not modified."""
        provider = LLMProvider(
            model="openai/gpt-4",
            custom_llm_provider="openai"
        )

        assert provider.model == "openai/gpt-4"

    def test_model_no_prefix_when_custom_provider_none(self):
        """Model is not prefixed when custom_llm_provider is None."""
        provider = LLMProvider(model="gpt-4")

        assert provider.model == "gpt-4"


class TestStreamingEdgeCases:
    """Test streaming-specific edge cases."""

    @pytest.mark.asyncio
    async def test_streaming_empty_delta(self):
        """Streaming handles chunks with no delta."""
        provider = LLMProvider(model="test-model")

        chunk1 = MagicMock()
        chunk1.choices = []  # No choices

        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta = None  # No delta

        chunk3 = MagicMock()
        chunk3.choices = [MagicMock()]
        chunk3.choices[0].delta = MagicMock()
        chunk3.choices[0].delta.content = "test"
        chunk3.choices[0].delta.tool_calls = None
        chunk3.choices[0].finish_reason = "stop"

        async def mock_stream(*args, **kwargs):
            for chunk in [chunk1, chunk2, chunk3]:
                yield chunk

        with patch("litellm.acompletion", side_effect=mock_stream):
            result_gen = await provider.chat([], stream=True)
            chunks = []
            async for chunk in result_gen:
                chunks.append(chunk)

        # Only chunk3 should produce output
        assert len(chunks) == 1
        assert chunks[0].content == "test"

    @pytest.mark.asyncio
    async def test_streaming_with_tool_calls(self):
        """Streaming extracts tool calls from deltas."""
        provider = LLMProvider(model="test-model")

        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta = MagicMock()
        chunk.choices[0].delta.content = ""

        # Mock tool call in delta
        tc = MagicMock()
        tc.id = "call_test"
        tc.function = MagicMock()
        tc.function.name = "test_tool"
        tc.function.arguments = {"arg": "value"}
        chunk.choices[0].delta.tool_calls = [tc]
        chunk.choices[0].finish_reason = None

        async def mock_stream(*args, **kwargs):
            yield chunk

        with patch("litellm.acompletion", side_effect=mock_stream):
            result_gen = await provider.chat([], stream=True)
            chunks = []
            async for c in result_gen:
                chunks.append(c)

        assert len(chunks) == 1
        assert len(chunks[0].tool_calls) == 1
        assert chunks[0].tool_calls[0].name == "test_tool"


class TestChatMethod:
    """Test the unified chat() method."""

    @pytest.mark.asyncio
    async def test_chat_delegates_to_stream(self):
        """chat(stream=True) returns async generator."""
        provider = LLMProvider(model="test-model")

        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta = MagicMock()
        chunk.choices[0].delta.content = "test"
        chunk.choices[0].delta.tool_calls = None
        chunk.choices[0].finish_reason = "stop"

        async def mock_stream(*args, **kwargs):
            yield chunk

        with patch("litellm.acompletion", side_effect=mock_stream):
            result = await provider.chat([], stream=True)

            # Should be an async generator
            assert hasattr(result, '__anext__')

            chunks = []
            async for c in result:
                chunks.append(c)

            assert len(chunks) == 1

    @pytest.mark.asyncio
    async def test_chat_delegates_to_once(self):
        """chat(stream=False) returns LLMResponse."""
        provider = LLMProvider(model="test-model")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "test response"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20

        with patch("litellm.acompletion", return_value=mock_response):
            result = await provider.chat([], stream=False)

            assert isinstance(result, LLMResponse)
            assert result.content == "test response"


class TestResponseParsing:
    """Test response parsing edge cases."""

    @pytest.mark.asyncio
    async def test_response_with_none_content(self):
        """Response with None content is converted to empty string."""
        provider = LLMProvider(model="test-model")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None  # None content
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20

        with patch("litellm.acompletion", return_value=mock_response):
            result = await provider.chat_once([])

            assert result.content == ""

    @pytest.mark.asyncio
    async def test_response_with_none_usage(self):
        """Response with None usage tokens defaults to 0."""
        provider = LLMProvider(model="test-model")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "test"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = None
        mock_response.usage.completion_tokens = None

        with patch("litellm.acompletion", return_value=mock_response):
            result = await provider.chat_once([])

            assert result.usage_prompt_tokens == 0
            assert result.usage_completion_tokens == 0
