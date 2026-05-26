"""Tests for GPU selector module."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from mdpilot.tools.builtin.amber.gpu_selector import (
    get_gpu_info,
    select_optimal_gpu,
    validate_gpu,
)


class TestGetGPUInfo:
    """Tests for get_gpu_info function."""

    def test_multiple_gpus(self):
        """Test parsing multiple GPUs."""
        mock_output = "0, 1024, 8192, 30\n1, 2048, 8192, 50\n2, 512, 8192, 10"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr=""
            )

            result = get_gpu_info()

            assert len(result) == 3
            assert result[0] == {
                "id": 0,
                "memory_used": 1024,
                "memory_total": 8192,
                "utilization": 30
            }
            assert result[1] == {
                "id": 1,
                "memory_used": 2048,
                "memory_total": 8192,
                "utilization": 50
            }
            assert result[2] == {
                "id": 2,
                "memory_used": 512,
                "memory_total": 8192,
                "utilization": 10
            }

    def test_single_gpu(self):
        """Test parsing single GPU."""
        mock_output = "0, 2048, 16384, 45"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr=""
            )

            result = get_gpu_info()

            assert len(result) == 1
            assert result[0] == {
                "id": 0,
                "memory_used": 2048,
                "memory_total": 16384,
                "utilization": 45
            }

    def test_no_gpus(self):
        """Test when no GPUs are available."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr=""
            )

            result = get_gpu_info()

            assert result == []

    def test_nvidia_smi_not_found(self):
        """Test when nvidia-smi command is not found."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("nvidia-smi not found")

            result = get_gpu_info()

            assert result == []

    def test_nvidia_smi_fails(self):
        """Test when nvidia-smi command fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="NVIDIA-SMI has failed"
            )

            result = get_gpu_info()

            assert result == []

    def test_parse_error_invalid_format(self):
        """Test handling of invalid CSV format."""
        mock_output = "0, invalid, 8192, 30"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr=""
            )

            result = get_gpu_info()

            # Should skip invalid lines
            assert result == []

    def test_parse_error_incomplete_line(self):
        """Test handling of incomplete CSV lines."""
        mock_output = "0, 1024, 8192\n1, 2048, 8192, 50"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr=""
            )

            result = get_gpu_info()

            # Should only parse valid lines
            assert len(result) == 1
            assert result[0]["id"] == 1

    def test_subprocess_timeout(self):
        """Test handling of subprocess timeout."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("nvidia-smi", 5)

            result = get_gpu_info()

            assert result == []


class TestSelectOptimalGPU:
    """Tests for select_optimal_gpu function."""

    def test_select_lowest_memory_usage(self):
        """Test selecting GPU with lowest memory usage."""
        mock_output = "0, 2048, 8192, 50\n1, 512, 8192, 30\n2, 1024, 8192, 40"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr=""
            )

            result = select_optimal_gpu()

            # GPU 1 has lowest memory usage (512)
            assert result == 1

    def test_select_lowest_id_on_tie(self):
        """Test selecting lowest ID when memory usage is tied."""
        mock_output = "0, 1024, 8192, 30\n1, 1024, 8192, 30\n2, 1024, 8192, 30"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr=""
            )

            result = select_optimal_gpu()

            # All have same memory usage, should select GPU 0
            assert result == 0

    def test_single_gpu_selection(self):
        """Test selecting the only available GPU."""
        mock_output = "0, 4096, 8192, 60"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr=""
            )

            result = select_optimal_gpu()

            assert result == 0

    def test_no_gpus_defaults_to_zero(self):
        """Test defaulting to GPU 0 when no GPUs detected."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr=""
            )

            result = select_optimal_gpu()

            assert result == 0

    def test_nvidia_smi_failure_defaults_to_zero(self):
        """Test defaulting to GPU 0 when nvidia-smi fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("nvidia-smi not found")

            result = select_optimal_gpu()

            assert result == 0

    def test_parse_error_defaults_to_zero(self):
        """Test defaulting to GPU 0 when parsing fails."""
        mock_output = "invalid, data, format, here"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr=""
            )

            result = select_optimal_gpu()

            assert result == 0


class TestValidateGPU:
    """Tests for validate_gpu function."""

    def test_valid_gpu_id(self):
        """Test validating an existing GPU ID."""
        mock_output = "0, 1024, 8192, 30\n1, 2048, 8192, 50"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr=""
            )

            assert validate_gpu(0) is True
            assert validate_gpu(1) is True

    def test_invalid_gpu_id(self):
        """Test validating a non-existent GPU ID."""
        mock_output = "0, 1024, 8192, 30\n1, 2048, 8192, 50"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr=""
            )

            assert validate_gpu(2) is False
            assert validate_gpu(5) is False

    def test_negative_gpu_id(self):
        """Test validating negative GPU ID."""
        mock_output = "0, 1024, 8192, 30"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr=""
            )

            assert validate_gpu(-1) is False

    def test_no_gpus_available(self):
        """Test validation when no GPUs are available."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr=""
            )

            assert validate_gpu(0) is False

    def test_nvidia_smi_failure(self):
        """Test validation when nvidia-smi fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("nvidia-smi not found")

            assert validate_gpu(0) is False
