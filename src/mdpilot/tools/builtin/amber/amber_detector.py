"""AmberTools 自动检测模块

自动检测系统中的 AmberTools 安装位置和可用工具。
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class AmberToolsDetector:
    """AmberTools 安装检测器"""

    def __init__(self):
        self.amberhome: Optional[Path] = None
        self.version: Optional[str] = None
        self.available_tools: dict[str, Path] = {}
        self._detect()

    def _detect(self):
        """检测 AmberTools 安装"""
        # 1. 检查 AMBERHOME 环境变量
        amberhome_env = os.environ.get("AMBERHOME")
        if amberhome_env:
            amberhome_path = Path(amberhome_env)
            if amberhome_path.exists():
                self.amberhome = amberhome_path
                logger.info(f"Found AMBERHOME: {self.amberhome}")
                self._detect_tools()
                self._detect_version()
                return

        # 2. 搜索常见安装位置
        search_paths = [
            Path.home() / "Downloads" / "amber26" / "ambertools26",
            Path.home() / "Downloads" / "amber24" / "ambertools24",
            Path("/opt/amber26"),
            Path("/opt/amber24"),
            Path("/usr/local/amber26"),
            Path("/usr/local/amber24"),
            Path.home() / "amber26",
            Path.home() / "amber24",
        ]

        for path in search_paths:
            if path.exists() and (path / "bin").exists():
                self.amberhome = path
                logger.info(f"Found AmberTools at: {self.amberhome}")
                self._detect_tools()
                self._detect_version()
                return

        # 3. 检查 PATH 中的工具
        logger.warning("AMBERHOME not found, checking PATH for individual tools")
        self._detect_tools_in_path()

    def _detect_tools(self):
        """检测 bin 目录中的工具"""
        if not self.amberhome:
            return

        bin_dir = self.amberhome / "bin"
        if not bin_dir.exists():
            logger.warning(f"bin directory not found: {bin_dir}")
            return

        tool_names = [
            "pdb4amber",
            "tleap",
            "sander",
            "pmemd",
            "pmemd.cuda",
            "pmemd.MPI",
            "cpptraj",
            "antechamber",
            "parmchk2",
            "reduce",
            "ambpdb",
        ]

        for tool in tool_names:
            tool_path = bin_dir / tool
            if tool_path.exists():
                self.available_tools[tool] = tool_path
                logger.debug(f"Found tool: {tool} at {tool_path}")

    def _detect_tools_in_path(self):
        """在 PATH 中检测工具"""
        tool_names = [
            "pdb4amber",
            "tleap",
            "sander",
            "pmemd",
            "pmemd.cuda",
            "pmemd.MPI",
            "cpptraj",
            "antechamber",
            "parmchk2",
            "reduce",
            "ambpdb",
        ]

        for tool in tool_names:
            tool_path = shutil.which(tool)
            if tool_path:
                self.available_tools[tool] = Path(tool_path)
                logger.debug(f"Found tool in PATH: {tool} at {tool_path}")

    def _detect_version(self):
        """检测 AmberTools 版本"""
        if not self.amberhome:
            return

        # 尝试从路径推断版本
        path_str = str(self.amberhome)
        if "26" in path_str:
            self.version = "26"
        elif "24" in path_str:
            self.version = "24"
        elif "23" in path_str:
            self.version = "23"
        else:
            self.version = "unknown"

        logger.info(f"Detected AmberTools version: {self.version}")

    def get_tool_path(self, tool_name: str) -> Optional[Path]:
        """获取工具路径

        Args:
            tool_name: 工具名称（如 "pdb4amber", "tleap"）

        Returns:
            工具的完整路径，如果不存在返回 None
        """
        return self.available_tools.get(tool_name)

    def is_tool_available(self, tool_name: str) -> bool:
        """检查工具是否可用

        Args:
            tool_name: 工具名称

        Returns:
            工具是否可用
        """
        return tool_name in self.available_tools

    def get_summary(self) -> dict:
        """获取检测摘要

        Returns:
            包含检测信息的字典
        """
        return {
            "amberhome": str(self.amberhome) if self.amberhome else None,
            "version": self.version,
            "available_tools": {
                name: str(path) for name, path in self.available_tools.items()
            },
            "tool_count": len(self.available_tools),
        }


# 全局单例
_detector: Optional[AmberToolsDetector] = None


def get_detector() -> AmberToolsDetector:
    """获取全局检测器实例"""
    global _detector
    if _detector is None:
        _detector = AmberToolsDetector()
    return _detector


def configure_amber_environment() -> dict:
    """配置 AMBER 环境

    自动检测 AmberTools 并设置环境变量。

    Returns:
        包含配置信息的字典
    """
    detector = get_detector()

    if detector.amberhome:
        # 设置 AMBERHOME 环境变量
        os.environ["AMBERHOME"] = str(detector.amberhome)

        # 添加 bin 目录到 PATH
        bin_dir = detector.amberhome / "bin"
        if bin_dir.exists():
            current_path = os.environ.get("PATH", "")
            if str(bin_dir) not in current_path:
                os.environ["PATH"] = f"{bin_dir}:{current_path}"
                logger.info(f"Added {bin_dir} to PATH")

    return detector.get_summary()


def get_tool_path(tool_name: str) -> Optional[str]:
    """获取工具路径的便捷函数

    Args:
        tool_name: 工具名称

    Returns:
        工具路径字符串，如果不存在返回 None
    """
    detector = get_detector()
    path = detector.get_tool_path(tool_name)
    return str(path) if path else None


def is_tool_available(tool_name: str) -> bool:
    """检查工具是否可用的便捷函数

    Args:
        tool_name: 工具名称

    Returns:
        工具是否可用
    """
    detector = get_detector()
    return detector.is_tool_available(tool_name)
