"""Tests for conftest.py fixtures"""
import pytest


def test_amber_tools_available_fixture(amber_tools_available):
    """测试 AMBER 工具检测 fixture"""
    assert isinstance(amber_tools_available, dict)
    assert "core" in amber_tools_available
    assert "pdb4amber" in amber_tools_available["core"]
    assert isinstance(amber_tools_available["core"]["pdb4amber"], bool)


def test_skip_if_tool_missing_fixture(skip_if_tool_missing):
    """测试工具跳过 fixture"""
    assert callable(skip_if_tool_missing)


def test_require_amber_tool_fixture(require_amber_tool):
    """测试工具要求 fixture"""
    assert callable(require_amber_tool)


def test_test_data_dir_fixture(test_data_dir):
    """测试数据目录 fixture"""
    from pathlib import Path
    assert isinstance(test_data_dir, Path)
    assert test_data_dir.exists()
    assert test_data_dir.is_dir()
    assert test_data_dir.name == "data"


def test_md_configs_fixture(md_configs):
    """测试 MD 配置 fixture"""
    assert isinstance(md_configs, dict)
    assert "min" in md_configs
    assert "heat" in md_configs
    assert "equil" in md_configs
    assert "prod" in md_configs
    for config_path in md_configs.values():
        assert config_path.exists()


def test_sample_pdb_fixture(sample_pdb):
    """测试样本 PDB fixture"""
    from pathlib import Path
    assert isinstance(sample_pdb, Path)
    assert sample_pdb.suffix == ".pdb"
