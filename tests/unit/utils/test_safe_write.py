"""
Unit tests for utils/safe_write.py

Tests safe concurrent write utilities for __init__.py files.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open, MagicMock
from mdpilot.utils.safe_write import safe_write_init_py, _parse_all_list


class TestParseAllList:
    """Test _parse_all_list helper function."""
    
    def test_parse_simple_list(self):
        """Test parsing simple __all__ list."""
        line = '__all__ = ["foo", "bar", "baz"]'
        result = _parse_all_list(line)
        
        assert result == {"foo", "bar", "baz"}
    
    def test_parse_single_quotes(self):
        """Test parsing with single quotes."""
        line = "__all__ = ['foo', 'bar']"
        result = _parse_all_list(line)
        
        assert result == {"foo", "bar"}
    
    def test_parse_mixed_quotes(self):
        """Test parsing with mixed quotes."""
        line = '__all__ = ["foo", \'bar\']'
        result = _parse_all_list(line)
        
        assert result == {"foo", "bar"}
    
    def test_parse_with_spaces(self):
        """Test parsing with extra spaces."""
        line = '__all__ = [ "foo" , "bar" , "baz" ]'
        result = _parse_all_list(line)
        
        assert result == {"foo", "bar", "baz"}
    
    def test_parse_empty_list(self):
        """Test parsing empty __all__ list."""
        line = '__all__ = []'
        result = _parse_all_list(line)
        
        assert result == set()
    
    def test_parse_no_brackets(self):
        """Test parsing line without brackets."""
        line = '__all__ = "foo"'
        result = _parse_all_list(line)
        
        assert result == set()
    
    def test_parse_single_item(self):
        """Test parsing single item list."""
        line = '__all__ = ["foo"]'
        result = _parse_all_list(line)
        
        assert result == {"foo"}


class TestSafeWriteInitPy:
    """Test safe_write_init_py function."""
    
    def test_create_new_init_file(self, tmp_path):
        """Test creating new __init__.py file."""
        init_path = tmp_path / "test_package" / "__init__.py"
        
        safe_write_init_py(
            init_path,
            imports=["from .module import foo"],
            all_exports=["foo"]
        )
        
        assert init_path.exists()
        content = init_path.read_text()
        assert "from .module import foo" in content
        assert '__all__ = ["foo"]' in content
    
    def test_creates_parent_directory(self, tmp_path):
        """Test that parent directory is created if missing."""
        init_path = tmp_path / "new_dir" / "subdir" / "__init__.py"
        
        safe_write_init_py(init_path, imports=["import os"])
        
        assert init_path.parent.exists()
        assert init_path.exists()
    
    def test_merge_imports(self, tmp_path):
        """Test merging new imports with existing ones."""
        init_path = tmp_path / "__init__.py"
        init_path.write_text("from .existing import bar\n")
        
        safe_write_init_py(
            init_path,
            imports=["from .new import foo"]
        )
        
        content = init_path.read_text()
        assert "from .existing import bar" in content
        assert "from .new import foo" in content
    
    def test_merge_all_exports(self, tmp_path):
        """Test merging __all__ exports."""
        init_path = tmp_path / "__init__.py"
        init_path.write_text('__all__ = ["existing"]\n')
        
        safe_write_init_py(
            init_path,
            all_exports=["new"]
        )
        
        content = init_path.read_text()
        assert '"existing"' in content
        assert '"new"' in content
    
    def test_preserve_docstring(self, tmp_path):
        """Test preserving module docstring."""
        init_path = tmp_path / "__init__.py"
        init_path.write_text('"""Module docstring."""\n\nfrom .module import foo\n')
        
        safe_write_init_py(
            init_path,
            imports=["from .new import bar"]
        )
        
        content = init_path.read_text()
        assert '"""Module docstring."""' in content
        assert "from .module import foo" in content
        assert "from .new import bar" in content
    
    def test_preserve_multiline_docstring(self, tmp_path):
        """Test preserving multi-line docstring."""
        init_path = tmp_path / "__init__.py"
        docstring = '"""\nMulti-line\ndocstring.\n"""\n'
        init_path.write_text(docstring + "import os\n")
        
        safe_write_init_py(
            init_path,
            imports=["import sys"]
        )
        
        content = init_path.read_text()
        assert "Multi-line" in content
        assert "docstring." in content
        assert "import os" in content
        assert "import sys" in content
    
    def test_add_extra_content(self, tmp_path):
        """Test adding extra content."""
        init_path = tmp_path / "__init__.py"
        
        safe_write_init_py(
            init_path,
            imports=["import os"],
            extra_content="# Custom comment\nVERSION = '1.0.0'"
        )
        
        content = init_path.read_text()
        assert "# Custom comment" in content
        assert "VERSION = '1.0.0'" in content
    
    def test_sorted_imports(self, tmp_path):
        """Test that imports are sorted."""
        init_path = tmp_path / "__init__.py"
        
        safe_write_init_py(
            init_path,
            imports=["from .z import z", "from .a import a", "from .m import m"]
        )
        
        content = init_path.read_text()
        lines = content.splitlines()
        import_lines = [l for l in lines if l.startswith("from .")]
        
        assert import_lines == sorted(import_lines)
    
    def test_sorted_all_exports(self, tmp_path):
        """Test that __all__ exports are sorted."""
        init_path = tmp_path / "__init__.py"
        
        safe_write_init_py(
            init_path,
            all_exports=["zebra", "apple", "monkey"]
        )
        
        content = init_path.read_text()
        assert '__all__ = ["apple", "monkey", "zebra"]' in content
    
    def test_deduplicate_imports(self, tmp_path):
        """Test that duplicate imports are removed."""
        init_path = tmp_path / "__init__.py"
        init_path.write_text("from .module import foo\n")
        
        safe_write_init_py(
            init_path,
            imports=["from .module import foo"]
        )
        
        content = init_path.read_text()
        assert content.count("from .module import foo") == 1
    
    def test_deduplicate_all_exports(self, tmp_path):
        """Test that duplicate __all__ entries are removed."""
        init_path = tmp_path / "__init__.py"
        init_path.write_text('__all__ = ["foo"]\n')
        
        safe_write_init_py(
            init_path,
            all_exports=["foo", "bar"]
        )
        
        content = init_path.read_text()
        assert content.count('"foo"') == 1
    
    def test_empty_inputs(self, tmp_path):
        """Test with no imports or exports."""
        init_path = tmp_path / "__init__.py"
        
        safe_write_init_py(init_path)
        
        assert init_path.exists()
        content = init_path.read_text()
        assert content.strip() == ""
    
    def test_preserve_existing_content(self, tmp_path):
        """Test preserving non-import/all content."""
        init_path = tmp_path / "__init__.py"
        init_path.write_text("import os\n\nVERSION = '1.0.0'\n")
        
        safe_write_init_py(
            init_path,
            imports=["import sys"]
        )
        
        content = init_path.read_text()
        assert "VERSION = '1.0.0'" in content
        assert "import os" in content
        assert "import sys" in content
    
    def test_file_locking(self, tmp_path):
        """Test that file locking is used."""
        init_path = tmp_path / "__init__.py"
        
        with patch('fcntl.flock') as mock_flock:
            safe_write_init_py(init_path, imports=["import os"])
            
            assert mock_flock.call_count >= 2
    
    def test_cleanup_lock_file(self, tmp_path):
        """Test that lock file is cleaned up."""
        init_path = tmp_path / "__init__.py"
        lock_path = init_path.with_suffix(".lock")
        
        safe_write_init_py(init_path, imports=["import os"])
        
        assert not lock_path.exists()
    
    def test_preserve_comments(self, tmp_path):
        """Test preserving header comments."""
        init_path = tmp_path / "__init__.py"
        init_path.write_text("# Header comment\n# Another comment\n\nimport os\n")
        
        safe_write_init_py(
            init_path,
            imports=["import sys"]
        )
        
        content = init_path.read_text()
        assert "# Header comment" in content
        assert "# Another comment" in content
    
    def test_single_line_docstring(self, tmp_path):
        """Test single-line docstring handling."""
        init_path = tmp_path / "__init__.py"
        init_path.write_text('"""Single line docstring."""\n\nimport os\n')
        
        safe_write_init_py(
            init_path,
            imports=["import sys"]
        )
        
        content = init_path.read_text()
        assert '"""Single line docstring."""' in content
        assert "import os" in content
        assert "import sys" in content
    
    def test_triple_single_quotes_docstring(self, tmp_path):
        """Test docstring with triple single quotes."""
        init_path = tmp_path / "__init__.py"
        init_path.write_text("'''Module docstring.'''\n\nimport os\n")
        
        safe_write_init_py(
            init_path,
            imports=["import sys"]
        )
        
        content = init_path.read_text()
        assert "'''Module docstring.'''" in content
        assert "import os" in content


class TestSafeWriteEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_file(self, tmp_path):
        """Test handling empty existing file."""
        init_path = tmp_path / "__init__.py"
        init_path.touch()
        
        safe_write_init_py(
            init_path,
            imports=["import os"]
        )
        
        content = init_path.read_text()
        assert "import os" in content
    
    def test_whitespace_only_file(self, tmp_path):
        """Test handling file with only whitespace."""
        init_path = tmp_path / "__init__.py"
        init_path.write_text("   \n\n   \n")
        
        safe_write_init_py(
            init_path,
            imports=["import os"]
        )
        
        content = init_path.read_text()
        assert "import os" in content
    
    def test_trailing_newline(self, tmp_path):
        """Test that output always ends with newline."""
        init_path = tmp_path / "__init__.py"
        
        safe_write_init_py(
            init_path,
            imports=["import os"]
        )
        
        content = init_path.read_text()
        assert content.endswith("\n")
    
    def test_none_inputs(self, tmp_path):
        """Test with None for optional parameters."""
        init_path = tmp_path / "__init__.py"
        
        safe_write_init_py(
            init_path,
            imports=None,
            all_exports=None,
            extra_content=""
        )
        
        assert init_path.exists()
