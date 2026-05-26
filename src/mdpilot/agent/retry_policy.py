"""Retry policies for LLM and tool execution."""

from __future__ import annotations

import logging

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


# LLM call retry policy: 3 attempts with exponential backoff
llm_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


# Tool execution retry policy: 2 attempts with shorter backoff
tool_retry = retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


def is_recoverable_error(exc: Exception) -> bool:
    """Check if an error is recoverable and should be retried.
    
    Args:
        exc: Exception to check
        
    Returns:
        True if error is recoverable, False otherwise
    """
    recoverable_types = (
        ConnectionError,
        TimeoutError,
    )
    return isinstance(exc, recoverable_types)
