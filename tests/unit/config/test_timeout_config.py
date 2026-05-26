"""Tests for TimeoutConfig schema."""

import pytest
from pydantic import ValidationError

from mdpilot.config.schema import TimeoutConfig


class TestTimeoutConfigValidation:
    """Test TimeoutConfig validation rules."""

    def test_valid_config_with_all_fields(self):
        """Test valid configuration with all fields specified."""
        config = TimeoutConfig(
            default_timeout_sec=300,
            by_category={"amber_simulation": 3600, "file_operations": 60},
            by_tool={"run_md_simulation": 7200, "prepare_system": 120},
            warning_threshold=0.75
        )
        
        assert config.default_timeout_sec == 300
        assert config.by_category == {"amber_simulation": 3600, "file_operations": 60}
        assert config.by_tool == {"run_md_simulation": 7200, "prepare_system": 120}
        assert config.warning_threshold == 0.75

    def test_valid_config_with_defaults(self):
        """Test valid configuration with default values."""
        config = TimeoutConfig()
        
        assert config.default_timeout_sec is None
        assert config.by_category == {}
        assert config.by_tool == {}
        assert config.warning_threshold == 0.8

    def test_valid_config_with_none_timeout(self):
        """Test valid configuration with explicit None timeout (unlimited)."""
        config = TimeoutConfig(default_timeout_sec=None)
        
        assert config.default_timeout_sec is None

    def test_invalid_default_timeout_zero(self):
        """Test that default_timeout_sec=0 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TimeoutConfig(default_timeout_sec=0)
        
        assert "greater than or equal to 1" in str(exc_info.value).lower()

    def test_invalid_default_timeout_negative(self):
        """Test that negative default_timeout_sec is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TimeoutConfig(default_timeout_sec=-10)
        
        assert "greater than or equal to 1" in str(exc_info.value).lower()

    def test_invalid_warning_threshold_negative(self):
        """Test that negative warning_threshold is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TimeoutConfig(warning_threshold=-0.1)
        
        assert "greater than or equal to 0" in str(exc_info.value).lower()

    def test_invalid_warning_threshold_above_one(self):
        """Test that warning_threshold > 1.0 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TimeoutConfig(warning_threshold=1.5)
        
        assert "less than or equal to 1" in str(exc_info.value).lower()

    def test_valid_warning_threshold_boundaries(self):
        """Test that warning_threshold boundaries (0.0 and 1.0) are valid."""
        config_zero = TimeoutConfig(warning_threshold=0.0)
        assert config_zero.warning_threshold == 0.0
        
        config_one = TimeoutConfig(warning_threshold=1.0)
        assert config_one.warning_threshold == 1.0

    def test_by_category_dict_works(self):
        """Test that by_category dictionary accepts string keys and int values."""
        config = TimeoutConfig(
            by_category={
                "amber_simulation": 3600,
                "analysis": 600,
                "file_operations": 30
            }
        )
        
        assert len(config.by_category) == 3
        assert config.by_category["amber_simulation"] == 3600
        assert config.by_category["analysis"] == 600
        assert config.by_category["file_operations"] == 30

    def test_by_tool_dict_works(self):
        """Test that by_tool dictionary accepts string keys and int values."""
        config = TimeoutConfig(
            by_tool={
                "run_md_simulation": 7200,
                "minimize_energy": 900,
                "prepare_system": 60
            }
        )
        
        assert len(config.by_tool) == 3
        assert config.by_tool["run_md_simulation"] == 7200
        assert config.by_tool["minimize_energy"] == 900
        assert config.by_tool["prepare_system"] == 60

    def test_empty_dicts_by_default(self):
        """Test that by_category and by_tool default to empty dicts."""
        config = TimeoutConfig()
        
        assert isinstance(config.by_category, dict)
        assert isinstance(config.by_tool, dict)
        assert len(config.by_category) == 0
        assert len(config.by_tool) == 0

    def test_config_serialization(self):
        """Test that config can be serialized to dict."""
        config = TimeoutConfig(
            default_timeout_sec=300,
            by_category={"amber": 3600},
            by_tool={"tool1": 120},
            warning_threshold=0.9
        )
        
        data = config.model_dump()
        
        assert data["default_timeout_sec"] == 300
        assert data["by_category"] == {"amber": 3600}
        assert data["by_tool"] == {"tool1": 120}
        assert data["warning_threshold"] == 0.9

    def test_config_deserialization(self):
        """Test that config can be created from dict."""
        data = {
            "default_timeout_sec": 300,
            "by_category": {"amber": 3600},
            "by_tool": {"tool1": 120},
            "warning_threshold": 0.9
        }
        
        config = TimeoutConfig(**data)
        
        assert config.default_timeout_sec == 300
        assert config.by_category == {"amber": 3600}
        assert config.by_tool == {"tool1": 120}
        assert config.warning_threshold == 0.9
