"""Tests for BioreasonClient"""

import pytest
from src.mdpilot.integrations.bioreason_client import BioreasonClient
from src.mdpilot.types import TaskProgress, ProgressStage


@pytest.mark.asyncio
async def test_bioreason_client_mock_mode():
    """Test BioreasonClient in mock mode"""
    client = BioreasonClient(use_remote=False)
    
    result = await client.annotate(
        sequence="MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLKSTVEAIWAGIKATEAAVSEEFGLAPFLPDQIHFVHSQELLSRYPDLDAKGRERAIAKDLGAVFLVGIGGKLSDGHRHDVRAPDYDDWSTPSELGHAGLNGDILVWNPVLEDAFELSSMGIRVDADTLKHQLALTGDEDRLELEWHQALLRGEMPQTIGGGIGQSRLTMLLLQLPHIGQVQAGVWPAAVRESVPSLL",
        organism="Homo sapiens",
    )
    
    assert result["success"] is True
    assert "go_terms" in result
    assert "MF" in result["go_terms"]
    assert "BP" in result["go_terms"]
    assert "CC" in result["go_terms"]
    assert result["metadata"]["mode"] == "mock"


@pytest.mark.asyncio
async def test_bioreason_client_health_check_mock():
    """Test health check in mock mode"""
    client = BioreasonClient(use_remote=False)
    
    health = await client.health_check()
    
    assert health["status"] == "mock"
    assert health["mode"] == "mock"


@pytest.mark.asyncio
async def test_bioreason_client_empty_sequence():
    """Test that empty sequence raises ValueError"""
    client = BioreasonClient(use_remote=False)
    
    with pytest.raises(ValueError, match="Sequence cannot be empty"):
        await client.annotate(sequence="")


@pytest.mark.asyncio
async def test_bioreason_client_progress_callback():
    """Test progress callback in mock mode"""
    client = BioreasonClient(use_remote=False)
    
    progress_updates = []
    
    def callback(progress: TaskProgress):
        progress_updates.append(progress)
    
    result = await client.annotate(
        sequence="MKTAYIAKQRQISFVK",
        progress_callback=callback,
    )
    
    assert result["success"] is True
    # Mock mode doesn't call progress callback
    assert len(progress_updates) == 0
