"""AlphaFold2 integration tests"""

import pytest
from src.mdpilot.integrations.alphafold2.celery_client import AlphaFold2CeleryClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_alphafold2_connection():
    """Test AlphaFold2 SSH connection"""
    config = {
        "ssh": {"host": "lab02", "username": "zhao", "key_path": "~/.ssh/id_rsa"},
        "celery": {
            "broker_url": "redis://localhost:6379/2",
            "backend_url": "redis://localhost:6379/3",
            "task_timeout": 14400,
            "poll_interval": 5
        },
        "work_dir": "/home/2-BB/changeshengjie/project/mdpilot",
        "conda_env": "af2_py310"
    }
    
    client = AlphaFold2CeleryClient(**config)
    await client.connect()
    
    try:
        assert client._conn is not None
    finally:
        await client.disconnect()


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_alphafold2_short_sequence():
    """Test AlphaFold2 prediction with short sequence (SLOW: ~5-10 min)"""
    config = {
        "ssh": {"host": "lab02", "username": "zhao", "key_path": "~/.ssh/id_rsa"},
        "celery": {
            "broker_url": "redis://localhost:6379/2",
            "backend_url": "redis://localhost:6379/3",
            "task_timeout": 14400,
            "poll_interval": 5
        },
        "work_dir": "/home/2-BB/changeshengjie/project/mdpilot",
        "conda_env": "af2_py310"
    }
    
    client = AlphaFold2CeleryClient(**config)
    await client.connect()
    
    try:
        # Short test sequence (50 aa)
        sequence = "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHF"
        result = await client.predict(sequence, "test_integration")
        
        assert result["success"] is True
        assert result["sequence_length"] == 50
        assert result["avg_plddt"] > 0
        assert "best_model" in result
    finally:
        await client.disconnect()
