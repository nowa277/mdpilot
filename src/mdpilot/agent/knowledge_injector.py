# src/mdpilot/agent/knowledge_injector.py
"""KnowledgeInjector — three-level knowledge injection into agent context."""

from __future__ import annotations

from typing import Optional

from mdpilot.tools.builtin.knowledge import get_knowledge_index_summary, _get_knowledge_system


class KnowledgeInjector:
    """Builds knowledge context strings for injection into system prompts.

    Three levels:
      Level 0 (always): Knowledge index summary
      Level 1 (on match): Top relevant document summaries
      Level 2 (MD_TASK): Full workflow document content
    """

    def __init__(
        self,
        max_level1_tokens: int = 500,
        max_level2_tokens: int = 2000,
    ) -> None:
        self._max_level1_tokens = max_level1_tokens
        self._max_level2_tokens = max_level2_tokens

    def inject(
        self,
        prompt: str,
        task_type: str = "CHAT",
        index=None,
        loader=None,
    ) -> str:
        """Build full knowledge injection context.

        Parameters
        ----------
        prompt : str
            User query.
        task_type : str
            Task classification (CHAT, MD_TASK, etc.).
        index : KnowledgeIndex, optional
            Pre-initialized index. If None, obtained from
            _get_knowledge_system() global singleton.
        loader : KnowledgeLoader, optional
            Pre-initialized loader. If None, obtained from
            _get_knowledge_system() global singleton.

        Returns
        -------
        str
            Knowledge context string to append to system prompt.
        """
        # Lazy-init index/loader from global singleton
        if index is None or loader is None:
            try:
                sys_index, sys_loader = _get_knowledge_system()
                index = index or sys_index
                loader = loader or sys_loader
            except Exception:
                return ""

        parts = []

        # Level 1: Relevant summaries
        level1 = self.build_level1(prompt, index)
        if level1:
            parts.append(level1)

        # Level 2: Full workflow docs (MD_TASK only)
        if task_type == "MD_TASK" and index and loader:
            level2 = self.build_level2(prompt, index, loader)
            if level2:
                parts.append(level2)

        return "\n\n".join(parts)

    def build_level0(self) -> str:
        """Level 0: knowledge index summary (always injected)."""
        try:
            return get_knowledge_index_summary()
        except Exception:
            return ""

    def build_level1(self, prompt: str, index) -> str:
        """Level 1: top relevant document summaries."""
        try:
            results = index.search(prompt, top_k=3)
        except Exception:
            return ""

        if not results:
            return ""

        parts = ["## Relevant Knowledge Documents"]
        budget = self._max_level1_tokens

        for doc in results:
            entry = f"- **{doc.get('title', doc.get('id', 'unknown'))}** (id: `{doc.get('id', '')}`)"
            keywords = doc.get("keywords", [])
            if keywords:
                entry += f"\n  Keywords: {', '.join(keywords[:5])}"
            entry += "\n"

            if len(entry) > budget:
                break
            parts.append(entry)
            budget -= len(entry)

        if len(parts) == 1:  # only header
            return ""

        return "\n".join(parts) + "\n\nUse `read_knowledge` to load full document content."

    def build_level2(self, prompt: str, index, loader) -> str:
        """Level 2: full workflow documents for MD tasks."""
        try:
            results = index.search(prompt, top_k=2)
        except Exception:
            return ""

        if not results:
            return ""

        doc_ids = [doc.get("id") for doc in results if doc.get("id")]

        try:
            docs = loader.load(doc_ids)
        except Exception:
            return ""

        if not docs:
            return ""

        parts = ["## Workflow Guide"]
        budget = self._max_level2_tokens

        for doc_id, content in docs.items():
            section = f"### Document: {doc_id}\n{content}\n\n"
            if len(section) > budget:
                section = section[:budget] + "\n...(truncated)\n"
            parts.append(section)
            budget -= len(section)
            if budget <= 0:
                break

        if len(parts) == 1:
            return ""

        return "\n".join(parts)
