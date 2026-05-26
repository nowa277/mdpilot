"""Pytest configuration and fixtures for amber-agent tests"""
import os
import pytest
import shutil
from pathlib import Path


# AmberTools26 完整工具列表
AMBER_TOOLS = {
    "core": ["pdb4amber", "tleap", "sander", "cpptraj"],
    "performance": ["pmemd", "pmemd.cuda", "pmemd.MPI"],
    "ligand": ["antechamber", "parmchk2", "sqm"],
    "auxiliary": ["reduce", "parmed", "ambpdb"],
    "analysis": ["cpptraj", "MMPBSA.py"],
}


def find_amber_tool(tool_name: str) -> bool:
    """查找 AMBER 工具，支持多种安装方式

    查找顺序：
    1. PATH 环境变量
    2. AMBERHOME 环境变量
    3. 常见安装路径
    """
    # 1. 检查 PATH
    if shutil.which(tool_name):
        return True

    # 2. 检查 AMBERHOME
    amberhome = os.environ.get("AMBERHOME")
    if amberhome:
        tool_path = Path(amberhome) / "bin" / tool_name
        if tool_path.exists() and tool_path.is_file():
            return True

    # 3. 检查常见安装路径
    common_paths = [
        Path.home() / "Downloads" / "amber26" / "ambertools26" / "bin",
        Path.home() / "amber26" / "bin",
        Path.home() / "ambertools26" / "bin",
        Path("/opt/amber26/bin"),
        Path("/opt/ambertools26/bin"),
        Path("/usr/local/amber26/bin"),
        Path("/usr/local/ambertools26/bin"),
    ]

    for base_path in common_paths:
        tool_path = base_path / tool_name
        if tool_path.exists() and tool_path.is_file():
            return True

    return False


def get_amber_tool_path(tool_name: str) -> str:
    """获取 AMBER 工具的完整路径

    返回工具的完整路径，如果找不到则返回工具名称本身。
    这样 subprocess 可以使用完整路径调用工具。
    """
    # 1. 检查 PATH
    path_result = shutil.which(tool_name)
    if path_result:
        return path_result

    # 2. 检查 AMBERHOME
    amberhome = os.environ.get("AMBERHOME")
    if amberhome:
        tool_path = Path(amberhome) / "bin" / tool_name
        if tool_path.exists() and tool_path.is_file():
            return str(tool_path)

    # 3. 检查常见安装路径
    common_paths = [
        Path.home() / "Downloads" / "amber26" / "ambertools26" / "bin",
        Path.home() / "amber26" / "bin",
        Path.home() / "ambertools26" / "bin",
        Path("/opt/amber26/bin"),
        Path("/opt/ambertools26/bin"),
        Path("/usr/local/amber26/bin"),
        Path("/usr/local/ambertools26/bin"),
    ]

    for base_path in common_paths:
        tool_path = base_path / tool_name
        if tool_path.exists() and tool_path.is_file():
            return str(tool_path)

    # 如果都找不到，返回工具名称本身（让 subprocess 尝试）
    return tool_name


@pytest.fixture(scope="session")
def amber_tools_available():
    """检测所有 AMBER 工具的可用性"""
    available = {}
    for category, tools in AMBER_TOOLS.items():
        available[category] = {}
        for tool in tools:
            available[category][tool] = find_amber_tool(tool)
    return available


@pytest.fixture
def skip_if_tool_missing(amber_tools_available):
    """根据工具可用性跳过测试"""
    def _skip(tool_name: str, category: str = None):
        if category:
            if not amber_tools_available.get(category, {}).get(tool_name, False):
                pytest.skip(f"{tool_name} not available")
        else:
            # 在所有类别中查找
            found = False
            for cat_tools in amber_tools_available.values():
                if cat_tools.get(tool_name, False):
                    found = True
                    break
            if not found:
                pytest.skip(f"{tool_name} not available")
    return _skip


@pytest.fixture
def require_amber_tool(skip_if_tool_missing):
    """要求特定 AMBER 工具可用，否则跳过测试"""
    return skip_if_tool_missing


@pytest.fixture(scope="session")
def amber_tool_paths():
    """获取所有 AMBER 工具的完整路径

    返回一个字典，键是工具名称，值是完整路径。
    测试可以使用这些路径来调用工具。
    """
    paths = {}
    for category, tools in AMBER_TOOLS.items():
        for tool in tools:
            if find_amber_tool(tool):
                paths[tool] = get_amber_tool_path(tool)
    return paths


# ============================================================================
# 测试数据 Fixtures
# ============================================================================

from pathlib import Path


@pytest.fixture(scope="session")
def test_data_dir():
    """测试数据目录"""
    return Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def md_configs(test_data_dir):
    """MD 配置文件路径"""
    configs_dir = test_data_dir / "configs"
    return {
        "min": configs_dir / "min_simple.in",
        "heat": configs_dir / "heat_simple.in",
        "equil": configs_dir / "equil_simple.in",
        "prod": configs_dir / "prod_simple.in",
    }


@pytest.fixture(scope="session")
def sample_pdb(test_data_dir):
    """样本 PDB 文件 (1AKI)"""
    pdb_file = test_data_dir / "1AKI.pdb"
    if not pdb_file.exists():
        pytest.skip("1AKI.pdb not found. Run: python tests/data/download_test_data.py")
    return pdb_file


@pytest.fixture(scope="session")
def sample_pdb_2lyz(test_data_dir):
    """样本 PDB 文件 (2LYZ)"""
    pdb_file = test_data_dir / "2LYZ.pdb"
    if not pdb_file.exists():
        pytest.skip("2LYZ.pdb not found. Run: python tests/data/download_test_data.py")
    return pdb_file


# ============================================================================
# LLM 配置 Fixtures
# ============================================================================

# LLM 配置策略
LLM_CONFIG = {
    "test": {
        "max_tokens": 2048,
        "temperature": 0.0,
    },
    "benchmark": {
        "max_tokens": 8192,
        "temperature": 0.0,
    },
    "integration": {
        "max_tokens": 16384,
        "temperature": 0.0,
    },
}


@pytest.fixture(scope="session")
def llm_config_test():
    """LLM 配置 - 测试环境"""
    return LLM_CONFIG["test"]


@pytest.fixture(scope="session")
def llm_config_benchmark():
    """LLM 配置 - 基准测试环境"""
    return LLM_CONFIG["benchmark"]


@pytest.fixture(scope="session")
def llm_config_integration():
    """LLM 配置 - 集成测试环境"""
    return LLM_CONFIG["integration"]


# ============================================================================
# Profiling Fixtures
# ============================================================================

from profiling.profile_runner import ProfileRunner
from profiling.resource_monitor import ResourceMonitor
from profiling.memory_profiler_wrapper import MemoryProfiler
from profiling.report_generator import ReportGenerator
from profiling.analyze_workflow import WorkflowAnalyzer


@pytest.fixture
def profile_runner(tmp_path):
    """ProfileRunner fixture for tests"""
    return ProfileRunner(output_dir=tmp_path / "profiles")


@pytest.fixture
def resource_monitor(tmp_path):
    """ResourceMonitor fixture for tests"""
    return ResourceMonitor(interval=0.1, output_dir=tmp_path / "resources")


@pytest.fixture
def memory_profiler(tmp_path):
    """MemoryProfiler fixture for tests"""
    return MemoryProfiler(output_dir=tmp_path / "memory")


@pytest.fixture
def report_generator(tmp_path):
    """ReportGenerator fixture for tests"""
    return ReportGenerator(output_dir=tmp_path / "reports")


@pytest.fixture
def workflow_analyzer(tmp_path):
    """WorkflowAnalyzer fixture for tests"""
    return WorkflowAnalyzer(output_dir=tmp_path / "analysis")
