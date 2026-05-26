"""Tool output summarizer — compresses long tool outputs before context injection.

AMBER tool outputs (especially sander) can produce thousands of lines of
repeating NSTEP/Etot tables. This module extracts the important information
(head, tail, key energy lines) and discards the repetitive middle.
"""

from __future__ import annotations

import re
from typing import Any


# Maximum output length before summarization kicks in
DEFAULT_MAX_OUTPUT_CHARS = 4000

# Patterns for "important" lines that should be preserved
_KEY_PATTERNS = [
    re.compile(r"(Etot|EPtot|BOND|ANGLE|EELEC|VDWAALS)\s*=", re.IGNORECASE),
    re.compile(r"^\s*NSTEP\s*=", re.IGNORECASE),
    re.compile(r"(FATAL|ERROR|Error|STOP|WARNING)", re.IGNORECASE),
    re.compile(r"\[(status|final|trajectory|restart|last|workdir)", re.IGNORECASE),
    re.compile(r"(completed|incomplete|timed out)", re.IGNORECASE),
]


def summarize_tool_output(
    output: str,
    max_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
    preserve_head_lines: int = 10,
    preserve_tail_lines: int = 20,
) -> str:
    """Summarize a long tool output string.

    Strategy:
    1. If output <= max_chars, return as-is
    2. Otherwise: keep head (setup info) + key lines + tail (final result)
    3. Add a "[... N lines summarized ...]" marker in the gap

    Args:
        output: The raw tool output string.
        max_chars: Character threshold for triggering summarization.
        preserve_head_lines: Number of lines to always keep from the start.
        preserve_tail_lines: Number of lines to always keep from the end.

    Returns:
        Summarized output string.
    """
    if len(output) <= max_chars:
        return output

    lines = output.splitlines()
    total_lines = len(lines)

    if total_lines <= preserve_head_lines + preserve_tail_lines:
        return output

    # Collect key lines from the middle section
    middle_start = preserve_head_lines
    middle_end = total_lines - preserve_tail_lines

    head_lines = lines[:preserve_head_lines]
    tail_lines = lines[middle_end:]

    # Extract important lines from the middle
    key_lines: list[str] = []
    seen_patterns: set[int] = set()
    for i in range(middle_start, middle_end):
        line = lines[i]
        for pat_idx, pattern in enumerate(_KEY_PATTERNS):
            if pattern.search(line):
                # Deduplicate similar consecutive matches
                if pat_idx not in seen_patterns or not key_lines:
                    key_lines.append(line)
                seen_patterns.add(pat_idx)
                break

    # Only keep last few key lines to avoid still being too long
    if len(key_lines) > 10:
        key_lines = key_lines[-10:]

    # Build summarized output
    parts = head_lines
    middle_skipped = middle_end - middle_start

    if key_lines:
        parts.append(f"  [... {middle_skipped - len(key_lines)} lines summarized ...]")
        parts.extend(key_lines)
    else:
        parts.append(f"  [... {middle_skipped} lines summarized ...]")

    parts.extend(tail_lines)

    result = "\n".join(parts)

    # Final safety: if still too long, truncate tail
    if len(result) > max_chars * 1.5:
        result = result[:max_chars] + "\n  [... output truncated ...]"

    return result


def estimate_output_tokens(text: str) -> int:
    """Rough token estimate for output text."""
    return max(1, len(text) // 4)
