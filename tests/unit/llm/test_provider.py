"""Tests for LLM provider."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import litellm
import pytest

from mdpilot.llm.provider import LLMProvider
from mdpilot.types import LLMChunk, LLMResponse, ToolCall


class TestLLMProviderInit:
    """Test LLMProvider initialization."""

    def test_default_initialization(self):
        """Test provider with default parameters."""
        provider = LLMProvider()
        
        assert provider.model == "claude-sonnet-4-20250514"
        assert provider.temperature == 0.0
        assert provider.max_tokens == 8192
        assert provider.timeout == 120
        assert provider.max_retries == 3

    def test_custom_initialization(self):
        """Test provider with custom parameters."""
        provider = LLMProvider(
            model="gpt-4",
            api_key="test-key",
            base_url="https://test.com",
            temperature=0.7,
            max_tokens=4096,
            timeout=60,
            max_retries=5
        )
        
        assert provider.model == "gpt-4"
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://test.com"
        assert provider.temperature == 0.7
        assert provider.max_tokens == 4096
        assert provider.timeout == 60
        assert provider.max_retries == 5

    def test_custom_llm_provider_prefix(self):
        """Test that custom_llm_provider adds prefix to model."""
        provider = LLMProvider(
            model="my-model",
            custom_llm_provider="openai"
        )
        
        assert provider.model == "openai/my-model"

    def test_custom_llm_provider_no_prefix_if_slash_exists(self):
        """Test that prefix is not added if model already has slash."""
        provider = LLMProvider(
            model="openai/gpt-4",
            custom_llm_provider="openai"
        )
        
        assert provider.model == "openai/gpt-4"


class TestLLMProviderBuildKwargs:
    """Test _build_kwargs method."""

    def test_build_kwargs_minimal(self):
        """Test building kwargs with minimal parameters."""
        provider = LLMProvider()
        messages = [{"role": "user", "content": "test"}]
        
        kwargs = provider._build_kwargs(messages, None, False)
        
        assert kwargs["model"] == "claude-sonnet-4-20250514"
        assert kwargs["messages"] == messages
        assert kwargs["temperature"] == 0.0
        assert kwargs["max_tokens"] == 8192
        assert kwargs["timeout"] == 120
        assert kwargs["stream"] is False
        assert "tools" not in kwargs

    def test_build_kwargs_with_tools(self):
        """Test building kwargs with tools."""
        provider = LLMProvider()
        messages = [{"role": "user", "content": "test"}]
        tools = [{"type": "function", "function": {"name": "test"}}]
        
        kwargs = provider._build_kwargs(messages, tools, False)
        
        assert kwargs["tools"] == tools

    def test_build_kwargs_with_api_key(self):
        """Test building kwargs with API key."""
        provider = LLMProvider(api_key="test-key")
        messages = [{"role": "user", "content": "test"}]
        
        kwargs = provider._build_kwargs(messages, None, False)
        
        assert kwargs["api_key"] == "test-key"

    def test_build_kwargs_with_base_url(self):
        """Test building kwargs with base URL."""
        provider = LLMProvider(base_url="https://test.com")
        messages = [{"role": "user", "content": "test"}]
        
        kwargs = provider._build_kwargs(messages, None, False)
        
        assert kwargs["api_base"] == "https://test.com"


class TestLLMProviderExtractToolCalls:
    """Test _extract_tool_calls method."""

    def test_extract_tool_calls_empty(self):
        """Test extracting tool calls from empty list."""
        result = LLMProvider._extract_tool_calls(None)
        assert result == []
        
        result = LLMProvider._extract_tool_calls([])
        assert result == []

    def test_extract_tool_calls_with_dict_arguments(self):
        """Test extracting tool calls with dict arguments."""
        mock_tc = MagicMock()
        mock_tc.id = "call_123"
        mock_tc.function.name = "test_function"
        mock_tc.function.arguments = {"arg1": "value1"}
        
        result = LLMProvider._extract_tool_calls([mock_tc])
        
        assert len(result) == 1
        assert result[0].id == "call_123"
        assert result[0].name == "test_function"
        assert result[0].arguments == {"arg1": "value1"}

    def test_extract_tool_calls_with_json_string_arguments(self):
        """Test extracting tool calls with JSON string arguments."""
        mock_tc = MagicMock()
        mock_tc.id = "call_456"
        mock_tc.function.name = "test_function"
        mock_tc.function.arguments = '{"arg1": "value1"}'
        
        result = LLMProvider._extract_tool_calls([mock_tc])
        
        assert len(result) == 1
        assert result[0].arguments == {"arg1": "value1"}

    def test_extract_tool_calls_with_invalid_json(self):
        """Test extracting tool calls with invalid JSON."""
        mock_tc = MagicMock()
        mock_tc.id = "call_789"
        mock_tc.function.name = "test_function"
        mock_tc.function.arguments = "invalid json"
        
        result = LLMProvider._extract_tool_calls([mock_tc])
        
        assert len(result) == 1
        assert result[0].arguments == {}


class TestLLMProviderChat:
    """Test chat method."""

    @pytest.mark.asyncio
    async def test_chat_non_streaming_success(self):
        """Test successful non-streaming chat."""
        provider = LLMProvider()
        messages = [{"role": "user", "content": "Hello"}]
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hi there"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        
        with patch("mdpilot.llm.provider.litellm.acompletion", new_callable=AsyncMock) as mock_completion:
            mock_completion.return_value = mock_response
            
            result = await provider.chat(messages, stream=False)
            
            assert isinstance(result, LLMResponse)
            assert result.content == "Hi there"
            assert result.tool_calls == []
            assert result.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_chat_with_retry_on_rate_limit(self):
        """Test chat retries on rate limit error."""
        provider = LLMProvider(max_retries=2)
        messages = [{"role": "user", "content": "Hello"}]
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Success"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        
        with patch("mdpilot.llm.provider.litellm.acompletion", new_callable=AsyncMock) as mock_completion:
            with patch("mdpilot.llm.provider.litellm.RateLimitError", Exception):
                mock_completion.side_effect = [
                    Exception("Rate limit"),
                    mock_response
                ]
                
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    result = await provider.chat(messages, stream=False)
                    
                    assert result.content == "Success"
                    assert mock_completion.call_count == 2


class TestLLMProviderStreaming:
    """Test streaming chat functionality."""

    @pytest.mark.asyncio
    async def test_chat_streaming_success(self):
        """Test successful streaming chat."""
        provider = LLMProvider()
        messages = [{"role": "user", "content": "Hello"}]
        
        # Mock streaming response
        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [MagicMock()]
        mock_chunk1.choices[0].delta = MagicMock(content="Hello", tool_calls=None)
        mock_chunk1.choices[0].finish_reason = None
        
        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [MagicMock()]
        mock_chunk2.choices[0].delta = MagicMock(content=" world", tool_calls=None)
        mock_chunk2.choices[0].finish_reason = "stop"
        
        async def mock_stream():
            yield mock_chunk1
            yield mock_chunk2
        
        with patch("mdpilot.llm.provider.litellm.acompletion", return_value=mock_stream()):
            chunks = []
            async for chunk in await provider.chat(messages, stream=True):
                chunks.append(chunk)
            
            assert len(chunks) == 2
            assert chunks[0].content == "Hello"
            assert chunks[1].content == " world"
            assert chunks[1].finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_chat_streaming_with_tool_calls(self):
        """Test streaming with tool calls."""
        provider = LLMProvider()
        messages = [{"role": "user", "content": "Use a tool"}]
        
        mock_func = MagicMock()
        mock_func.name = "test_tool"
        mock_func.arguments = {"arg": "value"}
        
        mock_tc = MagicMock()
        mock_tc.id = "call_123"
        mock_tc.function = mock_func
        
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta = MagicMock(content="", tool_calls=[mock_tc])
        mock_chunk.choices[0].finish_reason = "tool_calls"
        
        async def mock_stream():
            yield mock_chunk
        
        with patch("mdpilot.llm.provider.litellm.acompletion", return_value=mock_stream()):
            chunks = []
            async for chunk in await provider.chat(messages, stream=True):
                chunks.append(chunk)
            
            assert len(chunks) == 1
            assert len(chunks[0].tool_calls) == 1
            assert chunks[0].tool_calls[0].name == "test_tool"
            assert chunks[0].tool_calls[0].arguments == {"arg": "value"}

    @pytest.mark.asyncio
    async def test_chat_streaming_retry_on_rate_limit(self):
        """Test streaming retry on rate limit error."""
        provider = LLMProvider(max_retries=2)
        messages = [{"role": "user", "content": "Hello"}]
        
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta = MagicMock(content="Success", tool_calls=None)
        mock_chunk.choices[0].finish_reason = "stop"
        
        async def mock_stream_success():
            yield mock_chunk
        
        call_count = 0
        async def mock_acompletion(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise litellm.RateLimitError("Rate limit", llm_provider="test", model="test-model")
            return mock_stream_success()
        
        with patch("mdpilot.llm.provider.litellm.acompletion", side_effect=mock_acompletion):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                chunks = []
                async for chunk in await provider.chat(messages, stream=True):
                    chunks.append(chunk)
                
                assert len(chunks) == 1
                assert chunks[0].content == "Success"
                assert call_count == 2

    @pytest.mark.asyncio
    async def test_chat_streaming_timeout_error(self):
        """Test streaming timeout error handling."""
        provider = LLMProvider(max_retries=1)
        messages = [{"role": "user", "content": "Hello"}]
        
        async def mock_acompletion(**kwargs):
            raise litellm.Timeout("Timeout", model="test-model", llm_provider="test")
        
        with patch("mdpilot.llm.provider.litellm.acompletion", side_effect=mock_acompletion):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(litellm.Timeout):
                    async for _ in await provider.chat(messages, stream=True):
                        pass

    @pytest.mark.asyncio
    async def test_chat_streaming_api_connection_error(self):
        """Test streaming API connection error handling."""
        provider = LLMProvider(max_retries=1)
        messages = [{"role": "user", "content": "Hello"}]
        
        async def mock_acompletion(**kwargs):
            raise litellm.APIConnectionError("Connection failed", llm_provider="test", model="test-model")
        
        with patch("mdpilot.llm.provider.litellm.acompletion", side_effect=mock_acompletion):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(litellm.APIConnectionError):
                    async for _ in await provider.chat(messages, stream=True):
                        pass

    @pytest.mark.asyncio
    async def test_chat_streaming_authentication_error(self):
        """Test streaming authentication error (no retry)."""
        provider = LLMProvider()
        messages = [{"role": "user", "content": "Hello"}]
        
        async def mock_acompletion(**kwargs):
            raise litellm.AuthenticationError("Invalid API key", llm_provider="test", model="test-model")
        
        with patch("mdpilot.llm.provider.litellm.acompletion", side_effect=mock_acompletion):
            with pytest.raises(litellm.AuthenticationError):
                async for _ in await provider.chat(messages, stream=True):
                    pass

    @pytest.mark.asyncio
    async def test_chat_streaming_bad_request_error(self):
        """Test streaming bad request error (no retry)."""
        provider = LLMProvider()
        messages = [{"role": "user", "content": "Hello"}]
        
        async def mock_acompletion(**kwargs):
            raise litellm.BadRequestError("Invalid request", model="test-model", llm_provider="test")
        
        with patch("mdpilot.llm.provider.litellm.acompletion", side_effect=mock_acompletion):
            with pytest.raises(litellm.BadRequestError):
                async for _ in await provider.chat(messages, stream=True):
                    pass

    @pytest.mark.asyncio
    async def test_chat_streaming_unexpected_error(self):
        """Test streaming unexpected error handling."""
        provider = LLMProvider()
        messages = [{"role": "user", "content": "Hello"}]
        
        async def mock_acompletion(**kwargs):
            raise ValueError("Unexpected error")
        
        with patch("mdpilot.llm.provider.litellm.acompletion", side_effect=mock_acompletion):
            with pytest.raises(ValueError):
                async for _ in await provider.chat(messages, stream=True):
                    pass


class TestLLMProviderNonStreamingErrors:
    """Test non-streaming error handling."""

    @pytest.mark.asyncio
    async def test_chat_timeout_error(self):
        """Test timeout error with retry."""
        provider = LLMProvider(max_retries=1)
        messages = [{"role": "user", "content": "Hello"}]
        
        with patch("mdpilot.llm.provider.litellm.acompletion", new_callable=AsyncMock) as mock_completion:
            mock_completion.side_effect = litellm.Timeout("Timeout", model="test-model", llm_provider="test")
            
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(litellm.Timeout):
                    await provider.chat(messages, stream=False)
                
                assert mock_completion.call_count == 2  # Initial + 1 retry

    @pytest.mark.asyncio
    async def test_chat_api_connection_error(self):
        """Test API connection error with retry."""
        provider = LLMProvider(max_retries=1)
        messages = [{"role": "user", "content": "Hello"}]
        
        with patch("mdpilot.llm.provider.litellm.acompletion", new_callable=AsyncMock) as mock_completion:
            mock_completion.side_effect = litellm.APIConnectionError("Connection failed", llm_provider="test", model="test-model")
            
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(litellm.APIConnectionError):
                    await provider.chat(messages, stream=False)
                
                assert mock_completion.call_count == 2

    @pytest.mark.asyncio
    async def test_chat_authentication_error(self):
        """Test authentication error (no retry)."""
        provider = LLMProvider()
        messages = [{"role": "user", "content": "Hello"}]
        
        with patch("mdpilot.llm.provider.litellm.acompletion", new_callable=AsyncMock) as mock_completion:
            mock_completion.side_effect = litellm.AuthenticationError("Invalid API key", llm_provider="test", model="test-model")
            
            with pytest.raises(litellm.AuthenticationError):
                await provider.chat(messages, stream=False)
            
            assert mock_completion.call_count == 1  # No retry

    @pytest.mark.asyncio
    async def test_chat_bad_request_error(self):
        """Test bad request error (no retry)."""
        provider = LLMProvider()
        messages = [{"role": "user", "content": "Hello"}]
        
        with patch("mdpilot.llm.provider.litellm.acompletion", new_callable=AsyncMock) as mock_completion:
            mock_completion.side_effect = litellm.BadRequestError("Invalid request", model="test-model", llm_provider="test")
            
            with pytest.raises(litellm.BadRequestError):
                await provider.chat(messages, stream=False)
            
            assert mock_completion.call_count == 1

    @pytest.mark.asyncio
    async def test_chat_unexpected_error(self):
        """Test unexpected error handling."""
        provider = LLMProvider()
        messages = [{"role": "user", "content": "Hello"}]
        
        with patch("mdpilot.llm.provider.litellm.acompletion", new_callable=AsyncMock) as mock_completion:
            mock_completion.side_effect = ValueError("Unexpected error")
            
            with pytest.raises(ValueError):
                await provider.chat(messages, stream=False)
            
            assert mock_completion.call_count == 1


class TestLLMProviderChatOnce:
    """Test chat_once convenience method."""

    @pytest.mark.asyncio
    async def test_chat_once_success(self):
        """Test chat_once delegates to _chat_once_internal."""
        provider = LLMProvider()
        messages = [{"role": "user", "content": "Hello"}]
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock(content="Response", tool_calls=None)
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=20)
        
        with patch("mdpilot.llm.provider.litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
            result = await provider.chat_once(messages)
            
            assert isinstance(result, LLMResponse)
            assert result.content == "Response"
            assert result.usage_prompt_tokens == 10
            assert result.usage_completion_tokens == 20
