"""Tests for AMBER environment auto-detection."""

import pytest
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess


class TestAmberExecutable:
    """Test AmberExecutable dataclass."""
    
    def test_init_available(self):
        from mdpilot.tools.amber_detector import AmberExecutable
        
        exe = AmberExecutable(name="sander", available=True, path="/usr/bin/sander", version="24.0")
        
        assert exe.name == "sander"
        assert exe.available is True
        assert exe.path == "/usr/bin/sander"
        assert exe.version == "24.0"
    
    def test_init_not_available(self):
        from mdpilot.tools.amber_detector import AmberExecutable
        
        exe = AmberExecutable(name="pmemd.cuda", available=False)
        
        assert exe.name == "pmemd.cuda"
        assert exe.available is False
        assert exe.path is None


class TestAmberEnvironment:
    """Test AmberEnvironment dataclass."""
    
    def test_available_true(self):
        from mdpilot.tools.amber_detector import AmberEnvironment
        
        env = AmberEnvironment(amber_home="/opt/amber24")
        
        assert env.available is True
    
    def test_available_false(self):
        from mdpilot.tools.amber_detector import AmberEnvironment
        
        env = AmberEnvironment()
        
        assert env.available is False
    
    def test_summary_lines_not_available(self):
        from mdpilot.tools.amber_detector import AmberEnvironment
        
        env = AmberEnvironment()
        lines = env.summary_lines()
        
        assert any("No local AMBER installation" in line for line in lines)
    
    def test_summary_lines_available(self):
        from mdpilot.tools.amber_detector import AmberEnvironment, AmberExecutable
        
        env = AmberEnvironment(
            amber_home="/opt/amber24",
            tools_version="24.0",
            source="env",
            gpu_enabled=True,
            executables=[
                AmberExecutable("sander", True, "/opt/amber24/bin/sander"),
                AmberExecutable("pmemd.cuda", False)
            ],
            env_applied=True
        )
        
        lines = env.summary_lines()
        
        assert any("/opt/amber24" in line for line in lines)
        assert any("24.0" in line for line in lines)
        assert any("yes" in line for line in lines)
        assert any("sander" in line for line in lines)
        assert any("pmemd.cuda" in line for line in lines)


class TestCheckEnv:
    """Test _check_env function."""
    
    def test_amberhome_set_and_valid(self, tmp_path):
        from mdpilot.tools.amber_detector import _check_env
        
        amber_home = tmp_path / "amber24"
        amber_home.mkdir()
        (amber_home / "bin").mkdir()
        
        with patch.dict('os.environ', {'AMBERHOME': str(amber_home)}):
            result = _check_env()
            
            assert result == str(amber_home)
    
    def test_amberhome_not_set(self):
        from mdpilot.tools.amber_detector import _check_env
        
        with patch.dict('os.environ', {}, clear=True):
            result = _check_env()
            
            assert result is None
    
    def test_amberhome_set_but_invalid(self, tmp_path):
        from mdpilot.tools.amber_detector import _check_env
        
        amber_home = tmp_path / "amber24"
        amber_home.mkdir()
        
        with patch.dict('os.environ', {'AMBERHOME': str(amber_home)}):
            result = _check_env()
            
            assert result is None


class TestSearchCommonPaths:
    """Test _search_common_paths function."""
    
    def test_finds_home_directory(self, tmp_path):
        from mdpilot.tools.amber_detector import _search_common_paths
        
        amber_home = tmp_path / "amber25"
        amber_home.mkdir()
        (amber_home / "bin").mkdir()
        
        with patch('pathlib.Path.home', return_value=tmp_path):
            with patch.dict('os.environ', {}, clear=True):
                result = _search_common_paths()
                
                assert result == str(amber_home)
    
    def test_finds_conda_prefix(self, tmp_path):
        from mdpilot.tools.amber_detector import _search_common_paths
        
        conda_prefix = tmp_path / "conda"
        conda_prefix.mkdir()
        (conda_prefix / "bin").mkdir()
        
        with patch('pathlib.Path.home', return_value=tmp_path / "home"):
            with patch.dict('os.environ', {'CONDA_PREFIX': str(conda_prefix)}):
                result = _search_common_paths()
                
                assert result == str(conda_prefix)
    
    def test_not_found(self, tmp_path):
        from mdpilot.tools.amber_detector import _search_common_paths
        
        with patch('pathlib.Path.home', return_value=tmp_path):
            with patch.dict('os.environ', {}, clear=True):
                result = _search_common_paths()
                
                assert result is None


class TestFindCondaEnvs:
    """Test _find_conda_envs function."""
    
    def test_conda_not_found(self):
        from mdpilot.tools.amber_detector import _find_conda_envs
        
        with patch('shutil.which', return_value=None):
            result = _find_conda_envs()
            
            assert result is None
    
    def test_conda_command_fails(self):
        from mdpilot.tools.amber_detector import _find_conda_envs
        
        mock_result = Mock()
        mock_result.returncode = 1
        
        with patch('shutil.which', return_value="/usr/bin/conda"):
            with patch('subprocess.run', return_value=mock_result):
                result = _find_conda_envs()
                
                assert result is None
    
    def test_conda_finds_env_with_sander(self, tmp_path):
        from mdpilot.tools.amber_detector import _find_conda_envs
        
        env_path = tmp_path / "envs" / "amber"
        env_path.mkdir(parents=True)
        (env_path / "bin").mkdir()
        (env_path / "bin" / "sander").touch()
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"envs": [str(env_path)]})
        
        with patch('shutil.which', return_value="/usr/bin/conda"):
            with patch('subprocess.run', return_value=mock_result):
                result = _find_conda_envs()
                
                assert result == str(env_path)
    
    def test_conda_finds_env_with_tleap(self, tmp_path):
        from mdpilot.tools.amber_detector import _find_conda_envs
        
        env_path = tmp_path / "envs" / "amber"
        env_path.mkdir(parents=True)
        (env_path / "bin").mkdir()
        (env_path / "bin" / "tleap").touch()
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"envs": [str(env_path)]})
        
        with patch('shutil.which', return_value="/usr/bin/conda"):
            with patch('subprocess.run', return_value=mock_result):
                result = _find_conda_envs()
                
                assert result == str(env_path)
    
    def test_conda_json_decode_error(self):
        from mdpilot.tools.amber_detector import _find_conda_envs
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "invalid json"
        
        with patch('shutil.which', return_value="/usr/bin/conda"):
            with patch('subprocess.run', return_value=mock_result):
                result = _find_conda_envs()
                
                assert result is None


class TestScanDownloadsRecursive:
    """Test _scan_downloads_recursive function."""
    
    def test_downloads_not_exists(self, tmp_path):
        from mdpilot.tools.amber_detector import _scan_downloads_recursive
        
        with patch('pathlib.Path.home', return_value=tmp_path):
            result = _scan_downloads_recursive()
            
            assert result is None
    
    def test_finds_amber_sh(self, tmp_path):
        from mdpilot.tools.amber_detector import _scan_downloads_recursive
        
        downloads = tmp_path / "Downloads"
        downloads.mkdir()
        amber_dir = downloads / "amber24"
        amber_dir.mkdir()
        (amber_dir / "bin").mkdir()
        (amber_dir / "amber.sh").touch()
        
        with patch('pathlib.Path.home', return_value=tmp_path):
            result = _scan_downloads_recursive()
            
            assert result == str(amber_dir)
    
    def test_no_amber_sh_found(self, tmp_path):
        from mdpilot.tools.amber_detector import _scan_downloads_recursive
        
        downloads = tmp_path / "Downloads"
        downloads.mkdir()
        
        with patch('pathlib.Path.home', return_value=tmp_path):
            result = _scan_downloads_recursive()
            
            assert result is None


class TestDetectSanderVersion:
    """Test _detect_sander_version function."""
    
    def test_sander_not_exists(self, tmp_path):
        from mdpilot.tools.amber_detector import _detect_sander_version
        
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        
        result = _detect_sander_version(bin_dir)
        
        assert result is None
    
    def test_sander_version_found(self, tmp_path):
        from mdpilot.tools.amber_detector import _detect_sander_version
        
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        (bin_dir / "sander").touch()
        
        mock_result = Mock()
        mock_result.stdout = "Version 24.0\n"
        mock_result.stderr = ""
        
        with patch('subprocess.run', return_value=mock_result):
            result = _detect_sander_version(bin_dir)
            
            assert result == "Version 24.0"
    
    def test_sander_timeout(self, tmp_path):
        from mdpilot.tools.amber_detector import _detect_sander_version
        
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        (bin_dir / "sander").touch()
        
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired("sander", 10)):
            result = _detect_sander_version(bin_dir)
            
            assert result is None


class TestDetectCpptrajVersion:
    """Test _detect_cpptraj_version function."""
    
    def test_cpptraj_not_exists(self, tmp_path):
        from mdpilot.tools.amber_detector import _detect_cpptraj_version
        
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        
        result = _detect_cpptraj_version(bin_dir)
        
        assert result is None
    
    def test_cpptraj_version_found(self, tmp_path):
        from mdpilot.tools.amber_detector import _detect_cpptraj_version
        
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        (bin_dir / "cpptraj").touch()
        
        mock_result = Mock()
        mock_result.stdout = "AmberTools 24.0\n"
        mock_result.stderr = ""
        
        with patch('subprocess.run', return_value=mock_result):
            result = _detect_cpptraj_version(bin_dir)
            
            assert result == "AmberTools 24.0"


class TestDetectToolsVersion:
    """Test _detect_tools_version function."""
    
    def test_version_file_amber_version(self, tmp_path):
        from mdpilot.tools.amber_detector import _detect_tools_version
        
        amber_home = tmp_path / "amber24"
        amber_home.mkdir()
        (amber_home / "amber.version").write_text("24.0")
        
        result = _detect_tools_version(str(amber_home))
        
        assert result == "24.0"
    
    def test_version_file_VERSION(self, tmp_path):
        from mdpilot.tools.amber_detector import _detect_tools_version
        
        amber_home = tmp_path / "amber24"
        amber_home.mkdir()
        (amber_home / "VERSION").write_text("24.0")
        
        result = _detect_tools_version(str(amber_home))
        
        assert result == "24.0"
    
    def test_version_from_sander(self, tmp_path):
        from mdpilot.tools.amber_detector import _detect_tools_version
        
        amber_home = tmp_path / "amber24"
        amber_home.mkdir()
        bin_dir = amber_home / "bin"
        bin_dir.mkdir()
        (bin_dir / "sander").touch()
        
        mock_result = Mock()
        mock_result.stdout = "Version 24.0\n"
        mock_result.stderr = ""
        
        with patch('subprocess.run', return_value=mock_result):
            result = _detect_tools_version(str(amber_home))
            
            assert result == "24.0"
    
    def test_no_version_found(self, tmp_path):
        from mdpilot.tools.amber_detector import _detect_tools_version
        
        amber_home = tmp_path / "amber24"
        amber_home.mkdir()
        
        result = _detect_tools_version(str(amber_home))
        
        assert result is None


class TestDetectGpu:
    """Test _detect_gpu function."""
    
    def test_gpu_found(self, tmp_path):
        from mdpilot.tools.amber_detector import _detect_gpu
        
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        (bin_dir / "pmemd.cuda").touch()
        
        result = _detect_gpu(bin_dir)
        
        assert result is True
    
    def test_gpu_not_found(self, tmp_path):
        from mdpilot.tools.amber_detector import _detect_gpu
        
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        
        result = _detect_gpu(bin_dir)
        
        assert result is False


class TestProbeExecutables:
    """Test _probe_executables function."""
    
    def test_executable_in_bin_dir(self, tmp_path):
        from mdpilot.tools.amber_detector import _probe_executables
        
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        sander = bin_dir / "sander"
        sander.touch()
        sander.chmod(0o755)
        
        result = _probe_executables(bin_dir)
        
        sander_exe = next((e for e in result if e.name == "sander"), None)
        assert sander_exe is not None
        assert sander_exe.available is True
    
    def test_executable_in_path(self, tmp_path):
        from mdpilot.tools.amber_detector import _probe_executables
        
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        
        with patch('shutil.which', side_effect=lambda name: "/usr/bin/sander" if name == "sander" else None):
            result = _probe_executables(bin_dir)
            
            sander_exe = next((e for e in result if e.name == "sander"), None)
            assert sander_exe is not None
            assert sander_exe.available is True
            assert sander_exe.path == "/usr/bin/sander"
    
    def test_executable_not_found(self, tmp_path):
        from mdpilot.tools.amber_detector import _probe_executables
        
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        
        with patch('shutil.which', return_value=None):
            result = _probe_executables(bin_dir)
            
            sander_exe = next((e for e in result if e.name == "sander"), None)
            assert sander_exe is not None
            assert sander_exe.available is False


class TestApplyEnv:
    """Test _apply_env function."""
    
    def test_apply_env_sets_variables(self, tmp_path):
        from mdpilot.tools.amber_detector import _apply_env
        
        amber_home = tmp_path / "amber24"
        amber_home.mkdir()
        (amber_home / "bin").mkdir()
        (amber_home / "lib").mkdir()
        
        original_path = os.environ.get("PATH", "")
        original_amberhome = os.environ.get("AMBERHOME")
        
        try:
            _apply_env(str(amber_home))
            
            assert os.environ["AMBERHOME"] == str(amber_home)
            assert str(amber_home / "bin") in os.environ["PATH"]
            assert str(amber_home / "lib") in os.environ.get("LD_LIBRARY_PATH", "")
        finally:
            os.environ["PATH"] = original_path
            if original_amberhome:
                os.environ["AMBERHOME"] = original_amberhome
            elif "AMBERHOME" in os.environ:
                del os.environ["AMBERHOME"]
    
    def test_apply_env_with_site_packages(self, tmp_path):
        from mdpilot.tools.amber_detector import _apply_env
        
        amber_home = tmp_path / "amber24"
        amber_home.mkdir()
        (amber_home / "bin").mkdir()
        (amber_home / "lib").mkdir()
        site_packages = amber_home / "lib" / "python3.11" / "site-packages"
        site_packages.mkdir(parents=True)
        
        original_path = os.environ.get("PATH", "")
        original_pythonpath = os.environ.get("PYTHONPATH", "")
        
        try:
            _apply_env(str(amber_home))
            
            assert str(site_packages) in os.environ.get("PYTHONPATH", "")
        finally:
            os.environ["PATH"] = original_path
            os.environ["PYTHONPATH"] = original_pythonpath


class TestDetectAmberEnv:
    """Test detect_amber_env function."""
    
    def test_detect_from_env(self, tmp_path):
        from mdpilot.tools.amber_detector import detect_amber_env
        
        amber_home = tmp_path / "amber24"
        amber_home.mkdir()
        (amber_home / "bin").mkdir()
        
        with patch.dict('os.environ', {'AMBERHOME': str(amber_home)}):
            result = detect_amber_env(apply=False)
            
            assert result.amber_home == str(amber_home)
            assert result.source == "env"
            assert result.env_applied is False
    
    def test_detect_from_path_search(self, tmp_path):
        from mdpilot.tools.amber_detector import detect_amber_env
        
        amber_home = tmp_path / "amber25"
        amber_home.mkdir()
        (amber_home / "bin").mkdir()
        
        with patch('pathlib.Path.home', return_value=tmp_path):
            with patch.dict('os.environ', {}, clear=True):
                result = detect_amber_env(apply=False)
                
                assert result.amber_home == str(amber_home)
                assert result.source == "path_search"
    
    def test_detect_not_found(self, tmp_path):
        from mdpilot.tools.amber_detector import detect_amber_env
        
        with patch('pathlib.Path.home', return_value=tmp_path):
            with patch.dict('os.environ', {}, clear=True):
                with patch('shutil.which', return_value=None):
                    result = detect_amber_env(apply=False)
                    
                    assert result.available is False
    
    def test_detect_with_apply(self, tmp_path):
        from mdpilot.tools.amber_detector import detect_amber_env
        
        amber_home = tmp_path / "amber24"
        amber_home.mkdir()
        (amber_home / "bin").mkdir()
        (amber_home / "lib").mkdir()
        
        original_path = os.environ.get("PATH", "")
        
        try:
            with patch.dict('os.environ', {'AMBERHOME': str(amber_home)}):
                result = detect_amber_env(apply=True)
                
                assert result.env_applied is True
                assert str(amber_home / "bin") in os.environ["PATH"]
        finally:
            os.environ["PATH"] = original_path
