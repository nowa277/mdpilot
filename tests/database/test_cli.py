"""Tests for database CLI commands."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner
from unittest.mock import AsyncMock, MagicMock, patch

from mdpilot.cli.app import app


@pytest.fixture
def cli_runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_config():
    """Mock application configuration."""
    with patch("mdpilot.database.cli.load_config") as mock:
        config = MagicMock()
        config.database.url = "postgresql+asyncpg://test:test@localhost/test"
        mock.return_value = config
        yield mock


@pytest.fixture
def mock_alembic_config():
    """Mock Alembic configuration."""
    with patch("mdpilot.database.cli.Config") as mock:
        config = MagicMock()
        mock.return_value = config
        yield mock


class TestDatabaseCLI:
    """Test database CLI commands."""

    def test_db_check_success(self, cli_runner, mock_config):
        """Test database check command with successful connection."""
        with patch("mdpilot.database.cli.init_db"), \
             patch("mdpilot.database.cli.get_engine") as mock_engine, \
             patch("mdpilot.database.cli.dispose_engine"), \
             patch("mdpilot.database.cli.get_alembic_config"), \
             patch("mdpilot.database.cli.command"):

            # Mock engine and pool
            mock_pool = MagicMock()
            mock_pool.size.return_value = 5
            mock_pool.checkedin.return_value = 4
            mock_pool.checkedout.return_value = 1
            mock_pool.overflow.return_value = 0

            engine = MagicMock()
            engine.pool = mock_pool

            # Mock async connection
            mock_conn = MagicMock()
            mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_conn.__aexit__ = AsyncMock()
            mock_conn.execute = AsyncMock()

            engine.connect.return_value = mock_conn
            mock_engine.return_value = engine

            result = cli_runner.invoke(app, ["db", "check"])

            assert result.exit_code == 0
            assert "Checking database" in result.stdout

    def test_db_init(self, cli_runner, mock_config):
        """Test database initialization command."""
        with patch("mdpilot.database.cli.init_db"), \
             patch("mdpilot.database.cli.get_engine"), \
             patch("mdpilot.database.cli.dispose_engine"), \
             patch("mdpilot.database.cli.asyncio.run"):

            result = cli_runner.invoke(app, ["db", "init"])

            assert result.exit_code == 0
            assert "Initializing database" in result.stdout
            assert "initialized successfully" in result.stdout

    def test_db_upgrade(self, cli_runner, mock_config, mock_alembic_config):
        """Test database upgrade command."""
        with patch("mdpilot.database.cli.command") as mock_command, \
             patch("mdpilot.database.cli.get_alembic_config") as mock_get_config:

            mock_get_config.return_value = MagicMock()

            result = cli_runner.invoke(app, ["db", "upgrade"])

            assert result.exit_code == 0
            assert "Upgrading database" in result.stdout
            assert mock_command.upgrade.called

    def test_db_upgrade_specific_revision(self, cli_runner, mock_config, mock_alembic_config):
        """Test database upgrade to specific revision."""
        with patch("mdpilot.database.cli.command") as mock_command, \
             patch("mdpilot.database.cli.get_alembic_config") as mock_get_config:

            mock_get_config.return_value = MagicMock()

            result = cli_runner.invoke(app, ["db", "upgrade", "abc123"])

            assert result.exit_code == 0
            assert "Upgrading database to abc123" in result.stdout
            mock_command.upgrade.assert_called_once()

    def test_db_downgrade_with_confirmation(self, cli_runner, mock_config, mock_alembic_config):
        """Test database downgrade with user confirmation."""
        with patch("mdpilot.database.cli.command") as mock_command, \
             patch("mdpilot.database.cli.get_alembic_config") as mock_get_config:

            mock_get_config.return_value = MagicMock()

            # Simulate user confirming
            result = cli_runner.invoke(app, ["db", "downgrade"], input="y\n")

            assert result.exit_code == 0
            assert "Downgrading database" in result.stdout
            assert mock_command.downgrade.called

    def test_db_downgrade_cancelled(self, cli_runner, mock_config):
        """Test database downgrade cancelled by user."""
        with patch("mdpilot.database.cli.command") as mock_command:

            # Simulate user cancelling
            result = cli_runner.invoke(app, ["db", "downgrade"], input="n\n")

            assert result.exit_code == 0
            assert "Cancelled" in result.stdout
            assert not mock_command.downgrade.called

    def test_db_migrate(self, cli_runner, mock_config, mock_alembic_config):
        """Test creating a new migration."""
        with patch("mdpilot.database.cli.command") as mock_command, \
             patch("mdpilot.database.cli.get_alembic_config") as mock_get_config:

            mock_get_config.return_value = MagicMock()

            result = cli_runner.invoke(app, ["db", "migrate", "add new column"])

            assert result.exit_code == 0
            assert "Creating migration" in result.stdout
            mock_command.revision.assert_called_once()

    def test_db_current(self, cli_runner, mock_config, mock_alembic_config):
        """Test showing current revision."""
        with patch("mdpilot.database.cli.command") as mock_command, \
             patch("mdpilot.database.cli.get_alembic_config") as mock_get_config:

            mock_get_config.return_value = MagicMock()

            result = cli_runner.invoke(app, ["db", "current"])

            assert result.exit_code == 0
            assert mock_command.current.called

    def test_db_history(self, cli_runner, mock_config, mock_alembic_config):
        """Test showing migration history."""
        with patch("mdpilot.database.cli.command") as mock_command, \
             patch("mdpilot.database.cli.get_alembic_config") as mock_get_config:

            mock_get_config.return_value = MagicMock()

            result = cli_runner.invoke(app, ["db", "history"])

            assert result.exit_code == 0
            assert mock_command.history.called

    def test_db_seed(self, cli_runner, mock_config):
        """Test seeding database."""
        with patch("mdpilot.database.cli.init_db"), \
             patch("mdpilot.database.cli.asyncio.run") as mock_run:

            result = cli_runner.invoke(app, ["db", "seed"])

            assert result.exit_code == 0
            assert "Seeding database" in result.stdout
            assert mock_run.called

    def test_db_seed_with_clear(self, cli_runner, mock_config):
        """Test seeding database with clear flag."""
        with patch("mdpilot.database.cli.init_db"), \
             patch("mdpilot.database.cli.asyncio.run") as mock_run:

            # Simulate user confirming
            result = cli_runner.invoke(app, ["db", "seed", "--clear"], input="y\n")

            assert result.exit_code == 0
            assert "Seeding database" in result.stdout
            assert mock_run.called

    def test_db_reset_with_confirmation(self, cli_runner, mock_config, mock_alembic_config):
        """Test database reset with double confirmation."""
        with patch("mdpilot.database.cli.init_db"), \
             patch("mdpilot.database.cli.get_engine"), \
             patch("mdpilot.database.cli.dispose_engine"), \
             patch("mdpilot.database.cli.asyncio.run"), \
             patch("mdpilot.database.cli.command") as mock_command, \
             patch("mdpilot.database.cli.get_alembic_config") as mock_get_config:

            mock_get_config.return_value = MagicMock()

            # Simulate user confirming twice
            result = cli_runner.invoke(app, ["db", "reset"], input="y\ny\n")

            assert result.exit_code == 0
            assert "WARNING" in result.stdout
            assert mock_command.stamp.called

    def test_db_reset_cancelled(self, cli_runner, mock_config):
        """Test database reset cancelled by user."""
        with patch("mdpilot.database.cli.command") as mock_command:

            # Simulate user cancelling
            result = cli_runner.invoke(app, ["db", "reset"], input="n\n")

            assert result.exit_code == 0
            assert "Cancelled" in result.stdout
            assert not mock_command.stamp.called

    def test_db_help(self, cli_runner):
        """Test database help command."""
        result = cli_runner.invoke(app, ["db", "--help"])

        assert result.exit_code == 0
        assert "Database management commands" in result.stdout
        assert "init" in result.stdout
        assert "upgrade" in result.stdout
        assert "downgrade" in result.stdout
        assert "migrate" in result.stdout
        assert "seed" in result.stdout
        assert "reset" in result.stdout
        assert "check" in result.stdout
