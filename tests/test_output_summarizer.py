"""Tests for output_summarizer — tool output compression."""

from __future__ import annotations

from mdpilot.agent.output_summarizer import summarize_tool_output


class TestShortOutput:
    def test_short_output_unchanged(self):
        output = "Short output\nAll good"
        assert summarize_tool_output(output) == output

    def test_exactly_at_limit(self):
        output = "x" * 4000
        assert summarize_tool_output(output) == output


class TestLongOutput:
    def _make_long_output(self, middle_lines: int = 200) -> str:
        """Generate a realistic sander-like output."""
        lines = [
            "Minimization",
            " &cntrl",
            "  imin=1, maxcyc=10000,",
            " /",
            "",
            "--- begin minimization ---",
        ]
        for i in range(middle_lines):
            nstep = (i + 1) * 100
            lines.append(f"   NSTEP = {nstep:8d}  Etot = {-10000.0 + i:.4f}")
        lines.extend([
            "   STOP",
            "",
            "[status: completed]",
            "[final energy]",
            "   Etot = -12345.6789",
        ])
        return "\n".join(lines)

    def test_long_output_is_shortened(self):
        output = self._make_long_output(200)
        assert len(output) > 4000
        result = summarize_tool_output(output)
        assert len(result) < len(output)
        assert "summarized" in result

    def test_preserves_head(self):
        output = self._make_long_output(200)
        result = summarize_tool_output(output)
        assert "Minimization" in result
        assert "imin=1" in result

    def test_preserves_tail(self):
        output = self._make_long_output(200)
        result = summarize_tool_output(output)
        assert "[status: completed]" in result
        assert "STOP" in result

    def test_custom_max_chars(self):
        output = self._make_long_output(100)
        result = summarize_tool_output(output, max_chars=500)
        assert len(result) <= 800  # allow some overhead

    def test_preserves_error_lines(self):
        lines = ["header line 1", "header line 2"]
        for i in range(50):
            lines.append(f"normal output line {i}")
        lines.append("FATAL: something broke")
        for i in range(30):
            lines.append(f"more output {i}")

        output = "\n".join(lines)
        result = summarize_tool_output(output, max_chars=1000)
        assert "FATAL" in result


class TestEdgeCases:
    def test_empty_string(self):
        assert summarize_tool_output("") == ""

    def test_single_line(self):
        assert summarize_tool_output("one line") == "one line"

    def test_fewer_lines_than_threshold(self):
        output = "\n".join(["line"] * 15)
        # head=10 + tail=20 > 15 lines, so no summarization
        assert summarize_tool_output(output) == output
