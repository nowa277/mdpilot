"""体系构建过程记录和导出模块

记录 MD 体系构建的每个步骤，并导出为详细报告。
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class BuildStep:
    """单个构建步骤"""

    step_number: int
    step_name: str
    tool: str
    command: str
    input_files: list[str]
    output_files: list[str]
    status: str  # "success", "failed", "skipped"
    start_time: str
    end_time: Optional[str] = None
    duration_sec: Optional[float] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class SystemInfo:
    """体系信息"""

    pdb_id: Optional[str] = None
    protein_name: Optional[str] = None
    chains: list[str] = field(default_factory=list)
    residue_count: int = 0
    atom_count: int = 0
    force_field: Optional[str] = None
    water_model: Optional[str] = None
    box_type: Optional[str] = None
    box_size: Optional[tuple[float, float, float]] = None
    ion_count: dict[str, int] = field(default_factory=dict)
    total_atoms_solvated: int = 0


@dataclass
class BuildReport:
    """完整的构建报告"""

    project_name: str
    build_date: str
    amberhome: Optional[str] = None
    ambertools_version: Optional[str] = None
    system_info: SystemInfo = field(default_factory=SystemInfo)
    steps: list[BuildStep] = field(default_factory=list)
    total_duration_sec: float = 0.0
    success: bool = True
    final_files: dict[str, str] = field(default_factory=dict)


class BuildRecorder:
    """体系构建过程记录器"""

    def __init__(self, project_name: str, output_dir: Path):
        """初始化记录器

        Args:
            project_name: 项目名称
            output_dir: 输出目录
        """
        self.project_name = project_name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.report = BuildReport(
            project_name=project_name,
            build_date=datetime.now().isoformat(),
        )

        self.current_step: Optional[BuildStep] = None
        self.step_counter = 0

    def set_amber_info(self, amberhome: str, version: str):
        """设置 AMBER 信息"""
        self.report.amberhome = amberhome
        self.report.ambertools_version = version

    def set_system_info(self, **kwargs):
        """设置体系信息"""
        for key, value in kwargs.items():
            if hasattr(self.report.system_info, key):
                setattr(self.report.system_info, key, value)

    def start_step(
        self,
        step_name: str,
        tool: str,
        command: str,
        input_files: list[str],
        output_files: list[str],
    ) -> BuildStep:
        """开始一个构建步骤

        Args:
            step_name: 步骤名称
            tool: 使用的工具
            command: 执行的命令
            input_files: 输入文件列表
            output_files: 输出文件列表

        Returns:
            BuildStep 对象
        """
        self.step_counter += 1
        self.current_step = BuildStep(
            step_number=self.step_counter,
            step_name=step_name,
            tool=tool,
            command=command,
            input_files=input_files,
            output_files=output_files,
            status="running",
            start_time=datetime.now().isoformat(),
        )
        logger.info(f"Step {self.step_counter}: {step_name}")
        return self.current_step

    def end_step(
        self,
        status: str = "success",
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        warnings: Optional[list[str]] = None,
        errors: Optional[list[str]] = None,
        notes: Optional[list[str]] = None,
    ):
        """结束当前步骤

        Args:
            status: 状态 ("success", "failed", "skipped")
            stdout: 标准输出
            stderr: 标准错误
            warnings: 警告列表
            errors: 错误列表
            notes: 备注列表
        """
        if not self.current_step:
            logger.warning("No active step to end")
            return

        self.current_step.status = status
        self.current_step.end_time = datetime.now().isoformat()

        # 计算持续时间
        start = datetime.fromisoformat(self.current_step.start_time)
        end = datetime.fromisoformat(self.current_step.end_time)
        self.current_step.duration_sec = (end - start).total_seconds()

        if stdout:
            self.current_step.stdout = stdout
        if stderr:
            self.current_step.stderr = stderr
        if warnings:
            self.current_step.warnings = warnings
        if errors:
            self.current_step.errors = errors
        if notes:
            self.current_step.notes = notes

        self.report.steps.append(self.current_step)

        if status == "failed":
            self.report.success = False

        logger.info(
            f"Step {self.current_step.step_number} {status} "
            f"({self.current_step.duration_sec:.2f}s)"
        )

        self.current_step = None

    def add_final_file(self, file_type: str, file_path: str):
        """添加最终生成的文件

        Args:
            file_type: 文件类型 (如 "topology", "coordinates", "pdb")
            file_path: 文件路径
        """
        self.report.final_files[file_type] = file_path

    def export_json(self, filename: Optional[str] = None) -> Path:
        """导出为 JSON 格式

        Args:
            filename: 输出文件名（可选）

        Returns:
            输出文件路径
        """
        if filename is None:
            filename = f"{self.project_name}_build_report.json"

        output_path = self.output_dir / filename

        # 计算总时长
        self.report.total_duration_sec = sum(
            step.duration_sec for step in self.report.steps if step.duration_sec
        )

        # 转换为字典
        report_dict = asdict(self.report)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2, ensure_ascii=False)

        logger.info(f"Build report exported to: {output_path}")
        return output_path

    def export_markdown(self, filename: Optional[str] = None) -> Path:
        """导出为 Markdown 格式

        Args:
            filename: 输出文件名（可选）

        Returns:
            输出文件路径
        """
        if filename is None:
            filename = f"{self.project_name}_build_report.md"

        output_path = self.output_dir / filename

        # 计算总时长
        total_duration = sum(
            step.duration_sec for step in self.report.steps if step.duration_sec
        )

        lines = []

        # 标题
        lines.append(f"# {self.project_name} - 体系构建报告\n")
        lines.append(f"**构建日期**: {self.report.build_date}\n")
        lines.append(f"**状态**: {'✅ 成功' if self.report.success else '❌ 失败'}\n")
        lines.append(f"**总耗时**: {total_duration:.2f} 秒\n")

        # AMBER 信息
        if self.report.amberhome:
            lines.append("## AMBER 环境\n")
            lines.append(f"- **AMBERHOME**: `{self.report.amberhome}`\n")
            lines.append(f"- **版本**: AmberTools {self.report.ambertools_version}\n")

        # 体系信息
        lines.append("## 体系信息\n")
        sys_info = self.report.system_info
        if sys_info.pdb_id:
            lines.append(f"- **PDB ID**: {sys_info.pdb_id}\n")
        if sys_info.protein_name:
            lines.append(f"- **蛋白质**: {sys_info.protein_name}\n")
        if sys_info.chains:
            lines.append(f"- **链**: {', '.join(sys_info.chains)}\n")
        if sys_info.residue_count:
            lines.append(f"- **残基数**: {sys_info.residue_count}\n")
        if sys_info.atom_count:
            lines.append(f"- **原子数**: {sys_info.atom_count}\n")
        if sys_info.force_field:
            lines.append(f"- **力场**: {sys_info.force_field}\n")
        if sys_info.water_model:
            lines.append(f"- **水模型**: {sys_info.water_model}\n")
        if sys_info.box_type:
            lines.append(f"- **盒子类型**: {sys_info.box_type}\n")
        if sys_info.ion_count:
            ion_str = ", ".join(f"{ion}: {count}" for ion, count in sys_info.ion_count.items())
            lines.append(f"- **离子**: {ion_str}\n")
        if sys_info.total_atoms_solvated:
            lines.append(f"- **溶剂化后总原子数**: {sys_info.total_atoms_solvated:,}\n")

        # 构建步骤
        lines.append("## 构建步骤\n")
        for step in self.report.steps:
            status_icon = "✅" if step.status == "success" else "❌" if step.status == "failed" else "⏭️"
            lines.append(f"### {status_icon} 步骤 {step.step_number}: {step.step_name}\n")
            lines.append(f"- **工具**: `{step.tool}`\n")
            lines.append(f"- **命令**: `{step.command}`\n")
            lines.append(f"- **输入文件**: {', '.join(f'`{f}`' for f in step.input_files)}\n")
            lines.append(f"- **输出文件**: {', '.join(f'`{f}`' for f in step.output_files)}\n")
            if step.duration_sec:
                lines.append(f"- **耗时**: {step.duration_sec:.2f} 秒\n")

            if step.warnings:
                lines.append(f"- **警告** ({len(step.warnings)} 个):\n")
                for warning in step.warnings:
                    lines.append(f"  - {warning}\n")

            if step.errors:
                lines.append(f"- **错误** ({len(step.errors)} 个):\n")
                for error in step.errors:
                    lines.append(f"  - {error}\n")

            if step.notes:
                lines.append(f"- **备注**:\n")
                for note in step.notes:
                    lines.append(f"  - {note}\n")

            lines.append("\n")

        # 最终文件
        if self.report.final_files:
            lines.append("## 最终生成文件\n")
            for file_type, file_path in self.report.final_files.items():
                file_size = Path(file_path).stat().st_size if Path(file_path).exists() else 0
                size_mb = file_size / (1024 * 1024)
                lines.append(f"- **{file_type}**: `{file_path}` ({size_mb:.2f} MB)\n")

        # 写入文件
        with open(output_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        logger.info(f"Build report exported to: {output_path}")
        return output_path

    def export_html(self, filename: Optional[str] = None) -> Path:
        """导出为 HTML 格式

        Args:
            filename: 输出文件名（可选）

        Returns:
            输出文件路径
        """
        if filename is None:
            filename = f"{self.project_name}_build_report.html"

        output_path = self.output_dir / filename

        # 先导出 Markdown，然后转换为 HTML
        md_path = self.export_markdown(filename.replace(".html", ".md"))

        # 简单的 Markdown 到 HTML 转换
        with open(md_path, "r", encoding="utf-8") as f:
            md_content = f.read()

        # 基本的 Markdown 转 HTML（简化版）
        html_content = md_content
        html_content = html_content.replace("# ", "<h1>").replace("\n", "</h1>\n", 1)
        html_content = html_content.replace("## ", "<h2>").replace("\n", "</h2>\n")
        html_content = html_content.replace("### ", "<h3>").replace("\n", "</h3>\n")
        html_content = html_content.replace("**", "<strong>", 1).replace("**", "</strong>", 1)
        html_content = html_content.replace("`", "<code>", 1).replace("`", "</code>", 1)

        html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.project_name} - 体系构建报告</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        h3 {{ color: #7f8c8d; }}
        code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }}
        pre {{ background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }}
        .success {{ color: #27ae60; }}
        .failed {{ color: #e74c3c; }}
        .warning {{ color: #f39c12; }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_template)

        logger.info(f"Build report exported to: {output_path}")
        return output_path
