"""Tests for TaskClassifier."""
import pytest
from mdpilot.agent.task_classifier import classify, TaskClassifier


class TestClassify:
    @pytest.mark.parametrize("input_text,expected", [
        ("帮我构建 1AKI", "MD_TASK"),
        ("/path/1AKI.pdb 构建体系", "MD_TASK"),
        ("什么是 ff19SB", "CHAT"),
        ("帮我用 ff19SB 和 OPC3 构建 1AKI", "MD_TASK"),
        ("tleap 报错了怎么办", "CHAT"),
        ("蛋白怎么质子化", "MD_TASK"),
        ("1AKI 是什么蛋白", "CHAT"),
    ])
    def test_classify(self, input_text: str, expected: str) -> None:
        assert classify(input_text) == expected

    def test_returns_only_chat_or_md_task(self) -> None:
        for inp in ["你好", "再见", "hello", "thanks", "构建体系", "分析轨迹"]:
            assert classify(inp) in ("CHAT", "MD_TASK")

    def test_task_classifier_class(self) -> None:
        c = TaskClassifier()
        assert c.classify("帮我构建 1AKI") == "MD_TASK"
        assert c.classify("你好") == "CHAT"
