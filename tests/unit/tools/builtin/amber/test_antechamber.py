"""Tests for antechamber tool."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess


class TestAntechamberRun:
    """Test antechamber_run function."""
    
    def test_antechamber_not_found_no_amberhome(self):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        
        with patch('shutil.which', return_value=None):
            with patch.dict('os.environ', {}, clear=True):
                result = antechamber_run("input.mol2")
                
                assert "Error: antechamber not found" in result
                assert "AMBERHOME" in result
    
    def test_antechamber_found_in_path(self, tmp_path):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        
        input_file = tmp_path / "input.mol2"
        input_file.write_text("mock mol2 content")
        
        mock_result = Mock()
        mock_result.stdout = "antechamber output"
        mock_result.stderr = ""
        mock_result.returncode = 0
        
        with patch('shutil.which', return_value="/usr/bin/antechamber"):
            with patch('subprocess.run', return_value=mock_result) as mock_run:
                with patch('pathlib.Path.exists', return_value=True):
                    result = antechamber_run(
                        str(input_file),
                        workdir=str(tmp_path),
                        run_parmchk=False
                    )
                    
                    assert "antechamber output" in result
                    mock_run.assert_called_once()
                    cmd = mock_run.call_args[0][0]
                    assert cmd[0] == "/usr/bin/antechamber"
    
    def test_antechamber_found_in_amberhome(self, tmp_path):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        
        input_file = tmp_path / "input.mol2"
        input_file.write_text("mock mol2 content")
        
        amberhome = tmp_path / "amber"
        amberhome.mkdir()
        (amberhome / "bin").mkdir()
        ante_exe = amberhome / "bin" / "antechamber"
        ante_exe.touch()
        
        mock_result = Mock()
        mock_result.stdout = "output"
        mock_result.stderr = ""
        
        with patch('shutil.which', return_value=None):
            with patch.dict('os.environ', {'AMBERHOME': str(amberhome)}):
                with patch('subprocess.run', return_value=mock_result):
                    with patch('pathlib.Path.exists', return_value=True):
                        result = antechamber_run(
                            str(input_file),
                            workdir=str(tmp_path),
                            run_parmchk=False
                        )
                        
                        assert "output" in result
    
    def test_input_file_not_found(self, tmp_path):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        
        with patch('shutil.which', return_value="/usr/bin/antechamber"):
            result = antechamber_run(
                "nonexistent.mol2",
                workdir=str(tmp_path),
                run_parmchk=False
            )
            
            assert "Error: input file not found" in result
    
    def test_default_parameters(self, tmp_path):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        
        input_file = tmp_path / "input.mol2"
        input_file.write_text("mock mol2")
        
        mock_result = Mock()
        mock_result.stdout = "success"
        mock_result.stderr = ""
        
        with patch('shutil.which', return_value="/usr/bin/antechamber"):
            with patch('subprocess.run', return_value=mock_result) as mock_run:
                with patch('pathlib.Path.exists', return_value=True):
                    result = antechamber_run(
                        str(input_file),
                        workdir=str(tmp_path),
                        run_parmchk=False
                    )
                    
                    cmd = mock_run.call_args[0][0]
                    assert "-fi" in cmd
                    assert "mol2" in cmd
                    assert "-fo" in cmd
                    assert "-c" in cmd
                    assert "bcc" in cmd
                    assert "-nc" in cmd
                    assert "0" in cmd
                    assert "-at" in cmd
                    assert "gaff2" in cmd
    
    def test_custom_parameters(self, tmp_path):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        
        input_file = tmp_path / "input.pdb"
        input_file.write_text("mock pdb")
        
        mock_result = Mock()
        mock_result.stdout = "success"
        mock_result.stderr = ""
        
        with patch('shutil.which', return_value="/usr/bin/antechamber"):
            with patch('subprocess.run', return_value=mock_result) as mock_run:
                with patch('pathlib.Path.exists', return_value=True):
                    result = antechamber_run(
                        str(input_file),
                        input_format="pdb",
                        output_file="custom.prepc",
                        output_format="prepc",
                        charge_method="gas",
                        net_charge=-1,
                        atom_type="gaff",
                        workdir=str(tmp_path),
                        run_parmchk=False,
                        timeout=600
                    )
                    
                    cmd = mock_run.call_args[0][0]
                    assert "pdb" in cmd
                    assert "prepc" in cmd
                    assert "gas" in cmd
                    assert "-1" in cmd
                    assert "gaff" in cmd
                    
                    kwargs = mock_run.call_args[1]
                    assert kwargs['timeout'] == 600
    
    def test_stderr_captured(self, tmp_path):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        
        input_file = tmp_path / "input.mol2"
        input_file.write_text("mock mol2")
        
        mock_result = Mock()
        mock_result.stdout = "stdout content"
        mock_result.stderr = "stderr content"
        
        with patch('shutil.which', return_value="/usr/bin/antechamber"):
            with patch('subprocess.run', return_value=mock_result):
                with patch('pathlib.Path.exists', return_value=True):
                    result = antechamber_run(
                        str(input_file),
                        workdir=str(tmp_path),
                        run_parmchk=False
                    )
                    
                    assert "stdout content" in result
                    assert "[stderr]" in result
                    assert "stderr content" in result
    
    def test_output_file_created(self, tmp_path):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        
        input_file = tmp_path / "input.mol2"
        input_file.write_text("mock mol2")
        output_file = tmp_path / "output.mol2"
        
        mock_result = Mock()
        mock_result.stdout = "success"
        mock_result.stderr = ""
        
        def mock_exists(self):
            return self.name in ["input.mol2", "output.mol2"]
        
        with patch('shutil.which', return_value="/usr/bin/antechamber"):
            with patch('subprocess.run', return_value=mock_result):
                with patch.object(Path, 'exists', mock_exists):
                    result = antechamber_run(
                        str(input_file),
                        workdir=str(tmp_path),
                        run_parmchk=False
                    )
                    
                    assert "[output:" in result
                    assert "output.mol2" in result
    
    def test_output_file_not_created(self, tmp_path):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        
        input_file = tmp_path / "input.mol2"
        input_file.write_text("mock mol2")
        
        mock_result = Mock()
        mock_result.stdout = "failed"
        mock_result.stderr = ""
        
        def mock_exists(self):
            return self.name == "input.mol2"
        
        with patch('shutil.which', return_value="/usr/bin/antechamber"):
            with patch('subprocess.run', return_value=mock_result):
                with patch.object(Path, 'exists', mock_exists):
                    result = antechamber_run(
                        str(input_file),
                        workdir=str(tmp_path),
                        run_parmchk=False
                    )
                    
                    assert "[warning: output file not created]" in result
    
    def test_parmchk2_success(self, tmp_path):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        
        input_file = tmp_path / "input.mol2"
        input_file.write_text("mock mol2")
        
        mock_ante_result = Mock()
        mock_ante_result.stdout = "antechamber done"
        mock_ante_result.stderr = ""
        
        mock_pc_result = Mock()
        mock_pc_result.stdout = "parmchk2 done"
        mock_pc_result.stderr = ""
        
        def mock_exists(self):
            return self.name in ["input.mol2", "output.mol2", "output.frcmod"]
        
        with patch('shutil.which', side_effect=["/usr/bin/antechamber", "/usr/bin/parmchk2"]):
            with patch('subprocess.run', side_effect=[mock_ante_result, mock_pc_result]) as mock_run:
                with patch.object(Path, 'exists', mock_exists):
                    result = antechamber_run(
                        str(input_file),
                        workdir=str(tmp_path),
                        run_parmchk=True
                    )
                    
                    assert "antechamber done" in result
                    assert "[parmchk2]" in result
                    assert "parmchk2 done" in result
                    assert "[frcmod:" in result
                    assert mock_run.call_count == 2
    
    def test_parmchk2_not_found(self, tmp_path):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        
        input_file = tmp_path / "input.mol2"
        input_file.write_text("mock mol2")
        
        mock_result = Mock()
        mock_result.stdout = "antechamber done"
        mock_result.stderr = ""
        
        with patch('shutil.which', side_effect=["/usr/bin/antechamber", None]):
            with patch('subprocess.run', return_value=mock_result) as mock_run:
                with patch('pathlib.Path.exists', return_value=True):
                    result = antechamber_run(
                        str(input_file),
                        workdir=str(tmp_path),
                        run_parmchk=True
                    )
                    
                    assert "antechamber done" in result
                    assert "[parmchk2]" not in result
                    assert mock_run.call_count == 1
    
    def test_parmchk2_timeout(self, tmp_path):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        
        input_file = tmp_path / "input.mol2"
        input_file.write_text("mock mol2")
        
        mock_ante_result = Mock()
        mock_ante_result.stdout = "antechamber done"
        mock_ante_result.stderr = ""
        
        def mock_exists(self):
            return self.name in ["input.mol2", "output.mol2"]
        
        with patch('shutil.which', side_effect=["/usr/bin/antechamber", "/usr/bin/parmchk2"]):
            with patch('subprocess.run', side_effect=[mock_ante_result, subprocess.TimeoutExpired("parmchk2", 60)]):
                with patch.object(Path, 'exists', mock_exists):
                    result = antechamber_run(
                        str(input_file),
                        workdir=str(tmp_path),
                        run_parmchk=True
                    )
                    
                    assert "[parmchk2 timed out]" in result
    
    def test_parmchk2_exception(self, tmp_path):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        
        input_file = tmp_path / "input.mol2"
        input_file.write_text("mock mol2")
        
        mock_ante_result = Mock()
        mock_ante_result.stdout = "antechamber done"
        mock_ante_result.stderr = ""
        
        def mock_exists(self):
            return self.name in ["input.mol2", "output.mol2"]
        
        with patch('shutil.which', side_effect=["/usr/bin/antechamber", "/usr/bin/parmchk2"]):
            with patch('subprocess.run', side_effect=[mock_ante_result, Exception("parmchk2 failed")]):
                with patch.object(Path, 'exists', mock_exists):
                    result = antechamber_run(
                        str(input_file),
                        workdir=str(tmp_path),
                        run_parmchk=True
                    )
                    
                    assert "[parmchk2 error:" in result
                    assert "parmchk2 failed" in result
    
    def test_parmchk2_stderr(self, tmp_path):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        
        input_file = tmp_path / "input.mol2"
        input_file.write_text("mock mol2")
        
        mock_ante_result = Mock()
        mock_ante_result.stdout = "antechamber done"
        mock_ante_result.stderr = ""
        
        mock_pc_result = Mock()
        mock_pc_result.stdout = ""
        mock_pc_result.stderr = "parmchk2 warning"
        
        def mock_exists(self):
            return self.name in ["input.mol2", "output.mol2", "output.frcmod"]
        
        with patch('shutil.which', side_effect=["/usr/bin/antechamber", "/usr/bin/parmchk2"]):
            with patch('subprocess.run', side_effect=[mock_ante_result, mock_pc_result]):
                with patch.object(Path, 'exists', mock_exists):
                    result = antechamber_run(
                        str(input_file),
                        workdir=str(tmp_path),
                        run_parmchk=True
                    )
                    
                    assert "parmchk2 warning" in result
    
    def test_antechamber_timeout(self, tmp_path):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        
        input_file = tmp_path / "input.mol2"
        input_file.write_text("mock mol2")
        
        with patch('shutil.which', return_value="/usr/bin/antechamber"):
            with patch('subprocess.run', side_effect=subprocess.TimeoutExpired("antechamber", 300)):
                result = antechamber_run(
                    str(input_file),
                    workdir=str(tmp_path),
                    run_parmchk=False,
                    timeout=300
                )
                
                assert "Error: antechamber timed out after 300s" in result
    
    def test_antechamber_exception(self, tmp_path):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        
        input_file = tmp_path / "input.mol2"
        input_file.write_text("mock mol2")
        
        with patch('shutil.which', return_value="/usr/bin/antechamber"):
            with patch('subprocess.run', side_effect=RuntimeError("subprocess failed")):
                result = antechamber_run(
                    str(input_file),
                    workdir=str(tmp_path),
                    run_parmchk=False
                )
                
                assert "Error running antechamber" in result
                assert "RuntimeError" in result
                assert "subprocess failed" in result
    
    def test_temp_workdir_created(self, tmp_path):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        
        input_file = tmp_path / "input.mol2"
        input_file.write_text("mock mol2")
        
        mock_result = Mock()
        mock_result.stdout = "success"
        mock_result.stderr = ""
        
        with patch('shutil.which', return_value="/usr/bin/antechamber"):
            with patch('subprocess.run', return_value=mock_result):
                with patch('pathlib.Path.exists', return_value=True):
                    result = antechamber_run(
                        str(input_file),
                        workdir=None,
                        run_parmchk=False
                    )
                    
                    assert "[workdir:" in result
    
    def test_relative_input_path(self, tmp_path):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        
        input_file = tmp_path / "input.mol2"
        input_file.write_text("mock mol2")
        
        mock_result = Mock()
        mock_result.stdout = "success"
        mock_result.stderr = ""
        
        with patch('shutil.which', return_value="/usr/bin/antechamber"):
            with patch('subprocess.run', return_value=mock_result) as mock_run:
                with patch('pathlib.Path.exists', return_value=True):
                    result = antechamber_run(
                        "input.mol2",
                        workdir=str(tmp_path),
                        run_parmchk=False
                    )
                    
                    cmd = mock_run.call_args[0][0]
                    input_arg_idx = cmd.index("-i") + 1
                    assert "input.mol2" in cmd[input_arg_idx]
    
    def test_parmchk2_found_in_amberhome(self, tmp_path):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        
        input_file = tmp_path / "input.mol2"
        input_file.write_text("mock mol2")
        
        amberhome = tmp_path / "amber"
        amberhome.mkdir()
        (amberhome / "bin").mkdir()
        ante_exe = amberhome / "bin" / "antechamber"
        ante_exe.touch()
        pc_exe = amberhome / "bin" / "parmchk2"
        pc_exe.touch()
        
        mock_ante_result = Mock()
        mock_ante_result.stdout = "antechamber done"
        mock_ante_result.stderr = ""
        
        mock_pc_result = Mock()
        mock_pc_result.stdout = "parmchk2 done"
        mock_pc_result.stderr = ""
        
        def mock_exists(self):
            return self.name in ["input.mol2", "output.mol2", "output.frcmod", "antechamber", "parmchk2"]
        
        with patch('shutil.which', return_value=None):
            with patch.dict('os.environ', {'AMBERHOME': str(amberhome)}):
                with patch('subprocess.run', side_effect=[mock_ante_result, mock_pc_result]):
                    with patch.object(Path, 'exists', mock_exists):
                        result = antechamber_run(
                            str(input_file),
                            workdir=str(tmp_path),
                            run_parmchk=True
                        )
                        
                        assert "[parmchk2]" in result
    
    def test_no_output_empty_string(self, tmp_path):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        
        input_file = tmp_path / "input.mol2"
        input_file.write_text("mock mol2")
        
        mock_result = Mock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        
        def mock_exists(self):
            return self.name == "input.mol2"
        
        with patch('shutil.which', return_value="/usr/bin/antechamber"):
            with patch('subprocess.run', return_value=mock_result):
                with patch.object(Path, 'exists', mock_exists):
                    result = antechamber_run(
                        str(input_file),
                        workdir=str(tmp_path),
                        run_parmchk=False
                    )
                    
                    assert "[warning: output file not created]" in result
