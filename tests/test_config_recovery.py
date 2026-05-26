"""Tests for workflow recovery configuration schema."""

from __future__ import annotations

import pytest
import yaml
from pathlib import Path
from pydantic import ValidationError

from mdpilot.config import AppConfig, AgentConfig, load_config
from mdpilot.config.schema import CheckpointConfig, RetryConfig, RecoveryConfig


class TestCheckpointConfig:
    """Tests for CheckpointConfig validation and defaults."""

    def test_default_values(self):
        """CheckpointConfig has correct default values."""
        cfg = CheckpointConfig()
        assert cfg.enabled is True
        assert cfg.checkpoint_interval == 5
        assert cfg.long_operation_threshold == 60
        assert cfg.cleanup_on_success is True

    def test_custom_values(self):
        """CheckpointConfig accepts custom values."""
        cfg = CheckpointConfig(
            enabled=False,
            checkpoint_interval=10,
            long_operation_threshold=120,
            cleanup_on_success=False,
        )
        assert cfg.enabled is False
        assert cfg.checkpoint_interval == 10
        assert cfg.long_operation_threshold == 120
        assert cfg.cleanup_on_success is False

    def test_coerces_enabled_from_string(self):
        """enabled coerces string to bool (Pydantic behavior)."""
        cfg = CheckpointConfig(enabled="yes")  # type: ignore[arg-type]
        assert cfg.enabled is True

    def test_coerces_interval_from_string(self):
        """checkpoint_interval coerces numeric string to int (Pydantic behavior)."""
        cfg = CheckpointConfig(checkpoint_interval="5")  # type: ignore[arg-type]
        assert cfg.checkpoint_interval == 5

    def test_rejects_negative_interval(self):
        """checkpoint_interval must be positive."""
        with pytest.raises(ValidationError):
            CheckpointConfig(checkpoint_interval=-1)

    def test_rejects_negative_threshold(self):
        """long_operation_threshold must be positive."""
        with pytest.raises(ValidationError):
            CheckpointConfig(long_operation_threshold=-60)

    def test_accepts_zero_interval(self):
        """checkpoint_interval can be zero (disabled)."""
        cfg = CheckpointConfig(checkpoint_interval=0)
        assert cfg.checkpoint_interval == 0


class TestRetryConfig:
    """Tests for RetryConfig validation and defaults."""

    def test_default_values(self):
        """RetryConfig has correct default values."""
        cfg = RetryConfig()
        assert cfg.default_max_attempts == 3
        assert cfg.default_backoff_base == 2.0
        assert cfg.max_backoff == 300.0
        assert cfg.by_tool == {}
        assert cfg.by_error_type == {}

    def test_custom_values(self):
        """RetryConfig accepts custom values."""
        cfg = RetryConfig(
            default_max_attempts=5,
            default_backoff_base=1.5,
            max_backoff=600.0,
            by_tool={"pmemd": {"max_attempts": 10}},
            by_error_type={"TimeoutError": {"backoff_base": 3.0}},
        )
        assert cfg.default_max_attempts == 5
        assert cfg.default_backoff_base == 1.5
        assert cfg.max_backoff == 600.0
        assert cfg.by_tool == {"pmemd": {"max_attempts": 10}}
        assert cfg.by_error_type == {"TimeoutError": {"backoff_base": 3.0}}

    def test_coerces_max_attempts_from_string(self):
        """default_max_attempts coerces numeric string to int (Pydantic behavior)."""
        cfg = RetryConfig(default_max_attempts="3")  # type: ignore[arg-type]
        assert cfg.default_max_attempts == 3

    def test_coerces_backoff_base_from_string(self):
        """default_backoff_base coerces numeric string to float (Pydantic behavior)."""
        cfg = RetryConfig(default_backoff_base="2.0")  # type: ignore[arg-type]
        assert cfg.default_backoff_base == 2.0

    def test_rejects_negative_max_attempts(self):
        """default_max_attempts must be positive."""
        with pytest.raises(ValidationError):
            RetryConfig(default_max_attempts=-1)

    def test_rejects_negative_backoff_base(self):
        """default_backoff_base must be positive."""
        with pytest.raises(ValidationError):
            RetryConfig(default_backoff_base=-2.0)

    def test_rejects_negative_max_backoff(self):
        """max_backoff must be positive."""
        with pytest.raises(ValidationError):
            RetryConfig(max_backoff=-300.0)

    def test_accepts_zero_max_attempts(self):
        """default_max_attempts can be zero (no retries)."""
        cfg = RetryConfig(default_max_attempts=0)
        assert cfg.default_max_attempts == 0

    def test_by_tool_dict_structure(self):
        """by_tool accepts nested dict with tool-specific settings."""
        cfg = RetryConfig(
            by_tool={
                "pmemd": {"max_attempts": 5, "backoff_base": 3.0},
                "tleap": {"max_attempts": 2},
            }
        )
        assert cfg.by_tool["pmemd"]["max_attempts"] == 5
        assert cfg.by_tool["pmemd"]["backoff_base"] == 3.0
        assert cfg.by_tool["tleap"]["max_attempts"] == 2

    def test_by_error_type_dict_structure(self):
        """by_error_type accepts nested dict with error-specific settings."""
        cfg = RetryConfig(
            by_error_type={
                "TimeoutError": {"max_attempts": 10, "backoff_base": 1.5},
                "FileNotFoundError": {"max_attempts": 1},
            }
        )
        assert cfg.by_error_type["TimeoutError"]["max_attempts"] == 10
        assert cfg.by_error_type["FileNotFoundError"]["max_attempts"] == 1


class TestRecoveryConfig:
    """Tests for RecoveryConfig validation and defaults."""

    def test_default_values(self):
        """RecoveryConfig has correct default nested configs."""
        cfg = RecoveryConfig()
        assert isinstance(cfg.checkpoint, CheckpointConfig)
        assert isinstance(cfg.retry, RetryConfig)
        assert cfg.checkpoint.enabled is True
        assert cfg.retry.default_max_attempts == 3

    def test_custom_checkpoint(self):
        """RecoveryConfig accepts custom CheckpointConfig."""
        checkpoint = CheckpointConfig(enabled=False, checkpoint_interval=10)
        cfg = RecoveryConfig(checkpoint=checkpoint)
        assert cfg.checkpoint.enabled is False
        assert cfg.checkpoint.checkpoint_interval == 10
        # Retry should still have defaults
        assert cfg.retry.default_max_attempts == 3

    def test_custom_retry(self):
        """RecoveryConfig accepts custom RetryConfig."""
        retry = RetryConfig(default_max_attempts=5, max_backoff=600.0)
        cfg = RecoveryConfig(retry=retry)
        assert cfg.retry.default_max_attempts == 5
        assert cfg.retry.max_backoff == 600.0
        # Checkpoint should still have defaults
        assert cfg.checkpoint.enabled is True

    def test_custom_both(self):
        """RecoveryConfig accepts both custom configs."""
        checkpoint = CheckpointConfig(checkpoint_interval=15)
        retry = RetryConfig(default_max_attempts=7)
        cfg = RecoveryConfig(checkpoint=checkpoint, retry=retry)
        assert cfg.checkpoint.checkpoint_interval == 15
        assert cfg.retry.default_max_attempts == 7

    def test_nested_validation(self):
        """RecoveryConfig validates nested configs."""
        with pytest.raises(ValidationError):
            RecoveryConfig(
                checkpoint=CheckpointConfig(checkpoint_interval=-1)  # Invalid
            )


class TestAgentConfigWithRecovery:
    """Tests for AgentConfig with recovery field."""

    def test_agent_has_recovery_field(self):
        """AgentConfig includes recovery field with defaults."""
        cfg = AgentConfig()
        assert hasattr(cfg, "recovery")
        assert isinstance(cfg.recovery, RecoveryConfig)
        assert cfg.recovery.checkpoint.enabled is True
        assert cfg.recovery.retry.default_max_attempts == 3

    def test_agent_custom_recovery(self):
        """AgentConfig accepts custom RecoveryConfig."""
        recovery = RecoveryConfig(
            checkpoint=CheckpointConfig(enabled=False),
            retry=RetryConfig(default_max_attempts=10),
        )
        cfg = AgentConfig(recovery=recovery)
        assert cfg.recovery.checkpoint.enabled is False
        assert cfg.recovery.retry.default_max_attempts == 10
        # Other agent fields should have defaults
        assert cfg.max_iterations == 90

    def test_agent_partial_recovery_override(self):
        """AgentConfig allows partial recovery override."""
        cfg = AgentConfig(
            max_iterations=50,
            recovery=RecoveryConfig(
                checkpoint=CheckpointConfig(checkpoint_interval=10)
            ),
        )
        assert cfg.max_iterations == 50
        assert cfg.recovery.checkpoint.checkpoint_interval == 10
        # Unspecified recovery fields should have defaults
        assert cfg.recovery.retry.default_max_attempts == 3


class TestAppConfigWithRecovery:
    """Tests for AppConfig with nested recovery configuration."""

    def test_app_config_includes_recovery(self):
        """AppConfig includes recovery through AgentConfig."""
        cfg = AppConfig()
        assert isinstance(cfg.agent.recovery, RecoveryConfig)
        assert cfg.agent.recovery.checkpoint.enabled is True

    def test_app_config_custom_recovery(self):
        """AppConfig accepts custom recovery configuration."""
        cfg = AppConfig(
            agent=AgentConfig(
                recovery=RecoveryConfig(
                    checkpoint=CheckpointConfig(checkpoint_interval=20),
                    retry=RetryConfig(default_max_attempts=8),
                )
            )
        )
        assert cfg.agent.recovery.checkpoint.checkpoint_interval == 20
        assert cfg.agent.recovery.retry.default_max_attempts == 8


class TestLoadConfigWithRecovery:
    """Integration tests for loading recovery config from YAML."""

    def test_load_recovery_from_yaml(self, tmp_path: Path):
        """Recovery config can be loaded from project YAML."""
        proj_yaml = tmp_path / ".mdpilot.yaml"
        proj_yaml.write_text(
            yaml.dump({
                "agent": {
                    "max_iterations": 50,
                    "recovery": {
                        "checkpoint": {
                            "enabled": False,
                            "checkpoint_interval": 10,
                        },
                        "retry": {
                            "default_max_attempts": 5,
                            "max_backoff": 600.0,
                        },
                    },
                }
            })
        )

        cfg = load_config(project_dir=tmp_path)
        assert cfg.agent.max_iterations == 50
        assert cfg.agent.recovery.checkpoint.enabled is False
        assert cfg.agent.recovery.checkpoint.checkpoint_interval == 10
        assert cfg.agent.recovery.retry.default_max_attempts == 5
        assert cfg.agent.recovery.retry.max_backoff == 600.0

    def test_load_partial_recovery_from_yaml(self, tmp_path: Path):
        """Partial recovery config in YAML preserves defaults."""
        proj_yaml = tmp_path / ".mdpilot.yaml"
        proj_yaml.write_text(
            yaml.dump({
                "agent": {
                    "recovery": {
                        "checkpoint": {
                            "checkpoint_interval": 15,
                        },
                    },
                }
            })
        )

        cfg = load_config(project_dir=tmp_path)
        # Specified value
        assert cfg.agent.recovery.checkpoint.checkpoint_interval == 15
        # Defaults preserved
        assert cfg.agent.recovery.checkpoint.enabled is True
        assert cfg.agent.recovery.retry.default_max_attempts == 3

    def test_load_retry_by_tool_from_yaml(self, tmp_path: Path):
        """Tool-specific retry config can be loaded from YAML."""
        proj_yaml = tmp_path / ".mdpilot.yaml"
        proj_yaml.write_text(
            yaml.dump({
                "agent": {
                    "recovery": {
                        "retry": {
                            "by_tool": {
                                "pmemd": {
                                    "max_attempts": 10,
                                    "backoff_base": 3.0,
                                },
                                "tleap": {
                                    "max_attempts": 2,
                                },
                            },
                        },
                    },
                }
            })
        )

        cfg = load_config(project_dir=tmp_path)
        assert cfg.agent.recovery.retry.by_tool["pmemd"]["max_attempts"] == 10
        assert cfg.agent.recovery.retry.by_tool["pmemd"]["backoff_base"] == 3.0
        assert cfg.agent.recovery.retry.by_tool["tleap"]["max_attempts"] == 2

    def test_load_retry_by_error_type_from_yaml(self, tmp_path: Path):
        """Error-specific retry config can be loaded from YAML."""
        proj_yaml = tmp_path / ".mdpilot.yaml"
        proj_yaml.write_text(
            yaml.dump({
                "agent": {
                    "recovery": {
                        "retry": {
                            "by_error_type": {
                                "TimeoutError": {
                                    "max_attempts": 5,
                                    "backoff_base": 2.5,
                                },
                            },
                        },
                    },
                }
            })
        )

        cfg = load_config(project_dir=tmp_path)
        assert cfg.agent.recovery.retry.by_error_type["TimeoutError"]["max_attempts"] == 5
        assert cfg.agent.recovery.retry.by_error_type["TimeoutError"]["backoff_base"] == 2.5

    def test_backward_compatibility_without_recovery(self, tmp_path: Path):
        """Existing configs without recovery section still work."""
        proj_yaml = tmp_path / ".mdpilot.yaml"
        proj_yaml.write_text(
            yaml.dump({
                "provider": {"model": "claude-sonnet-4-20250514"},
                "agent": {"max_iterations": 100},
            })
        )

        cfg = load_config(project_dir=tmp_path)
        assert cfg.agent.max_iterations == 100
        # Recovery should have defaults
        assert cfg.agent.recovery.checkpoint.enabled is True
        assert cfg.agent.recovery.retry.default_max_attempts == 3

    def test_invalid_recovery_config_raises_error(self, tmp_path: Path):
        """Invalid recovery config in YAML raises ValidationError."""
        proj_yaml = tmp_path / ".mdpilot.yaml"
        proj_yaml.write_text(
            yaml.dump({
                "agent": {
                    "recovery": {
                        "checkpoint": {
                            "checkpoint_interval": -5,  # Invalid
                        },
                    },
                }
            })
        )

        with pytest.raises(ValueError) as exc_info:
            load_config(project_dir=tmp_path)
        assert "checkpoint_interval" in str(exc_info.value)


class TestRecoveryConfigSerialization:
    """Tests for serialization/deserialization of recovery config."""

    def test_recovery_config_to_dict(self):
        """RecoveryConfig can be serialized to dict."""
        cfg = RecoveryConfig(
            checkpoint=CheckpointConfig(checkpoint_interval=10),
            retry=RetryConfig(default_max_attempts=5),
        )
        data = cfg.model_dump()
        assert data["checkpoint"]["checkpoint_interval"] == 10
        assert data["retry"]["default_max_attempts"] == 5

    def test_recovery_config_from_dict(self):
        """RecoveryConfig can be deserialized from dict."""
        data = {
            "checkpoint": {
                "enabled": False,
                "checkpoint_interval": 15,
                "long_operation_threshold": 120,
                "cleanup_on_success": False,
            },
            "retry": {
                "default_max_attempts": 7,
                "default_backoff_base": 3.0,
                "max_backoff": 600.0,
                "by_tool": {"pmemd": {"max_attempts": 10}},
                "by_error_type": {},
            },
        }
        cfg = RecoveryConfig(**data)
        assert cfg.checkpoint.enabled is False
        assert cfg.checkpoint.checkpoint_interval == 15
        assert cfg.retry.default_max_attempts == 7
        assert cfg.retry.by_tool["pmemd"]["max_attempts"] == 10
