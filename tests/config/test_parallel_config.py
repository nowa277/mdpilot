"""Tests for ParallelConfig schema."""

from mdpilot.config.schema import ParallelConfig, AgentConfig


def test_parallel_config_defaults():
    """ParallelConfig should have correct default values."""
    config = ParallelConfig()
    assert config.enable_parallel is False
    assert config.max_concurrent_tools == 4
    assert config.max_memory_mb == 8192
    assert config.max_gpu_tools == 1


def test_parallel_config_validation():
    """ParallelConfig should validate field constraints."""
    # Valid config
    config = ParallelConfig(
        enable_parallel=True,
        max_concurrent_tools=8,
        max_memory_mb=16384,
        max_gpu_tools=2
    )
    assert config.max_concurrent_tools == 8

    # Invalid: max_concurrent_tools < 1
    try:
        ParallelConfig(max_concurrent_tools=0)
        assert False, "Should have raised validation error"
    except Exception:
        pass

    # Invalid: max_concurrent_tools > 32
    try:
        ParallelConfig(max_concurrent_tools=64)
        assert False, "Should have raised validation error"
    except Exception:
        pass


def test_agent_config_has_parallel_field():
    """AgentConfig should have parallel field with default."""
    config = AgentConfig()
    assert hasattr(config, 'parallel')
    assert isinstance(config.parallel, ParallelConfig)
    assert config.parallel.enable_parallel is False
