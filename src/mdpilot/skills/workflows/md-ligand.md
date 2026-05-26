---
name: md-ligand
title: 蛋白-配体复合物 MD
description: 含配体参数化 (antechamber → parmchk2 → tleap) 的蛋白-配体复合物 MD 工作流
tags: [md, ligand, protein-ligand, antechamber, gaff2, complex]
triggers: [ligand md, protein ligand, 配体模拟, 复合物模拟, drug design]
category: workflow
command: /md-ligand
tools:
  - name: pdb4amber, node: lab03, exec: local_subprocess
  - name: antechamber, node: lab03, exec: local_subprocess
  - name: parmchk2, node: lab03, exec: local_subprocess
  - name: tleap, node: lab03, exec: local_subprocess
  - name: pmemd_cuda, node: lab03, exec: local_subprocess
  - name: cpptraj, node: lab03, exec: local_subprocess
---

# 蛋白-配体复合物 MD 工作流

## 1. 蛋白准备

```bash
pdb4amber -i complex.pdb -o protein_clean.pdb --reduce
```

分离蛋白和配体: 蛋白保存为 `protein.pdb`，配体保存为 `ligand.mol2` (需包含正确键序和形式电荷)。

配体结构来源优先级:
1. 实验结构中共结晶配体 (直接从 PDB 提取)
2. 对接 pose (AutoDock Vina/Glide)
3. 手动构建 (Avogadro/MarvinSketch) → 3D 优化 → 导出 mol2

## 2. 配体参数化

### 2.1 antechamber: 原子类型 + 电荷

```bash
antechamber -i ligand.mol2 -fi mol2 \
            -o ligand_ac.mol2 -fo mol2 \
            -c bcc -nc 0 \
            -s 2 -rn LIG
```

- **GAFF2 原子类型**: antechamber 默认使用 GAFF2 (匹配 ff19SB)
- **AM1-BCC 电荷** (`-c bcc`): 速度与精度的最佳平衡; 小分子可用 RESP (`-c rc`) 但需 Gaussian/psi4 计算
- **净电荷** (`-nc`): 必须正确指定; 中性配体为 0，带电配体为 +1/-1 等
- **残基名** (`-rn`): 最多 3 字符，推荐 LIG/UNL/DRG

### 2.2 parmchk2: 缺失力场参数

```bash
parmchk2 -i ligand_ac.mol2 -f mol2 \
         -o ligand.frcmod -s gaff2
```

检查 `ligand.frcmod`:
- 若存在大量 "ATTN" 标记的参数 → 该参数完全缺失，需手动拟合或量子化学计算
- 若仅有少量参数 → GAFF 覆盖良好，可直接使用

### 2.3 验证配体参数

```bash
tleap -f check_leap
```

```tleap
source leaprc.gaff2
LIG = loadMol2 ligand_ac.mol2
loadAmberParams ligand.frcmod
check LIG
```

确认无 "missing parameters" 警告。

## 3. 复合物体系构建

```tleap
source leaprc.protein.ff19SB
source leaprc.water.opc
source leaprc.gaff2

protein = loadPDB protein_clean.pdb
ligand = loadMol2 ligand_ac.mol2
loadAmberParams ligand.frcmod

complex = combine { protein ligand }
solvateBox complex OPCBOX 10.0
addIons complex Na+ 0
addIons complex Cl- 0
addIonsRand complex Na+ 0.15M Cl- 0.15M

saveAmberParm complex prmtop inpcrd
savePDB complex complex_solvated.pdb
quit
```

注意: `combine` 后 Amber 自动为配体生成残基拓扑; 确保蛋白和配体间没有残留键连。

## 4. 能量最小化 — 配体敏感阶段

**阶段 1**: 重原子强限制 (10 kcal), 重点稳定溶剂

**阶段 2**: 骨架限制 (5 kcal), 放松侧链和配体周围

**阶段 3**: 弱限制 (2 kcal), 仅限制蛋白骨架, 配体自由放松

**阶段 4**: 无限制, 全面最小化

配体周围通常需要更多最小化步数; 检查蛋白-配体界面能量是否合理。

## 5. 加热 (NVT, 100ps)

```
 &cntrl
  imin=0, irest=0, ntx=1,
  nstlim=50000, dt=0.002,
  ntc=2, ntf=2,
  ntt=3, gamma_ln=2.0,
  tempi=0.0, temp0=300.0,
  ntr=1, restraint_wt=5.0,
  restraintmask='@CA,C,N|:LIG&!@H',
  ntp=0,
  cut=10.0,
 /
```

骨架 + 配体重原子同时施加 5 kcal 限制, 防止配体在冷启动时脱离结合口袋。

## 6. 平衡 — 逐步释放配体限制

| 阶段 | 时长 | 蛋白限制 | 配体限制 | 系综 |
|------|------|----------|----------|------|
| 密度平衡 | 200ps | 2 kcal | 3 kcal | NPT |
| 平衡 1 | 500ps | 1 kcal | 1 kcal | NPT |
| 平衡 2 | 1ns | 无 | 0.5 kcal | NPT |
| 平衡 3 | 1ns | 无 | 无 | NPT |

关键: 配体限制比蛋白晚释放, 确保口袋周围溶剂先充分平衡。

## 7. 成品模拟

```
 &cntrl
  imin=0, irest=1, ntx=5,
  nstlim=5000000, dt=0.002,
  ntc=2, ntf=2,
  ntt=3, gamma_ln=2.0, temp0=300.0,
  ntp=1, pres0=1.0, taup=5.0,
  ntwx=2500, ntpr=1000,
  cut=10.0,
 /
```

推荐: 至少 200-500 ns; 药物设计项目建议 1 us 以充分采样结合态构象。

## 8. 分析 — 蛋白-配体专有指标

```
cpptraj -p prmtop
trajin prod.nc
autoimage

# 配体 RMSD (结合口袋内)
rms first :LIG&!@H out ligand_rmsd.dat

# 蛋白骨架 RMSD
rms first @CA,C,N out protein_rmsd.dat

# 结合位点 RMSD (配体周围 5 Å)
rms first :LIG<:5&@CA out binding_site_rmsd.dat

# 配体-蛋白氢键
hbond distance out hbond_pl.dat \
  :LIG donor : protein acceptor avgout hbond_pl_avg.dat

# 接触分析
contacts contacts.out :LIG : protein distance 4.0 out contacts.dat

# 配体回转半径 (构象变化)
radgyr out ligand_rg.dat :LIG

# MM-GBSA 准备 (strip 水后保存)
strip :WAT,Na+,Cl-
trajout prod_strip.nc
go
quit
```

关键指标:
- **配体 RMSD**: <1.5 Å 表示稳定结合; >3 Å 可能表示解离或严重构象变化
- **结合位点 RMSD**: 口袋柔性程度
- **氢键**: 持续性 >30% 的氢键是关键相互作用
- **接触残基**: 识别热点残基 (可指导突变实验)
- **MM-GBSA**: 结合自由能估算 (需 MMPBSA.py 单独运行)
