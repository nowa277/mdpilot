"""Tests for propka integration."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess


class TestResiduePka:
    """Test ResiduePka dataclass."""
    
    def test_init(self):
        from mdpilot.tools.builtin.propka import ResiduePka
        
        res = ResiduePka(
            residue_name="HIS",
            residue_number=42,
            chain_id="A",
            pka=6.5,
            model_pka=6.0,
            buried=False
        )
        
        assert res.residue_name == "HIS"
        assert res.residue_number == 42
        assert res.chain_id == "A"
        assert res.pka == 6.5
        assert res.model_pka == 6.0
        assert res.buried is False
        assert res.metal_interaction is False
    
    def test_protonation_state_protonated(self):
        from mdpilot.tools.builtin.propka import ResiduePka
        
        res = ResiduePka("HIS", 42, "A", pka=8.0, model_pka=6.0, buried=False)
        
        assert res.protonation_state(ph=7.0) == "protonated"
    
    def test_protonation_state_deprotonated(self):
        from mdpilot.tools.builtin.propka import ResiduePka
        
        res = ResiduePka("ASP", 10, "A", pka=3.5, model_pka=3.8, buried=False)
        
        assert res.protonation_state(ph=7.0) == "deprotonated"
    
    def test_protonation_state_at_boundary(self):
        from mdpilot.tools.builtin.propka import ResiduePka
        
        res = ResiduePka("HIS", 42, "A", pka=7.0, model_pka=6.0, buried=False)
        
        assert res.protonation_state(ph=7.0) == "deprotonated"


class TestPropkaResult:
    """Test PropkaResult dataclass."""
    
    def test_init(self):
        from mdpilot.tools.builtin.propka import PropkaResult, ResiduePka
        
        pka_values = {
            ("HIS", 42, "A"): ResiduePka("HIS", 42, "A", 6.5, 6.0, False)
        }
        
        result = PropkaResult(pka_values=pka_values, summary="test summary")
        
        assert len(result.pka_values) == 1
        assert result.summary == "test summary"
    
    def test_get_residue_found(self):
        from mdpilot.tools.builtin.propka import PropkaResult, ResiduePka
        
        pka_values = {
            ("HIS", 42, "A"): ResiduePka("HIS", 42, "A", 6.5, 6.0, False)
        }
        result = PropkaResult(pka_values=pka_values, summary="")
        
        res = result.get_residue("HIS", 42, "A")
        
        assert res is not None
        assert res.residue_number == 42
    
    def test_get_residue_not_found(self):
        from mdpilot.tools.builtin.propka import PropkaResult
        
        result = PropkaResult(pka_values={}, summary="")
        
        res = result.get_residue("HIS", 99, "A")
        
        assert res is None
    
    def test_get_his_residues(self):
        from mdpilot.tools.builtin.propka import PropkaResult, ResiduePka
        
        pka_values = {
            ("HIS", 42, "A"): ResiduePka("HIS", 42, "A", 6.5, 6.0, False),
            ("HIS", 50, "A"): ResiduePka("HIS", 50, "A", 7.0, 6.0, False),
            ("ASP", 10, "A"): ResiduePka("ASP", 10, "A", 3.5, 3.8, False)
        }
        result = PropkaResult(pka_values=pka_values, summary="")
        
        his_residues = result.get_his_residues()
        
        assert len(his_residues) == 2
        assert all(r.residue_name == "HIS" for r in his_residues)
    
    def test_get_asp_residues(self):
        from mdpilot.tools.builtin.propka import PropkaResult, ResiduePka
        
        pka_values = {
            ("ASP", 10, "A"): ResiduePka("ASP", 10, "A", 3.5, 3.8, False),
            ("ASP", 20, "A"): ResiduePka("ASP", 20, "A", 4.0, 3.8, False),
            ("GLU", 30, "A"): ResiduePka("GLU", 30, "A", 4.5, 4.2, False)
        }
        result = PropkaResult(pka_values=pka_values, summary="")
        
        asp_residues = result.get_asp_residues()
        
        assert len(asp_residues) == 2
        assert all(r.residue_name == "ASP" for r in asp_residues)
    
    def test_get_glu_residues(self):
        from mdpilot.tools.builtin.propka import PropkaResult, ResiduePka
        
        pka_values = {
            ("GLU", 30, "A"): ResiduePka("GLU", 30, "A", 4.5, 4.2, False),
            ("ASP", 10, "A"): ResiduePka("ASP", 10, "A", 3.5, 3.8, False)
        }
        result = PropkaResult(pka_values=pka_values, summary="")
        
        glu_residues = result.get_glu_residues()
        
        assert len(glu_residues) == 1
        assert glu_residues[0].residue_name == "GLU"
    
    def test_get_lys_residues(self):
        from mdpilot.tools.builtin.propka import PropkaResult, ResiduePka
        
        pka_values = {
            ("LYS", 15, "A"): ResiduePka("LYS", 15, "A", 10.5, 10.4, False),
            ("LYS", 25, "A"): ResiduePka("LYS", 25, "A", 10.8, 10.4, False)
        }
        result = PropkaResult(pka_values=pka_values, summary="")
        
        lys_residues = result.get_lys_residues()
        
        assert len(lys_residues) == 2
        assert all(r.residue_name == "LYS" for r in lys_residues)


class TestPropkaWrapper:
    """Test PropkaWrapper class."""
    
    def test_init_propka_found(self):
        from mdpilot.tools.builtin.propka import PropkaWrapper
        
        with patch('shutil.which', return_value="/usr/bin/propka3"):
            wrapper = PropkaWrapper()
            
            assert wrapper.propka_path == "/usr/bin/propka3"
    
    def test_init_propka_not_found(self):
        from mdpilot.tools.builtin.propka import PropkaWrapper
        
        with patch('shutil.which', return_value=None):
            wrapper = PropkaWrapper()
            
            assert wrapper.propka_path is None
    
    def test_is_available_true(self):
        from mdpilot.tools.builtin.propka import PropkaWrapper
        
        with patch('shutil.which', return_value="/usr/bin/propka3"):
            wrapper = PropkaWrapper()
            
            assert wrapper.is_available() is True
    
    def test_is_available_false(self):
        from mdpilot.tools.builtin.propka import PropkaWrapper
        
        with patch('shutil.which', return_value=None):
            wrapper = PropkaWrapper()
            
            assert wrapper.is_available() is False
    
    def test_run_propka_not_available(self, tmp_path):
        from mdpilot.tools.builtin.propka import PropkaWrapper
        
        pdb_file = tmp_path / "test.pdb"
        pdb_file.touch()
        
        with patch('shutil.which', return_value=None):
            wrapper = PropkaWrapper()
            
            with pytest.raises(RuntimeError, match="propka3 not found"):
                wrapper.run(pdb_file)
    
    def test_run_pdb_not_found(self):
        from mdpilot.tools.builtin.propka import PropkaWrapper
        
        with patch('shutil.which', return_value="/usr/bin/propka3"):
            wrapper = PropkaWrapper()
            
            with pytest.raises(FileNotFoundError, match="PDB file not found"):
                wrapper.run("nonexistent.pdb")
    
    def test_run_path_not_file(self, tmp_path):
        from mdpilot.tools.builtin.propka import PropkaWrapper
        
        directory = tmp_path / "testdir"
        directory.mkdir()
        
        with patch('shutil.which', return_value="/usr/bin/propka3"):
            wrapper = PropkaWrapper()
            
            with pytest.raises(ValueError, match="Path is not a file"):
                wrapper.run(directory)
    
    def test_run_timeout(self, tmp_path):
        from mdpilot.tools.builtin.propka import PropkaWrapper
        
        pdb_file = tmp_path / "test.pdb"
        pdb_file.write_text("ATOM      1  CA  ALA A   1       0.000   0.000   0.000")
        
        with patch('shutil.which', return_value="/usr/bin/propka3"):
            wrapper = PropkaWrapper()
            
            with patch('subprocess.run', side_effect=subprocess.TimeoutExpired("propka3", 60)):
                with pytest.raises(RuntimeError, match="timed out after 60 seconds"):
                    wrapper.run(pdb_file)
    
    def test_run_nonzero_exit(self, tmp_path):
        from mdpilot.tools.builtin.propka import PropkaWrapper
        
        pdb_file = tmp_path / "test.pdb"
        pdb_file.write_text("ATOM      1  CA  ALA A   1       0.000   0.000   0.000")
        
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "error message"
        mock_result.stdout = "output"
        
        with patch('shutil.which', return_value="/usr/bin/propka3"):
            wrapper = PropkaWrapper()
            
            with patch('subprocess.run', return_value=mock_result):
                with pytest.raises(RuntimeError, match="propka3 failed with exit code 1"):
                    wrapper.run(pdb_file)
    
    def test_run_output_file_not_created(self, tmp_path):
        from mdpilot.tools.builtin.propka import PropkaWrapper
        
        pdb_file = tmp_path / "test.pdb"
        pdb_file.write_text("ATOM      1  CA  ALA A   1       0.000   0.000   0.000")
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "success"
        mock_result.stderr = ""
        
        with patch('shutil.which', return_value="/usr/bin/propka3"):
            wrapper = PropkaWrapper()
            
            with patch('subprocess.run', return_value=mock_result):
                with pytest.raises(RuntimeError, match="did not generate output file"):
                    wrapper.run(pdb_file)
    
    def test_run_success(self, tmp_path):
        from mdpilot.tools.builtin.propka import PropkaWrapper
        
        pdb_file = tmp_path / "test.pdb"
        pdb_file.write_text("ATOM      1  CA  ALA A   1       0.000   0.000   0.000")
        
        pka_file = tmp_path / "test.pka"
        pka_file.write_text("""
SUMMARY OF THIS PREDICTION
ASP  10 A    3.80     3.80    0.00  XXX   0   0    0
HIS  42 A    6.50     6.00    0.50  XXX   0   0    0
""")
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "propka output"
        mock_result.stderr = ""
        
        with patch('shutil.which', return_value="/usr/bin/propka3"):
            wrapper = PropkaWrapper()
            
            with patch('subprocess.run', return_value=mock_result):
                result = wrapper.run(pdb_file)
                
                assert len(result.pka_values) == 2
                assert ("ASP", 10, "A") in result.pka_values
                assert ("HIS", 42, "A") in result.pka_values
    
    def test_run_custom_output_dir(self, tmp_path):
        from mdpilot.tools.builtin.propka import PropkaWrapper
        
        pdb_file = tmp_path / "test.pdb"
        pdb_file.write_text("ATOM      1  CA  ALA A   1       0.000   0.000   0.000")
        
        output_dir = tmp_path / "output"
        pka_file = output_dir / "test.pka"
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "output"
        mock_result.stderr = ""
        
        with patch('shutil.which', return_value="/usr/bin/propka3"):
            wrapper = PropkaWrapper()
            
            with patch('subprocess.run', return_value=mock_result) as mock_run:
                pka_file.parent.mkdir(parents=True, exist_ok=True)
                pka_file.write_text("SUMMARY OF THIS PREDICTION\n")
                
                result = wrapper.run(pdb_file, output_dir=output_dir)
                
                assert mock_run.call_args[1]['cwd'] == output_dir
    
    def test_parse_output_empty_file(self, tmp_path):
        from mdpilot.tools.builtin.propka import PropkaWrapper
        
        pka_file = tmp_path / "test.pka"
        pka_file.write_text("")
        
        with patch('shutil.which', return_value="/usr/bin/propka3"):
            wrapper = PropkaWrapper()
            
            with pytest.raises(RuntimeError, match="output file is empty"):
                wrapper._parse_output(pka_file, "")
    
    def test_parse_output_missing_summary(self, tmp_path):
        from mdpilot.tools.builtin.propka import PropkaWrapper
        
        pka_file = tmp_path / "test.pka"
        pka_file.write_text("Some content without summary section")
        
        with patch('shutil.which', return_value="/usr/bin/propka3"):
            wrapper = PropkaWrapper()
            
            result = wrapper._parse_output(pka_file, "")
            
            assert len(result.pka_values) == 0
    
    def test_parse_output_with_metal_interaction(self, tmp_path):
        from mdpilot.tools.builtin.propka import PropkaWrapper
        
        pka_file = tmp_path / "test.pka"
        pka_file.write_text("""
HIS  60 A   3.50    92 %   -2.57  538   0.00    0    0.00 XXX   0 X    0.00 XXX   0 X   -0.36 ZN   ZN A
SUMMARY OF THIS PREDICTION
HIS  60 A    3.50     6.00   -2.50  XXX   0   0    0
""")
        
        with patch('shutil.which', return_value="/usr/bin/propka3"):
            wrapper = PropkaWrapper()
            
            result = wrapper._parse_output(pka_file, "")
            
            his_res = result.get_residue("HIS", 60, "A")
            assert his_res is not None
            assert his_res.metal_interaction is True
    
    def test_parse_output_buried_residue(self, tmp_path):
        from mdpilot.tools.builtin.propka import PropkaWrapper
        
        pka_file = tmp_path / "test.pka"
        pka_file.write_text("""
SUMMARY OF THIS PREDICTION
ASP  10 A    5.80     3.80    2.00  XXX   0   0    0
""")
        
        with patch('shutil.which', return_value="/usr/bin/propka3"):
            wrapper = PropkaWrapper()
            
            result = wrapper._parse_output(pka_file, "")
            
            asp_res = result.get_residue("ASP", 10, "A")
            assert asp_res is not None
            assert asp_res.buried is True
    
    def test_parse_output_not_buried(self, tmp_path):
        from mdpilot.tools.builtin.propka import PropkaWrapper
        
        pka_file = tmp_path / "test.pka"
        pka_file.write_text("""
SUMMARY OF THIS PREDICTION
ASP  10 A    3.90     3.80    0.10  XXX   0   0    0
""")
        
        with patch('shutil.which', return_value="/usr/bin/propka3"):
            wrapper = PropkaWrapper()
            
            result = wrapper._parse_output(pka_file, "")
            
            asp_res = result.get_residue("ASP", 10, "A")
            assert asp_res is not None
            assert asp_res.buried is False
    
    def test_parse_output_multiple_metals(self, tmp_path):
        from mdpilot.tools.builtin.propka import PropkaWrapper
        
        pka_file = tmp_path / "test.pka"
        pka_file.write_text("""
HIS  60 A   3.50    92 %   -2.57  538   0.00    0    0.00 XXX   0 X    0.00 XXX   0 X   -0.36 ZN   ZN A
ASP  70 A   2.00    80 %   -1.80  400   0.00    0    0.00 XXX   0 X    0.00 XXX   0 X   -0.20 FE   FE A
GLU  80 A   3.00    75 %   -1.20  350   0.00    0    0.00 XXX   0 X    0.00 XXX   0 X   -0.15 CU   CU A
CYS  90 A   8.00    85 %    2.00  450   0.00    0    0.00 XXX   0 X    0.00 XXX   0 X    0.50 MG   MG A
SUMMARY OF THIS PREDICTION
HIS  60 A    3.50     6.00   -2.50  XXX   0   0    0
ASP  70 A    2.00     3.80   -1.80  XXX   0   0    0
GLU  80 A    3.00     4.20   -1.20  XXX   0   0    0
CYS  90 A    8.00     8.50   -0.50  XXX   0   0    0
""")
        
        with patch('shutil.which', return_value="/usr/bin/propka3"):
            wrapper = PropkaWrapper()
            
            result = wrapper._parse_output(pka_file, "")
            
            assert result.get_residue("HIS", 60, "A").metal_interaction is True
            assert result.get_residue("ASP", 70, "A").metal_interaction is True
            assert result.get_residue("GLU", 80, "A").metal_interaction is True
            assert result.get_residue("CYS", 90, "A").metal_interaction is True


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_predict_pka(self, tmp_path):
        from mdpilot.tools.builtin.propka import predict_pka
        
        pdb_file = tmp_path / "test.pdb"
        pdb_file.write_text("ATOM      1  CA  ALA A   1       0.000   0.000   0.000")
        
        pka_file = tmp_path / "test.pka"
        pka_file.write_text("""
SUMMARY OF THIS PREDICTION
HIS  42 A    6.50     6.00    0.50  XXX   0   0    0
""")
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "output"
        mock_result.stderr = ""
        
        with patch('shutil.which', return_value="/usr/bin/propka3"):
            with patch('subprocess.run', return_value=mock_result):
                result = predict_pka(pdb_file, ph=7.0)
                
                assert len(result.pka_values) == 1
    
    def test_is_propka_available_true(self):
        from mdpilot.tools.builtin.propka import is_propka_available
        
        with patch('shutil.which', return_value="/usr/bin/propka3"):
            assert is_propka_available() is True
    
    def test_is_propka_available_false(self):
        from mdpilot.tools.builtin.propka import is_propka_available
        
        with patch('shutil.which', return_value=None):
            assert is_propka_available() is False
