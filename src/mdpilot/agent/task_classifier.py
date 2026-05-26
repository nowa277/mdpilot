"""TaskClassifier — routes user input to CHAT or MD_TASK."""

from __future__ import annotations

import re

SIGNALS: dict[str, float | dict[str, float]] = {
    "file_extensions": {
        ".pdb": 3, ".mol2": 3, ".prmtop": 3, ".inpcrd": 3,
        ".nc": 3, ".rst7": 3, ".frcmod": 3, ".lib": 3, ".off": 3,
        ".crd": 3, ".top": 3,
    },
    "pdb_id_pattern": r"(?:^|\s|:|/)[1-9][A-Z0-9]{3}(?:\s|$|\.|/)",
    "action_verbs": {
        "构建": 2, "建立": 2, "搭建": 2, "准备": 2, "构建出": 2,
        "跑": 2, "运行": 2, "执行": 2, "模拟": 2,
        "分析": 2, "计算": 2, "优化": 2, "最小化": 2,
        "参数化": 2, "加氢": 2, "质子化": 2, "溶剂化": 2,
        "清洗": 2, "处理": 2, "平衡": 2,
        "build": 2, "prepare": 2, "construct": 2, "setup": 2,
        "run": 2, "simulate": 2, "minimize": 2, "equilibrate": 2,
        "heat": 2, "produce": 2, "solvate": 2,
        "analyze": 2, "parameterize": 2, "clean": 2,
        "read": 2, "write": 2, "load": 2, "save": 2,
        "download": 2, "process": 2, "calculate": 2, "use": 2,
        "apply": 2,
    },
    "md_keywords": {
        "力场": 1, "水模型": 1, "盒子": 1, "截断": 1, "静电": 1,
        "能量最小化": 1, "分子动力学": 1, "动力学": 1,
        "自由能": 1, "结合自由能": 1,
        "拓扑": 1, "坐标": 1, "电荷": 1, "质子化": 1,
        "氢键": 1, "盐桥": 1, "二硫键": 1,
        "forcefield": 1, "force field": 1, "water model": 1,
        "solvate": 1, "ff19sb": 1, "ff14sb": 1, "gaff2": 1,
        "opc3": 1, "opc": 1, "tip3p": 1, "tip4p": 1,
        "amber": 1, "md": 1, "npt": 1, "nvt": 1, "nve": 1,
        "rmsd": 1, "rmsf": 1, "trajectory": 1,
        "topology": 1, "coord": 1,
        "minimization": 2, "simulation": 2, "workflow": 1,
        "hydrogen": 1, "bonds": 1, "energy": 1,
        "parameters": 1, "parameter": 1,
    },
    "system_types": {
        "蛋白": 1, "配体": 1, "核酸": 1, "膜": 1, "金属": 1,
        "多聚体": 1, "二聚体": 1, "复合物": 1, "离子通道": 1,
        "酶": 1, "受体": 1, "抗体": 1,
        "protein": 1, "ligand": 1, "enzyme": 1, "receptor": 1,
        "membrane": 1, "gpcr": 1, "dna": 1, "rna": 1, "nucleic": 1,
        "metal": 1, "zinc": 1, "iron": 1, "complex": 1, "dimer": 1,
    },
    "tool_names": {
        "tleap": 2, "cpptraj": 2, "pdb4amber": 2, "sander": 2,
        "pmemd": 2, "antechamber": 2, "parmchk": 2, "reduce": 2, "mdgx": 2,
    },
    "negative_signals": {
        "什么是": -2, "是什么": -2, "解释": -2, "解释一下": -2,
        "区别": -2, "比较": -2, "为什么": -2, "如何理解": -2,
        "概念": -2, "原理": -2, "定义": -2,
        "what is": -2, "explain": -2, "difference": -2,
        "why": -2, "how does": -2, "definition": -2,
        "meaning of": -2, "vs": -2,
    },
}

TASK_THRESHOLD = 3


def classify(text: str) -> str:
    """Classify user input as CHAT or MD_TASK."""
    score = 0.0
    text_lower = text.lower()
    for ext, weight in SIGNALS["file_extensions"].items():
        if ext in text_lower:
            score += weight
    if re.search(SIGNALS["pdb_id_pattern"], text, re.IGNORECASE):
        score += 2
    for verb, weight in SIGNALS["action_verbs"].items():
        if verb in text_lower:
            score += weight
    for kw, weight in SIGNALS["md_keywords"].items():
        if kw.lower() in text_lower:
            score += weight
    for st, weight in SIGNALS["system_types"].items():
        if st in text_lower:
            score += weight
    for tool, weight in SIGNALS["tool_names"].items():
        if tool in text_lower:
            score += weight
    for neg, weight in SIGNALS["negative_signals"].items():
        if neg.lower() in text_lower:
            score += weight
    return "MD_TASK" if score >= TASK_THRESHOLD else "CHAT"


class TaskClassifier:
    def classify(self, text: str) -> str:
        return classify(text)
    
    def classify_for_inspector(self, text: str) -> str:
        """Classify for Inspector visibility: 'workflow' or 'chat'.
        
        Parameters
        ----------
        text : str
            User message content.
            
        Returns
        -------
        str
            'workflow' if Inspector should be visible, 'chat' if hidden.
        """
        md_classification = classify(text)
        return 'workflow' if md_classification == 'MD_TASK' else 'chat'


# ---- Paradigm classification for agent routing ----

_MULTI_STEP_PATTERNS = [
    r"预测.*然后.*分析",
    r"先.*再.*",
    r"之后",
    r"接着",
    r"流程",
    r"模拟.*流程",
    r"alphafold2.*分析",
    r"结构预测.*功能",
    r"完整.*工作流",
    r"分子动力学.*模拟",
    r"amber.*模拟",
    r"sander.*cpptraj",
    r"tleap.*sander",
    r"能量最小化.*平衡.*生产",
]

_OPTIMIZE_PATTERNS = [
    r"优化",
    r"改进",
    r"调参",
    r"更好",
    r"检查.*结果",
    r"验证",
    r"确认.*正确",
    r"比较.*哪种",
    r"审查",
    r"交叉检查",
]

_PLAN_SOLVE_TOOLS = {
    "alphafold2_predict",
    "bioreason_run",
    "amber_minimize",
    "amber_md",
    "cpptraj",
    "tleap",
    "pdb4amber",
}


def classify_paradigm(text: str) -> str:
    """Classify which agent paradigm to use for a given prompt.

    Returns
    -------
    str
        One of "react", "plan_solve", "reflection".
    """
    import re

    text_lower = text.lower()

    # Check multi-step patterns first
    for pattern in _MULTI_STEP_PATTERNS:
        if re.search(pattern, text_lower):
            return "plan_solve"

    # Check optimization/reflection patterns
    for pattern in _OPTIMIZE_PATTERNS:
        if re.search(pattern, text_lower):
            return "reflection"

    return "react"


# Add method to TaskClassifier class
def _tc_classify_paradigm(self, text: str) -> str:
    """Classify paradigm for agent routing."""
    return classify_paradigm(text)

TaskClassifier.classify_paradigm = _tc_classify_paradigm
