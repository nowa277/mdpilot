"""Tests for LLM provider error handling and retry logic."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import litellm

from mdpilot.llm.provider import LLMProvider
from mdpilot.llm.fallback import FallbackChain
from mdpilot.types import LLMResponse


class TestLLMProviderRetryLogic:
    """Test retry logic for transient errors."""

    @pytest.mark.asyncio
    async def test_rate_limit_retry_succeeds(self, caplog):
        """Rate limit error should retry with exponential backoff."""
        provider = LLMProvider(model="test-model", max_retries=2)

        # Mock litellm to fail twice then succeed
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "success"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20

        call_count = 0
        async def mock_acompletion(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise litellm.RateLimitError(
                    message="Rate limit exceeded",
                    llm_provider="test",
                    model="test-model"
                )
            return mock_response

        with patch("litellm.acompletion", side_effect=mock_acompletion):
            with caplog.at_level(logging.WARNING):
                result = await provider.chat_once([{"role": "user", "content": "test"}])

        assert result.content == "success"
        assert call_count == 3
        assert "Rate limit error" in caplog.text
        assert "Retrying" in caplog.text

    @pytest.mark.asyncio
    async def test_rate_limit_exhausts_retries(self, caplog):
        """Rate limit error should fail after max retries."""
        provider = LLMProvider(model="test-model", max_retries=1)

        async def mock_acompletion(**kwargs):
            raise litellm.RateLimitError(
                message="Rate limit exceeded",
                llm_provider="test",
                model="test-model"
            )

        with patch("litellm.acompletion", side_effect=mock_acompletion):
            with caplog.at_level(logging.ERROR):
                with pytest.raises(litellm.RateLimitError):
                    await provider.chat_once([{"role": "user", "content": "test"}])

        assert "all 2 attempts exhausted" in caplog.text

    @pytest.mark.asyncio
    async def test_timeout_retry_succeeds(self, caplog):
        """Timeout error should retry with exponential backoff."""
        provider = LLMProvider(model="test-model", max_retries=2, timeout=30)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "success"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20

        call_count = 0
        async def mock_acompletion(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise litellm.Timeout(
                    message="Request timed out",
                    model="test-model",
                    llm_provider="test"
                )
            return mock_response

        with patch("litellm.acompletion", side_effect=mock_acompletion):
            with caplog.at_level(logging.WARNING):
                result = await provider.chat_once([{"role": "user", "content": "test"}])

        assert result.content == "success"
        assert call_count == 2
        assert "Timeout" in caplog.text
        assert "after 30s" in caplog.text

    @pytest.mark.asyncio
    async def test_connection_error_retry_succeeds(self, caplog):
        """API connection error should retry."""
        provider = LLMProvider(model="test-model", max_retries=1)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "success"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20

        call_count = 0
        async def mock_acompletion(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise litellm.APIConnectionError(
                    message="Connection failed",
                    llm_provider="test",
                    model="test-model"
                )
            return mock_response

        with patch("litellm.acompletion", side_effect=mock_acompletion):
            with caplog.at_level(logging.WARNING):
                result = await provider.chat_once([{"role": "user", "content": "test"}])

        assert result.content == "success"
        assert "API connection error" in caplog.text


class TestLLMProviderNonTransientErrors:
    """Test that non-transient errors fail immediately without retry."""

    @pytest.mark.asyncio
    async def test_authentication_error_no_retry(self, caplog):
        """Authentication error should fail immediately."""
        provider = LLMProvider(model="test-model", max_retries=3)

        async def mock_acompletion(**kwargs):
            raise litellm.AuthenticationError(
                message="Invalid API key",
                llm_provider="test",
                model="test-model"
            )

        with patch("litellm.acompletion", side_effect=mock_acompletion):
            with caplog.at_level(logging.ERROR):
                with pytest.raises(litellm.AuthenticationError):
                    await provider.chat_once([{"role": "user", "content": "test"}])

        assert "Authentication error" in caplog.text
        assert "Check API key" in caplog.text
        # Should not see retry messages
        assert "Retrying" not in caplog.text

    @pytest.mark.asyncio
    async def test_bad_request_error_no_retry(self, caplog):
        """Bad request error should fail immediately."""
        provider = LLMProvider(model="test-model", max_retries=3)

        async def mock_acompletion(**kwargs):
            raise litellm.BadRequestError(
                message="Invalid request parameters",
                llm_provider="test",
                model="test-model"
            )

        with patch("litellm.acompletion", side_effect=mock_acompletion):
            with caplog.at_level(logging.ERROR):
                with pytest.raises(litellm.BadRequestError):
                    await provider.chat_once([{"role": "user", "content": "test"}])

        assert "Bad request" in caplog.text
        assert "Check request parameters" in caplog.text
        assert "Retrying" not in caplog.text


class TestLLMProviderLogging:
    """Test logging behavior."""

    @pytest.mark.asyncio
    async def test_successful_request_logs_usage(self, caplog):
        """Successful request should log token usage."""
        provider = LLMProvider(model="test-model")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "test response"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50

        with patch("litellm.acompletion", return_value=mock_response):
            with caplog.at_level(logging.INFO):
                result = await provider.chat_once([{"role": "user", "content": "test"}])

        assert "100 prompt tokens" in caplog.text
        assert "50 completion tokens" in caplog.text
        assert "finish_reason=stop" in caplog.text

    @pytest.mark.asyncio
    async def test_debug_logging_on_start(self, caplog):
        """Should log at DEBUG level when starting request."""
        provider = LLMProvider(model="test-model")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "test"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 10

        with patch("litellm.acompletion", return_value=mock_response):
            with caplog.at_level(logging.DEBUG):
                await provider.chat_once([{"role": "user", "content": "test"}])

        assert "Starting non-streaming chat" in caplog.text
        assert "test-model" in caplog.text


class TestFallbackChain:
    """Test fallback chain behavior."""

    @pytest.mark.asyncio
    async def test_fallback_on_rate_limit(self, caplog):
        """Should fallback to second provider on rate limit."""
        provider1 = LLMProvider(model="primary-model", max_retries=0)
        provider2 = LLMProvider(model="fallback-model", max_retries=0)
        chain = FallbackChain([provider1, provider2])

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "fallback success"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20

        call_count = 0
        async def mock_acompletion(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise litellm.RateLimitError(
                    message="Rate limit on primary",
                    llm_provider="test",
                    model="primary-model"
                )
            return mock_response

        with patch("litellm.acompletion", side_effect=mock_acompletion):
            with caplog.at_level(logging.INFO):
                result = await chain.chat([{"role": "user", "content": "test"}])

        assert result.content == "fallback success"
        assert call_count == 2
        assert "Fallback successful" in caplog.text
        assert "fallback-model" in caplog.text

    @pytest.mark.asyncio
    async def test_all_providers_fail(self, caplog):
        """Should raise RuntimeError when all providers fail."""
        provider1 = LLMProvider(model="primary-model", max_retries=0)
        provider2 = LLMProvider(model="fallback-model", max_retries=0)
        chain = FallbackChain([provider1, provider2])

        async def mock_acompletion(**kwargs):
            raise litellm.RateLimitError(
                message="Rate limit",
                llm_provider="test",
                model="test-model"
            )

        with patch("litellm.acompletion", side_effect=mock_acompletion):
            with caplog.at_level(logging.ERROR):
                with pytest.raises(RuntimeError) as exc_info:
                    await chain.chat([{"role": "user", "content": "test"}])

        assert "All 2 providers failed" in str(exc_info.value)
        assert "All 2 providers failed" in caplog.text

    @pytest.mark.asyncio
    async def test_non_transient_error_no_fallback(self, caplog):
        """Non-transient errors should not trigger fallback."""
        provider1 = LLMProvider(model="primary-model", max_retries=0)
        provider2 = LLMProvider(model="fallback-model", max_retries=0)
        chain = FallbackChain([provider1, provider2])

        async def mock_acompletion(**kwargs):
            raise litellm.AuthenticationError(
                message="Invalid API key",
                llm_provider="test",
                model="test-model"
            )

        with patch("litellm.acompletion", side_effect=mock_acompletion):
            with caplog.at_level(logging.ERROR):
                with pytest.raises(litellm.AuthenticationError):
                    await chain.chat([{"role": "user", "content": "test"}])

        # Should only try first provider
        assert "non-transient error" in caplog.text

    @pytest.mark.asyncio
    async def test_primary_succeeds_no_fallback(self, caplog):
        """Should not try fallback if primary succeeds."""
        provider1 = LLMProvider(model="primary-model")
        provider2 = LLMProvider(model="fallback-model")
        chain = FallbackChain([provider1, provider2])

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "primary success"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20

        with patch("litellm.acompletion", return_value=mock_response):
            with caplog.at_level(logging.DEBUG):
                result = await chain.chat([{"role": "user", "content": "test"}])

        assert result.content == "primary success"
        # Should not see fallback messages
        assert "Fallback successful" not in caplog.text
        assert "provider 2" not in caplog.text.lower()


class TestExponentialBackoff:
    """Test exponential backoff timing."""

    @pytest.mark.asyncio
    async def test_backoff_timing(self):
        """Backoff should follow 2^n pattern."""
        provider = LLMProvider(model="test-model", max_retries=3)

        call_times = []

        async def mock_acompletion(**kwargs):
            call_times.append(asyncio.get_event_loop().time())
            if len(call_times) < 3:
                raise litellm.RateLimitError(
                    message="Rate limit",
                    llm_provider="test",
                    model="test-model"
                )

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "success"
            mock_response.choices[0].message.tool_calls = None
            mock_response.choices[0].finish_reason = "stop"
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 20
            return mock_response

        with patch("litellm.acompletion", side_effect=mock_acompletion):
            await provider.chat_once([{"role": "user", "content": "test"}])

        # Check that delays are approximately 2^1, 2^2 seconds
        assert len(call_times) == 3
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]

        # Allow some tolerance for timing
        assert 1.8 < delay1 < 2.2  # ~2 seconds
        assert 3.8 < delay2 < 4.2  # ~4 seconds
