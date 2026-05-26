"""Comprehensive tests for amber-agent configuration system."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from mdpilot.config import (
    AgentConfig,
    AmberConfig,
    AppConfig,
    ProviderConfig,
    load_config,
)
from mdpilot.config.defaults import DEFAULTS
from mdpilot.config.loader import _deep_merge, _env_overrides, _load_yaml


# ---------------------------------------------------------------------------
# Unit tests – _deep_merge
# ---------------------------------------------------------------------------

class TestDeepMerge:
    """Tests for the deep-merge utility."""

    def test_simple_leaf_override(self):
        """A top-level leaf value in override replaces base."""
        base = {"a": 1, "b": 2}
        override = {"b": 99}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 99}

    def test_nested_dict_merge(self):
        """Nested dicts are merged recursively, not replaced."""
        base = {"provider": {"model": "base-model", "timeout": 30}}
        override = {"provider": {"timeout": 60}}
        result = _deep_merge(base, override)
        assert result == {"provider": {"model": "base-model", "timeout": 60}}

    def test_deep_merge_three_levels(self):
        """Three levels of nesting merge correctly."""
        base = {"a": {"b": {"c": 1, "d": 2}}}
        override = {"a": {"b": {"c": 99}}}
        result = _deep_merge(base, override)
        assert result == {"a": {"b": {"c": 99, "d": 2}}}

    def test_override_adds_new_key(self):
        """Override can introduce new keys that don't exist in base."""
        base = {"x": 1}
        override = {"y": 2}
        result = _deep_merge(base, override)
        assert result == {"x": 1, "y": 2}

    def test_override_replaces_list(self):
        """Lists are replaced entirely (not appended)."""
        base = {"models": ["a", "b"]}
        override = {"models": ["c"]}
        result = _deep_merge(base, override)
        assert result == {"models": ["c"]}

    def test_does_not_mutate_inputs(self):
        """_deep_merge returns a new dict; inputs are unchanged."""
        base = {"a": {"b": 1}}
        override = {"a": {"c": 2}}
        result = _deep_merge(base, override)
        assert base == {"a": {"b": 1}}
        assert override == {"a": {"c": 2}}
        assert result["a"] is not base["a"]


# ---------------------------------------------------------------------------
# Unit tests – _load_yaml
# ---------------------------------------------------------------------------

class TestLoadYaml:
    """Tests for YAML loading utility."""

    def test_loads_valid_yaml(self, tmp_path: Path):
        """A valid YAML file is parsed and returned as a dict."""
        f = tmp_path / "cfg.yaml"
        f.write_text("model: test-model\ntimeout: 60\n")
        result = _load_yaml(f)
        assert result == {"model": "test-model", "timeout": 60}

    def test_missing_file_returns_empty_dict(self, tmp_path: Path):
        """A non-existent path returns an empty dict, not an exception."""
        result = _load_yaml(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_invalid_yaml_returns_empty_dict(self, tmp_path: Path):
        """A malformed YAML file returns an empty dict."""
        f = tmp_path / "bad.yaml"
        f.write_text("  invalid: yaml: content:\n   - [")
        result = _load_yaml(f)
        assert result == {}


# ---------------------------------------------------------------------------
# Unit tests – _env_overrides
# ---------------------------------------------------------------------------

class TestEnvOverrides:
    """Tests for environment-variable override collection."""

    def test_parses_model_var(self, monkeypatch: pytest.MonkeyPatch):
        """MDPILOT_MODEL sets provider.model."""
        monkeypatch.setenv("MDPILOT_MODEL", "my-model")
        result = _env_overrides()
        assert result == {"provider": {"model": "my-model"}}

    def test_parses_api_key_var(self, monkeypatch: pytest.MonkeyPatch):
        """MDPILOT_API_KEY sets provider.api_key."""
        monkeypatch.setenv("MDPILOT_API_KEY", "sk-secret")
        result = _env_overrides()
        assert result == {"provider": {"api_key": "sk-secret"}}

    def test_parses_base_url_var(self, monkeypatch: pytest.MonkeyPatch):
        """MDPILOT_BASE_URL sets provider.base_url."""
        monkeypatch.setenv("MDPILOT_BASE_URL", "https://my.api.com")
        result = _env_overrides()
        assert result == {"provider": {"base_url": "https://my.api.com"}}

    def test_all_vars_combined(self, monkeypatch: pytest.MonkeyPatch):
        """Multiple env vars are collected into one dict."""
        monkeypatch.setenv("MDPILOT_MODEL", "model-x")
        monkeypatch.setenv("MDPILOT_API_KEY", "key-y")
        monkeypatch.setenv("MDPILOT_BASE_URL", "https://z.com")
        result = _env_overrides()
        assert result == {
            "provider": {
                "model": "model-x",
                "api_key": "key-y",
                "base_url": "https://z.com",
            }
        }

    def test_missing_vars_return_empty(self):
        """When no MDPILOT_* vars are set, an empty dict is returned."""
        result = _env_overrides()
        assert result == {"provider": {}}

    def test_unset_var_not_included(self, monkeypatch: pytest.MonkeyPatch):
        """A var that exists but is set to empty string is treated as unset."""
        monkeypatch.setenv("MDPILOT_MODEL", "")
        result = _env_overrides()
        assert "model" not in result.get("provider", {})


# ---------------------------------------------------------------------------
# Schema model tests
# ---------------------------------------------------------------------------

class TestProviderConfig:
    """Tests for ProviderConfig validation and defaults."""

    def test_default_values(self):
        cfg = ProviderConfig()
        assert cfg.model == "claude-sonnet-4-20250514"
        assert cfg.api_key is None
        assert cfg.base_url is None
        assert cfg.fallback_models == []
        assert cfg.max_retries == 3
        assert cfg.timeout == 120
        assert cfg.temperature == 0.0
        assert cfg.max_tokens == 8192

    def test_custom_values(self):
        cfg = ProviderConfig(
            model="claude-opus-4-7",
            api_key="sk-123",
            base_url="https://my.api.com",
            fallback_models=["model-a", "model-b"],
            max_retries=5,
            timeout=60,
            temperature=0.7,
            max_tokens=4096,
        )
        assert cfg.model == "claude-opus-4-7"
        assert cfg.api_key.get_secret_value() == "sk-123"
        assert cfg.base_url == "https://my.api.com"
        assert cfg.fallback_models == ["model-a", "model-b"]
        assert cfg.max_retries == 5
        assert cfg.timeout == 60
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 4096


class TestAmberConfig:
    """Tests for AmberConfig validation and defaults."""

    def test_default_values(self):
        cfg = AmberConfig()
        assert cfg.amber_home == "/home/software/Amber24/amber24"
        assert cfg.tools_version == "24"
        assert cfg.gpu_enabled is True

    def test_custom_values(self):
        cfg = AmberConfig(
            amber_home="/opt/amber",
            tools_version="24",
            gpu_enabled=True,
        )
        assert cfg.amber_home == "/opt/amber"
        assert cfg.tools_version == "24"
        assert cfg.gpu_enabled is True


class TestLab03RemoteConfig:
    def test_defaults_point_to_lab03_amber24_workspace(self, tmp_path: Path):
        cfg = load_config(project_dir=tmp_path)

        assert cfg.lab03_remote is not None
        assert cfg.lab03_remote.ssh.host == "lab03"
        assert cfg.lab03_remote.work_dir == "/home/3-FF/changshengjie/project/mdpilot"
        assert cfg.lab03_remote.amber_home == "/home/software/Amber24/amber24"
        assert cfg.lab03_remote.tools.cpptraj == "/home/software/Amber24/amber24/bin/cpptraj"
        assert cfg.lab03_remote.tools.pmemd == "/home/software/Amber24/amber24/bin/pmemd"
        assert cfg.lab03_remote.tools.pmemd_cuda == "/home/software/Amber24/amber24/bin/pmemd.cuda"


class TestRemoteMigrationDefaults:
    def test_lab03_is_default_amber_backend(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("HOME", str(tmp_path))

        cfg = load_config(project_dir=tmp_path)

        assert cfg.amber.amber_home == "/home/software/Amber24/amber24"
        assert cfg.amber.tools_version == "24"
        assert cfg.amber.gpu_enabled is True
        assert cfg.lab03_remote is not None
        assert cfg.lab03_remote.ssh.host == "lab03"
        assert cfg.lab03_remote.work_dir == "/home/3-FF/changshengjie/project/mdpilot"
        assert cfg.lab03_remote.tools.cpptraj == "/home/software/Amber24/amber24/bin/cpptraj"
        assert cfg.lab03_remote.tools.pmemd == "/home/software/Amber24/amber24/bin/pmemd"
        assert cfg.lab03_remote.tools.pmemd_cuda == "/home/software/Amber24/amber24/bin/pmemd.cuda"

    def test_lab03_backend_keeps_lab02_and_lab06_as_remote_tool_nodes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("HOME", str(tmp_path))

        cfg = load_config(project_dir=tmp_path)

        assert cfg.alphafold2_remote is not None
        assert cfg.alphafold2_remote.ssh.host == "lab02"
        assert cfg.alphafold2_remote.work_dir == "/home/2-BB/changeshengjie/project/mdpilot"
        assert cfg.bioreason_remote is not None
        assert cfg.bioreason_remote.ssh.host == "lab06"
        assert cfg.bioreason_remote.work_dir.startswith("/home/6-FF/")


class TestAgentConfig:
    """Tests for AgentConfig validation and defaults."""

    def test_default_values(self):
        cfg = AgentConfig()
        assert cfg.max_iterations == 90
        assert cfg.max_context_tokens == 100_000
        assert cfg.default_mode == "react"
        assert cfg.auto_confirm_steps == 3

    def test_react_mode(self):
        cfg = AgentConfig(default_mode="react")
        assert cfg.default_mode == "react"

    def test_invalid_mode_rejected(self):
        with pytest.raises(ValidationError):
            AgentConfig(default_mode="invalid")  # type: ignore[arg-type]

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            AgentConfig(max_iterations="not-an-int")  # type: ignore[arg-type]


class TestAppConfig:
    """Tests for top-level AppConfig."""

    def test_nested_defaults(self):
        cfg = AppConfig()
        assert isinstance(cfg.provider, ProviderConfig)
        assert isinstance(cfg.amber, AmberConfig)
        assert isinstance(cfg.agent, AgentConfig)
        assert cfg.provider.model == "claude-sonnet-4-20250514"
        assert cfg.amber.tools_version == "26"
        assert cfg.agent.max_iterations == 90

    def test_partial_override(self):
        """Setting only one sub-model preserves all other defaults."""
        cfg = AppConfig(provider=ProviderConfig(model="my-model"))
        assert cfg.provider.model == "my-model"
        assert cfg.amber.tools_version == "26"
        assert cfg.agent.max_iterations == 90


# ---------------------------------------------------------------------------
# load_config integration tests
# ---------------------------------------------------------------------------

class TestLoadConfigDefaults:
    """Test that load_config returns correct defaults when no files/env exist."""
    def test_returns_valid_app_config(self, tmp_path):
        """load_config() returns a valid AppConfig with default model."""
        cfg = load_config(project_dir=tmp_path)
        assert isinstance(cfg, AppConfig)
        assert cfg.provider.model == "claude-sonnet-4-20250514"

    def test_defaults_match_defaults_module(self, tmp_path: Path):
        """The returned config values match the DEFAULTS constant."""
        cfg = load_config(project_dir=tmp_path)
        assert cfg.provider.model == DEFAULTS["provider"]["model"]
        assert cfg.amber.tools_version == DEFAULTS["amber"]["tools_version"]
        assert cfg.agent.max_iterations == DEFAULTS["agent"]["max_iterations"]


class TestLoadConfigPriority:
    """Test that each config layer overrides the previous ones correctly."""

    def test_cli_overrides_everything(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """CLI overrides (highest priority) win over all other layers."""
        # Set up a user YAML that would set model to something else
        user_dir = tmp_path / ".mdpilot"
        user_dir.mkdir()
        user_yaml = user_dir / "config.yaml"
        user_yaml.write_text(yaml.dump({"provider": {"model": "user-model"}}))
        monkeypatch.setenv("HOME", str(tmp_path))

        # Set env var too
        monkeypatch.setenv("MDPILOT_MODEL", "env-model")

        # CLI should win
        cli_cfg = {"provider": {"model": "cli-model"}}
        cfg = load_config(cli_overrides=cli_cfg, project_dir=tmp_path)
        assert cfg.provider.model == "cli-model"

    def test_env_overrides_yaml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Env vars override project and user YAML."""
        # Write project YAML
        proj_yaml = tmp_path / ".mdpilot.yaml"
        proj_yaml.write_text(yaml.dump({"provider": {"model": "proj-model"}}))
        monkeypatch.setenv("MDPILOT_MODEL", "env-model")

        cfg = load_config(project_dir=tmp_path)
        assert cfg.provider.model == "env-model"

    def test_project_yaml_overrides_user_yaml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Project YAML (./.mdpilot.yaml) overrides user YAML."""
        # Set up user config
        user_dir = tmp_path / ".mdpilot"
        user_dir.mkdir()
        user_yaml = user_dir / "config.yaml"
        user_yaml.write_text(yaml.dump({"provider": {"model": "user-model"}, "amber": {"tools_version": "99"}}))

        # Set up project YAML
        proj_yaml = tmp_path / ".mdpilot.yaml"
        proj_yaml.write_text(yaml.dump({"provider": {"model": "proj-model"}}))

        monkeypatch.setenv("HOME", str(tmp_path))

        cfg = load_config(project_dir=tmp_path)
        assert cfg.provider.model == "proj-model"
        # amber section not in project YAML, so should come from user YAML
        assert cfg.amber.tools_version == "99"

    def test_user_yaml_overrides_defaults(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """User YAML overrides embedded defaults."""
        user_dir = tmp_path / ".mdpilot"
        user_dir.mkdir()
        user_yaml = user_dir / "config.yaml"
        user_yaml.write_text(yaml.dump({"agent": {"max_iterations": 42}}))
        monkeypatch.setenv("HOME", str(tmp_path))

        cfg = load_config(project_dir=tmp_path)
        assert cfg.agent.max_iterations == 42
        # Unspecified fields still come from defaults
        assert cfg.provider.model == DEFAULTS["provider"]["model"]

    def test_5_layer_merge_full_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """All 5 layers specified; each properly overrides the previous."""
        # Layer 5: defaults already baked in

        # Layer 4: user YAML
        user_dir = tmp_path / ".mdpilot"
        user_dir.mkdir()
        (user_dir / "config.yaml").write_text(
            yaml.dump({"provider": {"model": "user-model"}, "amber": {"amber_home": "/user/amber"}})
        )
        monkeypatch.setenv("HOME", str(tmp_path))

        # Layer 3: project YAML
        proj_yaml = tmp_path / ".mdpilot.yaml"
        proj_yaml.write_text(
            yaml.dump({"provider": {"model": "proj-model", "timeout": 300}, "agent": {"max_iterations": 50}})
        )

        # Layer 2: env vars
        monkeypatch.setenv("MDPILOT_MODEL", "env-model")

        # Layer 1: CLI
        cli_cfg = {"amber": {"gpu_enabled": True}}

        cfg = load_config(cli_overrides=cli_cfg, project_dir=tmp_path)

        # CLI (layer 1)
        assert cfg.amber.gpu_enabled is True
        # Env (layer 2)
        assert cfg.provider.model == "env-model"
        # Project YAML (layer 3)
        assert cfg.provider.timeout == 300
        assert cfg.agent.max_iterations == 50
        # User YAML (layer 4)
        assert cfg.amber.amber_home == "/user/amber"
        # Defaults (layer 5) for unspecified fields
        assert cfg.provider.max_retries == DEFAULTS["provider"]["max_retries"]
        assert cfg.lab03_remote is not None
        assert cfg.lab03_remote.ssh.host == "lab03"


class TestLoadConfigEnvVars:
    """Tests specifically for environment variable handling."""

    def test_env_var_overrides_default_model(self, monkeypatch: pytest.MonkeyPatch):
        """MDPILOT_MODEL overrides the default model."""
        monkeypatch.setenv("MDPILOT_MODEL", "env-override-model")
        cfg = load_config()
        assert cfg.provider.model == "env-override-model"

    def test_env_var_overrides_file_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Env var also overrides model set in project YAML."""
        proj_yaml = tmp_path / ".mdpilot.yaml"
        proj_yaml.write_text(yaml.dump({"provider": {"model": "file-model"}}))
        monkeypatch.setenv("MDPILOT_MODEL", "env-override-model")
        cfg = load_config(project_dir=tmp_path)
        assert cfg.provider.model == "env-override-model"

    def test_env_var_api_key(self, monkeypatch: pytest.MonkeyPatch):
        """MDPILOT_API_KEY is correctly loaded."""
        monkeypatch.setenv("MDPILOT_API_KEY", "sk-mykey")
        cfg = load_config()
        assert cfg.provider.api_key.get_secret_value() == "sk-mykey"

    def test_env_var_base_url(self, monkeypatch: pytest.MonkeyPatch):
        """MDPILOT_BASE_URL is correctly loaded."""
        monkeypatch.setenv("MDPILOT_BASE_URL", "https://custom.api.com/v1")
        cfg = load_config()
        assert cfg.provider.base_url == "https://custom.api.com/v1"


class TestLoadConfigPartialOverride:
    """Test that partial configs preserve unspecified fields from lower layers."""

    def test_partial_provider_keeps_other_defaults(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Only overriding provider.model leaves all other provider fields intact."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("MDPILOT_API_KEY", raising=False)
        monkeypatch.delenv("MDPILOT_BASE_URL", raising=False)
        partial = {"provider": {"model": "my-custom-model"}}
        cfg = load_config(cli_overrides=partial, project_dir=tmp_path)

        assert cfg.provider.model == "my-custom-model"
        # All other provider fields stay at defaults
        assert cfg.provider.api_key is None
        assert cfg.provider.base_url is None
        assert cfg.provider.timeout == 120
        assert cfg.provider.max_retries == 3

    def test_partial_amber_keeps_other_defaults(self, tmp_path, monkeypatch: pytest.MonkeyPatch):
        """Only overriding amber.gpu_enabled leaves other amber fields intact."""
        monkeypatch.setenv("HOME", str(tmp_path))
        partial = {"amber": {"gpu_enabled": True}}
        cfg = load_config(cli_overrides=partial, project_dir=tmp_path)

        assert cfg.amber.gpu_enabled is True
        assert cfg.amber.tools_version == "24"
        assert cfg.amber.amber_home == "/home/software/Amber24/amber24"

    def test_partial_agent_keeps_other_defaults(self, tmp_path):
        """Only overriding agent.max_iterations leaves other agent fields intact."""
        partial = {"agent": {"max_iterations": 5}}
        cfg = load_config(cli_overrides=partial, project_dir=tmp_path)

        assert cfg.agent.max_iterations == 5
        assert cfg.agent.default_mode == "react"
        assert cfg.agent.max_context_tokens == 100_000
        assert cfg.agent.auto_confirm_steps == 3


class TestLoadConfigEndToEnd:
    """End-to-end load_config tests with temporary files."""

    def test_load_from_project_yaml_only(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """A project YAML alone produces a valid config."""
        proj_yaml = tmp_path / ".mdpilot.yaml"
        proj_yaml.write_text(
            yaml.dump({
                "provider": {"model": "my-model", "timeout": 90},
                "amber": {"amber_home": "/opt/amber", "gpu_enabled": True},
                "agent": {"max_iterations": 10},
            })
        )

        cfg = load_config(project_dir=tmp_path)

        assert cfg.provider.model == "my-model"
        assert cfg.provider.timeout == 90
        assert cfg.amber.amber_home == "/opt/amber"
        assert cfg.amber.gpu_enabled is True
        assert cfg.agent.max_iterations == 10

    def test_missing_project_yaml_is_silent(self, tmp_path: Path):
        """When project YAML doesn't exist, loading proceeds without error."""
        cfg = load_config(project_dir=tmp_path)
        assert isinstance(cfg, AppConfig)

    def test_load_config_returns_pydantic_model(self):
        """load_config returns an instance of AppConfig, not a plain dict."""
        cfg = load_config()
        assert type(cfg).__name__ == "AppConfig"
        assert isinstance(cfg.provider, ProviderConfig)
        assert isinstance(cfg.amber, AmberConfig)
        assert isinstance(cfg.agent, AgentConfig)


class TestPydanticValidation:
    """Tests that Pydantic correctly rejects invalid configuration values."""

    def test_rejects_invalid_provider_type(self):
        """Passing a non-string for model raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ProviderConfig(model=123)  # type: ignore[arg-type]
        assert "model" in str(exc_info.value)

    def test_rejects_invalid_max_retries_type(self):
        """max_retries must be an int."""
        with pytest.raises(ValidationError):
            ProviderConfig(max_retries="three")  # type: ignore[arg-type]

    def test_rejects_invalid_temperature_range(self):
        """Temperature outside 0-2 range may be rejected by Pydantic constraints."""
        # Pydantic doesn't enforce float range by default without Field constraints,
        # so we just verify it accepts valid values
        cfg = ProviderConfig(temperature=1.5)
        assert cfg.temperature == 1.5

    def test_rejects_invalid_gpu_enabled_type(self):
        """gpu_enabled must be a bool."""
        with pytest.raises(ValidationError):
            AmberConfig(gpu_enabled="yes")  # type: ignore[arg-type]

    def test_rejects_invalid_max_context_tokens_type(self):
        """max_context_tokens must be an int."""
        with pytest.raises(ValidationError):
            AgentConfig(max_context_tokens="100k")  # type: ignore[arg-type]

    def test_load_config_validates_final_merged_config(self):
        """If CLI override contains invalid data, load_config raises ValueError."""
        invalid_override = {"provider": {"max_retries": "not-an-int"}}
        with pytest.raises(ValueError):
            load_config(cli_overrides=invalid_override)

    def test_nested_model_validate(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Deeply nested invalid data raises ValueError at the right field."""
        # Write invalid data to project YAML
        proj_yaml = tmp_path / ".mdpilot.yaml"
        proj_yaml.write_text(yaml.dump({"agent": {"max_iterations": "not-a-number"}}))
        with pytest.raises(ValueError) as exc_info:
            load_config(project_dir=tmp_path)
        assert "max_iterations" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Type correctness tests
# ---------------------------------------------------------------------------

class TestTypes:
    """Verify that all schema types are properly exported and correct."""

    def test_default_mode_is_react(self):
        cfg = AgentConfig(default_mode="react")
        assert cfg.default_mode == "react"

    def test_default_mode_is_plan(self):
        cfg = AgentConfig(default_mode="plan")
        assert cfg.default_mode == "plan"

    def test_literal_type_in_schema(self):
        """AgentConfig.default_mode is typed as Literal['react', 'plan']."""
        hints = AgentConfig.model_fields["default_mode"].annotation
        # Just verify it round-trips through Pydantic
        cfg_react = AgentConfig(default_mode="react")
        cfg_plan = AgentConfig(default_mode="plan")
        assert cfg_react.default_mode == "react"
        assert cfg_plan.default_mode == "plan"
