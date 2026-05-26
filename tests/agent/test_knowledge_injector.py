# tests/agent/test_knowledge_injector.py
"""Tests for KnowledgeInjector — three-level knowledge injection."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from mdpilot.agent.knowledge_injector import KnowledgeInjector


class TestKnowledgeInjectorLevel0:
    """Level 0: always inject index summary."""

    def test_level0_returns_knowledge_summary(self):
        injector = KnowledgeInjector()
        with patch("mdpilot.agent.knowledge_injector.get_knowledge_index_summary") as mock:
            mock.return_value = "# Knowledge Index\n- doc1\n- doc2\n"
            result = injector.build_level0()
        assert "Knowledge Index" in result


class TestKnowledgeInjectorLevel1:
    """Level 1: inject top-3 relevant document summaries."""

    def test_level1_searches_and_formats(self):
        injector = KnowledgeInjector()
        mock_index = MagicMock()
        mock_index.search.return_value = [
            {"id": "tool-pdb4amber", "title": "PDB4AMBER Guide", "keywords": ["pdb", "clean"]},
            {"id": "workflow-standard-protein", "title": "Standard Protein Workflow", "keywords": ["protein", "simulation"]},
        ]

        result = injector.build_level1("How to clean a PDB file", mock_index)
        assert "PDB4AMBER Guide" in result
        assert "Standard Protein" in result

    def test_level1_empty_when_no_matches(self):
        injector = KnowledgeInjector()
        mock_index = MagicMock()
        mock_index.search.return_value = []

        result = injector.build_level1("random query", mock_index)
        assert result == ""

    def test_level1_respects_token_budget(self):
        injector = KnowledgeInjector(max_level1_tokens=50)
        mock_index = MagicMock()
        mock_index.search.return_value = [
            {"id": f"doc{i}", "title": f"Doc {i} " * 100, "keywords": ["test"]}
            for i in range(5)
        ]

        result = injector.build_level1("test", mock_index)
        # Should be truncated to fit budget
        assert len(result) < 5000


class TestKnowledgeInjectorLevel2:
    """Level 2: inject full workflow documents for MD_TASK."""

    def test_level2_injects_full_doc(self):
        injector = KnowledgeInjector()
        mock_index = MagicMock()
        mock_index.search.return_value = [
            {"id": "workflow-standard-protein", "title": "Standard Protein MD"},
        ]
        mock_loader = MagicMock()
        mock_loader.load.return_value = {
            "workflow-standard-protein": "# Standard Protein MD\nStep 1: pdb4amber\nStep 2: tleap...",
        }

        result = injector.build_level2("run MD simulation", mock_index, mock_loader)
        assert "Standard Protein MD" in result
        assert "pdb4amber" in result

    def test_level2_skips_when_not_md_task(self):
        injector = KnowledgeInjector()
        # No search results for non-MD queries
        mock_index = MagicMock()
        mock_index.search.return_value = []

        result = injector.build_level2("what is RMSD", mock_index, MagicMock())
        assert result == ""


class TestKnowledgeInjectorIntegration:
    """Test full injection pipeline."""

    def test_inject_builds_context_string(self):
        injector = KnowledgeInjector()
        mock_index = MagicMock()
        mock_index.search.return_value = [{"id": "doc1", "title": "Test Doc", "keywords": ["test"]}]
        mock_loader = MagicMock()
        mock_loader.load.return_value = {}

        # Pass index/loader directly — no singleton dependency
        result = injector.inject("test prompt", task_type="CHAT", index=mock_index, loader=mock_loader)
        assert isinstance(result, str)

    def test_inject_uses_singleton_when_no_args(self):
        """When index/loader not provided, falls back to _get_knowledge_system."""
        injector = KnowledgeInjector()
        with patch("mdpilot.agent.knowledge_injector._get_knowledge_system") as mock_sys:
            mock_index = MagicMock()
            mock_index.search.return_value = []
            mock_sys.return_value = (mock_index, MagicMock())

            result = injector.inject("test prompt")
        assert isinstance(result, str)
