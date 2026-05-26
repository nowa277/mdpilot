"""Fallback chain for LLM providers.

When the primary provider fails due to a transient error (rate-limit, timeout,
connection), the chain automatically tries the next provider in line.

Only ``RateLimitError``, ``APIConnectionError``, and ``Timeout`` are considered
transient — other exceptions propagate immediately.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

import litellm

from mdpilot.llm.provider import LLMProvider
from mdpilot.types import LLMChunk, LLMResponse

logger = logging.getLogger(__name__)


class FallbackChain:
    """Try each provider in order; fall back on transient errors.

    Parameters
    ----------
    providers : list[LLMProvider]
        Ordered list of providers.  The first is the primary.
    """

    def __init__(self, providers: list[LLMProvider]) -> None:
        if not providers:
            raise ValueError("At least one provider is required")
        self.providers = providers

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
    ) -> AsyncGenerator[LLMChunk, None] | LLMResponse:
        """Try primary provider, fallback to next on transient error.

        Returns
        -------
        AsyncGenerator[LLMChunk, None] | LLMResponse
            The successful response (streaming or non-streaming).

        Raises
        ------
        RuntimeError
            If *all* providers fail.
        """
        last_exc: Exception | None = None
        for idx, provider in enumerate(self.providers):
            try:
                logger.debug(f"Trying provider {idx + 1}/{len(self.providers)}: {provider.model}")
                result = await provider.chat(messages, tools, stream=stream)
                if idx > 0:
                    logger.info(f"Fallback successful: using provider {idx + 1} ({provider.model})")
                return result
            except (litellm.RateLimitError, litellm.APIConnectionError, litellm.Timeout) as exc:
                # Transient errors: try next provider
                last_exc = exc
                logger.warning(
                    f"Provider {idx + 1}/{len(self.providers)} ({provider.model}) failed with transient error: {exc}. "
                    f"Trying next provider..."
                )
                continue
            except Exception as exc:
                # Non-transient errors: propagate immediately
                logger.error(f"Provider {idx + 1}/{len(self.providers)} ({provider.model}) failed with non-transient error: {exc}")
                raise

        error_msg = f"All {len(self.providers)} providers failed"
        if last_exc:
            error_msg += f". Last error: {last_exc}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
