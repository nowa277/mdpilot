"""Tests for AMBER environment detection."""

import pytest
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


class TestAmberEnvironment:
    """Test AmberEnvironment dataclass."""
    
    def test_init_valid(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironment
        
        amberhome = tmp_path / "amber26"
        amberhome.mkdir()
        bin_dir = amberhome / "bin"
        bin_dir.mkdir()
        dat_dir = amberhome / "dat"
        dat_dir.mkdir()
        lib_dir = amberhome / "lib"
        lib_dir.mkdir()
        
        env = AmberEnvironment(
            amberhome=amberhome,
            bin_dir=bin_dir,
            dat_dir=dat_dir,
            lib_dir=lib_dir,
            version="26"
        )
        
        assert env.amberhome == amberhome
        assert env.bin_dir == bin_dir
        assert env.version == "26"
    
    def test_post_init_amberhome_not_exists(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironment
        
        amberhome = tmp_path / "nonexistent"
        bin_dir = tmp_path / "bin"
        
        with pytest.raises(ValueError, match="AMBERHOME does not exist"):
            AmberEnvironment(
                amberhome=amberhome,
                bin_dir=bin_dir,
                dat_dir=tmp_path / "dat",
                lib_dir=tmp_path / "lib"
            )
    
    def test_post_init_bin_not_exists(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironment
        
        amberhome = tmp_path / "amber26"
        amberhome.mkdir()
        bin_dir = amberhome / "nonexistent"
        
        with pytest.raises(ValueError, match="Binary directory does not exist"):
            AmberEnvironment(
                amberhome=amberhome,
                bin_dir=bin_dir,
                dat_dir=amberhome / "dat",
                lib_dir=amberhome / "lib"
            )
    
    def test_to_env_dict_basic(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironment
        
        amberhome = tmp_path / "amber26"
        amberhome.mkdir()
        bin_dir = amberhome / "bin"
        bin_dir.mkdir()
        dat_dir = amberhome / "dat"
        dat_dir.mkdir()
        lib_dir = amberhome / "lib"
        lib_dir.mkdir()
        
        env = AmberEnvironment(
            amberhome=amberhome,
            bin_dir=bin_dir,
            dat_dir=dat_dir,
            lib_dir=lib_dir
        )
        
        env_dict = env.to_env_dict()
        
        assert env_dict["AMBERHOME"] == str(amberhome)
        assert str(bin_dir) in env_dict["PATH"]
    
    def test_to_env_dict_path_already_in_path(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironment
        
        amberhome = tmp_path / "amber26"
        amberhome.mkdir()
        bin_dir = amberhome / "bin"
        bin_dir.mkdir()
        dat_dir = amberhome / "dat"
        dat_dir.mkdir()
        lib_dir = amberhome / "lib"
        lib_dir.mkdir()
        
        with patch.dict('os.environ', {'PATH': str(bin_dir)}):
            env = AmberEnvironment(
                amberhome=amberhome,
                bin_dir=bin_dir,
                dat_dir=dat_dir,
                lib_dir=lib_dir
            )
            
            env_dict = env.to_env_dict()
            
            path_parts = env_dict["PATH"].split(os.pathsep)
            assert path_parts.count(str(bin_dir)) == 1
    
    def test_to_env_dict_linux_ld_library_path(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironment
        
        amberhome = tmp_path / "amber26"
        amberhome.mkdir()
        bin_dir = amberhome / "bin"
        bin_dir.mkdir()
        dat_dir = amberhome / "dat"
        dat_dir.mkdir()
        lib_dir = amberhome / "lib"
        lib_dir.mkdir()
        
        mock_uname = Mock()
        mock_uname.sysname = "Linux"
        
        with patch('os.name', 'posix'):
            with patch('os.uname', return_value=mock_uname):
                env = AmberEnvironment(
                    amberhome=amberhome,
                    bin_dir=bin_dir,
                    dat_dir=dat_dir,
                    lib_dir=lib_dir
                )
                
                env_dict = env.to_env_dict()
                
                assert "LD_LIBRARY_PATH" in env_dict
                assert str(lib_dir) in env_dict["LD_LIBRARY_PATH"]
    
    def test_to_env_dict_macos_dyld_library_path(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironment
        
        amberhome = tmp_path / "amber26"
        amberhome.mkdir()
        bin_dir = amberhome / "bin"
        bin_dir.mkdir()
        dat_dir = amberhome / "dat"
        dat_dir.mkdir()
        lib_dir = amberhome / "lib"
        lib_dir.mkdir()
        
        mock_uname = Mock()
        mock_uname.sysname = "Darwin"
        
        with patch('os.name', 'posix'):
            with patch('os.uname', return_value=mock_uname):
                env = AmberEnvironment(
                    amberhome=amberhome,
                    bin_dir=bin_dir,
                    dat_dir=dat_dir,
                    lib_dir=lib_dir
                )
                
                env_dict = env.to_env_dict()
                
                assert "DYLD_LIBRARY_PATH" in env_dict
                assert str(lib_dir) in env_dict["DYLD_LIBRARY_PATH"]
    
    def test_to_env_dict_lib_already_in_path(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironment
        
        amberhome = tmp_path / "amber26"
        amberhome.mkdir()
        bin_dir = amberhome / "bin"
        bin_dir.mkdir()
        dat_dir = amberhome / "dat"
        dat_dir.mkdir()
        lib_dir = amberhome / "lib"
        lib_dir.mkdir()
        
        mock_uname = Mock()
        mock_uname.sysname = "Linux"
        
        with patch('os.name', 'posix'):
            with patch('os.uname', return_value=mock_uname):
                with patch.dict('os.environ', {'LD_LIBRARY_PATH': str(lib_dir)}):
                    env = AmberEnvironment(
                        amberhome=amberhome,
                        bin_dir=bin_dir,
                        dat_dir=dat_dir,
                        lib_dir=lib_dir
                    )
                    
                    env_dict = env.to_env_dict()
                    
                    lib_parts = env_dict["LD_LIBRARY_PATH"].split(os.pathsep)
                    assert lib_parts.count(str(lib_dir)) == 1
    
    def test_apply(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironment
        
        amberhome = tmp_path / "amber26"
        amberhome.mkdir()
        bin_dir = amberhome / "bin"
        bin_dir.mkdir()
        dat_dir = amberhome / "dat"
        dat_dir.mkdir()
        lib_dir = amberhome / "lib"
        lib_dir.mkdir()
        
        env = AmberEnvironment(
            amberhome=amberhome,
            bin_dir=bin_dir,
            dat_dir=dat_dir,
            lib_dir=lib_dir
        )
        
        original_amberhome = os.environ.get("AMBERHOME")
        
        try:
            env.apply()
            
            assert os.environ["AMBERHOME"] == str(amberhome)
            assert str(bin_dir) in os.environ["PATH"]
        finally:
            if original_amberhome:
                os.environ["AMBERHOME"] = original_amberhome
            elif "AMBERHOME" in os.environ:
                del os.environ["AMBERHOME"]
    
    def test_str(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironment
        
        amberhome = tmp_path / "amber26"
        amberhome.mkdir()
        bin_dir = amberhome / "bin"
        bin_dir.mkdir()
        dat_dir = amberhome / "dat"
        dat_dir.mkdir()
        lib_dir = amberhome / "lib"
        lib_dir.mkdir()
        
        env = AmberEnvironment(
            amberhome=amberhome,
            bin_dir=bin_dir,
            dat_dir=dat_dir,
            lib_dir=lib_dir,
            version="26"
        )
        
        result = str(env)
        
        assert "AMBERHOME:" in result
        assert "Version: 26" in result
        assert "Binary directory:" in result
    
    def test_str_no_version(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironment
        
        amberhome = tmp_path / "amber26"
        amberhome.mkdir()
        bin_dir = amberhome / "bin"
        bin_dir.mkdir()
        dat_dir = amberhome / "dat"
        dat_dir.mkdir()
        lib_dir = amberhome / "lib"
        lib_dir.mkdir()
        
        env = AmberEnvironment(
            amberhome=amberhome,
            bin_dir=bin_dir,
            dat_dir=dat_dir,
            lib_dir=lib_dir
        )
        
        result = str(env)
        
        assert "Version: unknown" in result


class TestAmberEnvironmentDetector:
    """Test AmberEnvironmentDetector class."""
    
    def test_detect_with_cache(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironmentDetector
        
        amberhome = tmp_path / "amber26"
        amberhome.mkdir()
        bin_dir = amberhome / "bin"
        bin_dir.mkdir()
        (bin_dir / "pdb4amber").touch()
        (bin_dir / "tleap").touch()
        (bin_dir / "sander").touch()
        
        detector = AmberEnvironmentDetector()
        
        with patch.dict('os.environ', {'AMBERHOME': str(amberhome)}):
            env1 = detector.detect(use_cache=True)
            env2 = detector.detect(use_cache=True)
            
            assert env1 is env2
    
    def test_detect_user_path_valid(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironmentDetector
        
        amberhome = tmp_path / "amber26"
        amberhome.mkdir()
        bin_dir = amberhome / "bin"
        bin_dir.mkdir()
        (bin_dir / "pdb4amber").touch()
        (bin_dir / "tleap").touch()
        (bin_dir / "sander").touch()
        
        detector = AmberEnvironmentDetector()
        env = detector.detect(user_path=str(amberhome))
        
        assert env.amberhome == amberhome
    
    def test_detect_user_path_invalid(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironmentDetector
        
        detector = AmberEnvironmentDetector()
        
        with pytest.raises(RuntimeError, match="Invalid AMBERHOME path"):
            detector.detect(user_path=str(tmp_path / "nonexistent"))
    
    def test_detect_from_amberhome_env(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironmentDetector
        
        amberhome = tmp_path / "amber26"
        amberhome.mkdir()
        bin_dir = amberhome / "bin"
        bin_dir.mkdir()
        (bin_dir / "pdb4amber").touch()
        (bin_dir / "tleap").touch()
        (bin_dir / "sander").touch()
        
        detector = AmberEnvironmentDetector()
        
        with patch.dict('os.environ', {'AMBERHOME': str(amberhome)}, clear=True):
            env = detector.detect(use_cache=False)
            
            assert env.amberhome == amberhome
    
    def test_detect_from_conda(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironmentDetector
        
        conda_prefix = tmp_path / "conda"
        conda_prefix.mkdir()
        bin_dir = conda_prefix / "bin"
        bin_dir.mkdir()
        (bin_dir / "pdb4amber").touch()
        
        detector = AmberEnvironmentDetector()
        
        with patch.dict('os.environ', {'CONDA_PREFIX': str(conda_prefix)}, clear=True):
            env = detector.detect(use_cache=False)
            
            assert env.amberhome == conda_prefix
            assert env.version == "conda"
    
    def test_detect_from_standard_paths(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironmentDetector
        
        amberhome = tmp_path / "amber26"
        amberhome.mkdir()
        bin_dir = amberhome / "bin"
        bin_dir.mkdir()
        (bin_dir / "pdb4amber").touch()
        (bin_dir / "tleap").touch()
        (bin_dir / "sander").touch()
        
        detector = AmberEnvironmentDetector()
        detector.STANDARD_PATHS = [amberhome]
        
        with patch.dict('os.environ', {}, clear=True):
            env = detector.detect(use_cache=False)
            
            assert env.amberhome == amberhome
    
    def test_detect_not_found(self):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironmentDetector
        
        detector = AmberEnvironmentDetector()
        detector.STANDARD_PATHS = []
        
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(RuntimeError, match="AmberTools installation not found"):
                detector.detect(use_cache=False)
    
    def test_validate_path_not_exists(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironmentDetector
        
        detector = AmberEnvironmentDetector()
        result = detector._validate_path(tmp_path / "nonexistent")
        
        assert result is None
    
    def test_validate_path_no_bin(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironmentDetector
        
        amberhome = tmp_path / "amber26"
        amberhome.mkdir()
        
        detector = AmberEnvironmentDetector()
        result = detector._validate_path(amberhome)
        
        assert result is None
    
    def test_validate_path_missing_tools(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironmentDetector
        
        amberhome = tmp_path / "amber26"
        amberhome.mkdir()
        bin_dir = amberhome / "bin"
        bin_dir.mkdir()
        (bin_dir / "pdb4amber").touch()
        
        detector = AmberEnvironmentDetector()
        result = detector._validate_path(amberhome)
        
        assert result is None
    
    def test_validate_path_success(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironmentDetector
        
        amberhome = tmp_path / "amber26"
        amberhome.mkdir()
        bin_dir = amberhome / "bin"
        bin_dir.mkdir()
        (bin_dir / "pdb4amber").touch()
        (bin_dir / "tleap").touch()
        (bin_dir / "sander").touch()
        
        detector = AmberEnvironmentDetector()
        result = detector._validate_path(amberhome)
        
        assert result is not None
        assert result.amberhome == amberhome
        assert result.version == "26"
    
    def test_validate_conda_path_no_bin(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironmentDetector
        
        conda_prefix = tmp_path / "conda"
        conda_prefix.mkdir()
        
        detector = AmberEnvironmentDetector()
        result = detector._validate_conda_path(conda_prefix)
        
        assert result is None
    
    def test_validate_conda_path_no_pdb4amber(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironmentDetector
        
        conda_prefix = tmp_path / "conda"
        conda_prefix.mkdir()
        bin_dir = conda_prefix / "bin"
        bin_dir.mkdir()
        
        detector = AmberEnvironmentDetector()
        result = detector._validate_conda_path(conda_prefix)
        
        assert result is None
    
    def test_validate_conda_path_success(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironmentDetector
        
        conda_prefix = tmp_path / "conda"
        conda_prefix.mkdir()
        bin_dir = conda_prefix / "bin"
        bin_dir.mkdir()
        (bin_dir / "pdb4amber").touch()
        
        detector = AmberEnvironmentDetector()
        result = detector._validate_conda_path(conda_prefix)
        
        assert result is not None
        assert result.amberhome == conda_prefix
        assert result.version == "conda"
    
    def test_find_tool_from_detected_env(self, tmp_path):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironmentDetector
        
        amberhome = tmp_path / "amber26"
        amberhome.mkdir()
        bin_dir = amberhome / "bin"
        bin_dir.mkdir()
        (bin_dir / "pdb4amber").touch()
        (bin_dir / "tleap").touch()
        (bin_dir / "sander").touch()
        
        detector = AmberEnvironmentDetector()
        
        with patch.dict('os.environ', {'AMBERHOME': str(amberhome)}):
            tool_path = detector.find_tool("pdb4amber")
            
            assert tool_path == bin_dir / "pdb4amber"
    
    def test_find_tool_fallback_to_path(self):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironmentDetector
        
        detector = AmberEnvironmentDetector()
        detector.STANDARD_PATHS = []
        
        with patch.dict('os.environ', {}, clear=True):
            with patch('shutil.which', return_value="/usr/bin/pdb4amber"):
                tool_path = detector.find_tool("pdb4amber")
                
                assert tool_path == Path("/usr/bin/pdb4amber")
    
    def test_find_tool_not_found(self):
        from mdpilot.tools.builtin.amber.env_detector import AmberEnvironmentDetector
        
        detector = AmberEnvironmentDetector()
        detector.STANDARD_PATHS = []
        
        with patch.dict('os.environ', {}, clear=True):
            with patch('shutil.which', return_value=None):
                tool_path = detector.find_tool("nonexistent")
                
                assert tool_path is None

