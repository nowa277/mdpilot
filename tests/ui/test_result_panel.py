"""Unit tests for ResultPanel."""

import io
import json
import pytest
from unittest.mock import MagicMock, patch

import yaml
from rich.console import Console

from mdpilot.ui.result_panel import ResultPanel


@pytest.fixture
def panel():
    """Create a ResultPanel for testing."""
    return ResultPanel()


@pytest.fixture
def test_console():
    """Create a console optimized for testing."""
    return Console(
        file=io.StringIO(),
        force_terminal=True,
        width=80,
        color_system="truecolor",
        legacy_windows=False,
        _environ={},
    )


class TestResultPanelInit:
    """Test ResultPanel initialization."""
    
    def test_init_creates_console(self, panel):
        """Test initialization creates Console instance."""
        assert panel.console is not None
        assert isinstance(panel.console, Console)


class TestResultPanelDisplayTable:
    """Test display_table method."""
    
    def test_display_table_with_data(self, panel):
        """Test displaying table with data."""
        data = [
            {"Name": "Alice", "Age": 30, "City": "NYC"},
            {"Name": "Bob", "Age": 25, "City": "LA"},
        ]
        
        with patch.object(panel.console, 'print') as mock_print:
            panel.display_table(data, "Test Table")
            mock_print.assert_called_once()
    
    def test_display_table_empty_data(self, panel):
        """Test displaying table with empty data."""
        with patch.object(panel.console, 'print') as mock_print:
            panel.display_table([], "Empty Table")
            mock_print.assert_called_once()
            call_args = str(mock_print.call_args)
            assert "No data" in call_args
    
    def test_display_table_single_row(self, panel):
        """Test displaying table with single row."""
        data = [{"Name": "Alice", "Status": "Active"}]
        
        with patch.object(panel.console, 'print') as mock_print:
            panel.display_table(data, "Single Row")
            mock_print.assert_called_once()
    
    def test_display_table_multiple_columns(self, panel):
        """Test displaying table with multiple columns."""
        data = [
            {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"},
            {"A": "6", "B": "7", "C": "8", "D": "9", "E": "10"},
        ]
        
        with patch.object(panel.console, 'print') as mock_print:
            panel.display_table(data, "Multi Column")
            mock_print.assert_called_once()


class TestResultPanelDisplayJson:
    """Test display_json method."""
    
    def test_display_json_simple_dict(self, panel):
        """Test displaying simple JSON dict."""
        data = {"name": "Alice", "age": 30}
        
        with patch.object(panel.console, 'print') as mock_print:
            panel.display_json(data, "Test JSON")
            mock_print.assert_called_once()
    
    def test_display_json_nested_dict(self, panel):
        """Test displaying nested JSON dict."""
        data = {
            "user": {
                "name": "Alice",
                "address": {
                    "city": "NYC",
                    "zip": "10001"
                }
            }
        }
        
        with patch.object(panel.console, 'print') as mock_print:
            panel.display_json(data, "Nested JSON")
            mock_print.assert_called_once()
    
    def test_display_json_with_list(self, panel):
        """Test displaying JSON with list."""
        data = {
            "items": ["apple", "banana", "cherry"],
            "count": 3
        }
        
        with patch.object(panel.console, 'print') as mock_print:
            panel.display_json(data, "JSON with List")
            mock_print.assert_called_once()
    
    def test_display_json_unicode(self, panel):
        """Test displaying JSON with unicode characters."""
        data = {"message": "你好世界", "emoji": "🎉"}
        
        with patch.object(panel.console, 'print') as mock_print:
            panel.display_json(data, "Unicode JSON")
            mock_print.assert_called_once()


class TestResultPanelDisplayYaml:
    """Test display_yaml method."""
    
    def test_display_yaml_simple_dict(self, panel):
        """Test displaying simple YAML dict."""
        data = {"name": "Alice", "age": 30}
        
        with patch.object(panel.console, 'print') as mock_print:
            panel.display_yaml(data, "Test YAML")
            mock_print.assert_called_once()
    
    def test_display_yaml_nested_dict(self, panel):
        """Test displaying nested YAML dict."""
        data = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "credentials": {
                    "user": "admin",
                    "password": "secret"
                }
            }
        }
        
        with patch.object(panel.console, 'print') as mock_print:
            panel.display_yaml(data, "Nested YAML")
            mock_print.assert_called_once()
    
    def test_display_yaml_with_list(self, panel):
        """Test displaying YAML with list."""
        data = {
            "servers": ["server1", "server2", "server3"],
            "enabled": True
        }
        
        with patch.object(panel.console, 'print') as mock_print:
            panel.display_yaml(data, "YAML with List")
            mock_print.assert_called_once()


class TestResultPanelDisplayText:
    """Test display_text method."""
    
    def test_display_text_plain(self, panel):
        """Test displaying plain text."""
        with patch.object(panel.console, 'print') as mock_print:
            panel.display_text("Hello World", "Plain Text")
            mock_print.assert_called_once()
    
    def test_display_text_with_syntax(self, panel):
        """Test displaying text with syntax highlighting."""
        code = "def hello():\n    print('Hello')"
        
        with patch.object(panel.console, 'print') as mock_print:
            panel.display_text(code, "Python Code", syntax="python")
            mock_print.assert_called_once()
    
    def test_display_text_multiline(self, panel):
        """Test displaying multiline text."""
        text = "Line 1\nLine 2\nLine 3"
        
        with patch.object(panel.console, 'print') as mock_print:
            panel.display_text(text, "Multiline")
            mock_print.assert_called_once()


class TestResultPanelDisplaySuccess:
    """Test display_success method."""
    
    def test_display_success_message(self, panel):
        """Test displaying success message."""
        with patch.object(panel.console, 'print') as mock_print:
            panel.display_success("Operation completed successfully")
            mock_print.assert_called_once()
            call_args = str(mock_print.call_args)
            assert "✓" in call_args or "Operation completed" in call_args


class TestResultPanelDisplayError:
    """Test display_error method."""
    
    def test_display_error_message_only(self, panel):
        """Test displaying error message without details."""
        with patch.object(panel.console, 'print') as mock_print:
            panel.display_error("Operation failed")
            mock_print.assert_called_once()
            call_args = str(mock_print.call_args)
            assert "✗" in call_args or "failed" in call_args
    
    def test_display_error_with_details(self, panel):
        """Test displaying error message with details."""
        with patch.object(panel.console, 'print') as mock_print:
            panel.display_error("Operation failed", "Connection timeout")
            assert mock_print.call_count == 2


class TestResultPanelIntegration:
    """Integration tests for ResultPanel."""
    
    def test_display_go_terms_table(self, panel):
        """Test displaying GO terms as table (BioReason use case)."""
        data = [
            {"Aspect": "MF", "Terms": "oxygen carrier, heme binding"},
            {"Aspect": "BP", "Terms": "oxygen transport"},
            {"Aspect": "CC", "Terms": "hemoglobin complex"},
        ]
        
        with patch.object(panel.console, 'print') as mock_print:
            panel.display_table(data, "GO Terms")
            mock_print.assert_called_once()
    
    def test_display_alphafold2_results(self, panel):
        """Test displaying AlphaFold2 results as JSON."""
        data = {
            "best_model": "model_1",
            "avg_plddt": 85.3,
            "output_dir": "/path/to/output",
            "num_models": 5
        }
        
        with patch.object(panel.console, 'print') as mock_print:
            panel.display_json(data, "AlphaFold2 Results")
            mock_print.assert_called_once()
