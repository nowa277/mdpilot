# tests/test_data_setup.py
from pathlib import Path

def test_download_script_exists():
    """测试下载脚本文件存在"""
    script = Path(__file__).parent / "data" / "download_test_data.py"
    assert script.exists()
    assert script.is_file()

def test_md_config_files_exist():
    """测试 MD 配置文件存在"""
    configs = [
        "tests/data/configs/min_simple.in",
        "tests/data/configs/heat_simple.in",
        "tests/data/configs/equil_simple.in",
        "tests/data/configs/prod_simple.in",
    ]
    for config in configs:
        assert Path(config).exists(), f"{config} not found"
