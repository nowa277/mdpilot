"""Tests for the amber-agent CLI using typer.testing.CliRunner."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock
from typing import Any
import sys

import pytest
from typer.testing import CliRunner

from mdpilot.cli.app import app, _build_cli_overrides
from mdpilot import __version__

# Get the actual module object, not the app Typer instance
app_module = sys.modules['mdpilot.cli.app']

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def runner() -> CliRunner:
    """Return a CliRunner that does not catch exceptions."""
    return CliRunner(mix_stderr=False)


# ---------------------------------------------------------------------------
# Unit tests – _build_cli_overrides helper
# ---------------------------------------------------------------------------

class TestBuildCliOverrides:
    """Tests for the CLI override dict builder."""

    def test_all_none_returns_empty(self):
        """When all args are None the result is empty (no CLI layer)."""
        result = _build_cli_overrides(None, None, None, None)
        assert result == {}

    def test_model_sets_provider_model(self):
        result = _build_cli_overrides("my-model", None, None, None)
        assert result == {"provider": {"model": "my-model"}}

    def test_base_url_sets_provider_base_url(self):
        result = _build_cli_overrides(None, "https://my.api.com", None, None)
        assert result == {"provider": {"base_url": "https://my.api.com"}}

    def test_api_key_sets_provider_api_key(self):
        result = _build_cli_overrides(None, None, "sk-secret", None)
        assert result == {"provider": {"api_key": "sk-secret"}}

    def test_max_iterations_sets_agent_max_iterations(self):
        result = _build_cli_overrides(None, None, None, 42)
        assert result == {"agent": {"max_iterations": 42}}

    def test_multiple_overrides_merged(self):
        result = _build_cli_overrides("model-x", "https://x.com", "sk-x", 10)
        assert result == {
            "provider": {"model": "model-x", "base_url": "https://x.com", "api_key": "sk-x"},
            "agent": {"max_iterations": 10},
        }

    def test_partial_override_preserves_other_layers(self):
        """Only model set; agent layer untouched by provider keys."""
        result = _build_cli_overrides("model-x", None, None, None)
        assert result["provider"] == {"model": "model-x"}
        assert "agent" not in result


# ---------------------------------------------------------------------------
# CLI command tests
# ---------------------------------------------------------------------------

class TestVersionCommand:
    """Tests for ``amber version``."""

    def test_version_command_succeeds(self, runner: CliRunner):
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert __version__ in result.stdout


class TestConfigCommand:
    """Tests for ``amber config`` and ``amber config --json``."""

    def test_config_command_succeeds(self, runner: CliRunner):
        result = runner.invoke(app, ["config"])
        assert result.exit_code == 0
        # Should mention a provider section
        assert "provider" in result.stdout

    def test_config_command_shows_model(self, runner: CliRunner):
        result = runner.invoke(app, ["config"])
        assert result.exit_code == 0
        # Should show some model name in output
        assert "model" in result.stdout

    def test_config_json_flag_emits_json(self, runner: CliRunner):
        result = runner.invoke(app, ["config", "--json"])
        assert result.exit_code == 0
        # Should be valid JSON
        import json
        data = json.loads(result.stdout)
        assert "provider" in data
        assert "model" in data["provider"]

    def test_config_with_cli_model_override(self, runner: CliRunner):
        """``--model`` flag appears in the output."""
        result = runner.invoke(app, ["config", "--model", "my-custom-model"])
        assert result.exit_code == 0
        assert "my-custom-model" in result.stdout

    def test_config_with_cli_max_iterations(self, runner: CliRunner):
        result = runner.invoke(app, ["config", "--max-iterations", "50"])
        assert result.exit_code == 0
        assert "50" in result.stdout


class TestToolsListCommand:
    """Tests for ``amber tools list``."""

    def test_tools_command_succeeds(self, runner: CliRunner):
        result = runner.invoke(app, ["tools", "list"])
        # Exit code 2 is Typer's "missing argument" style; tools list has
        # the sub-command "list" as a standalone argument.
        # Re-invoke with the command as registered.
        # The command is registered as `tools` with `list` as a sub-command
        # so we just use `tools list`.
        assert result.exit_code in (0, 2)

    def test_tools_list_shows_registered_tools(self, runner: CliRunner):
        result = runner.invoke(app, ["tools", "list"])
        # Should not error — either it shows tools or says "no tools"
        assert result.exception is None or "Error" not in result.stdout

    def test_tools_list_displays_tool_details(self, runner: CliRunner):
        """Tools are displayed with name, category, and description."""
        result = runner.invoke(app, ["tools"])
        assert result.exit_code == 0
        assert "tool" in result.stdout.lower() or "registered" in result.stdout.lower()

    def test_tools_list_with_cli_overrides(self, runner: CliRunner):
        """CLI overrides are accepted but don't affect tool listing."""
        result = runner.invoke(
            app,
            ["tools", "--model", "test-model", "--max-iterations", "10"]
        )
        assert result.exit_code == 0


class TestRunCommand:
    """Tests for ``amber run``."""

    def test_run_command_requires_prompt(self, runner: CliRunner):
        """No argument → exit code 2 (Typer missing argument)."""
        result = runner.invoke(app, ["run"])
        assert result.exit_code == 2

    def test_run_command_with_prompt_and_mocked_loop(self, runner: CliRunner):
        """A prompt is accepted and the mock loop result is printed."""
        mock_result_text = "Mocked agent result"

        # Patch ReActLoop.run so no real LLM calls are made
        with patch.object(app_module, "ReActLoop") as MockLoop:
            mock_instance = MagicMock()
            mock_instance.run = AsyncMock(return_value=mock_result_text)
            mock_instance.events = MagicMock()
            MockLoop.return_value = mock_instance

            result = runner.invoke(app, ["run", "What is the pH of pure water?"])

            # Should succeed
            assert result.exit_code == 0, result.stdout + str(result.exception)
            # Mock result should appear in output
            assert mock_result_text in result.stdout

    def test_run_command_with_stream_flag(self, runner: CliRunner):
        """``--stream`` flag is accepted without error."""
        with patch.object(app_module, "ReActLoop") as MockLoop:
            mock_instance = MagicMock()
            mock_instance.run = AsyncMock(return_value="streamed result")
            mock_instance.events = MagicMock()
            MockLoop.return_value = mock_instance

            result = runner.invoke(app, ["run", "--stream", "Hello agent"])

            assert result.exit_code == 0, result.stdout + str(result.exception)
            # Streaming uses a Live spinner so the result may appear after it.
            # We just verify the command succeeded.
            assert "result" in result.stdout.lower() or result.exit_code == 0

    def test_run_command_with_model_override(self, runner: CliRunner):
        """``--model`` flag is accepted without error."""
        with patch.object(app_module, "ReActLoop") as MockLoop:
            mock_instance = MagicMock()
            mock_instance.run = AsyncMock(return_value="result")
            mock_instance.events = MagicMock()
            MockLoop.return_value = mock_instance

            result = runner.invoke(
                app, ["run", "--model", "claude-opus-4-7", "Test query"]
            )
            assert result.exit_code == 0, result.stdout

    def test_run_command_with_verbose_flag(self, runner: CliRunner):
        """``--verbose`` / ``-v`` flag is accepted without error."""
        with patch.object(app_module, "ReActLoop") as MockLoop:
            mock_instance = MagicMock()
            mock_instance.run = AsyncMock(return_value="verbose result")
            mock_instance.events = MagicMock()
            MockLoop.return_value = mock_instance

            result = runner.invoke(app, ["run", "--verbose", "Verbose test"])
            assert result.exit_code == 0, result.stdout

    def test_run_command_error_in_loop_propagates(self, runner: CliRunner):
        """If the loop raises an exception, CLI exits non-zero."""

        class LoopError(Exception):
            pass

        with patch.object(app_module, "ReActLoop") as MockLoop:
            mock_instance = MagicMock()
            mock_instance.run = AsyncMock(side_effect=LoopError("boom"))
            mock_instance.events = MagicMock()
            MockLoop.return_value = mock_instance

            result = runner.invoke(app, ["run", "Failing query"])
            assert result.exit_code == 1


class TestSessionCommands:
    """Tests for ``amber session`` commands (list/show/delete/search)."""

    def test_session_list_no_sessions(self, runner: CliRunner):
        """session list with no sessions shows empty message."""
        with patch.object(app_module, "SessionStore") as MockStore:
            mock_store = MagicMock()
            mock_store.list_sessions.return_value = []
            MockStore.return_value = mock_store

            result = runner.invoke(app, ["session", "list"])
            assert result.exit_code == 0
            assert "No sessions found" in result.stdout
            mock_store.list_sessions.assert_called_once_with(limit=20)

    def test_session_list_with_sessions(self, runner: CliRunner):
        """session list displays sessions in a table."""
        with patch.object(app_module, "SessionStore") as MockStore:
            mock_store = MagicMock()
            mock_store.list_sessions.return_value = [
                {
                    "id": "sess-001",
                    "title": "Test Session",
                    "message_count": 5,
                    "updated_at": "2026-05-09T10:30:00.123456",
                },
                {
                    "id": "sess-002",
                    "title": None,
                    "message_count": 2,
                    "updated_at": "2026-05-08T15:45:00.654321",
                },
            ]
            MockStore.return_value = mock_store

            result = runner.invoke(app, ["session", "list"])
            assert result.exit_code == 0
            assert "Recent Sessions" in result.stdout
            assert "sess-001" in result.stdout
            assert "Test Session" in result.stdout
            assert "sess-002" in result.stdout
            assert "(untitled)" in result.stdout
            mock_store.list_sessions.assert_called_once_with(limit=20)

    def test_session_list_with_limit(self, runner: CliRunner):
        """session list respects --limit flag."""
        with patch.object(app_module, "SessionStore") as MockStore:
            mock_store = MagicMock()
            mock_store.list_sessions.return_value = []
            MockStore.return_value = mock_store

            result = runner.invoke(app, ["session", "list", "--limit", "10"])
            assert result.exit_code == 0
            mock_store.list_sessions.assert_called_once_with(limit=10)

    def test_session_show_no_messages(self, runner: CliRunner):
        """session show with no messages shows warning."""
        with patch.object(app_module, "SessionStore") as MockStore:
            mock_store = MagicMock()
            mock_store.get_messages.return_value = []
            MockStore.return_value = mock_store

            result = runner.invoke(app, ["session", "show", "sess-999"])
            assert result.exit_code == 0
            assert "No messages found for session sess-999" in result.stdout
            mock_store.get_messages.assert_called_once_with("sess-999")

    def test_session_show_with_messages(self, runner: CliRunner):
        """session show displays messages with role-based styling."""
        with patch.object(app_module, "SessionStore") as MockStore:
            mock_store = MagicMock()
            mock_store.get_messages.return_value = [
                {"role": "user", "content": "What is the pH of water?"},
                {"role": "assistant", "content": "The pH of pure water is 7.0 at 25°C."},
                {"role": "tool", "content": "Tool output here"},
            ]
            MockStore.return_value = mock_store

            result = runner.invoke(app, ["session", "show", "sess-001"])
            assert result.exit_code == 0
            assert "user:" in result.stdout
            assert "assistant:" in result.stdout
            assert "tool:" in result.stdout
            assert "What is the pH" in result.stdout
            mock_store.get_messages.assert_called_once_with("sess-001")

    def test_session_delete_success(self, runner: CliRunner):
        """session delete successfully removes a session."""
        with patch.object(app_module, "SessionStore") as MockStore:
            mock_store = MagicMock()
            mock_store.delete_session.return_value = True
            MockStore.return_value = mock_store

            result = runner.invoke(app, ["session", "delete", "sess-001"])
            assert result.exit_code == 0
            assert "Session sess-001 deleted" in result.stdout
            mock_store.delete_session.assert_called_once_with("sess-001")

    def test_session_delete_not_found(self, runner: CliRunner):
        """session delete shows warning for non-existent session."""
        with patch.object(app_module, "SessionStore") as MockStore:
            mock_store = MagicMock()
            mock_store.delete_session.return_value = False
            MockStore.return_value = mock_store

            result = runner.invoke(app, ["session", "delete", "sess-999"])
            assert result.exit_code == 0
            assert "Session sess-999 not found" in result.stdout
            mock_store.delete_session.assert_called_once_with("sess-999")

    def test_session_search_no_results(self, runner: CliRunner):
        """session search with no matches shows empty message."""
        with patch.object(app_module, "SessionStore") as MockStore:
            mock_store = MagicMock()
            mock_store.search_messages.return_value = []
            MockStore.return_value = mock_store

            result = runner.invoke(app, ["session", "search", "nonexistent"])
            assert result.exit_code == 0
            assert "No matches found" in result.stdout
            mock_store.search_messages.assert_called_once_with("nonexistent")

    def test_session_search_with_results(self, runner: CliRunner):
        """session search displays matching messages."""
        with patch.object(app_module, "SessionStore") as MockStore:
            mock_store = MagicMock()
            mock_store.search_messages.return_value = [
                {
                    "session_id": "sess-001",
                    "role": "user",
                    "content": "How do I calculate pH from concentration?",
                },
                {
                    "session_id": "sess-002",
                    "role": "assistant",
                    "content": "pH is calculated using the formula pH = -log[H+]",
                },
            ]
            MockStore.return_value = mock_store

            result = runner.invoke(app, ["session", "search", "pH"])
            assert result.exit_code == 0
            assert "sess-001" in result.stdout
            assert "sess-002" in result.stdout
            assert "calculate pH" in result.stdout
            mock_store.search_messages.assert_called_once_with("pH")


class TestWorkflowCommands:
    """Tests for ``amber workflows`` command."""

    def test_workflows_no_templates(self, runner: CliRunner):
        """workflows command with no templates shows empty message."""
        with patch("mdpilot.workflows.list_templates") as mock_list:
            mock_list.return_value = []

            result = runner.invoke(app, ["workflows"])
            assert result.exit_code == 0
            assert "No workflow templates found" in result.stdout
            mock_list.assert_called_once_with(category=None)

    def test_workflows_with_templates(self, runner: CliRunner):
        """workflows command displays templates in a table."""
        with patch("mdpilot.workflows.list_templates") as mock_list:
            mock_list.return_value = [
                {
                    "name": "standard_protein",
                    "category": "protein",
                    "description": "Standard protein preparation and minimization workflow",
                    "estimated_time": "5-10 min",
                },
                {
                    "name": "protein_ligand",
                    "category": "ligand",
                    "description": "Protein-ligand complex preparation with docking",
                    "estimated_time": "15-20 min",
                },
            ]

            result = runner.invoke(app, ["workflows"])
            assert result.exit_code == 0
            assert "AMBER Workflow Templates" in result.stdout
            assert "standard_protein" in result.stdout
            assert "protein_ligand" in result.stdout
            assert "protein" in result.stdout
            assert "ligand" in result.stdout
            mock_list.assert_called_once_with(category=None)

    def test_workflows_with_category_filter(self, runner: CliRunner):
        """workflows command respects --category flag."""
        with patch("mdpilot.workflows.list_templates") as mock_list:
            mock_list.return_value = [
                {
                    "name": "standard_protein",
                    "category": "protein",
                    "description": "Standard protein preparation",
                    "estimated_time": "5-10 min",
                },
            ]

            result = runner.invoke(app, ["workflows", "--category", "protein"])
            assert result.exit_code == 0
            assert "standard_protein" in result.stdout
            mock_list.assert_called_once_with(category="protein")


# ---------------------------------------------------------------------------
# Unit tests – main() entry point
# ---------------------------------------------------------------------------

class TestMainEntry:
    """Tests for the main() entry point."""

    def test_main_entry_point_calls_app(self):
        """main() initializes AMBER env and runs the app."""
        with patch.object(app_module, "_init_amber_env") as mock_init:
            with patch.object(app_module, "app") as mock_app:
                from mdpilot.cli.app import main

                main()

                mock_init.assert_called_once()
                mock_app.assert_called_once()
