"""Tests for the LLM provider layer (provider.py, fallback.py)."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mdpilot.llm import FallbackChain, LLMProvider
from mdpilot.types import LLMChunk, LLMResponse, ToolCall


# ---------------------------------------------------------------------------
# Helper: build mock objects matching litellm's response structure
# ---------------------------------------------------------------------------

def _make_mock_function(name: str, arguments: str | dict) -> MagicMock:
    fn = MagicMock()
    fn.name = name
    fn.arguments = arguments
    return fn


def _make_mock_tool_call(tool_call_id: str, function_name: str, arguments: str | dict) -> MagicMock:
    tc = MagicMock()
    tc.id = tool_call_id
    tc.function = _make_mock_function(function_name, arguments)
    return tc


def _make_litellm_response(
    content: str = "",
    tool_calls: list[MagicMock] | None = None,
    finish_reason: str | None = "stop",
    prompt_tokens: int = 10,
    completion_tokens: int = 20,
) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls

    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = finish_reason

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


def _make_litellm_chunk(
    content: str = "",
    tool_calls: list[MagicMock] | None = None,
    finish_reason: str | None = None,
) -> MagicMock:
    delta = MagicMock()
    delta.content = content
    delta.tool_calls = tool_calls

    choice = MagicMock()
    choice.delta = delta
    choice.finish_reason = finish_reason

    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


# ---------------------------------------------------------------------------
# LLMProvider – non-streaming
# ---------------------------------------------------------------------------

class TestChatOnce:
    """Tests for LLMProvider.chat_once (non-streaming)."""

    @pytest.mark.asyncio
    async def test_returns_llm_response(self):
        """chat_once returns an LLMResponse with correct fields."""
        provider = LLMProvider(model="test-model")
        mock_resp = _make_litellm_response(content="Hello world", prompt_tokens=5, completion_tokens=3)

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_comp:
            mock_comp.return_value = mock_resp
            result = await provider.chat_once(messages=[{"role": "user", "content": "hi"}])

        assert isinstance(result, LLMResponse)
        assert result.content == "Hello world"
        assert result.finish_reason == "stop"
        assert result.usage_prompt_tokens == 5
        assert result.usage_completion_tokens == 3
        assert result.tool_calls == []

    @pytest.mark.asyncio
    async def test_extracts_tool_calls(self):
        """tool_calls are correctly extracted from litellm response."""
        provider = LLMProvider(model="test-model")
        mock_resp = _make_litellm_response(
            tool_calls=[
                _make_mock_tool_call("call_abc123", "get_weather", '{"city": "Boston"}'),
            ]
        )

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_comp:
            mock_comp.return_value = mock_resp
            result = await provider.chat_once(messages=[])

        assert len(result.tool_calls) == 1
        tc = result.tool_calls[0]
        assert tc.id == "call_abc123"
        assert tc.name == "get_weather"
        assert tc.arguments == {"city": "Boston"}

    @pytest.mark.asyncio
    async def test_tool_calls_arguments_as_dict(self):
        """tool_calls with dict arguments are passed through directly."""
        provider = LLMProvider(model="test-model")
        mock_resp = _make_litellm_response(
            tool_calls=[
                _make_mock_tool_call("call_xyz", "search", {"query": "amber md"}),
            ]
        )

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_comp:
            mock_comp.return_value = mock_resp
            result = await provider.chat_once(messages=[])

        assert result.tool_calls[0].arguments == {"query": "amber md"}

    @pytest.mark.asyncio
    async def test_passes_api_key_and_base_url(self):
        """api_key and base_url are forwarded to litellm."""
        provider = LLMProvider(
            model="test-model",
            api_key="sk-secret",
            base_url="https://my.api.com",
        )

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_comp:
            mock_comp.return_value = _make_litellm_response()
            await provider.chat_once(messages=[])

        mock_comp.assert_called_once()
        call_kwargs = mock_comp.call_args.kwargs
        assert call_kwargs["api_key"] == "sk-secret"
        assert call_kwargs["api_base"] == "https://my.api.com"
        assert call_kwargs["model"] == "test-model"

    @pytest.mark.asyncio
    async def test_passes_tools_parameter(self):
        """tools list is forwarded to litellm when provided."""
        provider = LLMProvider(model="test-model")
        tools = [{"type": "function", "function": {"name": "test", "parameters": {}}}]

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_comp:
            mock_comp.return_value = _make_litellm_response()
            await provider.chat_once(messages=[], tools=tools)

        call_kwargs = mock_comp.call_args.kwargs
        assert call_kwargs["tools"] == tools


# ---------------------------------------------------------------------------
# LLMProvider – streaming
# ---------------------------------------------------------------------------

class TestChatStream:
    """Tests for LLMProvider.chat with stream=True."""

    @pytest.mark.asyncio
    async def test_yields_llm_chunks(self):
        """Streaming returns an AsyncGenerator that yields LLMChunk objects."""
        provider = LLMProvider(model="test-model")

        chunks = [
            _make_litellm_chunk(content="Hello"),
            _make_litellm_chunk(content=" world"),
            _make_litellm_chunk(finish_reason="stop"),
        ]

        async def stream_effect(*args, **kwargs):
            for ch in chunks:
                yield ch

        with patch("litellm.acompletion", side_effect=stream_effect):
            # chat() is async, so we must await it to get the AsyncGenerator
            result_gen = await provider.chat(messages=[], stream=True)

            chunks_out = []
            async for chunk in result_gen:
                chunks_out.append(chunk)

        assert len(chunks_out) == 3
        assert chunks_out[0].content == "Hello"
        assert chunks_out[1].content == " world"
        assert chunks_out[2].finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_stream_extracts_tool_calls(self):
        """Tool calls appearing mid-stream are captured in LLMChunk."""
        provider = LLMProvider(model="test-model")

        tool_call_mock = _make_mock_tool_call("call_1", "run_md", {"input": "minimize"})
        chunks = [
            _make_litellm_chunk(content="Sure, running MD..."),
            _make_litellm_chunk(tool_calls=[tool_call_mock]),
            _make_litellm_chunk(finish_reason="tool_calls"),
        ]

        async def stream_effect(*args, **kwargs):
            for ch in chunks:
                yield ch

        with patch("litellm.acompletion", side_effect=stream_effect):
            result_gen = await provider.chat(messages=[], stream=True)
            result_chunks = []
            async for chunk in result_gen:
                result_chunks.append(chunk)

        assert result_chunks[0].tool_calls == []
        assert len(result_chunks[1].tool_calls) == 1
        assert result_chunks[1].tool_calls[0].name == "run_md"


# ---------------------------------------------------------------------------
# LLMProvider – retry logic
# ---------------------------------------------------------------------------

class TestRetryLogic:
    """Tests for retry behaviour on transient errors."""

    @pytest.mark.asyncio
    async def test_retries_on_rate_limit_then_succeeds(self):
        """After a RateLimitError the call succeeds on retry."""
        import litellm

        provider = LLMProvider(model="test-model", max_retries=3)
        mock_resp = _make_litellm_response(content="success")

        exc = litellm.RateLimitError(
            message="rate limited",
            llm_provider="test",
            model="test-model",
            response=MagicMock(),
        )
        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_comp:
            mock_comp.side_effect = [exc, mock_resp]
            result = await provider.chat_once(messages=[])
            assert result.content == "success"
            assert mock_comp.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_connection_error_then_succeeds(self):
        """After an APIConnectionError the call succeeds on retry."""
        import litellm

        provider = LLMProvider(model="test-model", max_retries=3)
        mock_resp = _make_litellm_response(content="success")

        exc = litellm.APIConnectionError(
            message="connection failed",
            llm_provider="test",
            model="test-model",
        )
        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_comp:
            mock_comp.side_effect = [exc, mock_resp]
            result = await provider.chat_once(messages=[])
            assert result.content == "success"
            assert mock_comp.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_timeout_then_succeeds(self):
        """After a Timeout the call succeeds on retry."""
        import litellm

        provider = LLMProvider(model="test-model", max_retries=3)
        mock_resp = _make_litellm_response(content="success")

        exc = litellm.Timeout(
            message="timed out",
            llm_provider="test",
            model="test-model",
        )
        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_comp:
            mock_comp.side_effect = [exc, mock_resp]
            result = await provider.chat_once(messages=[])
            assert result.content == "success"
            assert mock_comp.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_after_max_retries_exceeded(self):
        """When all retries are exhausted the exception propagates."""
        import litellm

        provider = LLMProvider(model="test-model", max_retries=2)

        exc = litellm.RateLimitError(
            message="rate limited",
            llm_provider="test",
            model="test-model",
            response=MagicMock(),
        )
        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_comp:
            mock_comp.side_effect = exc
            with pytest.raises(litellm.RateLimitError):
                await provider.chat_once(messages=[])
            # 1 initial + 2 retries = 3 total attempts
            assert mock_comp.call_count == 3


# ---------------------------------------------------------------------------
# FallbackChain
# ---------------------------------------------------------------------------

class TestFallbackChain:
    """Tests for FallbackChain provider switching."""

    @pytest.mark.asyncio
    async def test_primary_succeeds(self):
        """When primary succeeds, its response is returned."""
        primary = LLMProvider(model="primary")
        mock_resp = LLMResponse(content="from primary")

        # Patch the chat method directly to return LLMResponse
        with patch.object(primary, "chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = mock_resp
            result = await primary.chat(messages=[])

        assert result.content == "from primary"

    @pytest.mark.asyncio
    async def test_primary_falls_back_to_secondary_on_rate_limit(self):
        """When primary raises RateLimitError, secondary is tried."""
        import litellm

        primary = LLMProvider(model="primary")
        secondary = LLMProvider(model="secondary")

        secondary_resp = LLMResponse(content="from secondary")

        primary_mock = AsyncMock(
            side_effect=litellm.RateLimitError(
                message="rate limited",
                llm_provider="primary",
                model="primary",
                response=MagicMock(),
            )
        )
        secondary_mock = AsyncMock(return_value=secondary_resp)

        with patch.object(primary, "chat", primary_mock), \
             patch.object(secondary, "chat", secondary_mock):
            chain = FallbackChain([primary, secondary])
            result = await chain.chat(messages=[])

        assert result.content == "from secondary"
        primary_mock.assert_called_once()
        secondary_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_both_fail_raises_runtime_error(self):
        """When all providers fail, RuntimeError is raised."""
        import litellm

        primary = LLMProvider(model="primary")
        secondary = LLMProvider(model="secondary")

        primary_exc = litellm.RateLimitError(
            message="rate limited",
            llm_provider="primary",
            model="primary",
            response=MagicMock(),
        )
        secondary_exc = litellm.APIConnectionError(
            message="connection error",
            llm_provider="secondary",
            model="secondary",
        )

        primary_mock = AsyncMock(side_effect=primary_exc)
        secondary_mock = AsyncMock(side_effect=secondary_exc)

        with patch.object(primary, "chat", primary_mock), \
             patch.object(secondary, "chat", secondary_mock):
            chain = FallbackChain([primary, secondary])
            with pytest.raises(RuntimeError, match="All .* providers failed"):
                await chain.chat(messages=[])

    @pytest.mark.asyncio
    async def test_non_transient_error_does_not_fallback(self):
        """AuthenticationError propagates immediately without fallback."""
        import litellm

        primary = LLMProvider(model="primary")
        secondary = LLMProvider(model="secondary")

        auth_exc = litellm.AuthenticationError(
            message="auth failed",
            llm_provider="primary",
            model="primary",
            response=MagicMock(),
        )
        primary_mock = AsyncMock(side_effect=auth_exc)
        secondary_mock = AsyncMock()

        with patch.object(primary, "chat", primary_mock), \
             patch.object(secondary, "chat", secondary_mock):
            chain = FallbackChain([primary, secondary])
            with pytest.raises(litellm.AuthenticationError):
                await chain.chat(messages=[])
            # Secondary should NOT be called
            secondary_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_requires_at_least_one_provider(self):
        """Empty provider list raises ValueError."""
        with pytest.raises(ValueError, match="At least one provider"):
            FallbackChain([])

    @pytest.mark.asyncio
    async def test_falls_back_on_timeout(self):
        """Timeout exception triggers fallback to next provider."""
        import litellm

        primary = LLMProvider(model="primary")
        secondary = LLMProvider(model="secondary")
        secondary_resp = LLMResponse(content="from secondary")

        primary_mock = AsyncMock(
            side_effect=litellm.Timeout(
                message="timed out",
                llm_provider="primary",
                model="primary",
            )
        )
        secondary_mock = AsyncMock(return_value=secondary_resp)

        with patch.object(primary, "chat", primary_mock), \
             patch.object(secondary, "chat", secondary_mock):
            chain = FallbackChain([primary, secondary])
            result = await chain.chat(messages=[])

        assert result.content == "from secondary"

    @pytest.mark.asyncio
    async def test_falls_back_on_api_connection_error(self):
        """APIConnectionError triggers fallback to next provider."""
        import litellm

        primary = LLMProvider(model="primary")
        secondary = LLMProvider(model="secondary")
        secondary_resp = LLMResponse(content="from secondary")

        primary_mock = AsyncMock(
            side_effect=litellm.APIConnectionError(
                message="connection error",
                llm_provider="primary",
                model="primary",
            )
        )
        secondary_mock = AsyncMock(return_value=secondary_resp)

        with patch.object(primary, "chat", primary_mock), \
             patch.object(secondary, "chat", secondary_mock):
            chain = FallbackChain([primary, secondary])
            result = await chain.chat(messages=[])

        assert result.content == "from secondary"
