---
name: fix-leap
title: LEaP 错误排查
description: tleap 常见错误：缺失参数、电荷不平衡、未知残基
tags: [tleap, leap, error, topology, parameter]
triggers: [tleap error, leap error, LEaP错误, tleap报错, 拓扑错误]
category: troubleshooting
command: /fix-leap
tools:
  - name: tleap, node: lab03, exec: local_subprocess
  - name: antechamber, node: lab03, exec: local_subprocess
  - name: parmchk2, node: lab03, exec: local_subprocess
---

# LEaP 错误排查指南

## 1. 缺失键/角参数（Missing Bond/Angle Parameters）

**典型错误信息：**
```
Could not find bond parameter for: CA - CX
Could not find angle parameter for: CA - CX - HA
```

**解决方案：**

```bash
# Step 1: 使用 parmchk2 生成缺失参数
antechamber -i ligand.mol2 -fi mol2 -o ligand_prep.mol2 -fo mol2 -c bcc -pf y -nc <net_charge>

# Step 2: 生成 frcmod 文件（包含缺失参数）
parmchk2 -i ligand_prep.mol2 -f mol2 -o ligand.frcmod -a Y

# Step 3: 检查 frcmod 文件
# 标记为 "CAUTION" 的行是 parmchk2 的近似估计，需要人工审查
# 标记为 "SAME" 的行是直接复制的已有参数，通常可信

cat ligand.frcmod
# 关注带有 "***" 或 "CAUTION" 标记的参数
```

**在 tleap 中加载：**
```tclap
source leaprc.protein.ff14SB
source leaprc.gaff2
mol = loadMol2 ligand_prep.mol2
loadAmberParams ligand.frcmod
```

**参数质量检查：**
- 键参数：k 值应在 100-800 kcal/(mol·A^2) 范围
- 角参数：k 值应在 20-200 kcal/(mol·rad^2) 范围
- 扭转参数：Vn/2 值通常 < 20 kcal/mol
- 异常值需查阅文献或 QM 计算验证

## 2. 系统电荷不平衡（Non-neutral System Charge）

**典型错误信息：**
```
Total charge of system is not neutral: -5.000000
```

**排查步骤：**

```bash
# 1. 计算各组分电荷
# 蛋白质：检查 N-端 (+1) 和 C-端 (-1) 是否正确
# 配体：检查 net_charge 参数
# 离子：检查添加的离子数量

# 2. 使用 tleap 检查
charge mol          # 查看总电荷
charge mol.1        # 查看第一个残基的电荷
```

**解决方案：**
```tclap
# 添加抗衡离子中和系统
addIons mol Na+ 0    # 自动计算需要的 Na+ 数量
addIons mol Cl- 0    # 自动计算需要的 Cl- 数量

# 或手动指定数量
addIons mol Na+ 5
addIons mol Cl- 3

# 对于非中性系统（特殊研究需求）：
# 需使用 PME 的细微处理，确保足够大的溶剂盒子
# 建议至少 12 A 缓冲层
```

**配体电荷检查：**
```bash
# 使用 antechamber 时指定正确的净电荷
antechamber -i ligand.pdb -fi pdb -o ligand.mol2 -fo mol2 -c bcc -nc <charge>

# ESP 拟合电荷（更精确，需要 Gaussian 输出）
antechamber -i ligand_gaussian.log -fi gout -o ligand.mol2 -fo mol2 -c resp -nc <charge>
```

## 3. 未知残基错误（Unknown Residue）

**典型错误信息：**
```
Unknown residue: LIG    number: 301    type: terminal
Unknown residue: MSE    number: 45     type: terminal
```

**原因分析：**
- 残基名不在已加载的力场库中
- 配体文件未在 PDB 之前加载
- 残基名拼写错误

**解决方案：**

```tclap
# 方法1：先加载配体库，再加载 PDB
source leaprc.protein.ff14SB
source leaprc.gaff2
loadAmberParams ligand.frcmod
loadOff ligand.lib        # 或先 loadMol2
mol = loadPDB complex.pdb

# 方法2：使用 pdb4amber 预处理
# pdb4amber 会将 MSE 转为 MET 等标准残基
```

```bash
# 配体库文件生成
antechamber -i ligand.pdb -fi pdb -o ligand.mol2 -fo mol2 -c bcc -pf y -nc <charge>
parmchk2 -i ligand.mol2 -f mol2 -o ligand.frcmod

# 在 tleap 中
# mol2 文件可直接作为残基模板加载
```

**检查残基名：**
```bash
# 提取 PDB 中所有残基名
awk '/^ATOM/ || /^HETATM/ {print substr($0,18,3)}' input.pdb | sort -u

# 对比力场中的残基名
grep "residue" $AMBERHOME/dat/leap/cmd/leaprc.protein.ff14SB
```

## 4. 原子类型未找到（Atom Type Not Found）

**典型错误信息：**
```
FATAL: Atom .R<HIS 45>.A<HD1 18> does not have a type!
```

**原因分析：**
- 蛋白质原子使用了 GAFF2 原子类型（应为力场原子类型）
- 配体原子使用了蛋白质力场原子类型（应为 GAFF2）

**解决方案：**

```tclap
# 确保蛋白质和配体使用正确的力场
source leaprc.protein.ff14SB    # 蛋白质
source leaprc.gaff2             # 配体（自动用于 mol2 加载的分子）

# 配体原子类型由 antechamber 分配
antechamber -i ligand.pdb -fi pdb -o ligand.mol2 -fo mol2 -c bcc -pf y
```

**检查原子类型：**
```bash
# 查看 mol2 文件中的原子类型
grep "^@" ligand.mol2    # 查看原子类型列

# 查看 frcmod 中的原子类型
head -20 ligand.frcmod
```

## 5. 异常键长（Unusual Bond Lengths）

**典型错误信息：**
```
Warning: Bond length 18.5 A is too long for atoms:
```

**原因分析：**
- 链断裂（缺失残基）
- TER 卡片缺失或错误
- 氢原子与重原子距离异常
- 二硫键配对错误

**解决方案：**

```bash
# 1. 检查是否有缺失残基导致的链断裂
pdb4amber -i input.pdb -o output.pdb --dry
# 查看日志中的缺失残基报告

# 2. 添加 TER 卡片分隔不同链
# 在不同链的 TER 记录之间插入 TER 行
# pdb4amber 通常会自动处理

# 3. 补全缺失残基（参见 fix-pdb 技能）
```

```tclap
# 在 tleap 中允许较大的键长（谨慎使用）
# crossLink = bond a1 a2
```

## 6. 交替构象导致的重复原子

**典型错误信息：**
```
FATAL: Duplicate atom name: CA in residue 45
```

**解决方案：**
```bash
# 使用 pdb4amber 处理交替构象
pdb4amber -i input.pdb -o output.pdb --altloc occupancy
```

## 7. 增量式调试工作流

推荐的 tleap 调试流程：

```bash
# Step 1: 清洗 PDB（参见 fix-pdb 技能）
pdb4amber -i raw.pdb -o cleaned.pdb --reduce --dry --altloc occupancy

# Step 2: 逐步加载检查
```

```tclap
# 先加载力场
source leaprc.protein.ff14SB
source leaprc.water.opc

# 仅加载蛋白质检查
prot = loadPDB cleaned.pdb
check prot
charge prot

# 检查通过后，再处理配体
source leaprc.gaff2
loadAmberParams ligand.frcmod
# ... 加载配体

# 最后组装完整系统
```

```bash
# Step 3: 检查输出
# tleap 的警告信息分类：
# "Warning" → 通常可忽略但应确认
# "Error" → 必须修复
# "FATAL" → 致命错误，停止执行

# Step 4: 验证拓扑
cpptraj -p prmtop <<EOF
parminfo
EOF
```

## 错误信息速查表

| 错误关键词 | 可能原因 | 首选解决方案 |
|-----------|---------|------------|
| `unknown residue` | 力场中无此残基 | pdb4amber 或 loadOff |
| `does not have a type` | 原子类型缺失 | 检查力场/antechamber |
| `could not find bond/angle` | 参数缺失 | parmchk2 生成 frcmod |
| `not neutral` | 电荷不平衡 | addIons 中和 |
| `too long` | 异常键长 | 检查缺失残基/TER 卡片 |
| `duplicate atom` | 交替构象 | pdb4amber --altloc |
| ` solvent` 相关 | 水模型不匹配 | 检查 leaprc.water.* |
