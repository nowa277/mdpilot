"""Tests for TimeoutConfig integration into AgentConfig."""

import pytest

from mdpilot.config.schema import AgentConfig, TimeoutConfig


class TestAgentConfigTimeoutIntegration:
    """Test TimeoutConfig integration with AgentConfig."""

    def test_agent_config_has_timeout_field(self):
        """Test that AgentConfig has a timeout field."""
        config = AgentConfig()
        
        assert hasattr(config, "timeout")
        assert isinstance(config.timeout, TimeoutConfig)

    def test_agent_config_timeout_defaults_to_empty(self):
        """Test that timeout field defaults to empty TimeoutConfig."""
        config = AgentConfig()
        
        assert config.timeout.default_timeout_sec is None
        assert config.timeout.by_category == {}
        assert config.timeout.by_tool == {}
        assert config.timeout.warning_threshold == 0.8

    def test_agent_config_accepts_custom_timeout(self):
        """Test that AgentConfig accepts custom TimeoutConfig."""
        timeout_config = TimeoutConfig(
            default_timeout_sec=300,
            by_category={"amber_simulation": 3600},
            by_tool={"run_md_simulation": 7200},
            warning_threshold=0.75
        )
        
        config = AgentConfig(timeout=timeout_config)
        
        assert config.timeout.default_timeout_sec == 300
        assert config.timeout.by_category == {"amber_simulation": 3600}
        assert config.timeout.by_tool == {"run_md_simulation": 7200}
        assert config.timeout.warning_threshold == 0.75

    def test_agent_config_timeout_from_dict(self):
        """Test that AgentConfig can be created from dict with timeout."""
        data = {
            "max_iterations": 50,
            "timeout": {
                "default_timeout_sec": 300,
                "by_category": {"amber": 3600},
                "warning_threshold": 0.9
            }
        }
        
        config = AgentConfig(**data)
        
        assert config.max_iterations == 50
        assert config.timeout.default_timeout_sec == 300
        assert config.timeout.by_category == {"amber": 3600}
        assert config.timeout.warning_threshold == 0.9

    def test_agent_config_serialization_with_timeout(self):
        """Test that AgentConfig serializes timeout correctly."""
        config = AgentConfig(
            max_iterations=50,
            timeout=TimeoutConfig(
                default_timeout_sec=300,
                by_category={"amber": 3600}
            )
        )
        
        data = config.model_dump()
        
        assert data["max_iterations"] == 50
        assert data["timeout"]["default_timeout_sec"] == 300
        assert data["timeout"]["by_category"] == {"amber": 3600}
        assert data["timeout"]["warning_threshold"] == 0.8

    def test_agent_config_without_timeout_in_dict(self):
        """Test backward compatibility - AgentConfig works without timeout in dict."""
        data = {
            "max_iterations": 50,
            "default_mode": "plan"
        }
        
        config = AgentConfig(**data)
        
        assert config.max_iterations == 50
        assert config.default_mode == "plan"
        assert config.timeout.default_timeout_sec is None  # Default empty timeout

    def test_agent_config_preserves_other_fields(self):
        """Test that adding timeout doesn't break other AgentConfig fields."""
        config = AgentConfig(
            max_iterations=100,
            max_context_tokens=50000,
            default_mode="react",
            auto_confirm_steps=5,
            timeout=TimeoutConfig(default_timeout_sec=300)
        )
        
        assert config.max_iterations == 100
        assert config.max_context_tokens == 50000
        assert config.default_mode == "react"
        assert config.auto_confirm_steps == 5
        assert config.timeout.default_timeout_sec == 300
        assert hasattr(config, "recovery")
        assert hasattr(config, "parallel")
