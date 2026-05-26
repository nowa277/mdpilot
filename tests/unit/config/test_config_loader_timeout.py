"""Tests for timeout configuration loading."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from mdpilot.config.loader import load_config
from mdpilot.config.schema import AppConfig


class TestConfigLoaderTimeout:
    """Test config loader handles timeout section correctly."""

    def test_load_config_with_timeout_from_yaml(self, tmp_path):
        """Test loading config with timeout section from YAML."""
        config_file = tmp_path / ".mdpilot.yaml"
        config_data = {
            "agent": {
                "timeout": {
                    "default_timeout_sec": 300,
                    "by_category": {"amber_simulation": 3600},
                    "by_tool": {"run_md_simulation": 7200},
                    "warning_threshold": 0.75
                }
            }
        }
        
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        
        config = load_config(project_dir=tmp_path)
        
        assert config.agent.timeout.default_timeout_sec == 300
        assert config.agent.timeout.by_category == {"amber_simulation": 3600}
        assert config.agent.timeout.by_tool == {"run_md_simulation": 7200}
        assert config.agent.timeout.warning_threshold == 0.75

    def test_load_config_without_timeout_section(self, tmp_path):
        """Test backward compatibility - config without timeout section."""
        config_file = tmp_path / ".mdpilot.yaml"
        config_data = {
            "agent": {
                "max_iterations": 50
            }
        }
        
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        
        config = load_config(project_dir=tmp_path)
        
        assert config.agent.max_iterations == 50
        assert config.agent.timeout.default_timeout_sec is None
        assert config.agent.timeout.by_category == {}
        assert config.agent.timeout.by_tool == {}
        assert config.agent.timeout.warning_threshold == 0.8

    def test_load_config_with_empty_timeout_section(self, tmp_path):
        """Test loading config with empty timeout section."""
        config_file = tmp_path / ".mdpilot.yaml"
        config_data = {
            "agent": {
                "timeout": {}
            }
        }
        
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        
        config = load_config(project_dir=tmp_path)
        
        assert config.agent.timeout.default_timeout_sec is None
        assert config.agent.timeout.by_category == {}
        assert config.agent.timeout.by_tool == {}
        assert config.agent.timeout.warning_threshold == 0.8

    def test_validation_error_invalid_timeout(self, tmp_path):
        """Test that validation errors propagate correctly for invalid timeout."""
        config_file = tmp_path / ".mdpilot.yaml"
        config_data = {
            "agent": {
                "timeout": {
                    "default_timeout_sec": 0  # Invalid: must be >= 1
                }
            }
        }
        
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        
        with pytest.raises(ValueError) as exc_info:
            load_config(project_dir=tmp_path)
        
        error_msg = str(exc_info.value)
        assert "validation failed" in error_msg.lower()
        assert "timeout" in error_msg.lower()

    def test_validation_error_invalid_warning_threshold(self, tmp_path):
        """Test that validation errors propagate for invalid warning_threshold."""
        config_file = tmp_path / ".mdpilot.yaml"
        config_data = {
            "agent": {
                "timeout": {
                    "warning_threshold": 1.5  # Invalid: must be <= 1.0
                }
            }
        }
        
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        
        with pytest.raises(ValueError) as exc_info:
            load_config(project_dir=tmp_path)
        
        error_msg = str(exc_info.value)
        assert "validation failed" in error_msg.lower()

    def test_timeout_config_deep_merge(self, tmp_path):
        """Test that timeout config is deep-merged correctly across layers."""
        # User config: sets default_timeout_sec
        user_config_dir = tmp_path / ".mdpilot"
        user_config_dir.mkdir()
        user_config_file = user_config_dir / "config.yaml"
        user_config_data = {
            "agent": {
                "timeout": {
                    "default_timeout_sec": 300,
                    "by_category": {"amber": 3600}
                }
            }
        }
        with open(user_config_file, "w") as f:
            yaml.dump(user_config_data, f)
        
        # Project config: adds by_tool and overrides warning_threshold
        project_config_file = tmp_path / ".mdpilot.yaml"
        project_config_data = {
            "agent": {
                "timeout": {
                    "by_tool": {"tool1": 120},
                    "warning_threshold": 0.9
                }
            }
        }
        with open(project_config_file, "w") as f:
            yaml.dump(project_config_data, f)
        
        # Temporarily change HOME to tmp_path for this test
        original_home = os.environ.get("HOME")
        try:
            os.environ["HOME"] = str(tmp_path)
            config = load_config(project_dir=tmp_path)
            
            # Should have merged values from both layers
            assert config.agent.timeout.default_timeout_sec == 300  # From user
            assert config.agent.timeout.by_category == {"amber": 3600}  # From user
            assert config.agent.timeout.by_tool == {"tool1": 120}  # From project
            assert config.agent.timeout.warning_threshold == 0.9  # From project (overrides default)
        finally:
            if original_home:
                os.environ["HOME"] = original_home
            else:
                os.environ.pop("HOME", None)

    def test_cli_overrides_timeout(self, tmp_path):
        """Test that CLI overrides work for timeout config."""
        config_file = tmp_path / ".mdpilot.yaml"
        config_data = {
            "agent": {
                "timeout": {
                    "default_timeout_sec": 300
                }
            }
        }
        
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        
        cli_overrides = {
            "agent": {
                "timeout": {
                    "default_timeout_sec": 600  # Override from CLI
                }
            }
        }
        
        config = load_config(cli_overrides=cli_overrides, project_dir=tmp_path)
        
        assert config.agent.timeout.default_timeout_sec == 600  # CLI wins

    def test_partial_timeout_config_in_yaml(self, tmp_path):
        """Test that partial timeout config works (only some fields specified)."""
        config_file = tmp_path / ".mdpilot.yaml"
        config_data = {
            "agent": {
                "timeout": {
                    "default_timeout_sec": 300
                    # by_category, by_tool, warning_threshold use defaults
                }
            }
        }
        
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        
        config = load_config(project_dir=tmp_path)
        
        assert config.agent.timeout.default_timeout_sec == 300
        assert config.agent.timeout.by_category == {}  # Default
        assert config.agent.timeout.by_tool == {}  # Default
        assert config.agent.timeout.warning_threshold == 0.8  # Default
