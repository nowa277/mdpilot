"""Tests for ContextCompressor and ConversationContext.replace_messages."""
import pytest
from mdpilot.agent.context import ConversationContext


def test_replace_messages_basic():
    ctx = ConversationContext("system", max_tokens=100_000)
    ctx.add(role="user", content="hello")
    ctx.add(role="assistant", content="hi")
    ctx.add(role="user", content="how are you")
    ctx.add(role="assistant", content="fine")

    assert len(ctx._messages) == 4

    ctx.replace_messages(
        summary_content="[Compressed] 2 rounds of greeting",
        keep_recent=1,
    )

    # Should have: summary + last assistant message
    assert len(ctx._messages) == 2
    assert ctx._messages[0]["role"] == "system"
    assert "[Compressed]" in ctx._messages[0]["content"]
    assert ctx._messages[1]["content"] == "fine"


def test_replace_messages_keeps_all_if_nothing_to_compress():
    ctx = ConversationContext("system", max_tokens=100_000)
    ctx.add(role="user", content="only message")

    ctx.replace_messages(
        summary_content="[Compressed] empty",
        keep_recent=2,
    )

    # keep_recent=2 but only 1 message, nothing to compress
    assert len(ctx._messages) == 1
    assert ctx._messages[0]["content"] == "only message"


def test_replace_messages_token_count_decreases():
    ctx = ConversationContext("system", max_tokens=100_000)
    for i in range(20):
        ctx.add(role="user", content=f"message {i} " * 50)
        ctx.add(role="assistant", content=f"reply {i} " * 50)

    before = ctx.token_count
    ctx.replace_messages(
        summary_content="[Compressed] early messages",
        keep_recent=2,
    )
    after = ctx.token_count

    assert after < before


from mdpilot.agent.context_compressor import IterationGroup, _group_by_iteration


def test_group_by_iteration_basic():
    messages = [
        {"role": "user", "content": "do task"},
        {"role": "assistant", "content": "thinking", "tool_calls": [{"id": "tc1"}]},
        {"role": "tool", "content": "result1", "tool_call_id": "tc1"},
        {"role": "assistant", "content": "more thinking", "tool_calls": [{"id": "tc2"}]},
        {"role": "tool", "content": "result2", "tool_call_id": "tc2"},
        {"role": "assistant", "content": "final answer"},
    ]
    groups = _group_by_iteration(messages)

    assert len(groups) == 3
    assert groups[0].index == 0
    assert len(groups[0].messages) == 2
    assert groups[1].index == 1
    assert len(groups[1].messages) == 2
    assert groups[2].index == 2
    assert len(groups[2].messages) == 1


def test_group_by_iteration_user_messages_skipped():
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    groups = _group_by_iteration(messages)
    assert len(groups) == 1
    assert groups[0].messages[0]["role"] == "assistant"


def test_group_by_iteration_empty():
    groups = _group_by_iteration([])
    assert groups == []


def test_compressor_notes_text():
    from mdpilot.agent.context_compressor import CompressedNote

    from mdpilot.agent.context_compressor import ContextCompressor

    compressor = ContextCompressor.__new__(ContextCompressor)
    compressor.notes = [
        CompressedNote(
            stage="PDB cleaning",
            goal="clean PDB file",
            tools_called=[{"name": "pdb4amber", "result_summary": "cleaned 129 residues"}],
            conclusions="File is ready",
        )
    ]

    text = compressor.build_notes_text()
    assert "PDB cleaning" in text
    assert "pdb4amber" in text
