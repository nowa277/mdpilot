"""Configuration loader implementing 5-layer config merge.

Priority (high → low):
    1. CLI overrides
    2. Environment variables (MDPILOT_ prefix)
    3. Project-level YAML  (./.mdpilot.yaml)
    4. User-level YAML     (~/.mdpilot/config.yaml)
    5. Embedded defaults

Deep merge is performed: for each leaf field, the higher-priority value wins.
"""

from __future__ import annotations

import logging
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .defaults import DEFAULTS
from .schema import AppConfig

logger = logging.getLogger(__name__)


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base*, returning a new dict.

    - Dict values are merged recursively.
    - Non-dict values in *override* replace those in *base*.
    """
    merged = deepcopy(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _load_yaml(path: Path) -> dict:
    """Load a YAML file and return its contents as a dict.

    Returns an empty dict if the file does not exist or is unreadable.
    Logs warnings for YAML parsing errors or I/O errors.
    """
    if not path.exists():
        return {}

    try:
        with open(path, "r") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as e:
        logger.warning(f"Invalid YAML in {path}: {e}. Using defaults for this layer.")
        return {}
    except OSError as e:
        logger.warning(f"Cannot read {path}: {e}. Using defaults for this layer.")
        return {}

    if not isinstance(data, dict):
        logger.warning(f"Config file {path} does not contain a dict (got {type(data).__name__}). Ignoring.")
        return {}

    return data


def _env_overrides() -> dict:
    """Read MDPILOT_* environment variables and return an override dict.

    Recognised env vars:
        MDPILOT_MODEL      → provider.model
        MDPILOT_API_KEY    → provider.api_key
        MDPILOT_BASE_URL   → provider.base_url
    """
    env: dict[str, Any] = {"provider": {}}
    mapping = {
        "MDPILOT_MODEL": "model",
        "MDPILOT_API_KEY": "api_key",
        "MDPILOT_BASE_URL": "base_url",
    }
    for env_key, field in mapping.items():
        value = os.environ.get(env_key)
        if value is not None and value != "":
            env["provider"][field] = value
    return env


def load_config(
    cli_overrides: dict | None = None,
    project_dir: Path | None = None,
) -> AppConfig:
    """Load and merge configuration from all layers.

    Parameters
    ----------
    cli_overrides : dict | None
        Highest-priority overrides (typically from CLI flags).
    project_dir : Path | None
        Directory containing the project-level config file
        (``.mdpilot.yaml``).  Defaults to the current working directory.

    Returns
    -------
    AppConfig
        Validated configuration object.

    Raises
    ------
    ValueError
        If the merged configuration fails validation with a user-friendly error message.
    """
    # Layer 5: embedded defaults
    merged: dict = deepcopy(DEFAULTS)
    logger.debug("Loaded embedded defaults")

    # Layer 4: user-level YAML (~/.mdpilot/config.yaml)
    user_config_path = Path.home() / ".mdpilot" / "config.yaml"
    user_cfg = _load_yaml(user_config_path)
    if user_cfg:
        merged = _deep_merge(merged, user_cfg)
        logger.debug(f"Merged user config from {user_config_path}")

    # Layer 3: project-level YAML
    proj_cfg = {}
    if project_dir is not False:
        _project_dir = project_dir or Path.cwd()
        project_config_path = _project_dir / ".mdpilot.yaml"
        proj_cfg = _load_yaml(project_config_path)
        if proj_cfg:
            merged = _deep_merge(merged, proj_cfg)
            logger.debug(f"Merged project config from {project_config_path}")

    # Layer 2: environment variables
    env_cfg = _env_overrides()
    if env_cfg["provider"]:
        merged = _deep_merge(merged, env_cfg)
        logger.debug("Merged environment variable overrides")

    # Layer 1: CLI overrides
    if cli_overrides:
        merged = _deep_merge(merged, cli_overrides)
        logger.debug("Merged CLI overrides")

    # Validate the merged configuration
    try:
        config = AppConfig.model_validate(merged)
        logger.info("Configuration loaded successfully")
        return config
    except ValidationError as e:
        # Format validation errors in a user-friendly way
        error_lines = ["Configuration validation failed:"]
        for error in e.errors():
            field_path = " → ".join(str(loc) for loc in error["loc"])
            error_lines.append(f"  • {field_path}: {error['msg']}")

        error_message = "\n".join(error_lines)
        logger.error(error_message)
        raise ValueError(error_message) from e
