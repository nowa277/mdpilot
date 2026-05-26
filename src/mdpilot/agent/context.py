"""ConversationContext — manages the rolling message history for the ReAct loop."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


class ConversationContext:
    """Rolling message history with accurate token estimation and truncation.

    Parameters
    ----------
    system_prompt : str
        The system prompt to prepend to every context.
    max_tokens : int
        Soft upper bound on estimated token count. When exceeded, older
        messages (excluding the system prompt) are dropped.
    """

    def __init__(self, system_prompt: str, max_tokens: int = 100_000) -> None:
        self._system_prompt = system_prompt
        self._max_tokens = max_tokens
        self._messages: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def messages(self) -> list[dict[str, Any]]:
        """Return the full message list suitable for the LLM API."""
        msgs = [{"role": "system", "content": self._system_prompt}]
        msgs.extend(self._messages)
        return msgs

    def add(
        self,
        role: str,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str | None = None,
    ) -> None:
        """Append a message to the history.

        Parameters
        ----------
        role : str
            One of ``"user"``, ``"assistant"``, or ``"tool"``.
        content : str
            The message text.
        tool_calls : list[dict] | None
            Optional list of tool-call objects (OpenAI format) to attach
            to an assistant message.
        tool_call_id : str | None
            When *role* is ``"tool"``, the ID of the tool call this result
            belongs to.
        """
        msg: dict[str, Any] = {"role": role, "content": content}
        if tool_calls is not None:
            msg["tool_calls"] = tool_calls
        if tool_call_id is not None:
            msg["tool_call_id"] = tool_call_id
        self._messages.append(msg)

    def update_system_prompt(self, new_prompt: str) -> None:
        """Replace the system prompt (e.g. after skill context injection).

        Parameters
        ----------
        new_prompt : str
            The new system prompt text.
        """
        self._system_prompt = new_prompt

    @property
    def token_count(self) -> int:
        """Estimated token count for the full context (system + history)."""
        system_tokens = self.estimate_tokens(self._system_prompt)
        history_tokens = sum(self.estimate_tokens(m.get("content", "") or "") for m in self._messages)
        return system_tokens + history_tokens

    def truncate(self, keep_system: bool = True) -> None:
        """Drop oldest messages until under *max_tokens*.

        Parameters
        ----------
        keep_system : bool
            If True (the default), the system prompt is always preserved.
            If False, the entire context is truncated to *max_tokens*.
        """
        if keep_system:
            # System prompt + history must fit
            target = self._max_tokens
        else:
            # Entire context must fit
            target = self._max_tokens
            self._system_prompt = ""

        # Binary search: remove chunks of oldest messages until under target
        low, high = 0, len(self._messages)
        while low < high:
            mid = (low + high + 1) // 2
            removed = self._messages[:mid]
            remaining = self._messages[mid:]
            est = (
                self.estimate_tokens(self._system_prompt)
                + sum(self.estimate_tokens(m.get("content", "") or "") for m in remaining)
            )
            if est <= target:
                high = mid - 1
            else:
                low = mid
        if low > 0:
            self._messages = self._messages[low:]

    def replace_messages(self, summary_content: str, keep_recent: int = 2) -> None:
        """Replace older messages with a compression summary.

        Parameters
        ----------
        summary_content : str
            The compressed summary text to prepend.
        keep_recent : int
            Number of recent messages to preserve intact.
        """
        if len(self._messages) <= keep_recent:
            return
        kept = self._messages[-keep_recent:] if keep_recent > 0 else []
        self._messages = [
            {"role": "system", "content": summary_content},
            *kept,
        ]

    # ------------------------------------------------------------------
    # Token estimation
    # ------------------------------------------------------------------

    @staticmethod
    @lru_cache(maxsize=1)
    def _get_encoder(model: str = "cl100k_base"):
        """Get tiktoken encoder with caching.
        
        Parameters
        ----------
        model : str
            Encoding model name (default: cl100k_base for GPT-4/Claude)
            
        Returns
        -------
        tiktoken.Encoding or None
            Cached encoder instance or None if unavailable
        """
        if not TIKTOKEN_AVAILABLE:
            return None
        try:
            return tiktoken.get_encoding(model)
        except Exception:
            try:
                return tiktoken.get_encoding("cl100k_base")
            except Exception:
                return None

    @staticmethod
    def estimate_tokens(text: str, model: str = "cl100k_base") -> int:
        """Accurate token estimate using tiktoken with fallback.
        
        Uses tiktoken for accurate counting when available, falls back to
        rough estimate (len(text) // 4) if tiktoken is unavailable.

        Parameters
        ----------
        text : str
            Text to estimate tokens for
        model : str
            Encoding model name (default: cl100k_base)
            
        Returns
        -------
        int
            Estimated token count
        """
        if not text:
            return 0
            
        # Try tiktoken first
        if TIKTOKEN_AVAILABLE:
            try:
                encoder = ConversationContext._get_encoder(model)
                if encoder is not None:
                    return len(encoder.encode(text))
            except Exception:
                pass
        
        # Fallback to rough estimate
        return max(1, len(text) // 4)
