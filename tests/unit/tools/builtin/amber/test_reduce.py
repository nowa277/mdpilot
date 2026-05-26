"""
Unit tests for tools/builtin/amber/reduce.py

Tests reduce tool wrapper for adding/removing hydrogens.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open, MagicMock
from mdpilot.tools.builtin.amber.reduce import reduce_run


class TestReduceRun:
    """Test reduce_run function."""
    
    @patch('shutil.which')
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open)
    def test_build_mode_success(self, mock_file, mock_run, mock_which, tmp_path):
        """Test successful hydrogen building."""
        mock_which.return_value = "/usr/bin/reduce"
        mock_run.return_value = Mock(stderr="reduce: processing...", returncode=0)
        
        input_pdb = tmp_path / "input.pdb"
        input_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        output_pdb = tmp_path / "input_H.pdb"
        output_pdb.write_text("ATOM      1  CA  ALA A   1\nATOM      2  H   ALA A   1\n")
        
        result = reduce_run(str(input_pdb), workdir=str(tmp_path))
        
        assert "reduce: processing..." in result
        assert "output:" in result.lower()
        mock_run.assert_called_once()
    
    @patch('shutil.which')
    def test_reduce_not_found(self, mock_which):
        """Test error when reduce is not found."""
        mock_which.return_value = None
        
        with patch.dict('os.environ', {}, clear=True):
            result = reduce_run("/tmp/test.pdb")
        
        assert "Error: reduce not found" in result
    
    @patch('shutil.which')
    @patch('os.environ.get')
    def test_reduce_from_amberhome(self, mock_env_get, mock_which, tmp_path):
        """Test finding reduce in AMBERHOME."""
        mock_which.return_value = None
        
        amber_bin = tmp_path / "amber" / "bin"
        amber_bin.mkdir(parents=True)
        reduce_exe = amber_bin / "reduce"
        reduce_exe.touch()
        reduce_exe.chmod(0o755)
        
        def env_side_effect(key, default=""):
            if key == "AMBERHOME":
                return str(tmp_path / "amber")
            return default
        
        mock_env_get.side_effect = env_side_effect
        
        input_pdb = tmp_path / "input.pdb"
        input_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(stderr="", returncode=0)
            with patch('builtins.open', mock_open()):
                result = reduce_run(str(input_pdb), workdir=str(tmp_path))
        
        assert "Error: reduce not found" not in result
    
    @patch('shutil.which')
    def test_input_file_not_found(self, mock_which):
        """Test error when input file doesn't exist."""
        mock_which.return_value = "/usr/bin/reduce"
        result = reduce_run("/nonexistent/file.pdb")
        
        assert "Error: input PDB not found" in result
    
    @patch('shutil.which')
    def test_input_not_a_file(self, mock_which, tmp_path):
        """Test error when input is a directory."""
        mock_which.return_value = "/usr/bin/reduce"
        dir_path = tmp_path / "not_a_file"
        dir_path.mkdir()
        
        result = reduce_run(str(dir_path))
        
        assert "Error: input path is not a file" in result
    
    @patch('shutil.which')
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open)
    def test_trim_mode(self, mock_file, mock_run, mock_which, tmp_path):
        """Test hydrogen removal mode."""
        mock_which.return_value = "/usr/bin/reduce"
        mock_run.return_value = Mock(stderr="", returncode=0)
        
        input_pdb = tmp_path / "input.pdb"
        input_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        output_pdb = tmp_path / "input_noH.pdb"
        output_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        result = reduce_run(str(input_pdb), mode="trim", workdir=str(tmp_path))
        
        cmd_args = mock_run.call_args[0][0]
        assert "-trim" in cmd_args
    
    @patch('shutil.which')
    def test_invalid_mode(self, mock_which, tmp_path):
        """Test error with invalid mode."""
        mock_which.return_value = "/usr/bin/reduce"
        
        input_pdb = tmp_path / "input.pdb"
        input_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        result = reduce_run(str(input_pdb), mode="invalid")
        
        assert "Error: invalid mode" in result
    
    @patch('shutil.which')
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open)
    def test_noflip_option(self, mock_file, mock_run, mock_which, tmp_path):
        """Test disabling flip optimization."""
        mock_which.return_value = "/usr/bin/reduce"
        mock_run.return_value = Mock(stderr="", returncode=0)
        
        input_pdb = tmp_path / "input.pdb"
        input_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        output_pdb = tmp_path / "input_H.pdb"
        output_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        result = reduce_run(str(input_pdb), flip=False, workdir=str(tmp_path))
        
        cmd_args = mock_run.call_args[0][0]
        assert "-noflip" in cmd_args
    
    @patch('shutil.which')
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open)
    def test_quiet_option(self, mock_file, mock_run, mock_which, tmp_path):
        """Test quiet mode."""
        mock_which.return_value = "/usr/bin/reduce"
        mock_run.return_value = Mock(stderr="", returncode=0)
        
        input_pdb = tmp_path / "input.pdb"
        input_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        output_pdb = tmp_path / "input_H.pdb"
        output_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        result = reduce_run(str(input_pdb), quiet=True, workdir=str(tmp_path))
        
        cmd_args = mock_run.call_args[0][0]
        assert "-quiet" in cmd_args
    
    @patch('shutil.which')
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open)
    def test_custom_output_name(self, mock_file, mock_run, mock_which, tmp_path):
        """Test custom output filename."""
        mock_which.return_value = "/usr/bin/reduce"
        mock_run.return_value = Mock(stderr="", returncode=0)
        
        input_pdb = tmp_path / "input.pdb"
        input_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        output_pdb = tmp_path / "custom_output.pdb"
        output_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        result = reduce_run(str(input_pdb), output="custom_output.pdb", workdir=str(tmp_path))
        
        assert "custom_output.pdb" in result
    
    @patch('shutil.which')
    @patch('subprocess.run')
    def test_timeout_handling(self, mock_run, mock_which, tmp_path):
        """Test timeout error handling."""
        mock_which.return_value = "/usr/bin/reduce"
        mock_run.side_effect = subprocess.TimeoutExpired("reduce", 120)
        
        input_pdb = tmp_path / "input.pdb"
        input_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        result = reduce_run(str(input_pdb), timeout=120, workdir=str(tmp_path))
        
        assert "Error: reduce timed out" in result
    
    @patch('shutil.which')
    @patch('subprocess.run')
    def test_subprocess_error(self, mock_run, mock_which, tmp_path):
        """Test subprocess error handling."""
        mock_which.return_value = "/usr/bin/reduce"
        mock_run.side_effect = OSError("Command failed")
        
        input_pdb = tmp_path / "input.pdb"
        input_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        result = reduce_run(str(input_pdb), workdir=str(tmp_path))
        
        assert "Error running reduce" in result
        assert "OSError" in result
    
    @patch('shutil.which')
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open)
    def test_atom_counting(self, mock_file, mock_run, mock_which, tmp_path):
        """Test atom and hydrogen counting in output."""
        mock_which.return_value = "/usr/bin/reduce"
        mock_run.return_value = Mock(stderr="", returncode=0)
        
        input_pdb = tmp_path / "input.pdb"
        input_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        output_content = """ATOM      1  CA  ALA A   1      10.000  10.000  10.000  1.00 20.00           C
ATOM      2  H   ALA A   1      11.000  11.000  11.000  1.00 20.00           H
HETATM    3  O   HOH A 100      12.000  12.000  12.000  1.00 20.00           O
"""
        output_pdb = tmp_path / "input_H.pdb"
        output_pdb.write_text(output_content)
        
        result = reduce_run(str(input_pdb), workdir=str(tmp_path))
        
        assert "atoms: 2" in result
        assert "hetatm: 1" in result
        assert "hydrogens: 1" in result
    
    @patch('shutil.which')
    def test_path_traversal_prevention(self, mock_which, tmp_path):
        """Test prevention of path traversal attacks."""
        mock_which.return_value = "/usr/bin/reduce"
        input_pdb = tmp_path / "input.pdb"
        input_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        result = reduce_run(
            str(input_pdb),
            output="../../../etc/passwd",
            workdir=str(tmp_path)
        )
        
        assert "Error: output path escapes working directory" in result
    
    @patch('shutil.which')
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open)
    def test_default_output_build_mode(self, mock_file, mock_run, mock_which, tmp_path):
        """Test default output filename in build mode."""
        mock_which.return_value = "/usr/bin/reduce"
        mock_run.return_value = Mock(stderr="", returncode=0)
        
        input_pdb = tmp_path / "protein.pdb"
        input_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        output_pdb = tmp_path / "protein_H.pdb"
        output_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        result = reduce_run(str(input_pdb), workdir=str(tmp_path))
        
        assert "protein_H.pdb" in result
    
    @patch('shutil.which')
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open)
    def test_default_output_trim_mode(self, mock_file, mock_run, mock_which, tmp_path):
        """Test default output filename in trim mode."""
        mock_which.return_value = "/usr/bin/reduce"
        mock_run.return_value = Mock(stderr="", returncode=0)
        
        input_pdb = tmp_path / "protein.pdb"
        input_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        output_pdb = tmp_path / "protein_noH.pdb"
        output_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        result = reduce_run(str(input_pdb), mode="trim", workdir=str(tmp_path))
        
        assert "protein_noH.pdb" in result
    
    @patch('shutil.which')
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open)
    def test_workdir_creation(self, mock_file, mock_run, mock_which, tmp_path):
        """Test that workdir is created if it doesn't exist."""
        mock_which.return_value = "/usr/bin/reduce"
        mock_run.return_value = Mock(stderr="", returncode=0)
        
        input_pdb = tmp_path / "input.pdb"
        input_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        new_workdir = tmp_path / "new_dir" / "subdir"
        output_pdb = new_workdir / "input_H.pdb"
        output_pdb.parent.mkdir(parents=True, exist_ok=True)
        output_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        result = reduce_run(str(input_pdb), workdir=str(new_workdir))
        
        assert new_workdir.exists()
    
    @patch('shutil.which')
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open)
    def test_minimal_environment(self, mock_file, mock_run, mock_which, tmp_path):
        """Test that minimal environment is used."""
        mock_which.return_value = "/usr/bin/reduce"
        mock_run.return_value = Mock(stderr="", returncode=0)
        
        input_pdb = tmp_path / "input.pdb"
        input_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        output_pdb = tmp_path / "input_H.pdb"
        output_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        result = reduce_run(str(input_pdb), workdir=str(tmp_path))
        
        env = mock_run.call_args[1]['env']
        assert set(env.keys()) == {"PATH", "AMBERHOME"}
    
    @patch('shutil.which')
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open)
    def test_output_file_not_created(self, mock_file, mock_run, mock_which, tmp_path):
        """Test warning when output file is not created."""
        mock_which.return_value = "/usr/bin/reduce"
        mock_run.return_value = Mock(stderr="", returncode=0)
        
        input_pdb = tmp_path / "input.pdb"
        input_pdb.write_text("ATOM      1  CA  ALA A   1\n")
        
        result = reduce_run(str(input_pdb), workdir=str(tmp_path))
        
        assert "warning: output file not created" in result


# Import subprocess for TimeoutExpired
import subprocess
