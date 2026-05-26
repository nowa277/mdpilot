"""Tests for pmemd.cuda tool."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, mock_open, patch

import pytest

from mdpilot.tools.builtin.amber.pmemd import pmemd_cuda


class TestPmemdCuda:
    """Test suite for pmemd_cuda tool."""

    @pytest.fixture
    def mock_files(self):
        """Mock file existence checks."""
        with patch("pathlib.Path.exists", return_value=True):
            yield

    @pytest.fixture
    def mock_gpu_selector(self):
        """Mock GPU selector functions."""
        with patch(
            "amber_agent.tools.builtin.amber.pmemd.select_optimal_gpu"
        ) as mock_select, patch(
            "amber_agent.tools.builtin.amber.pmemd.validate_gpu"
        ) as mock_validate:
            mock_select.return_value = 0
            mock_validate.return_value = True
            yield mock_select, mock_validate

    @pytest.fixture
    def mock_popen(self):
        """Mock subprocess.Popen for pmemd.cuda execution."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = iter(
            [
                " NSTEP =     1000   TIME(PS) =      2.000  TEMP(K) =   310.15  PRESS =     0.0\n",
                " Etot   =   -123456.7890  EKtot   =     12345.6789  EPtot      =   -135802.4679\n",
                " BOND   =       123.4567  ANGLE   =       234.5678  DIHED      =       345.6789\n",
                "\n",
                " NSTEP =     2000   TIME(PS) =      4.000  TEMP(K) =   308.45  PRESS =     0.0\n",
                " Etot   =   -123450.1234  EKtot   =     12340.5678  EPtot      =   -135790.6912\n",
                "\n",
                "|  Average timings for last    1000 steps:\n",
                "|     Elapsed(s) =       5.23 Per Step(ms) =       5.23\n",
                "|         ns/day =      16.52   seconds/ns =    5229.12\n",
                "\n",
                "   5.  TIMINGS\n",
                "--------------------------------------------------------------------------------\n",
            ]
        )
        mock_proc.stderr = iter([])
        mock_proc.wait.return_value = 0
        mock_proc.poll.return_value = 0

        with patch("subprocess.Popen", return_value=mock_proc) as mock:
            yield mock, mock_proc

    def test_basic_execution_auto_gpu(self, mock_files, mock_gpu_selector, mock_popen):
        """Test basic execution with automatic GPU selection."""
        mock_select, mock_validate = mock_gpu_selector
        mock_popen_call, mock_proc = mock_popen

        result = pmemd_cuda(
            input_file="min.in",
            output_file="min.out",
            topology_file="system.prmtop",
            coordinate_file="system.inpcrd",
            restart_file="min.rst7",
        )

        # Verify GPU selection was called
        mock_select.assert_called_once()

        # Verify command construction
        mock_popen_call.assert_called_once()
        call_args = mock_popen_call.call_args
        cmd = call_args[0][0]

        assert cmd[0] == "pmemd.cuda"
        assert "-O" in cmd
        assert "-i" in cmd and "min.in" in cmd
        assert "-o" in cmd and "min.out" in cmd
        assert "-p" in cmd and "system.prmtop" in cmd
        assert "-c" in cmd and "system.inpcrd" in cmd
        assert "-r" in cmd and "min.rst7" in cmd

        # Verify environment variable
        env = call_args[1]["env"]
        assert "CUDA_VISIBLE_DEVICES" in env
        assert env["CUDA_VISIBLE_DEVICES"] == "0"

        # Verify result
        assert result["success"] is True
        assert result["return_code"] == 0
        assert result["final_step"] == 2000
        assert result["final_energy"] == pytest.approx(-123450.1234)
        assert result["average_ns_per_day"] == pytest.approx(16.52)

    def test_manual_gpu_selection(self, mock_files, mock_gpu_selector, mock_popen):
        """Test manual GPU ID specification."""
        mock_select, mock_validate = mock_gpu_selector
        mock_popen_call, mock_proc = mock_popen

        result = pmemd_cuda(
            input_file="md.in",
            output_file="md.out",
            topology_file="system.prmtop",
            coordinate_file="system.rst7",
            gpu_id=2,
        )

        # Verify GPU selection was NOT called (manual override)
        mock_select.assert_not_called()

        # Verify GPU validation was called
        mock_validate.assert_called_once_with(2)

        # Verify environment variable
        call_args = mock_popen_call.call_args
        env = call_args[1]["env"]
        assert env["CUDA_VISIBLE_DEVICES"] == "2"

        assert result["success"] is True

    def test_invalid_gpu_id(self, mock_files, mock_gpu_selector):
        """Test error handling for invalid GPU ID."""
        mock_select, mock_validate = mock_gpu_selector
        mock_validate.return_value = False

        result = pmemd_cuda(
            input_file="md.in",
            output_file="md.out",
            topology_file="system.prmtop",
            coordinate_file="system.rst7",
            gpu_id=5,
        )

        assert result["success"] is False
        assert "GPU 5 not available" in result["error"]

    def test_all_parameters(self, mock_files, mock_gpu_selector, mock_popen):
        """Test execution with all optional parameters."""
        mock_popen_call, mock_proc = mock_popen

        result = pmemd_cuda(
            input_file="prod.in",
            output_file="prod.out",
            topology_file="system.prmtop",
            coordinate_file="equil.rst7",
            restart_file="prod.rst7",
            trajectory_file="prod.nc",
            reference_file="system.inpcrd",
            mdinfo_file="prod.mdinfo",
            gpu_id=1,
        )

        # Verify all parameters in command
        call_args = mock_popen_call.call_args
        cmd = call_args[0][0]

        assert "-i" in cmd and "prod.in" in cmd
        assert "-o" in cmd and "prod.out" in cmd
        assert "-p" in cmd and "system.prmtop" in cmd
        assert "-c" in cmd and "equil.rst7" in cmd
        assert "-r" in cmd and "prod.rst7" in cmd
        assert "-x" in cmd and "prod.nc" in cmd
        assert "-ref" in cmd and "system.inpcrd" in cmd
        assert "-inf" in cmd and "prod.mdinfo" in cmd

        assert result["success"] is True

    def test_progress_callback(self, mock_files, mock_gpu_selector, mock_popen):
        """Test progress callback functionality."""
        callback = Mock()

        result = pmemd_cuda(
            input_file="md.in",
            output_file="md.out",
            topology_file="system.prmtop",
            coordinate_file="system.rst7",
            progress_callback=callback,
        )

        # Verify callback was called with progress updates
        # Should be called for NSTEP lines and energy lines separately
        assert callback.call_count >= 2

        # Find a callback with step info
        step_calls = [c[0][0] for c in callback.call_args_list if "step" in c[0][0]]
        assert len(step_calls) >= 2

        first_step_call = step_calls[0]
        assert first_step_call["step"] == 1000
        assert "temperature" in first_step_call
        assert first_step_call["temperature"] == pytest.approx(310.15)

        # Find a callback with energy info
        energy_calls = [c[0][0] for c in callback.call_args_list if "energy" in c[0][0]]
        assert len(energy_calls) >= 2

        first_energy_call = energy_calls[0]
        assert first_energy_call["energy"] == pytest.approx(-123456.7890)

        assert result["success"] is True

    def test_pmemd_not_found(self, mock_files, mock_gpu_selector):
        """Test error handling when pmemd.cuda is not found."""
        with patch("subprocess.Popen", side_effect=FileNotFoundError("pmemd.cuda")):
            result = pmemd_cuda(
                input_file="md.in",
                output_file="md.out",
                topology_file="system.prmtop",
                coordinate_file="system.rst7",
            )

            assert result["success"] is False
            assert "pmemd.cuda" in result["error"].lower()

    def test_missing_input_file(self, mock_gpu_selector):
        """Test error handling for missing input file."""
        with patch("pathlib.Path.exists") as mock_exists:
            # Only input file is missing
            mock_exists.side_effect = lambda: False

            result = pmemd_cuda(
                input_file="missing.in",
                output_file="md.out",
                topology_file="system.prmtop",
                coordinate_file="system.rst7",
            )

            assert result["success"] is False
            assert "missing.in" in result["error"]

    def test_simulation_failure(self, mock_files, mock_gpu_selector):
        """Test handling of simulation failure (non-zero return code)."""
        mock_proc = Mock()
        mock_proc.returncode = 1
        mock_proc.stdout = iter(
            [
                " NSTEP =      100   TIME(PS) =      0.200  TEMP(K) =   310.15\n",
                " Etot   =   ************  EKtot   =     12345.6789  EPtot      =   ************\n",
                "\n",
                " ERROR: Energy explosion detected!\n",
            ]
        )
        mock_proc.stderr = iter(["FATAL: Coordinate error\n"])
        mock_proc.wait.return_value = 1

        with patch("subprocess.Popen", return_value=mock_proc):
            result = pmemd_cuda(
                input_file="md.in",
                output_file="md.out",
                topology_file="system.prmtop",
                coordinate_file="bad.rst7",
            )

            assert result["success"] is False
            assert result["return_code"] == 1
            assert "FATAL" in result["stderr"] or "ERROR" in result["stdout"]

    def test_timeout_handling(self, mock_files, mock_gpu_selector):
        """Test timeout handling for long-running simulations."""
        mock_proc = Mock()
        mock_proc.stdout = iter([])  # Simulate hanging process
        mock_proc.stderr = iter([])
        mock_proc.wait.side_effect = subprocess.TimeoutExpired("pmemd.cuda", 10)

        with patch("subprocess.Popen", return_value=mock_proc):
            result = pmemd_cuda(
                input_file="md.in",
                output_file="md.out",
                topology_file="system.prmtop",
                coordinate_file="system.rst7",
                timeout=10,
            )

            assert result["success"] is False
            assert "timeout" in result["error"].lower()

    def test_output_parsing_nstep(self, mock_files, mock_gpu_selector):
        """Test parsing of NSTEP lines."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = iter(
            [
                " NSTEP =      500   TIME(PS) =      1.000  TEMP(K) =   300.00  PRESS =     0.0\n",
                " Etot   =   -100000.0000  EKtot   =     10000.0000  EPtot      =   -110000.0000\n",
            ]
        )
        mock_proc.stderr = iter([])
        mock_proc.wait.return_value = 0

        with patch("subprocess.Popen", return_value=mock_proc):
            result = pmemd_cuda(
                input_file="md.in",
                output_file="md.out",
                topology_file="system.prmtop",
                coordinate_file="system.rst7",
            )

            assert result["final_step"] == 500
            assert result["final_energy"] == pytest.approx(-100000.0)
            assert result["final_temperature"] == pytest.approx(300.0)

    def test_output_parsing_timing(self, mock_files, mock_gpu_selector):
        """Test parsing of timing information."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = iter(
            [
                " NSTEP =     1000   TIME(PS) =      2.000  TEMP(K) =   310.15\n",
                " Etot   =   -123456.7890  EKtot   =     12345.6789  EPtot      =   -135802.4679\n",
                "|  Average timings for last    1000 steps:\n",
                "|     Elapsed(s) =      10.50 Per Step(ms) =      10.50\n",
                "|         ns/day =       8.23   seconds/ns =   10500.00\n",
            ]
        )
        mock_proc.stderr = iter([])
        mock_proc.wait.return_value = 0

        with patch("subprocess.Popen", return_value=mock_proc):
            result = pmemd_cuda(
                input_file="md.in",
                output_file="md.out",
                topology_file="system.prmtop",
                coordinate_file="system.rst7",
            )

            assert result["average_ns_per_day"] == pytest.approx(8.23)

    def test_no_timing_info(self, mock_files, mock_gpu_selector):
        """Test handling when no timing information is available."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = iter(
            [
                " NSTEP =      100   TIME(PS) =      0.200  TEMP(K) =   300.00\n",
                " Etot   =   -100000.0000  EKtot   =     10000.0000  EPtot      =   -110000.0000\n",
            ]
        )
        mock_proc.stderr = iter([])
        mock_proc.wait.return_value = 0

        with patch("subprocess.Popen", return_value=mock_proc):
            result = pmemd_cuda(
                input_file="md.in",
                output_file="md.out",
                topology_file="system.prmtop",
                coordinate_file="system.rst7",
            )

            assert result["average_ns_per_day"] is None

    def test_empty_output(self, mock_files, mock_gpu_selector):
        """Test handling of empty output."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = iter([])
        mock_proc.stderr = iter([])
        mock_proc.wait.return_value = 0

        with patch("subprocess.Popen", return_value=mock_proc):
            result = pmemd_cuda(
                input_file="md.in",
                output_file="md.out",
                topology_file="system.prmtop",
                coordinate_file="system.rst7",
            )

            assert result["success"] is True
            assert result["final_step"] is None
            assert result["final_energy"] is None

    def test_partial_output(self, mock_files, mock_gpu_selector):
        """Test handling of partial/incomplete output."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = iter(
            [
                " NSTEP =      100   TIME(PS) =      0.200  TEMP(K) =   300.00\n",
                # Missing energy line
            ]
        )
        mock_proc.stderr = iter([])
        mock_proc.wait.return_value = 0

        with patch("subprocess.Popen", return_value=mock_proc):
            result = pmemd_cuda(
                input_file="md.in",
                output_file="md.out",
                topology_file="system.prmtop",
                coordinate_file="system.rst7",
            )

            assert result["success"] is True
            assert result["final_step"] == 100
            assert result["final_energy"] is None  # No energy line parsed

    def test_energy_explosion(self, mock_files, mock_gpu_selector):
        """Test handling of energy explosion (asterisks in output)."""
        mock_proc = Mock()
        mock_proc.returncode = 1
        mock_proc.stdout = iter(
            [
                " NSTEP =      100   TIME(PS) =      0.200  TEMP(K) =   999.99\n",
                " Etot   =   ************  EKtot   =   ************  EPtot      =   ************\n",
            ]
        )
        mock_proc.stderr = iter([])
        mock_proc.wait.return_value = 1

        with patch("subprocess.Popen", return_value=mock_proc):
            result = pmemd_cuda(
                input_file="md.in",
                output_file="md.out",
                topology_file="system.prmtop",
                coordinate_file="bad.rst7",
            )

            assert result["success"] is False
            assert result["final_step"] == 100
            assert result["final_energy"] is None  # Asterisks parsed as None
