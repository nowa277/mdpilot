"""Security tests for file operations tools."""

import os
import tempfile
from pathlib import Path

import pytest

from mdpilot.tools.builtin.file_ops import file_read, file_search, file_write


class TestFileOpsSecurity:
    """Test security validations in file operations."""

    def test_file_read_blocks_path_traversal(self):
        """Should block reading files outside working directory."""
        result = file_read("../../../../etc/passwd")
        assert "Path traversal blocked" in result or "Error" in result

    def test_file_read_blocks_absolute_path_outside_workdir(self):
        """Should block reading absolute paths outside working directory."""
        result = file_read("/etc/passwd")
        assert "Path traversal blocked" in result or "Error" in result

    def test_file_write_blocks_path_traversal(self):
        """Should block writing files outside working directory."""
        result = file_write("../../../../tmp/malicious.txt", "evil content")
        assert "Path traversal blocked" in result or "Error" in result

    def test_file_write_blocks_absolute_path_outside_workdir(self):
        """Should block writing to absolute paths outside working directory."""
        result = file_write("/tmp/malicious.txt", "evil content")
        assert "Path traversal blocked" in result or "Error" in result

    def test_file_search_blocks_path_traversal(self):
        """Should block searching outside working directory."""
        result = file_search("passwd", path="../../../../etc")
        assert "Path traversal blocked" in result or "Error" in result

    def test_file_search_blocks_absolute_path_outside_workdir(self):
        """Should block searching absolute paths outside working directory."""
        result = file_search("passwd", path="/etc")
        assert "Path traversal blocked" in result or "Error" in result

    def test_file_read_allows_relative_paths_in_workdir(self):
        """Should allow reading files within working directory."""
        # Create a temp file in current directory
        with tempfile.NamedTemporaryFile(mode="w", delete=False, dir=".", suffix=".txt") as f:
            f.write("test content")
            temp_path = f.name

        try:
            result = file_read(Path(temp_path).name)
            assert "test content" in result
        finally:
            os.unlink(temp_path)

    def test_file_write_allows_relative_paths_in_workdir(self):
        """Should allow writing files within working directory."""
        temp_name = f"test_write_{os.getpid()}.txt"
        try:
            result = file_write(temp_name, "test content")
            assert "Successfully wrote" in result
            assert Path(temp_name).exists()
        finally:
            if Path(temp_name).exists():
                os.unlink(temp_name)

    def test_file_search_allows_relative_paths_in_workdir(self):
        """Should allow searching within working directory."""
        result = file_search("test", path=".")
        assert "Error" not in result or "No files found" in result

    def test_file_read_allows_subdirectories(self):
        """Should allow reading files in subdirectories of working directory."""
        # Create a temp subdirectory
        temp_dir = Path(f"test_subdir_{os.getpid()}")
        temp_dir.mkdir(exist_ok=True)
        temp_file = temp_dir / "test.txt"

        try:
            temp_file.write_text("test content")
            result = file_read(str(temp_file))
            assert "test content" in result
        finally:
            if temp_file.exists():
                temp_file.unlink()
            if temp_dir.exists():
                temp_dir.rmdir()

    def test_file_write_allows_subdirectories(self):
        """Should allow writing files in subdirectories of working directory."""
        temp_dir = Path(f"test_subdir_{os.getpid()}")
        temp_file = temp_dir / "test.txt"

        try:
            result = file_write(str(temp_file), "test content")
            assert "Successfully wrote" in result
            assert temp_file.exists()
        finally:
            if temp_file.exists():
                temp_file.unlink()
            if temp_dir.exists():
                temp_dir.rmdir()

    def test_file_search_allows_subdirectories(self):
        """Should allow searching in subdirectories of working directory."""
        temp_dir = Path(f"test_subdir_{os.getpid()}")
        temp_dir.mkdir(exist_ok=True)

        try:
            result = file_search("test", path=str(temp_dir))
            assert "Path traversal blocked" not in result
        finally:
            if temp_dir.exists():
                temp_dir.rmdir()
