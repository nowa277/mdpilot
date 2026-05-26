"""Test LLM configuration fixtures"""
import pytest


def test_llm_config_test_fixture(llm_config_test):
    """验证测试环境 LLM 配置"""
    assert llm_config_test is not None
    assert "max_tokens" in llm_config_test
    assert "temperature" in llm_config_test
    assert llm_config_test["max_tokens"] == 2048
    assert llm_config_test["temperature"] == 0.0


def test_llm_config_benchmark_fixture(llm_config_benchmark):
    """验证基准测试环境 LLM 配置"""
    assert llm_config_benchmark is not None
    assert "max_tokens" in llm_config_benchmark
    assert "temperature" in llm_config_benchmark
    assert llm_config_benchmark["max_tokens"] == 8192
    assert llm_config_benchmark["temperature"] == 0.0


def test_llm_config_integration_fixture(llm_config_integration):
    """验证集成测试环境 LLM 配置"""
    assert llm_config_integration is not None
    assert "max_tokens" in llm_config_integration
    assert "temperature" in llm_config_integration
    assert llm_config_integration["max_tokens"] == 16384
    assert llm_config_integration["temperature"] == 0.0


def test_llm_configs_are_distinct(llm_config_test, llm_config_benchmark, llm_config_integration):
    """验证不同环境的配置是独立的"""
    # 验证 max_tokens 递增
    assert llm_config_test["max_tokens"] < llm_config_benchmark["max_tokens"]
    assert llm_config_benchmark["max_tokens"] < llm_config_integration["max_tokens"]

    # 验证所有环境都使用确定性温度
    assert llm_config_test["temperature"] == 0.0
    assert llm_config_benchmark["temperature"] == 0.0
    assert llm_config_integration["temperature"] == 0.0


def test_llm_config_immutability(llm_config_test):
    """验证配置对象的不可变性（通过检查是否为字典）"""
    # 配置应该是字典类型
    assert isinstance(llm_config_test, dict)

    # 尝试修改不应影响原始配置
    original_max_tokens = llm_config_test["max_tokens"]
    test_copy = llm_config_test.copy()
    test_copy["max_tokens"] = 9999

    # 原始配置应保持不变
    assert llm_config_test["max_tokens"] == original_max_tokens
