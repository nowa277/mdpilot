"""LLM provider wrapping litellm for unified chat completions.

Supports both streaming and non-streaming modes, automatic retries on
transient errors, and tool-calling (function-calling) via the OpenAI schema.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

import litellm

from mdpilot.types import LLMChunk, LLMResponse, ToolCall

logger = logging.getLogger(__name__)


class LLMProvider:
    """Wraps litellm to provide a unified chat completion interface.

    Parameters
    ----------
    model : str
          Model identifier understood by litellm (e.g. ``MiniMax-M2.7-highspeed``).
    api_key : str | None
        Optional API key override.  When *None*, litellm reads the standard
        environment variables.
    base_url : str | None
        Optional base URL override for the provider endpoint.
    temperature : float
        Sampling temperature.
    max_tokens : int
        Maximum tokens in the completion.
    timeout : int
        Request timeout in seconds.
    max_retries : int
        Number of retry attempts on transient errors (rate-limit / timeout).
    """

    def __init__(
        self,
        model: str = "MiniMax-M2.7-highspeed",
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 32768,
        timeout: int = 120,
        max_retries: int = 3,
        custom_llm_provider: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        self.custom_llm_provider = custom_llm_provider

        # Ensure model has provider prefix so LiteLLM routes correctly.
        # When custom_llm_provider is set (e.g. "openai"), prepend it as a
        # prefix so that *every* internal LiteLLM call uses the right provider —
        # some code paths (streaming, plan generation) may ignore the
        # ``custom_llm_provider`` kwarg but always respect the model prefix.
        if custom_llm_provider and "/" not in model:
            self.model = f"{custom_llm_provider}/{model}"
        else:
            self.model = model

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_kwargs(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        stream: bool,
    ) -> dict:
        """Build the keyword arguments dict for litellm.acompletion."""
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "stream": stream,
        }
        if self.api_key is not None:
            # Convert SecretStr to plain string for LiteLLM
            from pydantic import SecretStr
            api_key_str = self.api_key.get_secret_value() if isinstance(self.api_key, SecretStr) else self.api_key
            kwargs["api_key"] = api_key_str
        if self.base_url is not None:
            kwargs["api_base"] = self.base_url
        if tools is not None:
            kwargs["tools"] = tools
        if self.custom_llm_provider is not None:
            kwargs["custom_llm_provider"] = self.custom_llm_provider
        return kwargs

    @staticmethod
    def _extract_tool_calls(
        raw_tool_calls: list | None,
    ) -> list[ToolCall]:
        """Convert litellm tool-call objects to our ToolCall dataclass.

        For streaming deltas, arguments may be incomplete JSON fragments.
        These are preserved via the ``__streaming_raw__`` key so that
        ``_consume_stream`` can concatenate and parse them after the stream ends.
        """
        if not raw_tool_calls:
            return []
        import json
        result: list[ToolCall] = []
        for tc in raw_tool_calls:
            func = getattr(tc, "function", None)
            if func is None:
                continue
            args: dict = {}
            if hasattr(func, "arguments") and isinstance(func.arguments, dict):
                args = func.arguments
            elif hasattr(func, "arguments") and isinstance(func.arguments, str):
                raw = func.arguments
                if raw:
                    try:
                        args = json.loads(raw)
                    except json.JSONDecodeError:
                        # Incomplete JSON from a streaming delta — preserve raw
                        args = {"__streaming_raw__": raw}
            name = getattr(func, "name", "") or ""
            tc_id = getattr(tc, "id", "") or ""
            result.append(ToolCall(id=tc_id, name=name, arguments=args))
        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
    ) -> AsyncGenerator[LLMChunk, None] | LLMResponse:
        """Unified chat interface.

        If *stream* is ``True``, returns an ``AsyncGenerator[LLMChunk]``.
        If *stream* is ``False``, returns an ``LLMResponse``.
        """
        if stream:
            return self._chat_stream(messages, tools)
        return await self._chat_once_internal(messages, tools)

    async def _chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None,
    ) -> AsyncGenerator[LLMChunk, None]:
        """Streaming chat: yield LLMChunk objects for each delta."""
        kwargs = self._build_kwargs(messages, tools, stream=True)

        retries = 0
        while retries <= self.max_retries:
            try:
                logger.debug(f"Starting streaming chat with model {self.model} (attempt {retries + 1}/{self.max_retries + 1})")
                response = await litellm.acompletion(**kwargs)
                async for chunk in response:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta is None:
                        continue
                    content = getattr(delta, "content", "") or ""
                    raw_tcs = getattr(delta, "tool_calls", None)
                    tc_list = self._extract_tool_calls(raw_tcs) if raw_tcs else []
                    finish = getattr(chunk.choices[0], "finish_reason", None)
                    yield LLMChunk(content=content, tool_calls=tc_list, finish_reason=finish)
                logger.debug(f"Streaming chat completed successfully")
                return
            except litellm.RateLimitError as exc:
                retries += 1
                backoff = 2 ** retries
                logger.warning(
                    f"Rate limit error from {self.model} (attempt {retries}/{self.max_retries + 1}): {exc}. "
                    f"Retrying in {backoff}s..."
                )
                if retries > self.max_retries:
                    logger.error(f"Rate limit error: all {self.max_retries + 1} attempts exhausted")
                    raise
                await asyncio.sleep(backoff)
            except litellm.Timeout as exc:
                retries += 1
                backoff = 2 ** retries
                logger.warning(
                    f"Timeout from {self.model} after {self.timeout}s (attempt {retries}/{self.max_retries + 1}): {exc}. "
                    f"Retrying in {backoff}s..."
                )
                if retries > self.max_retries:
                    logger.error(f"Timeout error: all {self.max_retries + 1} attempts exhausted")
                    raise
                await asyncio.sleep(backoff)
            except litellm.APIConnectionError as exc:
                retries += 1
                backoff = 2 ** retries
                logger.warning(
                    f"API connection error to {self.model} (attempt {retries}/{self.max_retries + 1}): {exc}. "
                    f"Retrying in {backoff}s..."
                )
                if retries > self.max_retries:
                    logger.error(f"API connection error: all {self.max_retries + 1} attempts exhausted")
                    raise
                await asyncio.sleep(backoff)
            except litellm.AuthenticationError as exc:
                logger.error(f"Authentication error with {self.model}: {exc}. Check API key.")
                raise
            except litellm.BadRequestError as exc:
                logger.error(f"Bad request to {self.model}: {exc}. Check request parameters.")
                raise
            except Exception as exc:
                logger.exception(f"Unexpected error during streaming chat with {self.model}: {exc}")
                raise

    async def _chat_once_internal(
        self,
        messages: list[dict],
        tools: list[dict] | None,
    ) -> LLMResponse:
        """Non-streaming implementation with retry logic."""
        kwargs = self._build_kwargs(messages, tools, stream=False)

        retries = 0
        response = None
        while retries <= self.max_retries:
            try:
                logger.debug(f"Starting non-streaming chat with model {self.model} (attempt {retries + 1}/{self.max_retries + 1})")
                response = await litellm.acompletion(**kwargs)
                logger.debug(f"Non-streaming chat completed successfully")
                break
            except litellm.RateLimitError as exc:
                retries += 1
                backoff = 2 ** retries
                logger.warning(
                    f"Rate limit error from {self.model} (attempt {retries}/{self.max_retries + 1}): {exc}. "
                    f"Retrying in {backoff}s..."
                )
                if retries > self.max_retries:
                    logger.error(f"Rate limit error: all {self.max_retries + 1} attempts exhausted")
                    raise
                await asyncio.sleep(backoff)
            except litellm.Timeout as exc:
                retries += 1
                backoff = 2 ** retries
                logger.warning(
                    f"Timeout from {self.model} after {self.timeout}s (attempt {retries}/{self.max_retries + 1}): {exc}. "
                    f"Retrying in {backoff}s..."
                )
                if retries > self.max_retries:
                    logger.error(f"Timeout error: all {self.max_retries + 1} attempts exhausted")
                    raise
                await asyncio.sleep(backoff)
            except litellm.APIConnectionError as exc:
                retries += 1
                backoff = 2 ** retries
                logger.warning(
                    f"API connection error to {self.model} (attempt {retries}/{self.max_retries + 1}): {exc}. "
                    f"Retrying in {backoff}s..."
                )
                if retries > self.max_retries:
                    logger.error(f"API connection error: all {self.max_retries + 1} attempts exhausted")
                    raise
                await asyncio.sleep(backoff)
            except litellm.AuthenticationError as exc:
                logger.error(f"Authentication error with {self.model}: {exc}. Check API key.")
                raise
            except litellm.BadRequestError as exc:
                logger.error(f"Bad request to {self.model}: {exc}. Check request parameters.")
                raise
            except Exception as exc:
                logger.exception(f"Unexpected error during non-streaming chat with {self.model}: {exc}")
                raise

        if response is None:
            # Should not reach here, but for type-safety:
            raise RuntimeError("All retry attempts exhausted without response")

        # Parse the response
        choice = response.choices[0]
        content = getattr(choice.message, "content", "") or ""
        raw_tcs = getattr(choice.message, "tool_calls", None)
        tool_calls = self._extract_tool_calls(raw_tcs) if raw_tcs else []
        finish_reason = getattr(choice, "finish_reason", None)

        usage_prompt = getattr(response.usage, "prompt_tokens", 0) or 0
        usage_completion = getattr(response.usage, "completion_tokens", 0) or 0

        logger.info(
            f"LLM response: {usage_prompt} prompt tokens, {usage_completion} completion tokens, "
            f"finish_reason={finish_reason}"
        )

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage_prompt_tokens=usage_prompt,
            usage_completion_tokens=usage_completion,
        )

    async def chat_once(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Non-streaming convenience method (delegates to _chat_once_internal)."""
        return await self._chat_once_internal(messages, tools)
