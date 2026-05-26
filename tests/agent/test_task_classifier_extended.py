# tests/agent/test_task_classifier_extended.py
"""Extended tests for TaskClassifier paradigm routing."""

from __future__ import annotations

import pytest

from mdpilot.agent.task_classifier import TaskClassifier, classify_paradigm


class TestClassifyParadigm:
    """Test paradigm classification for agent routing."""

    def test_simple_chat_returns_react(self):
        result = classify_paradigm("你好，请问什么是分子动力学？")
        assert result == "react"

    def test_single_tool_call_returns_react(self):
        result = classify_paradigm("帮我检查一下 AMBER 环境是否安装正确")
        assert result == "react"

    def test_multi_step_workflow_returns_plan_solve(self):
        result = classify_paradigm("请帮我预测这个蛋白质的结构，然后分析它的功能")
        assert result == "plan_solve"

    def test_alphafold2_then_analysis_returns_plan_solve(self):
        result = classify_paradigm("先用 AlphaFold2 预测结构，然后用 BioReason 分析")
        assert result == "plan_solve"

    def test_amber_md_workflow_returns_plan_solve(self):
        result = classify_paradigm("帮我跑一个标准的 AMBER MD 模拟流程")
        assert result == "plan_solve"

    def test_optimization_returns_reflection(self):
        result = classify_paradigm("优化一下模拟参数，看看能不能得到更好的结果")
        assert result == "reflection"

    def test_verify_results_returns_reflection(self):
        result = classify_paradigm("检查一下 RMSD 分析结果是否正确")
        assert result == "reflection"

    def test_compare_approaches_returns_reflection(self):
        result = classify_paradigm("比较两种力场参数哪个更好")
        assert result == "reflection"


class TestTaskClassifierExtended:
    """Test TaskClassifier with paradigm method."""

    def test_classify_paradigm_method(self):
        tc = TaskClassifier()
        result = tc.classify_paradigm("预测结构并分析功能")
        assert result in ("react", "plan_solve", "reflection")

    def test_classify_original_still_works(self):
        tc = TaskClassifier()
        result = tc.classify("帮我跑一个 MD 模拟")
        assert result in ("MD_TASK", "CHAT", "GENERAL")
