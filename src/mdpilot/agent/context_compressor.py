"""ContextCompressor — layered context compression for long agent sessions."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from mdpilot.agent.context import ConversationContext

logger = logging.getLogger(__name__)


@dataclass
class IterationGroup:
    """A group of messages belonging to one ReAct iteration."""
    messages: list[dict[str, Any]]
    index: int


@dataclass
class CompressedNote:
    """Structured summary of a compressed iteration group."""
    stage: str
    goal: str
    tools_called: list[dict[str, str]] = field(default_factory=list)
    conclusions: str = ""
    decisions: str = ""


def _group_by_iteration(messages: list[dict[str, Any]]) -> list[IterationGroup]:
    """Group messages into iteration pairs: assistant(+tool_calls) + tool results.

    User messages are skipped. Each group starts with an assistant message
    that has tool_calls, followed by its tool result messages. A final
    assistant message without tool_calls forms its own group.
    """
    groups: list[IterationGroup] = []
    current: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role", "")

        if role == "user":
            continue

        if role == "assistant":
            if current:
                groups.append(IterationGroup(messages=current, index=len(groups)))
                current = []
            current.append(msg)
            if not msg.get("tool_calls"):
                groups.append(IterationGroup(messages=current, index=len(groups)))
                current = []

        elif role == "tool":
            current.append(msg)

    if current:
        groups.append(IterationGroup(messages=current, index=len(groups)))

    return groups


_COMPRESSION_PROMPT = """\
You are a context compression assistant. Summarize the following agent iteration into a structured JSON object.

Fields:
- "stage": one-sentence description of what phase this was (e.g., "PDB structure cleaning")
- "goal": what the agent was trying to accomplish
- "tools_called": list of {{"name": "...", "result_summary": "..."}} objects (one per tool, result_summary max 50 words)
- "conclusions": key findings or results (1-2 sentences)
- "decisions": important decisions made (1 sentence, or empty string)

Iteration messages:
{messages}

Respond with ONLY the JSON object, no markdown fences."""


class ContextCompressor:
    """Layered context compression engine.

    Groups old messages by iteration, compresses them via LLM into
    structured notes, and replaces raw messages with a summary.
    """

    def __init__(
        self,
        llm_provider: Any,
        trigger_ratio: float = 0.7,
        keep_recent: int = 2,
    ) -> None:
        self._llm = llm_provider
        self._trigger_ratio = trigger_ratio
        self._keep_recent = keep_recent
        self.notes: list[CompressedNote] = []
        self.compression_count: int = 0

    @property
    def should_compress(self) -> bool:
        """Whether compression notes exist (for system prompt injection)."""
        return len(self.notes) > 0

    def build_notes_text(self, max_tokens: int = 2000) -> str:
        """Format compressed notes for system prompt injection."""
        if not self.notes:
            return ""
        lines = ["## Previous Session Summary (compressed)"]
        for i, note in enumerate(self.notes, 1):
            lines.append(f"### Stage {i}: {note.stage}")
            lines.append(f"Goal: {note.goal}")
            if note.tools_called:
                tool_strs = [f"  - {t['name']}: {t['result_summary']}" for t in note.tools_called]
                lines.append("Tools:\n" + "\n".join(tool_strs))
            if note.conclusions:
                lines.append(f"Conclusions: {note.conclusions}")
            if note.decisions:
                lines.append(f"Decisions: {note.decisions}")
            lines.append("")
        text = "\n".join(lines)
        char_limit = max_tokens * 4
        if len(text) > char_limit:
            text = text[:char_limit] + "\n...(older notes truncated)"
        return text

    async def maybe_compress(self, context: ConversationContext) -> bool:
        """Check token usage and compress if over trigger ratio."""
        threshold = context._max_tokens * self._trigger_ratio
        if context.token_count < threshold:
            return False

        groups = _group_by_iteration(context._messages)
        if len(groups) <= self._keep_recent:
            return False

        old_groups = groups[:-self._keep_recent]
        for group in old_groups:
            note = await self._compress_group(group)
            if note:
                self.notes.append(note)

        summary = self._build_summary_message()
        keep_count = 0
        if self._keep_recent > 0 and groups:
            keep_count = sum(len(g.messages) for g in groups[-self._keep_recent:])

        context.replace_messages(summary_content=summary, keep_recent=keep_count)
        self.compression_count += 1

        logger.info(
            "context_compressed",
            groups_compressed=len(old_groups),
            total_notes=len(self.notes),
            token_count=context.token_count,
        )
        return True

    async def _compress_group(self, group: IterationGroup) -> CompressedNote | None:
        """Compress one iteration group into a structured note via LLM."""
        messages_text = "\n".join(
            f"[{m.get('role', '?')}] {m.get('content', '')[:500]}"
            for m in group.messages
        )

        prompt = _COMPRESSION_PROMPT.format(messages=messages_text)

        try:
            response = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                stream=False,
            )
            raw = response.content.strip()

            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw.rsplit("```", 1)[0]
            if raw.startswith("json"):
                raw = raw[4:]

            data = json.loads(raw)
            return CompressedNote(
                stage=data.get("stage", "unknown"),
                goal=data.get("goal", ""),
                tools_called=data.get("tools_called", []),
                conclusions=data.get("conclusions", ""),
                decisions=data.get("decisions", ""),
            )
        except Exception as e:
            logger.warning("compression_failed", error=str(e), group_index=group.index)
            contents = [m.get("content", "")[:100] for m in group.messages if m.get("content")]
            return CompressedNote(
                stage=f"Iteration {group.index + 1}",
                goal=" ".join(contents)[:200],
                conclusions="",
            )

    def _build_summary_message(self) -> str:
        """Build the compression summary message to replace old messages."""
        lines = ["[已压缩的上下文摘要]"]
        for i, note in enumerate(self.notes, 1):
            stage_line = f"阶段{i}: {note.stage}"
            if note.conclusions:
                stage_line += f" → {note.conclusions}"
            lines.append(stage_line)
            for t in note.tools_called:
                lines.append(f"  工具 {t['name']}: {t.get('result_summary', '')}")
        return "\n".join(lines)
