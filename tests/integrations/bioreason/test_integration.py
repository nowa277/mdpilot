"""Integration tests for BioReason Celery client (mocked SSH)."""

import pytest

from mdpilot.config.defaults import DEFAULT_BIOREASON_REMOTE
from mdpilot.integrations.bioreason.celery_client import BioreasonCeleryClient
from mdpilot.types import ProgressStage


def _make_client():
    """Create a client with poll_interval=0 for fast tests."""
    cfg = dict(DEFAULT_BIOREASON_REMOTE)
    cfg["celery"] = dict(cfg["celery"], poll_interval=0)
    return BioreasonCeleryClient(**cfg)


@pytest.mark.asyncio
async def test_full_workflow(mock_asyncssh):
    """Verify annotate() returns GO terms and fires progress callbacks."""
    client = _make_client()

    progress_updates = []

    async def progress_callback(progress):
        progress_updates.append(progress)

    result = await client.annotate(
        sequence="MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHF",
        organism="Homo sapiens",
        progress_callback=progress_callback,
    )

    assert result["success"] is True
    assert "go_terms" in result
    assert "MF" in result["go_terms"]
    assert "BP" in result["go_terms"]
    assert "CC" in result["go_terms"]

    # At least 4 progress updates: PREPARING (from annotate) + poll stages
    assert len(progress_updates) >= 4

    stages = [p.stage for p in progress_updates]
    assert ProgressStage.PREPARING in stages
    assert ProgressStage.EXECUTING in stages
    assert ProgressStage.PARSING in stages
    assert ProgressStage.COMPLETED in stages


@pytest.mark.asyncio
async def test_connection_management(mock_asyncssh):
    """Verify connect/disconnect lifecycle."""
    client = _make_client()

    await client.connect()
    assert client._conn is not None
    assert not client._conn.is_closed()

    await client.disconnect()
    assert client._conn is None


@pytest.mark.asyncio
async def test_queue_length(mock_asyncssh):
    """Verify get_queue_length() returns int >= 0."""
    client = _make_client()

    queue_length = await client.get_queue_length()

    assert isinstance(queue_length, int)
    assert queue_length >= 0
    await client.disconnect()


@pytest.mark.asyncio
async def test_error_handling():
    """Verify ValueError raised for empty sequence (no SSH needed)."""
    client = _make_client()

    with pytest.raises(ValueError):
        await client.annotate(
            sequence="",
            organism="Homo sapiens",
        )
