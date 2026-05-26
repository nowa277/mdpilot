"""LLM caller with retry logic."""

from __future__ import annotations

from typing import Any

from mdpilot.llm import LLMProvider
from mdpilot.types import LLMResponse

from .retry_policy import llm_retry


class LLMCaller:
    """Wrapper for LLM provider with automatic retry on transient failures."""

    def __init__(self, provider: LLMProvider) -> None:
        """Initialize LLM caller.
        
        Args:
            provider: LLM provider instance
        """
        self._provider = provider

    @llm_retry
    async def call(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        """Call LLM with automatic retry on connection/timeout errors.
        
        Args:
            messages: Conversation messages
            tools: Available tools in OpenAI format
            
        Returns:
            LLM response
            
        Raises:
            Exception: After all retry attempts exhausted
        """
        return await self._provider.chat_once(messages, tools)
