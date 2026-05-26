"""Tests for sander tool."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import subprocess
import threading


class TestParseEnergyLine:
    """Test _parse_energy_line helper function."""
    
    def test_parse_energy_line_with_etot(self):
        from mdpilot.tools.builtin.amber.sander import _parse_energy_line
        
        line = "   NSTEP =    100   TIME(PS) =      20.000  Temp  =   300.12  Etot   =  -12345.6789"
        result = _parse_energy_line(line)
        
        assert result is not None
        assert "NSTEP" in result
        assert result["NSTEP"] == "100"
        assert "Temp" in result
        assert result["Temp"] == "300.12"
        assert "Etot" in result
        assert result["Etot"] == "-12345.6789"
    
    def test_parse_energy_line_without_etot(self):
        from mdpilot.tools.builtin.amber.sander import _parse_energy_line
        
        line = "   NSTEP =    100   TIME(PS) =      20.000"
        result = _parse_energy_line(line)
        
        assert result is None
    
    def test_parse_energy_line_scientific_notation(self):
        from mdpilot.tools.builtin.amber.sander import _parse_energy_line
        
        line = "Etot   =    -1.2345e+04  EPtot      =    -2.3456E+04"
        result = _parse_energy_line(line)
        
        assert result is not None
        assert result["Etot"] == "-1.2345e+04"
        assert result["EPtot"] == "-2.3456E+04"
    
    def test_parse_energy_line_empty(self):
        from mdpilot.tools.builtin.amber.sander import _parse_energy_line
        
        result = _parse_energy_line("")
        assert result is None


class TestSanderRun:
    """Test sander_run function."""
    
    def test_sander_not_found(self):
        from mdpilot.tools.builtin.amber.sander import sander_run
        
        with patch('shutil.which', return_value=None):
            with patch.dict('os.environ', {}, clear=True):
                result = sander_run(
                    input_config="test",
                    prmtop="test.prmtop",
                    inpcrd="test.inpcrd"
                )
                
                assert "Error: sander/pmemd not found" in result
    
    def test_sander_found_in_path(self, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        
        prmtop = tmp_path / "test.prmtop"
        prmtop.touch()
        inpcrd = tmp_path / "test.inpcrd"
        inpcrd.touch()
        
        mock_proc = Mock()
        mock_stdout = Mock()
        mock_stdout.__iter__ = Mock(return_value=iter(["test output\n"]))
        mock_stdout.close = Mock()
        mock_proc.stdout = mock_stdout
        mock_proc.stderr = None
        mock_proc.wait = Mock(return_value=0)
        
        with patch('shutil.which', return_value="/usr/bin/sander"):
            with patch('subprocess.Popen', return_value=mock_proc):
                with patch('threading.Timer') as mock_timer:
                    result = sander_run(
                        input_config="test config",
                        prmtop=str(prmtop),
                        inpcrd=str(inpcrd),
                        workdir=str(tmp_path)
                    )
                    
                    assert isinstance(result, str)
                    mock_timer.return_value.start.assert_called_once()
                    mock_timer.return_value.cancel.assert_called_once()
    
    def test_sander_found_in_amberhome(self, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        
        amberhome = tmp_path / "amber"
        amberhome.mkdir()
        (amberhome / "bin").mkdir()
        sander_exe = amberhome / "bin" / "sander"
        sander_exe.touch()
        
        prmtop = tmp_path / "test.prmtop"
        prmtop.touch()
        inpcrd = tmp_path / "test.inpcrd"
        inpcrd.touch()
        
        mock_proc = Mock()
        mock_stdout = Mock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.close = Mock()
        mock_proc.stdout = mock_stdout
        mock_proc.stderr = None
        mock_proc.wait = Mock(return_value=0)
        
        with patch('shutil.which', return_value=None):
            with patch.dict('os.environ', {'AMBERHOME': str(amberhome)}):
                with patch('subprocess.Popen', return_value=mock_proc):
                    with patch('threading.Timer'):
                        result = sander_run(
                            input_config="test",
                            prmtop=str(prmtop),
                            inpcrd=str(inpcrd),
                            workdir=str(tmp_path)
                        )
                        
                        assert isinstance(result, str)
    
    def test_use_pmemd_cuda_mpi(self, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        
        prmtop = tmp_path / "test.prmtop"
        prmtop.touch()
        inpcrd = tmp_path / "test.inpcrd"
        inpcrd.touch()
        
        mock_proc = Mock()
        mock_stdout = Mock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.close = Mock()
        mock_proc.stdout = mock_stdout
        mock_proc.stderr = None
        mock_proc.wait = Mock(return_value=0)
        
        with patch('shutil.which', side_effect=lambda x: "/usr/bin/pmemd.cuda.MPI" if x == "pmemd.cuda.MPI" else None):
            with patch('subprocess.Popen', return_value=mock_proc) as mock_popen:
                with patch('threading.Timer'):
                    result = sander_run(
                        input_config="test",
                        prmtop=str(prmtop),
                        inpcrd=str(inpcrd),
                        workdir=str(tmp_path),
                        use_pmemd=True
                    )
                    
                    cmd = mock_popen.call_args[0][0]
                    assert "/usr/bin/pmemd.cuda.MPI" in cmd
    
    def test_use_pmemd_fallback_order(self, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        
        prmtop = tmp_path / "test.prmtop"
        prmtop.touch()
        inpcrd = tmp_path / "test.inpcrd"
        inpcrd.touch()
        
        mock_proc = Mock()
        mock_stdout = Mock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.close = Mock()
        mock_proc.stdout = mock_stdout
        mock_proc.stderr = None
        mock_proc.wait = Mock(return_value=0)
        
        def which_side_effect(name):
            if name == "pmemd":
                return "/usr/bin/pmemd"
            return None
        
        with patch('shutil.which', side_effect=which_side_effect):
            with patch('subprocess.Popen', return_value=mock_proc) as mock_popen:
                with patch('threading.Timer'):
                    result = sander_run(
                        input_config="test",
                        prmtop=str(prmtop),
                        inpcrd=str(inpcrd),
                        workdir=str(tmp_path),
                        use_pmemd=True
                    )
                    
                    cmd = mock_popen.call_args[0][0]
                    assert "/usr/bin/pmemd" in cmd
    
    def test_prmtop_not_found(self, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        
        inpcrd = tmp_path / "test.inpcrd"
        inpcrd.touch()
        
        with patch('shutil.which', return_value="/usr/bin/sander"):
            result = sander_run(
                input_config="test",
                prmtop="nonexistent.prmtop",
                inpcrd=str(inpcrd),
                workdir=str(tmp_path)
            )
            
            assert "Error: prmtop not found" in result
    
    def test_inpcrd_not_found(self, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        
        prmtop = tmp_path / "test.prmtop"
        prmtop.touch()
        
        with patch('shutil.which', return_value="/usr/bin/sander"):
            result = sander_run(
                input_config="test",
                prmtop=str(prmtop),
                inpcrd="nonexistent.inpcrd",
                workdir=str(tmp_path)
            )
            
            assert "Error: inpcrd not found" in result
    
    def test_mpi_command_with_nproc(self, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        
        prmtop = tmp_path / "test.prmtop"
        prmtop.touch()
        inpcrd = tmp_path / "test.inpcrd"
        inpcrd.touch()
        
        mock_proc = Mock()
        mock_stdout = Mock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.close = Mock()
        mock_proc.stdout = mock_stdout
        mock_proc.stderr = None
        mock_proc.wait = Mock(return_value=0)
        
        with patch('shutil.which', side_effect=lambda x: "/usr/bin/pmemd.MPI" if x == "pmemd.MPI" else None):
            with patch('subprocess.Popen', return_value=mock_proc) as mock_popen:
                with patch('threading.Timer'):
                    result = sander_run(
                        input_config="test",
                        prmtop=str(prmtop),
                        inpcrd=str(inpcrd),
                        workdir=str(tmp_path),
                        use_pmemd=True,
                        nproc=4
                    )
                    
                    cmd = mock_popen.call_args[0][0]
                    assert "mpirun" in cmd
                    assert "-np" in cmd
                    assert "4" in cmd
    
    def test_trajectory_output(self, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        
        prmtop = tmp_path / "test.prmtop"
        prmtop.touch()
        inpcrd = tmp_path / "test.inpcrd"
        inpcrd.touch()
        
        mock_proc = Mock()
        mock_stdout = Mock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.close = Mock()
        mock_proc.stdout = mock_stdout
        mock_proc.stderr = None
        mock_proc.wait = Mock(return_value=0)
        
        with patch('shutil.which', return_value="/usr/bin/sander"):
            with patch('subprocess.Popen', return_value=mock_proc) as mock_popen:
                with patch('threading.Timer'):
                    result = sander_run(
                        input_config="test",
                        prmtop=str(prmtop),
                        inpcrd=str(inpcrd),
                        workdir=str(tmp_path),
                        trajectory="md.nc"
                    )
                    
                    cmd = mock_popen.call_args[0][0]
                    assert "-x" in cmd
                    x_idx = cmd.index("-x")
                    assert "md.nc" in cmd[x_idx + 1]
    
    def test_progress_callback_nstep(self, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        
        prmtop = tmp_path / "test.prmtop"
        prmtop.touch()
        inpcrd = tmp_path / "test.inpcrd"
        inpcrd.touch()
        
        output_lines = [
            "   NSTEP =    100   TIME(PS) =      20.000  Temp  =   300.12  Etot   =  -12345.6789\n",
            "   NSTEP =    200   TIME(PS) =      40.000  Temp  =   301.00  Etot   =  -12340.0000\n"
        ]
        
        mock_proc = Mock()
        mock_stdout = Mock()
        mock_stdout.__iter__ = Mock(return_value=iter(output_lines))
        mock_stdout.close = Mock()
        mock_proc.stdout = mock_stdout
        mock_proc.stderr = None
        mock_proc.wait = Mock(return_value=0)
        
        callback_data = []
        def callback(data):
            callback_data.append(data)
        
        with patch('shutil.which', return_value="/usr/bin/sander"):
            with patch('subprocess.Popen', return_value=mock_proc):
                with patch('threading.Timer'):
                    result = sander_run(
                        input_config="test",
                        prmtop=str(prmtop),
                        inpcrd=str(inpcrd),
                        workdir=str(tmp_path),
                        progress_callback=callback
                    )
                    
                    assert len(callback_data) == 2
                    assert callback_data[0]["nstep"] == 100
                    assert "Etot" in callback_data[0]["energy"]
                    assert callback_data[1]["nstep"] == 200
    
    def test_progress_callback_energy_line(self, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        
        prmtop = tmp_path / "test.prmtop"
        prmtop.touch()
        inpcrd = tmp_path / "test.inpcrd"
        inpcrd.touch()
        
        output_lines = [
            "Etot   =    -12345.6789  EPtot      =    -23456.7890\n"
        ]
        
        mock_proc = Mock()
        mock_stdout = Mock()
        mock_stdout.__iter__ = Mock(return_value=iter(output_lines))
        mock_stdout.close = Mock()
        mock_proc.stdout = mock_stdout
        mock_proc.stderr = None
        mock_proc.wait = Mock(return_value=0)
        
        callback_data = []
        def callback(data):
            callback_data.append(data)
        
        with patch('shutil.which', return_value="/usr/bin/sander"):
            with patch('subprocess.Popen', return_value=mock_proc):
                with patch('threading.Timer'):
                    result = sander_run(
                        input_config="test",
                        prmtop=str(prmtop),
                        inpcrd=str(inpcrd),
                        workdir=str(tmp_path),
                        progress_callback=callback
                    )
                    
                    assert len(callback_data) == 1
                    assert "Etot" in callback_data[0]["energy"]
                    assert callback_data[0]["energy"]["Etot"] == "-12345.6789"
    
    def test_timeout_handling(self, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        
        prmtop = tmp_path / "test.prmtop"
        prmtop.touch()
        inpcrd = tmp_path / "test.inpcrd"
        inpcrd.touch()
        
        mock_proc = Mock()
        mock_stdout = Mock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.close = Mock()
        mock_proc.stdout = mock_stdout
        mock_proc.stderr = None
        mock_proc.wait = Mock(return_value=0)
        mock_proc.kill = Mock()
        
        def timer_side_effect(timeout_val, func, args):
            timer = Mock()
            timer.daemon = True
            timer.start = Mock(side_effect=lambda: func(*args))
            timer.cancel = Mock()
            return timer
        
        with patch('shutil.which', return_value="/usr/bin/sander"):
            with patch('subprocess.Popen', return_value=mock_proc):
                with patch('threading.Timer', side_effect=timer_side_effect):
                    result = sander_run(
                        input_config="test",
                        prmtop=str(prmtop),
                        inpcrd=str(inpcrd),
                        workdir=str(tmp_path),
                        timeout=10
                    )
                    
                    assert "timed out after 10s" in result
                    mock_proc.kill.assert_called_once()
    
    def test_output_file_parsing_completed(self, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        
        prmtop = tmp_path / "test.prmtop"
        prmtop.touch()
        inpcrd = tmp_path / "test.inpcrd"
        inpcrd.touch()
        
        output_file = tmp_path / "md.out"
        output_file.write_text("""
   NSTEP =    100   TIME(PS) =      20.000  Temp  =   300.12  Etot   =  -12345.6789
   NSTEP =    200   TIME(PS) =      40.000  Temp  =   301.00  Etot   =  -12340.0000
|  STOP  STOP  STOP  STOP  STOP  STOP  STOP  STOP  STOP  STOP  STOP  STOP  STOP
""")
        
        mock_proc = Mock()
        mock_stdout = Mock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.close = Mock()
        mock_proc.stdout = mock_stdout
        mock_proc.stderr = None
        mock_proc.wait = Mock(return_value=0)
        
        with patch('shutil.which', return_value="/usr/bin/sander"):
            with patch('subprocess.Popen', return_value=mock_proc):
                with patch('threading.Timer'):
                    result = sander_run(
                        input_config="test",
                        prmtop=str(prmtop),
                        inpcrd=str(inpcrd),
                        workdir=str(tmp_path)
                    )
                    
                    assert "[status: completed]" in result
                    assert "[final energy]" in result
    
    def test_output_file_parsing_incomplete(self, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        
        prmtop = tmp_path / "test.prmtop"
        prmtop.touch()
        inpcrd = tmp_path / "test.inpcrd"
        inpcrd.touch()
        
        output_file = tmp_path / "md.out"
        output_file.write_text("""
   NSTEP =    100   TIME(PS) =      20.000  Temp  =   300.12  Etot   =  -12345.6789
""")
        
        mock_proc = Mock()
        mock_stdout = Mock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.close = Mock()
        mock_proc.stdout = mock_stdout
        mock_proc.stderr = None
        mock_proc.wait = Mock(return_value=1)
        
        with patch('shutil.which', return_value="/usr/bin/sander"):
            with patch('subprocess.Popen', return_value=mock_proc):
                with patch('threading.Timer'):
                    result = sander_run(
                        input_config="test",
                        prmtop=str(prmtop),
                        inpcrd=str(inpcrd),
                        workdir=str(tmp_path)
                    )
                    
                    assert "[status: may be incomplete" in result
    
    def test_stderr_captured_when_no_output(self, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        
        prmtop = tmp_path / "test.prmtop"
        prmtop.touch()
        inpcrd = tmp_path / "test.inpcrd"
        inpcrd.touch()
        
        mock_stderr = Mock()
        mock_stderr.read = Mock(return_value="error message from sander")
        
        mock_proc = Mock()
        mock_stdout = Mock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.close = Mock()
        mock_proc.stdout = mock_stdout
        mock_proc.stderr = mock_stderr
        mock_proc.wait = Mock(return_value=1)
        
        with patch('shutil.which', return_value="/usr/bin/sander"):
            with patch('subprocess.Popen', return_value=mock_proc):
                with patch('threading.Timer'):
                    result = sander_run(
                        input_config="test",
                        prmtop=str(prmtop),
                        inpcrd=str(inpcrd),
                        workdir=str(tmp_path)
                    )
                    
                    assert "[stderr]" in result
                    assert "error message" in result
    
    def test_trajectory_file_info(self, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        
        prmtop = tmp_path / "test.prmtop"
        prmtop.touch()
        inpcrd = tmp_path / "test.inpcrd"
        inpcrd.touch()
        traj = tmp_path / "md.nc"
        traj.write_bytes(b"x" * (5 * 1024 * 1024))
        
        mock_proc = Mock()
        mock_stdout = Mock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.close = Mock()
        mock_proc.stdout = mock_stdout
        mock_proc.stderr = None
        mock_proc.wait = Mock(return_value=0)
        
        with patch('shutil.which', return_value="/usr/bin/sander"):
            with patch('subprocess.Popen', return_value=mock_proc):
                with patch('threading.Timer'):
                    result = sander_run(
                        input_config="test",
                        prmtop=str(prmtop),
                        inpcrd=str(inpcrd),
                        workdir=str(tmp_path),
                        trajectory="md.nc"
                    )
                    
                    assert "[trajectory:" in result
                    assert "5.0 MB" in result
    
    def test_restart_file_info(self, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        
        prmtop = tmp_path / "test.prmtop"
        prmtop.touch()
        inpcrd = tmp_path / "test.inpcrd"
        inpcrd.touch()
        restart = tmp_path / "md.rst"
        restart.touch()
        
        mock_proc = Mock()
        mock_stdout = Mock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.close = Mock()
        mock_proc.stdout = mock_stdout
        mock_proc.stderr = None
        mock_proc.wait = Mock(return_value=0)
        
        with patch('shutil.which', return_value="/usr/bin/sander"):
            with patch('subprocess.Popen', return_value=mock_proc):
                with patch('threading.Timer'):
                    result = sander_run(
                        input_config="test",
                        prmtop=str(prmtop),
                        inpcrd=str(inpcrd),
                        workdir=str(tmp_path)
                    )
                    
                    assert "[restart:" in result
    
    def test_temp_workdir_info(self, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        
        prmtop = tmp_path / "test.prmtop"
        prmtop.touch()
        inpcrd = tmp_path / "test.inpcrd"
        inpcrd.touch()
        
        mock_proc = Mock()
        mock_stdout = Mock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.close = Mock()
        mock_proc.stdout = mock_stdout
        mock_proc.stderr = None
        mock_proc.wait = Mock(return_value=0)
        
        with patch('shutil.which', return_value="/usr/bin/sander"):
            with patch('subprocess.Popen', return_value=mock_proc):
                with patch('threading.Timer'):
                    with patch('tempfile.mkdtemp', return_value=str(tmp_path)):
                        result = sander_run(
                            input_config="test",
                            prmtop=str(prmtop),
                            inpcrd=str(inpcrd),
                            workdir=None
                        )
                        
                        assert "[workdir:" in result
    
    def test_popen_exception(self, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        
        prmtop = tmp_path / "test.prmtop"
        prmtop.touch()
        inpcrd = tmp_path / "test.inpcrd"
        inpcrd.touch()
        
        with patch('shutil.which', return_value="/usr/bin/sander"):
            with patch('subprocess.Popen', side_effect=OSError("cannot execute")):
                result = sander_run(
                    input_config="test",
                    prmtop=str(prmtop),
                    inpcrd=str(inpcrd),
                    workdir=str(tmp_path)
                )
                
                assert "Error starting sander" in result
                assert "OSError" in result
    
    def test_input_file_written(self, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        
        prmtop = tmp_path / "test.prmtop"
        prmtop.touch()
        inpcrd = tmp_path / "test.inpcrd"
        inpcrd.touch()
        
        mock_proc = Mock()
        mock_stdout = Mock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.close = Mock()
        mock_proc.stdout = mock_stdout
        mock_proc.stderr = None
        mock_proc.wait = Mock(return_value=0)
        
        config = "imin=1, maxcyc=100"
        
        with patch('shutil.which', return_value="/usr/bin/sander"):
            with patch('subprocess.Popen', return_value=mock_proc):
                with patch('threading.Timer'):
                    result = sander_run(
                        input_config=config,
                        prmtop=str(prmtop),
                        inpcrd=str(inpcrd),
                        workdir=str(tmp_path)
                    )
                    
                    input_file = tmp_path / "sander.in"
                    assert input_file.exists()
                    assert input_file.read_text() == config
    
    def test_last_nstep_and_energy_reported(self, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        
        prmtop = tmp_path / "test.prmtop"
        prmtop.touch()
        inpcrd = tmp_path / "test.inpcrd"
        inpcrd.touch()
        
        output_lines = [
            "   NSTEP =    500   TIME(PS) =     100.000  Temp  =   305.00  Etot   =  -11111.1111  Press =  1.0\n"
        ]
        
        mock_proc = Mock()
        mock_stdout = Mock()
        mock_stdout.__iter__ = Mock(return_value=iter(output_lines))
        mock_stdout.close = Mock()
        mock_proc.stdout = mock_stdout
        mock_proc.stderr = None
        mock_proc.wait = Mock(return_value=0)
        
        with patch('shutil.which', return_value="/usr/bin/sander"):
            with patch('subprocess.Popen', return_value=mock_proc):
                with patch('threading.Timer'):
                    result = sander_run(
                        input_config="test",
                        prmtop=str(prmtop),
                        inpcrd=str(inpcrd),
                        workdir=str(tmp_path)
                    )
                    
                    assert "[last nstep: 500]" in result
                    assert "[final energies:" in result
                    assert "Etot" in result
                    assert "Temp" in result
