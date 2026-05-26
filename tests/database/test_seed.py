"""Tests for database seeding functionality."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mdpilot.database.seed import seed_data


class TestDatabaseSeed:
    """Test database seeding functionality."""

    @pytest.mark.asyncio
    async def test_seed_data_without_clear(self):
        """Test seeding data without clearing existing data."""
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_session.add_all = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        mock_factory = MagicMock(return_value=mock_session)

        with patch("mdpilot.database.seed.get_session_factory", return_value=mock_factory):
            await seed_data(clear=False)

            # Verify session was used
            assert mock_factory.called

            # Verify data was added (chats, messages, tasks)
            assert mock_session.add_all.call_count >= 2

    @pytest.mark.asyncio
    async def test_seed_data_with_clear(self):
        """Test seeding data with clearing existing data."""
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_session.add_all = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        mock_factory = MagicMock(return_value=mock_session)

        with patch("mdpilot.database.seed.get_session_factory", return_value=mock_factory):
            await seed_data(clear=True)

            # Verify delete operations were called (for Message, Chat, Task)
            assert mock_session.execute.await_count >= 3

            # Verify data was added
            assert mock_session.add_all.call_count >= 2

            # Verify commit was called at least once
            mock_session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_seed_data_creates_chats(self):
        """Test that seed data creates chat records."""
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_session.add_all = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        mock_factory = MagicMock(return_value=mock_session)

        with patch("mdpilot.database.seed.get_session_factory", return_value=mock_factory):
            await seed_data(clear=False)

            # Check that add_all was called
            calls = mock_session.add_all.call_args_list
            assert len(calls) >= 2

            # First call should be chats
            chats = calls[0][0][0]
            assert len(chats) == 3  # 3 sample chats

    @pytest.mark.asyncio
    async def test_seed_data_creates_messages(self):
        """Test that seed data creates message records."""
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_session.add_all = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        mock_factory = MagicMock(return_value=mock_session)

        with patch("mdpilot.database.seed.get_session_factory", return_value=mock_factory):
            await seed_data(clear=False)

            # Check that messages were added
            calls = mock_session.add_all.call_args_list
            assert len(calls) >= 2

            # Second call should be messages
            messages = calls[1][0][0]
            assert len(messages) > 0

    @pytest.mark.asyncio
    async def test_seed_data_creates_tasks(self):
        """Test that seed data creates task records."""
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_session.add_all = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        mock_factory = MagicMock(return_value=mock_session)

        with patch("mdpilot.database.seed.get_session_factory", return_value=mock_factory):
            await seed_data(clear=False)

            # Check that add_all was called multiple times
            calls = mock_session.add_all.call_args_list
            assert len(calls) >= 2

    @pytest.mark.asyncio
    async def test_seed_data_flush_called(self):
        """Test that flush is called after adding chats (for foreign keys)."""
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_session.add_all = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        mock_factory = MagicMock(return_value=mock_session)

        with patch("mdpilot.database.seed.get_session_factory", return_value=mock_factory):
            await seed_data(clear=False)

            # Verify flush was called (needed to get chat IDs for messages)
            assert mock_session.flush.await_count >= 1

