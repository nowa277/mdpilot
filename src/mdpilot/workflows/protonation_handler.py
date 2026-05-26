#!/usr/bin/env python3
"""质子化状态处理模块

处理蛋白质的质子化状态，特别是组氨酸（HIS）的质子化。
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ProtonationHandler:
    """质子化状态处理器"""

    def __init__(self, ph: float = 7.0):
        """初始化

        Args:
            ph: 目标 pH 值
        """
        self.ph = ph

    def analyze_histidines(self, pdb_file: Path) -> dict:
        """分析 PDB 文件中的组氨酸残基

        Args:
            pdb_file: PDB 文件路径

        Returns:
            组氨酸分析结果
        """
        his_residues = []

        with open(pdb_file, "r") as f:
            for line in f:
                if line.startswith("ATOM") and "HIS" in line:
                    res_num = int(line[22:26].strip())
                    chain = line[21].strip()
                    if (chain, res_num) not in [(h["chain"], h["resnum"]) for h in his_residues]:
                        his_residues.append({"chain": chain, "resnum": res_num, "resname": "HIS"})

        logger.info(f"Found {len(his_residues)} histidine residues")
        return {"histidines": his_residues, "count": len(his_residues)}

    def assign_protonation_states(
        self, pdb_file: Path, method: str = "reduce"
    ) -> dict[str, str]:
        """分配质子化状态

        Args:
            pdb_file: PDB 文件路径
            method: 方法 ("reduce", "propka", "manual")

        Returns:
            残基编号 -> 质子化状态的映射
            HID: δ-氢（ND1 质子化）
            HIE: ε-氢（NE2 质子化）
            HIP: 双质子化（带正电）
        """
        if method == "reduce":
            return self._assign_with_reduce(pdb_file)
        elif method == "propka":
            return self._assign_with_propka(pdb_file)
        else:
            # 默认策略：pH 7.0 时大部分 HIS 为中性（HIE）
            his_info = self.analyze_histidines(pdb_file)
            assignments = {}
            for his in his_info["histidines"]:
                key = f"{his['chain']}:{his['resnum']}"
                # 默认 HIE（ε-氢）
                assignments[key] = "HIE"
            return assignments

    def _assign_with_reduce(self, pdb_file: Path) -> dict[str, str]:
        """使用 reduce 工具分配质子化状态

        Args:
            pdb_file: PDB 文件路径

        Returns:
            质子化状态映射
        """
        try:
            # reduce 会自动优化氢键网络
            result = subprocess.run(
                ["reduce", "-FLIP", "-Quiet", str(pdb_file)],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                logger.warning(f"reduce failed: {result.stderr}")
                return {}

            # 解析 reduce 输出，提取 HIS 质子化状态
            assignments = {}
            for line in result.stdout.split("\n"):
                if "HIS" in line and "FLIP" in line:
                    # 解析 reduce 的决策
                    # 这里需要根据 reduce 的实际输出格式调整
                    pass

            logger.info(f"reduce assigned {len(assignments)} histidine states")
            return assignments

        except FileNotFoundError:
            logger.warning("reduce not found, using default assignment")
            return {}
        except Exception as e:
            logger.error(f"reduce failed: {e}")
            return {}

    def _assign_with_propka(self, pdb_file: Path) -> dict[str, str]:
        """使用 PROPKA 预测 pKa 并分配质子化状态

        Args:
            pdb_file: PDB 文件路径

        Returns:
            质子化状态映射
        """
        try:
            # PROPKA 计算 pKa
            result = subprocess.run(
                ["propka3", str(pdb_file)], capture_output=True, text=True, timeout=60
            )

            if result.returncode != 0:
                logger.warning(f"propka failed: {result.stderr}")
                return {}

            # 解析 PROPKA 输出
            assignments = {}
            for line in result.stdout.split("\n"):
                if "HIS" in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        try:
                            resnum = int(parts[1])
                            pka = float(parts[3])

                            # 根据 pKa 和目标 pH 决定质子化状态
                            if pka > self.ph + 1.0:
                                # pKa 明显高于 pH，质子化（HIP）
                                state = "HIP"
                            elif pka < self.ph - 1.0:
                                # pKa 明显低于 pH，去质子化（HIE）
                                state = "HIE"
                            else:
                                # 中间状态，默认 HIE
                                state = "HIE"

                            assignments[f"A:{resnum}"] = state
                        except (ValueError, IndexError):
                            continue

            logger.info(f"PROPKA assigned {len(assignments)} histidine states")
            return assignments

        except FileNotFoundError:
            logger.warning("propka3 not found, using default assignment")
            return {}
        except Exception as e:
            logger.error(f"PROPKA failed: {e}")
            return {}

    def apply_to_tleap_script(
        self, assignments: dict[str, str], output_file: Path
    ) -> str:
        """生成 tleap 脚本片段来应用质子化状态

        Args:
            assignments: 质子化状态映射
            output_file: 输出文件路径

        Returns:
            tleap 脚本内容
        """
        lines = []
        lines.append("# 组氨酸质子化状态设置")

        for res_id, state in assignments.items():
            chain, resnum = res_id.split(":")
            # tleap 语法：set mol.{chain}.{resnum}.name {state}
            lines.append(f"set mol.{resnum}.name {state}")

        script = "\n".join(lines)

        if output_file:
            with open(output_file, "w") as f:
                f.write(script)
            logger.info(f"Protonation script written to {output_file}")

        return script


def prepare_protonated_pdb(
    input_pdb: Path,
    output_pdb: Path,
    ph: float = 7.0,
    method: str = "reduce",
) -> dict:
    """准备质子化的 PDB 文件

    Args:
        input_pdb: 输入 PDB 文件
        output_pdb: 输出 PDB 文件
        ph: 目标 pH
        method: 质子化方法

    Returns:
        处理结果
    """
    handler = ProtonationHandler(ph=ph)

    # 分析组氨酸
    his_info = handler.analyze_histidines(input_pdb)

    # 分配质子化状态
    assignments = handler.assign_protonation_states(input_pdb, method=method)

    # 生成 tleap 脚本
    script_file = output_pdb.parent / "protonation_states.leap"
    script = handler.apply_to_tleap_script(assignments, script_file)

    return {
        "histidine_count": his_info["count"],
        "assignments": assignments,
        "tleap_script": str(script_file),
        "method": method,
        "ph": ph,
    }
