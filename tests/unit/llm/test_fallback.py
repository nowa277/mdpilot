"""Tests for LLM fallback chain."""

from unittest.mock import AsyncMock, MagicMock, patch

import litellm
import pytest

from mdpilot.llm.fallback import FallbackChain
from mdpilot.llm.provider import LLMProvider
from mdpilot.types import LLMResponse


class TestFallbackChainInit:
    """Test FallbackChain initialization."""

    def test_initialization_with_providers(self):
        """Test initialization with provider list."""
        provider1 = LLMProvider(model="model1")
        provider2 = LLMProvider(model="model2")
        
        chain = FallbackChain([provider1, provider2])
        
        assert len(chain.providers) == 2
        assert chain.providers[0] == provider1
        assert chain.providers[1] == provider2

    def test_initialization_empty_providers_raises(self):
        """Test initialization with empty provider list raises ValueError."""
        with pytest.raises(ValueError, match="At least one provider is required"):
            FallbackChain([])


class TestFallbackChainChat:
    """Test fallback chain chat functionality."""

    @pytest.mark.asyncio
    async def test_primary_provider_success(self):
        """Test successful response from primary provider."""
        provider1 = LLMProvider(model="model1")
        provider2 = LLMProvider(model="model2")
        chain = FallbackChain([provider1, provider2])
        
        messages = [{"role": "user", "content": "Hello"}]
        mock_response = MagicMock(spec=LLMResponse)
        mock_response.content = "Response from primary"
        
        with patch.object(provider1, 'chat', new_callable=AsyncMock, return_value=mock_response):
            with patch.object(provider2, 'chat', new_callable=AsyncMock) as mock_p2:
                result = await chain.chat(messages, stream=False)
                
                assert result == mock_response
                mock_p2.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_on_rate_limit(self):
        """Test fallback to second provider on rate limit."""
        provider1 = LLMProvider(model="model1")
        provider2 = LLMProvider(model="model2")
        chain = FallbackChain([provider1, provider2])
        
        messages = [{"role": "user", "content": "Hello"}]
        mock_response = MagicMock(spec=LLMResponse)
        mock_response.content = "Response from fallback"
        
        with patch.object(provider1, 'chat', new_callable=AsyncMock) as mock_p1:
            mock_p1.side_effect = litellm.RateLimitError("Rate limit", llm_provider="test", model="model1")
            with patch.object(provider2, 'chat', new_callable=AsyncMock, return_value=mock_response):
                result = await chain.chat(messages, stream=False)
                
                assert result == mock_response

    @pytest.mark.asyncio
    async def test_fallback_on_timeout(self):
        """Test fallback to second provider on timeout."""
        provider1 = LLMProvider(model="model1")
        provider2 = LLMProvider(model="model2")
        chain = FallbackChain([provider1, provider2])
        
        messages = [{"role": "user", "content": "Hello"}]
        mock_response = MagicMock(spec=LLMResponse)
        
        with patch.object(provider1, 'chat', new_callable=AsyncMock) as mock_p1:
            mock_p1.side_effect = litellm.Timeout("Timeout", model="model1", llm_provider="test")
            with patch.object(provider2, 'chat', new_callable=AsyncMock, return_value=mock_response):
                result = await chain.chat(messages, stream=False)
                
                assert result == mock_response

    @pytest.mark.asyncio
    async def test_fallback_on_api_connection_error(self):
        """Test fallback to second provider on API connection error."""
        provider1 = LLMProvider(model="model1")
        provider2 = LLMProvider(model="model2")
        chain = FallbackChain([provider1, provider2])
        
        messages = [{"role": "user", "content": "Hello"}]
        mock_response = MagicMock(spec=LLMResponse)
        
        with patch.object(provider1, 'chat', new_callable=AsyncMock) as mock_p1:
            mock_p1.side_effect = litellm.APIConnectionError("Connection failed", llm_provider="test", model="model1")
            with patch.object(provider2, 'chat', new_callable=AsyncMock, return_value=mock_response):
                result = await chain.chat(messages, stream=False)
                
                assert result == mock_response

    @pytest.mark.asyncio
    async def test_non_transient_error_propagates(self):
        """Test non-transient errors propagate immediately."""
        provider1 = LLMProvider(model="model1")
        provider2 = LLMProvider(model="model2")
        chain = FallbackChain([provider1, provider2])
        
        messages = [{"role": "user", "content": "Hello"}]
        
        with patch.object(provider1, 'chat', new_callable=AsyncMock) as mock_p1:
            mock_p1.side_effect = litellm.AuthenticationError("Invalid API key", llm_provider="test", model="model1")
            with patch.object(provider2, 'chat', new_callable=AsyncMock) as mock_p2:
                with pytest.raises(litellm.AuthenticationError):
                    await chain.chat(messages, stream=False)
                
                mock_p2.assert_not_called()

    @pytest.mark.asyncio
    async def test_all_providers_fail_transient(self):
        """Test RuntimeError when all providers fail with transient errors."""
        provider1 = LLMProvider(model="model1")
        provider2 = LLMProvider(model="model2")
        chain = FallbackChain([provider1, provider2])
        
        messages = [{"role": "user", "content": "Hello"}]
        
        with patch.object(provider1, 'chat', new_callable=AsyncMock) as mock_p1:
            mock_p1.side_effect = litellm.RateLimitError("Rate limit", llm_provider="test", model="model1")
            with patch.object(provider2, 'chat', new_callable=AsyncMock) as mock_p2:
                mock_p2.side_effect = litellm.Timeout("Timeout", model="model2", llm_provider="test")
                
                with pytest.raises(RuntimeError, match="All 2 providers failed"):
                    await chain.chat(messages, stream=False)

    @pytest.mark.asyncio
    async def test_three_provider_chain(self):
        """Test fallback through three providers."""
        provider1 = LLMProvider(model="model1")
        provider2 = LLMProvider(model="model2")
        provider3 = LLMProvider(model="model3")
        chain = FallbackChain([provider1, provider2, provider3])
        
        messages = [{"role": "user", "content": "Hello"}]
        mock_response = MagicMock(spec=LLMResponse)
        
        with patch.object(provider1, 'chat', new_callable=AsyncMock) as mock_p1:
            mock_p1.side_effect = litellm.RateLimitError("Rate limit", llm_provider="test", model="model1")
            with patch.object(provider2, 'chat', new_callable=AsyncMock) as mock_p2:
                mock_p2.side_effect = litellm.Timeout("Timeout", model="model2", llm_provider="test")
                with patch.object(provider3, 'chat', new_callable=AsyncMock, return_value=mock_response):
                    result = await chain.chat(messages, stream=False)
                    
                    assert result == mock_response

    @pytest.mark.asyncio
    async def test_chat_with_tools(self):
        """Test fallback with tools parameter."""
        provider1 = LLMProvider(model="model1")
        provider2 = LLMProvider(model="model2")
        chain = FallbackChain([provider1, provider2])
        
        messages = [{"role": "user", "content": "Hello"}]
        tools = [{"type": "function", "function": {"name": "test_tool"}}]
        mock_response = MagicMock(spec=LLMResponse)
        
        with patch.object(provider1, 'chat', new_callable=AsyncMock) as mock_p1:
            mock_p1.side_effect = litellm.RateLimitError("Rate limit", llm_provider="test", model="model1")
            with patch.object(provider2, 'chat', new_callable=AsyncMock, return_value=mock_response) as mock_p2:
                result = await chain.chat(messages, tools=tools, stream=False)
                
                assert result == mock_response
                mock_p2.assert_called_once_with(messages, tools, stream=False)

    @pytest.mark.asyncio
    async def test_chat_streaming_mode(self):
        """Test fallback in streaming mode."""
        provider1 = LLMProvider(model="model1")
        provider2 = LLMProvider(model="model2")
        chain = FallbackChain([provider1, provider2])
        
        messages = [{"role": "user", "content": "Hello"}]
        
        async def mock_stream():
            yield MagicMock()
        
        with patch.object(provider1, 'chat', new_callable=AsyncMock) as mock_p1:
            mock_p1.side_effect = litellm.RateLimitError("Rate limit", llm_provider="test", model="model1")
            with patch.object(provider2, 'chat', new_callable=AsyncMock, return_value=mock_stream()) as mock_p2:
                result = await chain.chat(messages, stream=True)
                
                assert result is not None
                mock_p2.assert_called_once_with(messages, None, stream=True)
