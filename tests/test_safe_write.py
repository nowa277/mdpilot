"""Tests for safe_write utilities."""

import pytest
from pathlib import Path
from mdpilot.utils.safe_write import safe_write_init_py


class TestSafeWriteInitPy:
    """Test safe_write_init_py function."""
    
    def test_create_new_init_file(self, tmp_path):
        init_file = tmp_path / "__init__.py"
        
        safe_write_init_py(init_file, imports=["from foo import bar"])
        
        assert init_file.exists()
        content = init_file.read_text()
        assert "from foo import bar" in content
    
    def test_add_imports_to_existing_file(self, tmp_path):
        init_file = tmp_path / "__init__.py"
        init_file.write_text("from existing import module\n")
        
        safe_write_init_py(init_file, imports=["from new import module"])
        
        content = init_file.read_text()
        assert "from existing import module" in content
        assert "from new import module" in content
    
    def test_deduplicate_imports(self, tmp_path):
        init_file = tmp_path / "__init__.py"
        init_file.write_text("from foo import bar\n")
        
        safe_write_init_py(init_file, imports=["from foo import bar"])
        
        content = init_file.read_text()
        assert content.count("from foo import bar") == 1
    
    def test_add_all_exports(self, tmp_path):
        init_file = tmp_path / "__init__.py"
        
        safe_write_init_py(init_file, all_exports=["foo", "bar"])
        
        content = init_file.read_text()
        assert '__all__ = ["bar", "foo"]' in content
    
    def test_merge_all_exports(self, tmp_path):
        init_file = tmp_path / "__init__.py"
        init_file.write_text('__all__ = ["existing"]\n')
        
        safe_write_init_py(init_file, all_exports=["new"])
        
        content = init_file.read_text()
        assert '"existing"' in content
        assert '"new"' in content
    
    def test_add_extra_content(self, tmp_path):
        init_file = tmp_path / "__init__.py"
        
        safe_write_init_py(init_file, extra_content="# Extra comment")
        
        content = init_file.read_text()
        assert "# Extra comment" in content
    
    def test_preserve_docstring(self, tmp_path):
        init_file = tmp_path / "__init__.py"
        init_file.write_text('"""Module docstring."""\n')
        
        safe_write_init_py(init_file, imports=["from foo import bar"])
        
        content = init_file.read_text()
        assert '"""Module docstring."""' in content
        assert "from foo import bar" in content
    
    def test_creates_parent_directory(self, tmp_path):
        nested_init = tmp_path / "nested" / "dir" / "__init__.py"
        
        safe_write_init_py(nested_init, imports=["from foo import bar"])
        
        assert nested_init.exists()
        assert nested_init.parent.exists()
    
    def test_sorted_imports(self, tmp_path):
        init_file = tmp_path / "__init__.py"
        
        safe_write_init_py(init_file, imports=["from z import a", "from a import z"])
        
        content = init_file.read_text()
        lines = content.splitlines()
        import_lines = [l for l in lines if l.startswith("from")]
        assert import_lines == ["from a import z", "from z import a"]
    
    def test_sorted_all_exports(self, tmp_path):
        init_file = tmp_path / "__init__.py"
        
        safe_write_init_py(init_file, all_exports=["zebra", "apple", "banana"])
        
        content = init_file.read_text()
        assert '__all__ = ["apple", "banana", "zebra"]' in content


class TestSafeWriteEdgeCases:
    """Test edge cases for safe_write_init_py."""
    
    def test_single_line_docstring_triple_double_quotes(self, tmp_path):
        """Test single-line docstring with triple double quotes."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text('"""Single line docstring."""\n')
        
        safe_write_init_py(init_file, imports=["from foo import bar"])
        
        content = init_file.read_text()
        assert '"""Single line docstring."""' in content
        assert "from foo import bar" in content
    
    def test_single_line_docstring_triple_single_quotes(self, tmp_path):
        """Test single-line docstring with triple single quotes."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("'''Single line docstring.'''\n")
        
        safe_write_init_py(init_file, imports=["from foo import bar"])
        
        content = init_file.read_text()
        assert "'''Single line docstring.'''" in content
        assert "from foo import bar" in content
    
    def test_multiline_docstring_triple_double_quotes(self, tmp_path):
        """Test multi-line docstring with triple double quotes."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text('"""Multi-line\ndocstring\nhere."""\n')
        
        safe_write_init_py(init_file, imports=["from foo import bar"])
        
        content = init_file.read_text()
        assert '"""Multi-line' in content
        assert 'here."""' in content
        assert "from foo import bar" in content
    
    def test_multiline_docstring_triple_single_quotes(self, tmp_path):
        """Test multi-line docstring with triple single quotes."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("'''Multi-line\ndocstring\nhere.'''\n")
        
        safe_write_init_py(init_file, imports=["from foo import bar"])
        
        content = init_file.read_text()
        assert "'''Multi-line" in content
        assert "here.'''" in content
        assert "from foo import bar" in content
    
    def test_header_with_comments(self, tmp_path):
        """Test preserving header comments."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("# Header comment\n# Another comment\n\n")
        
        safe_write_init_py(init_file, imports=["from foo import bar"])
        
        content = init_file.read_text()
        assert "# Header comment" in content
        assert "# Another comment" in content
        assert "from foo import bar" in content
    
    def test_empty_lines_in_header(self, tmp_path):
        """Test preserving empty lines in header."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("# Comment\n\n# Another\n")
        
        safe_write_init_py(init_file, imports=["from foo import bar"])
        
        content = init_file.read_text()
        lines = content.splitlines()
        assert "# Comment" in lines
        assert "# Another" in lines


class TestParseAllList:
    """Test _parse_all_list helper function."""
    
    def test_parse_all_with_brackets(self, tmp_path):
        """Test parsing __all__ with square brackets."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text('__all__ = ["foo", "bar", "baz"]\n')
        
        safe_write_init_py(init_file, all_exports=["qux"])
        
        content = init_file.read_text()
        assert '"foo"' in content
        assert '"bar"' in content
        assert '"baz"' in content
        assert '"qux"' in content
    
    def test_parse_all_single_quotes(self, tmp_path):
        """Test parsing __all__ with single quotes."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("__all__ = ['foo', 'bar']\n")
        
        safe_write_init_py(init_file, all_exports=["baz"])
        
        content = init_file.read_text()
        # Should preserve or convert to double quotes
        assert "foo" in content
        assert "bar" in content
        assert "baz" in content
