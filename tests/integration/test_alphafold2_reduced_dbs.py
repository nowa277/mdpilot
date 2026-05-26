"""Integration tests for AlphaFold2 reduced_dbs mode"""

import pytest
import time
from mdpilot.integrations.alphafold2.celery_client import AlphaFold2CeleryClient


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_reduced_dbs_mode():
    """Test AlphaFold2 with reduced_dbs preset (fast mode)"""
    config = {
        "ssh": {
            "host": "lab02",
            "username": "zhao",
            "key_path": "~/.ssh/id_rsa"
        },
        "celery": {
            "broker_url": "redis://localhost:6379/2",
            "backend_url": "redis://localhost:6379/3",
            "task_timeout": 900,  # 15 minutes
            "poll_interval": 5
        },
        "work_dir": "/home/2-BB/changeshengjie/project/mdpilot",
        "conda_env": "af2_py310"
    }
    
    client = AlphaFold2CeleryClient(**config)
    await client.connect()
    
    try:
        sequence = "FVNQHLCGSHLVEALYLVCGERGFFYTPKT"
        
        start = time.time()
        
        result = await client.predict(
            sequence=sequence,
            job_name="test_reduced_dbs",
            db_preset="reduced_dbs"
        )
        
        elapsed = time.time() - start
        
        assert result["success"] is True
        assert result["db_preset"] == "reduced_dbs"
        assert result["avg_plddt"] > 80
        assert elapsed < 900
        
        print(f"\n✅ Reduced_dbs mode test passed:")
        print(f"   Time: {elapsed:.1f}s ({elapsed/60:.1f} min)")
        print(f"   pLDDT: {result['avg_plddt']:.2f}")
        print(f"   Model: {result['best_model']}")
        
    finally:
        await client.disconnect()


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_db_preset_parameter_validation():
    """Test that db_preset parameter is correctly passed"""
    config = {
        "ssh": {
            "host": "lab02",
            "username": "zhao",
            "key_path": "~/.ssh/id_rsa"
        },
        "celery": {
            "broker_url": "redis://localhost:6379/2",
            "backend_url": "redis://localhost:6379/3",
            "task_timeout": 900,
            "poll_interval": 5
        },
        "work_dir": "/home/2-BB/changeshengjie/project/mdpilot",
        "conda_env": "af2_py310"
    }
    
    client = AlphaFold2CeleryClient(**config)
    await client.connect()
    
    try:
        sequence = "MVHLTPEEKSAVTALWGKVNVDEVGGEALGRLLVVYPWTQRF"
        
        result = await client.predict(
            sequence=sequence,
            job_name="test_db_preset_param",
            db_preset="reduced_dbs"
        )
        
        assert "db_preset" in result
        assert result["db_preset"] == "reduced_dbs"
        
        print(f"\n✅ db_preset parameter validation passed")
        
    finally:
        await client.disconnect()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tool_schema_includes_db_preset():
    """Test that alphafold2_predict tool schema includes db_preset parameter"""
    from mdpilot.tools.registry import ToolRegistry
    
    registry = ToolRegistry()
    registry.auto_discover("mdpilot.tools.builtin")
    
    schemas = registry.schemas()
    af2_schema = next(
        (s for s in schemas if s["function"]["name"] == "alphafold2_predict"),
        None
    )
    
    assert af2_schema is not None, "alphafold2_predict tool not found"
    
    params = af2_schema["function"]["parameters"]
    assert "db_preset" in params["properties"]
    
    db_preset_param = params["properties"]["db_preset"]
    assert db_preset_param["type"] == "string"
    assert db_preset_param["default"] == "reduced_dbs"
    
    print(f"\n✅ Tool schema validation passed")
    print(f"   db_preset parameter: {db_preset_param}")
