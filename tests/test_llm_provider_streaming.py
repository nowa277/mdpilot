"""Tests for LLM provider streaming error handling and edge cases."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import litellm

from mdpilot.llm.provider import LLMProvider
from mdpilot.types import LLMChunk


class TestStreamingRetryLogic:
    """Test retry logic for streaming mode."""

    @pytest.mark.asyncio
    async def test_streaming_rate_limit_retry_succeeds(self, caplog):
        """Streaming should retry on rate limit error."""
        provider = LLMProvider(model="test-model", max_retries=2)

        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta = MagicMock()
        chunk.choices[0].delta.content = "success"
        chunk.choices[0].delta.tool_calls = None
        chunk.choices[0].finish_reason = "stop"

        call_count = 0

        async def mock_stream(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise litellm.RateLimitError(
                    message="Rate limit exceeded",
                    llm_provider="test",
                    model="test-model"
                )
            yield chunk

        with patch("litellm.acompletion", side_effect=mock_stream):
            with caplog.at_level(logging.WARNING):
                result_gen = await provider.chat([], stream=True)
                chunks = []
                async for c in result_gen:
                    chunks.append(c)

        assert len(chunks) == 1
        assert chunks[0].content == "success"
        assert call_count == 3
        assert "Rate limit error" in caplog.text
        assert "Retrying" in caplog.text

    @pytest.mark.asyncio
    async def test_streaming_rate_limit_exhausts_retries(self, caplog):
        """Streaming should fail after max retries on rate limit."""
        provider = LLMProvider(model="test-model", max_retries=1)

        async def mock_stream(**kwargs):
            raise litellm.RateLimitError(
                message="Rate limit exceeded",
                llm_provider="test",
                model="test-model"
            )

        with patch("litellm.acompletion", side_effect=mock_stream):
            with caplog.at_level(logging.ERROR):
                with pytest.raises(litellm.RateLimitError):
                    result_gen = await provider.chat([], stream=True)
                    async for _ in result_gen:
                        pass

        assert "all 2 attempts exhausted" in caplog.text

    @pytest.mark.asyncio
    async def test_streaming_timeout_retry_succeeds(self, caplog):
        """Streaming should retry on timeout error."""
        provider = LLMProvider(model="test-model", max_retries=1, timeout=30)

        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta = MagicMock()
        chunk.choices[0].delta.content = "success"
        chunk.choices[0].delta.tool_calls = None
        chunk.choices[0].finish_reason = "stop"

        call_count = 0

        async def mock_stream(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise litellm.Timeout(
                    message="Request timed out",
                    model="test-model",
                    llm_provider="test"
                )
            yield chunk

        with patch("litellm.acompletion", side_effect=mock_stream):
            with caplog.at_level(logging.WARNING):
                result_gen = await provider.chat([], stream=True)
                chunks = []
                async for c in result_gen:
                    chunks.append(c)

        assert len(chunks) == 1
        assert "Timeout" in caplog.text
        assert "after 30s" in caplog.text

    @pytest.mark.asyncio
    async def test_streaming_timeout_exhausts_retries(self, caplog):
        """Streaming should fail after max retries on timeout."""
        provider = LLMProvider(model="test-model", max_retries=1)

        async def mock_stream(**kwargs):
            raise litellm.Timeout(
                message="Request timed out",
                model="test-model",
                llm_provider="test"
            )

        with patch("litellm.acompletion", side_effect=mock_stream):
            with caplog.at_level(logging.ERROR):
                with pytest.raises(litellm.Timeout):
                    result_gen = await provider.chat([], stream=True)
                    async for _ in result_gen:
                        pass

        assert "all 2 attempts exhausted" in caplog.text

    @pytest.mark.asyncio
    async def test_streaming_connection_error_retry_succeeds(self, caplog):
        """Streaming should retry on API connection error."""
        provider = LLMProvider(model="test-model", max_retries=1)

        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta = MagicMock()
        chunk.choices[0].delta.content = "success"
        chunk.choices[0].delta.tool_calls = None
        chunk.choices[0].finish_reason = "stop"

        call_count = 0

        async def mock_stream(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise litellm.APIConnectionError(
                    message="Connection failed",
                    llm_provider="test",
                    model="test-model"
                )
            yield chunk

        with patch("litellm.acompletion", side_effect=mock_stream):
            with caplog.at_level(logging.WARNING):
                result_gen = await provider.chat([], stream=True)
                chunks = []
                async for c in result_gen:
                    chunks.append(c)

        assert len(chunks) == 1
        assert "API connection error" in caplog.text

    @pytest.mark.asyncio
    async def test_streaming_connection_error_exhausts_retries(self, caplog):
        """Streaming should fail after max retries on connection error."""
        provider = LLMProvider(model="test-model", max_retries=1)

        async def mock_stream(**kwargs):
            raise litellm.APIConnectionError(
                message="Connection failed",
                llm_provider="test",
                model="test-model"
            )

        with patch("litellm.acompletion", side_effect=mock_stream):
            with caplog.at_level(logging.ERROR):
                with pytest.raises(litellm.APIConnectionError):
                    result_gen = await provider.chat([], stream=True)
                    async for _ in result_gen:
                        pass

        assert "all 2 attempts exhausted" in caplog.text


class TestStreamingNonTransientErrors:
    """Test that non-transient errors fail immediately in streaming mode."""

    @pytest.mark.asyncio
    async def test_streaming_authentication_error_no_retry(self, caplog):
        """Streaming authentication error should fail immediately."""
        provider = LLMProvider(model="test-model", max_retries=3)

        async def mock_stream(**kwargs):
            raise litellm.AuthenticationError(
                message="Invalid API key",
                llm_provider="test",
                model="test-model"
            )

        with patch("litellm.acompletion", side_effect=mock_stream):
            with caplog.at_level(logging.ERROR):
                with pytest.raises(litellm.AuthenticationError):
                    result_gen = await provider.chat([], stream=True)
                    async for _ in result_gen:
                        pass

        assert "Authentication error" in caplog.text
        assert "Check API key" in caplog.text
        assert "Retrying" not in caplog.text

    @pytest.mark.asyncio
    async def test_streaming_bad_request_error_no_retry(self, caplog):
        """Streaming bad request error should fail immediately."""
        provider = LLMProvider(model="test-model", max_retries=3)

        async def mock_stream(**kwargs):
            raise litellm.BadRequestError(
                message="Invalid request parameters",
                llm_provider="test",
                model="test-model"
            )

        with patch("litellm.acompletion", side_effect=mock_stream):
            with caplog.at_level(logging.ERROR):
                with pytest.raises(litellm.BadRequestError):
                    result_gen = await provider.chat([], stream=True)
                    async for _ in result_gen:
                        pass

        assert "Bad request" in caplog.text
        assert "Check request parameters" in caplog.text
        assert "Retrying" not in caplog.text

    @pytest.mark.asyncio
    async def test_streaming_unexpected_error_no_retry(self, caplog):
        """Streaming unexpected error should fail immediately."""
        provider = LLMProvider(model="test-model", max_retries=3)

        async def mock_stream(**kwargs):
            raise ValueError("Unexpected error")

        with patch("litellm.acompletion", side_effect=mock_stream):
            with caplog.at_level(logging.ERROR):
                with pytest.raises(ValueError):
                    result_gen = await provider.chat([], stream=True)
                    async for _ in result_gen:
                        pass

        assert "Unexpected error during streaming chat" in caplog.text
        assert "Retrying" not in caplog.text


class TestStreamingLogging:
    """Test logging behavior in streaming mode."""

    @pytest.mark.asyncio
    async def test_streaming_debug_logging_on_start(self, caplog):
        """Streaming should log at DEBUG level when starting."""
        provider = LLMProvider(model="test-model")

        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta = MagicMock()
        chunk.choices[0].delta.content = "test"
        chunk.choices[0].delta.tool_calls = None
        chunk.choices[0].finish_reason = "stop"

        async def mock_stream(**kwargs):
            yield chunk

        with patch("litellm.acompletion", side_effect=mock_stream):
            with caplog.at_level(logging.DEBUG):
                result_gen = await provider.chat([], stream=True)
                async for _ in result_gen:
                    pass

        assert "Starting streaming chat" in caplog.text
        assert "test-model" in caplog.text
        assert "Streaming chat completed successfully" in caplog.text


class TestNonStreamingEdgeCases:
    """Test edge cases in non-streaming mode."""

    @pytest.mark.asyncio
    async def test_non_streaming_unexpected_error(self, caplog):
        """Non-streaming unexpected error should be logged and raised."""
        provider = LLMProvider(model="test-model", max_retries=3)

        async def mock_acompletion(**kwargs):
            raise ValueError("Unexpected error")

        with patch("litellm.acompletion", side_effect=mock_acompletion):
            with caplog.at_level(logging.ERROR):
                with pytest.raises(ValueError):
                    await provider.chat_once([])

        assert "Unexpected error during non-streaming chat" in caplog.text

    @pytest.mark.asyncio
    async def test_non_streaming_none_response_after_retries(self):
        """Non-streaming should raise RuntimeError if response is None after retries."""
        provider = LLMProvider(model="test-model", max_retries=0)

        # This is a pathological case that shouldn't happen in practice
        # but we test the safety check
        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_comp:
            # Mock to return None (shouldn't happen but tests line 272-274)
            mock_comp.return_value = None

            with pytest.raises(RuntimeError, match="All retry attempts exhausted without response"):
                await provider.chat_once([])

    @pytest.mark.asyncio
    async def test_non_streaming_timeout_exhausts_all_retries(self, caplog):
        """Non-streaming timeout should exhaust all retries and log error."""
        provider = LLMProvider(model="test-model", max_retries=2, timeout=30)

        async def mock_acompletion(**kwargs):
            raise litellm.Timeout(
                message="Request timed out",
                model="test-model",
                llm_provider="test"
            )

        with patch("litellm.acompletion", side_effect=mock_acompletion):
            with caplog.at_level(logging.ERROR):
                with pytest.raises(litellm.Timeout):
                    await provider.chat_once([])

        # Should see the final error log after all retries exhausted
        assert "Timeout error: all 3 attempts exhausted" in caplog.text

    @pytest.mark.asyncio
    async def test_non_streaming_connection_error_exhausts_all_retries(self, caplog):
        """Non-streaming connection error should exhaust all retries and log error."""
        provider = LLMProvider(model="test-model", max_retries=2)

        async def mock_acompletion(**kwargs):
            raise litellm.APIConnectionError(
                message="Connection failed",
                llm_provider="test",
                model="test-model"
            )

        with patch("litellm.acompletion", side_effect=mock_acompletion):
            with caplog.at_level(logging.ERROR):
                with pytest.raises(litellm.APIConnectionError):
                    await provider.chat_once([])

        # Should see the final error log after all retries exhausted
        assert "API connection error: all 3 attempts exhausted" in caplog.text
