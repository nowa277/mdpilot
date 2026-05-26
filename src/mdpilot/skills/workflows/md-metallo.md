---
name: md-metallo
title: 金属蛋白建模
description: MCPB.py 金属位点建模与力场参数化
tags: [metalloprotein, mcpb, metal, zinc, copper, iron]
triggers: [metal protein, metallo, MCPB, 金属蛋白, 金属位点]
category: workflow
command: /md-metallo
tools:
  - name: pdb4amber, node: lab03, exec: local_subprocess
  - name: mcpb_py, node: lab03, exec: local_subprocess
  - name: tleap, node: lab03, exec: local_subprocess
  - name: pmemd_cuda, node: lab03, exec: local_subprocess
---

# 金属蛋白建模

本 Skill 覆盖 AMBER MCPB.py 工作流，用于构建金属位点（锌指、铁硫簇、铜位点等）的分子力场参数。

## MCPB.py 概述

MCPB.py (Metal Center Parameter Builder) 将 QM 计算与经验力场结合，为金属位点生成专用参数。工作流分为 4 步。

## Step 1: 模型生成 — pdb4amber 预处理

```bash
# 标准预处理
pdb4amber -i protein.pdb -o protein_clean.pdb --dry

# 手动检查并确认金属配位残基
# 常见配位残基: CYS (S), HIS (Nδ/Nε), ASP (O), GLU (O), MET (S)
```

### 确定金属位点

1. 从 PDB 文件中识别金属离子及其配位残基（距离 < 3.0 Å 的残基）。
2. 记录金属离子名称和配位残基的残基编号。

### 准备 MCPB.py 输入文件

```ini
# MCPB.in
original_model  protein_clean.pdb
group_name      ZN_SITE

# 金属离子
metal ion       ZN    401   ZN

# 配位残基 (残基编号来自 PDB)
residue         HIS   45
residue         CYS   48
residue         CYS   51
residue         HIS   75

# 配位原子
link            Nδ1   HIS   45    ZN    401
link            Sγ    CYS   48    ZN    401
link            Sγ    CYS   51    ZN    401
link            Nε2   HIS   75    ZN    401

# QM 设置
theory          b3lyp
basis_set       6-31g*
```

运行模型生成：

```bash
MCPB.py -i MCPB.in -s 1
```

此步骤生成 small_model、large_model 和 big_model 三个级别的 QM 模型。

## Step 2: 力常数计算 (Gaussian Hessian)

### QM 计算

使用 Gaussian 对小模型（金属离子 + 配位残基截断片段）进行频率计算：

```bash
# MCPB.py 自动生成 Gaussian 输入文件
MCPB.py -i MCPB.in -s 2

# 提交 Gaussian 计算 (生成的 .com 文件)
g16 < small_model.com > small_model.log

# 或者使用已完成的 checkpoint
# small_model.chk 应包含优化后结构和 Hessian
```

### Gaussian 设置要点

| 金属 | 推荐基组 | 说明 |
|------|----------|------|
| Zn²⁺ | b3lyp/6-31g* | 标准选择 |
| Fe²⁺/³⁺ | b3lyp/6-31g* (使用 ECP) | 过渡金属需注意自旋态 |
| Cu²⁺ | b3lyp/6-31g* | d⁹ 体系需使用 unrestricted |
| Mg²⁺ | b3lyp/6-31g* | 闭壳层，计算稳定 |
| Ca²⁺ | b3lyp/6-31g* | 类似 Mg |

对于过渡金属 (Fe, Cu, Mn)，需要：

- 确认正确的自旋多重度 (spin multiplicity)
- 考虑使用 LANL2DZ 或 def2-TZVP 作为 ECP 基组
- 对开壳层体系使用 UHF/UKS

## Step 3: RESP 电荷拟合

```bash
# 从 Gaussian 计算提取 ESP 电荷
MCPB.py -i MCPB.in -s 3

# 这会调用 Antechamber 和 RESP 程序
# 生成拟合电荷的 .prep 文件
```

RESP (Restrained Electrostatic Potential) 拟合确保金属位点的部分电荷与 QM 计算的静电势一致。MCPB.py 会自动处理电荷约束，保持非金属位点残基的力场电荷不变。

## Step 4: LEaP 输入生成

```bash
# 生成最终的 tleap 输入文件
MCPB.py -i MCPB.in -s 4

# 使用 tleap 构建完整体系
tleap -f MCPB.tleap
```

生成的 tleap 脚本会：

1. 加载标准力场 (ff14SB, ff19SB 等)
2. 加载 MCPB.py 生成的金属位点参数 (.frcmod 和 .prep 文件)
3. 溶剂化体系
4. 添加抗衡离子

### 完整体系构建后的检查

```bash
# 检查金属配位距离
cpptraj -p complex.prmtop <<EOF
distance d1 :45@ND1 :401@ZN
distance d2 :48@SG :401@ZN
distance d3 :51@SG :401@ZN
distance d4 :75@NE2 :401@ZN
EOF
# Zn-N/S 典型距离: 2.0-2.3 Å
```

## 常见金属类型及注意事项

### 锌 (Zn²⁺)

- 最常见的金属蛋白金属
- 配位数：4 (四面体) 或 6 (八面体)
- 典型配位：CYS-Sγ, HIS-Nδ1/Nε2, ASP-COO⁻
- 闭壳层 d¹⁰，计算简单稳定

### 铁 (Fe²⁺/Fe³⁺)

- 铁硫簇 (Fe-S cluster) 需要特殊处理
- 血红素体系建议使用 heme 参数库
- 注意自旋态：高自旋 vs 低自旋
- Fe-S 簇建议使用 Seminario 方法验证力常数

### 铜 (Cu²⁺/Cu⁺)

- Cu²⁺ 为 d⁹ 开壳层，需要 UKS
- Cu⁺ 为 d¹⁰ 闭壳层
- Jahn-Teller 效应导致轴向拉长

### 镁 (Mg²⁺)

- 闭壳层，计算简单
- 通常为八面体配位 (6 配位)
- ATP 结合位点常见

## 实践建议

1. **验证 QM 结构**：在拟合前确认 Gaussian 优化的结构合理，金属配位距离符合预期。
2. **电荷守恒**：确认整个金属位点（金属 + 配位残基）的总电荷正确。Zn²⁺ 为 +2，配位残基的质子化状态需对应调整。
3. **力场兼容性**：MCPB.py 生成的参数与 ff14SB/ff19SB 兼容；避免混用不同力场的蛋白质参数。
4. **MD 平衡**：金属位点体系需更长的平衡时间（5-10 ns），使用位置限制逐步释放。
5. **轨迹监控**：MD 过程中持续监控金属配位距离，如果配位键断裂需检查参数质量。
