"""Comprehensive test for 5-layer config priority system.

This test validates the complete priority chain:
    1. CLI arguments (highest)
    2. Environment variables
    3. Project YAML (.mdpilot.yaml)
    4. User YAML (~/.mdpilot/config.yaml)
    5. Defaults (lowest)

Each layer should override lower layers while preserving unspecified fields.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from mdpilot.config import load_config
from mdpilot.config.defaults import DEFAULTS


class TestConfigPriority:
    """Test 5-layer config priority with all layers active."""

    def test_config_priority_full_stack(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Test 5-layer config priority with all layers providing values.

        Setup:
            - Layer 5 (defaults): model="claude-sonnet-4-20250514"
            - Layer 4 (user YAML): model="user-model", timeout=200
            - Layer 3 (project YAML): model="project-model", max_retries=5
            - Layer 2 (env var): model="env-model"
            - Layer 1 (CLI): model="cli-model", temperature=0.5

        Expected result:
            - model="cli-model" (CLI wins)
            - temperature=0.5 (CLI only)
            - max_retries=5 (project YAML, not overridden)
            - timeout=200 (user YAML, not overridden)
            - max_tokens=8192 (default, not overridden)
        """
        # Layer 4: User YAML
        user_dir = tmp_path / ".mdpilot"
        user_dir.mkdir()
        user_yaml = user_dir / "config.yaml"
        user_yaml.write_text(
            yaml.dump({
                "provider": {
                    "model": "user-model",
                    "timeout": 200,
                },
                "amber": {
                    "amber_home": "/user/amber",
                },
            })
        )
        monkeypatch.setenv("HOME", str(tmp_path))

        # Layer 3: Project YAML
        project_yaml = tmp_path / ".mdpilot.yaml"
        project_yaml.write_text(
            yaml.dump({
                "provider": {
                    "model": "project-model",
                    "max_retries": 5,
                },
                "agent": {
                    "max_iterations": 50,
                },
            })
        )

        # Layer 2: Environment variables
        monkeypatch.setenv("MDPILOT_MODEL", "env-model")
        monkeypatch.setenv("MDPILOT_API_KEY", "sk-env-key")

        # Layer 1: CLI overrides
        cli_overrides = {
            "provider": {
                "model": "cli-model",
                "temperature": 0.5,
            },
            "amber": {
                "gpu_enabled": True,
            },
        }

        # Load config
        cfg = load_config(cli_overrides=cli_overrides, project_dir=tmp_path)

        # Verify priority order
        # Layer 1 (CLI) - highest priority
        assert cfg.provider.model == "cli-model"
        assert cfg.provider.temperature == 0.5
        assert cfg.amber.gpu_enabled is True

        # Layer 2 (env) - overrides layers 3-5
        assert cfg.provider.api_key.get_secret_value() == "sk-env-key"

        # Layer 3 (project YAML) - overrides layers 4-5
        assert cfg.provider.max_retries == 5
        assert cfg.agent.max_iterations == 50

        # Layer 4 (user YAML) - overrides layer 5
        assert cfg.provider.timeout == 200
        assert cfg.amber.amber_home == "/user/amber"

        # Layer 5 (defaults) - lowest priority, used when not overridden
        assert cfg.provider.max_tokens == DEFAULTS["provider"]["max_tokens"]
        assert cfg.agent.max_context_tokens == DEFAULTS["agent"]["max_context_tokens"]

    def test_config_priority_partial_layers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Test priority with only some layers active.

        Setup:
            - Layer 5 (defaults): always present
            - Layer 4 (user YAML): NOT present
            - Layer 3 (project YAML): model="project-model"
            - Layer 2 (env var): NOT present
            - Layer 1 (CLI): temperature=0.7

        Expected:
            - temperature=0.7 (CLI)
            - model="project-model" (project YAML)
            - All other fields from defaults
        """
        # Layer 3: Project YAML only
        project_yaml = tmp_path / ".mdpilot.yaml"
        project_yaml.write_text(
            yaml.dump({
                "provider": {
                    "model": "project-model",
                },
            })
        )

        # Layer 1: CLI overrides
        cli_overrides = {
            "provider": {
                "temperature": 0.7,
            },
        }

        cfg = load_config(cli_overrides=cli_overrides, project_dir=tmp_path)

        # CLI wins
        assert cfg.provider.temperature == 0.7

        # Project YAML wins over defaults
        assert cfg.provider.model == "project-model"

        # Defaults for everything else
        assert cfg.provider.timeout == DEFAULTS["provider"]["timeout"]
        assert cfg.provider.max_retries == DEFAULTS["provider"]["max_retries"]

    def test_config_priority_env_over_yaml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that environment variables override both user and project YAML."""
        # Layer 4: User YAML
        user_dir = tmp_path / ".mdpilot"
        user_dir.mkdir()
        (user_dir / "config.yaml").write_text(
            yaml.dump({"provider": {"model": "user-model", "api_key": "user-key"}})
        )
        monkeypatch.setenv("HOME", str(tmp_path))

        # Layer 3: Project YAML
        (tmp_path / ".mdpilot.yaml").write_text(
            yaml.dump({"provider": {"model": "project-model", "api_key": "project-key"}})
        )

        # Layer 2: Env var should win
        monkeypatch.setenv("MDPILOT_MODEL", "env-model")
        monkeypatch.setenv("MDPILOT_API_KEY", "env-key")

        cfg = load_config(project_dir=tmp_path)

        # Env vars win over both YAMLs
        assert cfg.provider.model == "env-model"
        assert cfg.provider.api_key.get_secret_value() == "env-key"

    def test_config_priority_cli_over_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that CLI overrides environment variables."""
        monkeypatch.setenv("MDPILOT_MODEL", "env-model")
        monkeypatch.setenv("MDPILOT_API_KEY", "env-key")
        monkeypatch.setenv("MDPILOT_BASE_URL", "https://env.api.com")

        cli_overrides = {
            "provider": {
                "model": "cli-model",
                "base_url": "https://cli.api.com",
            }
        }

        cfg = load_config(cli_overrides=cli_overrides, project_dir=tmp_path)

        # CLI wins over env
        assert cfg.provider.model == "cli-model"
        assert cfg.provider.base_url == "https://cli.api.com"

        # Env var not overridden by CLI still applies
        assert cfg.provider.api_key.get_secret_value() == "env-key"

    def test_config_priority_deep_merge_preserves_siblings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that deep merge preserves sibling fields at each level.

        When project YAML sets provider.model, it should NOT wipe out
        provider.timeout from user YAML or provider.max_retries from defaults.
        """
        # User YAML sets timeout
        user_dir = tmp_path / ".mdpilot"
        user_dir.mkdir()
        (user_dir / "config.yaml").write_text(
            yaml.dump({"provider": {"timeout": 300}})
        )
        monkeypatch.setenv("HOME", str(tmp_path))

        # Project YAML sets model
        (tmp_path / ".mdpilot.yaml").write_text(
            yaml.dump({"provider": {"model": "project-model"}})
        )

        cfg = load_config(project_dir=tmp_path)

        # All three should coexist
        assert cfg.provider.model == "project-model"  # from project
        assert cfg.provider.timeout == 300  # from user
        assert cfg.provider.max_retries == DEFAULTS["provider"]["max_retries"]  # from defaults

    def test_config_priority_cross_section_independence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that different config sections (provider, amber, agent) merge independently.

        Setting provider.model in CLI should not affect amber.gpu_enabled from project YAML.
        """
        # Project YAML sets amber and agent sections
        (tmp_path / ".mdpilot.yaml").write_text(
            yaml.dump({
                "amber": {"gpu_enabled": True, "tools_version": "24"},
                "agent": {"max_iterations": 100},
            })
        )

        # CLI only sets provider section
        cli_overrides = {
            "provider": {"model": "cli-model", "temperature": 0.8}
        }

        cfg = load_config(cli_overrides=cli_overrides, project_dir=tmp_path)

        # CLI provider settings
        assert cfg.provider.model == "cli-model"
        assert cfg.provider.temperature == 0.8

        # Project YAML amber and agent settings preserved
        assert cfg.amber.gpu_enabled is True
        assert cfg.amber.tools_version == "24"
        assert cfg.agent.max_iterations == 100

        # Defaults for unspecified fields
        assert cfg.provider.timeout == DEFAULTS["provider"]["timeout"]


class TestConfigPriorityEdgeCases:
    """Test edge cases in config priority system."""

    def test_empty_yaml_files_ignored(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Empty YAML files should not affect config loading."""
        user_dir = tmp_path / ".mdpilot"
        user_dir.mkdir()
        (user_dir / "config.yaml").write_text("")
        monkeypatch.setenv("HOME", str(tmp_path))

        (tmp_path / ".mdpilot.yaml").write_text("")

        cfg = load_config(project_dir=tmp_path)

        # Should get all defaults
        assert cfg.provider.model == DEFAULTS["provider"]["model"]
        assert cfg.amber.tools_version == DEFAULTS["amber"]["tools_version"]

    def test_malformed_yaml_ignored(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Malformed YAML files should be silently ignored."""
        (tmp_path / ".mdpilot.yaml").write_text("invalid: yaml: [[[")

        cfg = load_config(project_dir=tmp_path)

        # Should still load with defaults
        assert cfg.provider.model == DEFAULTS["provider"]["model"]

    def test_empty_env_vars_ignored(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Empty string env vars should be treated as unset."""
        monkeypatch.setenv("MDPILOT_MODEL", "")
        monkeypatch.setenv("MDPILOT_API_KEY", "")

        cfg = load_config(project_dir=tmp_path)

        # Should use defaults, not empty strings
        assert cfg.provider.model == DEFAULTS["provider"]["model"]
        assert cfg.provider.api_key is None

    def test_none_cli_overrides(self, tmp_path: Path):
        """Passing None for cli_overrides should work."""
        cfg = load_config(cli_overrides=None, project_dir=tmp_path)
        assert cfg.provider.model == DEFAULTS["provider"]["model"]

    def test_empty_dict_cli_overrides(self, tmp_path: Path):
        """Passing empty dict for cli_overrides should work."""
        cfg = load_config(cli_overrides={}, project_dir=tmp_path)
        assert cfg.provider.model == DEFAULTS["provider"]["model"]


class TestConfigPriorityDocumentation:
    """Test that config priority matches documented behavior."""

    def test_priority_order_matches_docstring(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Verify priority order matches loader.py docstring.

        Docstring states:
            1. CLI overrides
            2. Environment variables (MDPILOT_ prefix)
            3. Project-level YAML  (./.mdpilot.yaml)
            4. User-level YAML     (~/.mdpilot/config.yaml)
            5. Embedded defaults
        """
        # Set up all 5 layers with different values for the same field
        user_dir = tmp_path / ".mdpilot"
        user_dir.mkdir()
        (user_dir / "config.yaml").write_text(
            yaml.dump({"provider": {"model": "layer-4-user"}})
        )
        monkeypatch.setenv("HOME", str(tmp_path))

        (tmp_path / ".mdpilot.yaml").write_text(
            yaml.dump({"provider": {"model": "layer-3-project"}})
        )

        monkeypatch.setenv("MDPILOT_MODEL", "layer-2-env")

        cli_overrides = {"provider": {"model": "layer-1-cli"}}

        cfg = load_config(cli_overrides=cli_overrides, project_dir=tmp_path)

        # Layer 1 (CLI) should win
        assert cfg.provider.model == "layer-1-cli"

    def test_priority_without_cli(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Without CLI, env should win."""
        user_dir = tmp_path / ".mdpilot"
        user_dir.mkdir()
        (user_dir / "config.yaml").write_text(
            yaml.dump({"provider": {"model": "layer-4-user"}})
        )
        monkeypatch.setenv("HOME", str(tmp_path))

        (tmp_path / ".mdpilot.yaml").write_text(
            yaml.dump({"provider": {"model": "layer-3-project"}})
        )

        monkeypatch.setenv("MDPILOT_MODEL", "layer-2-env")

        cfg = load_config(project_dir=tmp_path)

        # Layer 2 (env) should win
        assert cfg.provider.model == "layer-2-env"

    def test_priority_without_cli_and_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Without CLI and env, project YAML should win."""
        user_dir = tmp_path / ".mdpilot"
        user_dir.mkdir()
        (user_dir / "config.yaml").write_text(
            yaml.dump({"provider": {"model": "layer-4-user"}})
        )
        monkeypatch.setenv("HOME", str(tmp_path))

        (tmp_path / ".mdpilot.yaml").write_text(
            yaml.dump({"provider": {"model": "layer-3-project"}})
        )

        cfg = load_config(project_dir=tmp_path)

        # Layer 3 (project) should win
        assert cfg.provider.model == "layer-3-project"

    def test_priority_user_yaml_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """With only user YAML, it should override defaults."""
        user_dir = tmp_path / ".mdpilot"
        user_dir.mkdir()
        (user_dir / "config.yaml").write_text(
            yaml.dump({"provider": {"model": "layer-4-user"}})
        )
        monkeypatch.setenv("HOME", str(tmp_path))

        cfg = load_config(project_dir=tmp_path)

        # Layer 4 (user) should win over layer 5 (defaults)
        assert cfg.provider.model == "layer-4-user"

    def test_priority_defaults_only(self, tmp_path: Path):
        """With no overrides, defaults should be used."""
        cfg = load_config(project_dir=tmp_path)

        # Layer 5 (defaults)
        assert cfg.provider.model == DEFAULTS["provider"]["model"]
