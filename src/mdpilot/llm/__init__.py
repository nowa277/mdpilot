"""LLM provider sub-package for mdpilot.

Re-exports LLMProvider and FallbackChain for convenience.
"""

from __future__ import annotations

from mdpilot.llm.fallback import FallbackChain
from mdpilot.llm.provider import LLMProvider

__all__ = ["LLMProvider", "FallbackChain"]
