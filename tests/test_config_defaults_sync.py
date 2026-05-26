"""Tests to ensure config defaults and schema stay synchronized.

This test suite validates that default values in defaults.py match
the default values in schema.py to prevent configuration mismatches.
"""

from __future__ import annotations

import pytest
from pydantic import Field

from mdpilot.config.defaults import DEFAULTS
from mdpilot.config.schema import AmberConfig, ProviderConfig, AgentConfig


class TestDefaultsSchemaSynchronization:
    """Validate that defaults.py and schema.py have matching default values."""

    def test_tools_version_matches(self) -> None:
        """Ensure tools_version default is the same in both files."""
        # Get default from DEFAULTS dict
        defaults_tools_version = DEFAULTS["amber"]["tools_version"]

        # Get default from schema by inspecting the field
        schema_field = AmberConfig.model_fields["tools_version"]
        schema_default = schema_field.default

        assert defaults_tools_version == schema_default, (
            f"tools_version mismatch: defaults.py has '{defaults_tools_version}' "
            f"but schema.py has '{schema_default}'"
        )

    def test_provider_model_matches(self) -> None:
        """Ensure provider.model default is the same in both files."""
        defaults_model = DEFAULTS["provider"]["model"]
        schema_field = ProviderConfig.model_fields["model"]
        schema_default = schema_field.default

        assert defaults_model == schema_default, (
            f"provider.model mismatch: defaults.py has '{defaults_model}' "
            f"but schema.py has '{schema_default}'"
        )

    def test_agent_max_iterations_matches(self) -> None:
        """Ensure agent.max_iterations default is the same in both files."""
        defaults_max_iter = DEFAULTS["agent"]["max_iterations"]
        schema_field = AgentConfig.model_fields["max_iterations"]
        schema_default = schema_field.default

        assert defaults_max_iter == schema_default, (
            f"agent.max_iterations mismatch: defaults.py has '{defaults_max_iter}' "
            f"but schema.py has '{schema_default}'"
        )

    def test_agent_default_mode_matches(self) -> None:
        """Ensure agent.default_mode default is the same in both files."""
        defaults_mode = DEFAULTS["agent"]["default_mode"]
        schema_field = AgentConfig.model_fields["default_mode"]
        schema_default = schema_field.default

        assert defaults_mode == schema_default, (
            f"agent.default_mode mismatch: defaults.py has '{defaults_mode}' "
            f"but schema.py has '{schema_default}'"
        )

    def test_all_amber_fields_match(self) -> None:
        """Ensure all amber.* fields have matching defaults."""
        amber_defaults = DEFAULTS["amber"]

        for field_name, default_value in amber_defaults.items():
            schema_field = AmberConfig.model_fields[field_name]
            schema_default = schema_field.default

            # Handle None defaults (which are valid)
            if default_value is None and schema_default is None:
                continue

            assert default_value == schema_default, (
                f"amber.{field_name} mismatch: defaults.py has '{default_value}' "
                f"but schema.py has '{schema_default}'"
            )
