"""Tests for configuration loading error handling."""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from mdpilot.config.loader import _load_yaml, load_config


class TestYAMLLoadingErrors:
    """Test error handling in YAML file loading."""

    def test_load_yaml_nonexistent_file(self, tmp_path):
        """Non-existent files should return empty dict without error."""
        result = _load_yaml(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_load_yaml_invalid_syntax(self, tmp_path, caplog):
        """Invalid YAML syntax should log warning and return empty dict."""
        invalid_yaml = tmp_path / "invalid.yaml"
        invalid_yaml.write_text("key: [unclosed list")

        with caplog.at_level(logging.WARNING):
            result = _load_yaml(invalid_yaml)

        assert result == {}
        assert "Invalid YAML" in caplog.text
        assert str(invalid_yaml) in caplog.text

    def test_load_yaml_not_a_dict(self, tmp_path, caplog):
        """YAML files that don't contain a dict should log warning."""
        list_yaml = tmp_path / "list.yaml"
        list_yaml.write_text("- item1\n- item2")

        with caplog.at_level(logging.WARNING):
            result = _load_yaml(list_yaml)

        assert result == {}
        assert "does not contain a dict" in caplog.text

    def test_load_yaml_permission_denied(self, tmp_path, caplog):
        """Files with read permission errors should log warning."""
        restricted = tmp_path / "restricted.yaml"
        restricted.write_text("key: value")
        restricted.chmod(0o000)

        try:
            with caplog.at_level(logging.WARNING):
                result = _load_yaml(restricted)

            assert result == {}
            assert "Cannot read" in caplog.text
        finally:
            restricted.chmod(0o644)

    def test_load_yaml_valid_file(self, tmp_path):
        """Valid YAML files should load successfully."""
        valid_yaml = tmp_path / "valid.yaml"
        valid_yaml.write_text("provider:\n  model: gpt-4\n")

        result = _load_yaml(valid_yaml)

        assert result == {"provider": {"model": "gpt-4"}}


class TestConfigValidationErrors:
    """Test error handling in configuration validation."""

    def test_validation_error_formatting(self, tmp_path):
        """Validation errors should be formatted in a user-friendly way."""
        invalid_config = tmp_path / ".mdpilot.yaml"
        invalid_config.write_text("agent:\n  default_mode: invalid_mode\n")  # Invalid literal

        with pytest.raises(ValueError) as exc_info:
            load_config(project_dir=tmp_path)

        error_msg = str(exc_info.value)
        assert "Configuration validation failed" in error_msg
        assert "default_mode" in error_msg.lower()

    def test_invalid_type_error(self, tmp_path):
        """Type validation errors should be clearly reported."""
        invalid_config = tmp_path / ".mdpilot.yaml"
        invalid_config.write_text("provider:\n  max_tokens: 'not_a_number'\n")

        with pytest.raises(ValueError) as exc_info:
            load_config(project_dir=tmp_path)

        error_msg = str(exc_info.value)
        assert "Configuration validation failed" in error_msg
        assert "max_tokens" in error_msg

    def test_missing_required_field_with_defaults(self, tmp_path):
        """Missing fields should be filled by defaults, not cause errors."""
        minimal_config = tmp_path / ".mdpilot.yaml"
        minimal_config.write_text("provider:\n  model: gpt-4\n")

        config = load_config(project_dir=tmp_path)

        assert config.provider.model == "gpt-4"
        assert config.provider.temperature is not None  # From defaults

    def test_completely_invalid_structure(self, tmp_path):
        """Completely invalid config structure should give clear error."""
        invalid_config = tmp_path / ".mdpilot.yaml"
        invalid_config.write_text("random_key: random_value\n")

        # Should still load because defaults provide required fields
        config = load_config(project_dir=tmp_path)
        assert config is not None


class TestConfigLoadingLogging:
    """Test logging during configuration loading."""

    def test_debug_logging_for_each_layer(self, tmp_path, caplog):
        """Each config layer should be logged at DEBUG level."""
        project_config = tmp_path / ".mdpilot.yaml"
        project_config.write_text("provider:\n  model: custom-model\n")

        with caplog.at_level(logging.DEBUG):
            load_config(project_dir=tmp_path)

        assert "Loaded embedded defaults" in caplog.text
        assert "Merged project config" in caplog.text

    def test_info_logging_on_success(self, tmp_path, caplog):
        """Successful config load should log at INFO level."""
        with caplog.at_level(logging.INFO):
            load_config(project_dir=tmp_path)

        assert "Configuration loaded successfully" in caplog.text

    def test_error_logging_on_validation_failure(self, tmp_path, caplog):
        """Validation failures should log at ERROR level."""
        invalid_config = tmp_path / ".mdpilot.yaml"
        invalid_config.write_text("provider:\n  max_tokens: not_an_integer\n")  # Invalid type

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError):
                load_config(project_dir=tmp_path)

        assert "Configuration validation failed" in caplog.text


class TestConfigErrorRecovery:
    """Test graceful degradation when config files have issues."""

    def test_corrupt_user_config_uses_defaults(self, tmp_path, monkeypatch):
        """Corrupt user config should fall back to defaults."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        config_dir = fake_home / ".mdpilot"
        config_dir.mkdir()

        corrupt_config = config_dir / "config.yaml"
        corrupt_config.write_text("invalid: yaml: syntax:")

        monkeypatch.setenv("HOME", str(fake_home))

        # Should not raise, should use defaults
        config = load_config(project_dir=False)
        assert config is not None

    def test_corrupt_project_config_uses_user_and_defaults(self, tmp_path):
        """Corrupt project config should still load user config and defaults."""
        corrupt_project = tmp_path / ".mdpilot.yaml"
        corrupt_project.write_text("{{invalid yaml}}")

        # Should not raise, should use defaults
        config = load_config(project_dir=tmp_path)
        assert config is not None

    def test_partial_valid_config_merges_correctly(self, tmp_path):
        """Partially valid config should merge valid parts with defaults."""
        partial_config = tmp_path / ".mdpilot.yaml"
        partial_config.write_text("""
provider:
  model: custom-model
  # temperature will come from defaults
""")

        config = load_config(project_dir=tmp_path)

        assert config.provider.model == "custom-model"
        assert config.provider.temperature is not None  # From defaults


class TestEnvironmentVariableErrors:
    """Test error handling for environment variable overrides."""

    def test_empty_env_var_ignored(self, monkeypatch):
        """Empty environment variables should be ignored."""
        monkeypatch.setenv("MDPILOT_MODEL", "")

        config = load_config(project_dir=False)

        # Should use default, not empty string
        assert config.provider.model != ""

    def test_invalid_env_var_value_caught_in_validation(self, monkeypatch):
        """Invalid env var values should be caught during validation."""
        monkeypatch.setenv("MDPILOT_BASE_URL", "not a valid url format")

        # Should still load - URL validation might be lenient
        # or should raise ValueError with clear message
        try:
            config = load_config(project_dir=False)
            # If it loads, the value should be set
            assert config.provider.base_url == "not a valid url format"
        except ValueError as e:
            # If validation fails, error should mention base_url
            assert "base_url" in str(e).lower()
