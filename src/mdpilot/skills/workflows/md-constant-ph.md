---
name: md-constant-ph
title: 恒 pH MD
description: 恒 pH 分子动力学模拟，支持隐式/显式溶剂及 pH-REMD
tags: [constant-ph, cphmd, protonation, ph, titration]
triggers: [constant ph, CpHMD, 恒pH, 质子化, pKa]
category: workflow
command: /md-constant-ph
tools:
  - name: pdb4amber, node: lab03, exec: local_subprocess
  - name: tleap, node: lab03, exec: local_subprocess
  - name: cpinutil_py, node: lab03, exec: local_subprocess
  - name: pmemd, node: lab03, exec: local_subprocess
  - name: cphstats, node: lab03, exec: local_subprocess
---

# 恒 pH 分子动力学

本 Skill 覆盖 AMBER 恒 pH MD (CpHMD) 模拟工作流，支持隐式溶剂、显式溶剂和 pH-REMD 模式。CpHMD 允许可滴定残基在模拟过程中动态改变质子化状态，从而研究 pH 依赖的构象变化并预测 pKa 值。

## 工作流概览

```
PDB → pdb4amber --constantph → tleap → cpinutil.py → pmemd/pmemd.MPI → cphstats
```

## Step 1: 结构预处理 — pdb4amber

```bash
pdb4amber -i protein.pdb -o protein_cph.pdb --constantph
```

`--constantph` 标志执行以下残基重命名：

| 原始残基 | 重命名为 | 说明 |
|----------|----------|------|
| ASP | AS4 | 可滴定的天冬氨酸 |
| GLU | GL4 | 可滴定的谷氨酸 |
| HIS | HIP | 可滴变的组氨酸 (δ 和 ε 两个位点) |

其他可滴定残基（CYS、TYR、LYS）视研究目的手动处理。

### 手动残基选择

如果只想让部分残基可滴定（例如排除埋藏在内部的 ASP）：

1. 运行 `pdb4amber --constantph` 转换所有残基。
2. 手动编辑 PDB 文件，将不需要滴定的残基改回原始名称（AS4 → ASP, GL4 → GLU, HIP → HIS）。
3. 对 HIS 需决定质子化状态：HID (Nδ), HIE (Nε), 或保持 HIP (双质子化可滴变)。

## Step 2: 系统构建 — tleap

```bash
tleap -f build_cph.leap
```

### 隐式溶剂 tleap 脚本

```bash
source leaprc.protein.ff14SB
source leaprc.constph

# 加载可滴定残基力场参数
loadAmberParams constph.lib

mol = loadPDB protein_cph.pdb

# 隐式溶剂: 使用 GB-OBC2 模型
set default PBRadii bondi

solvateCap mol TIP3PBOX {0.0 0.0 0.0} 10.0

saveAmberParm mol complex.prmtop complex.inpcrd
quit
```

### 显式溶剂 tleap 脚本

```bash
source leaprc.protein.ff14SB
source leaprc.constph

mol = loadPDB protein_cph.pdb

# 显式溶剂
solvateOct mol TIP3PBOX 10.0

# 添加抗衡离子
addIons mol NaCl 0.15

saveAmberParm mol complex.prmtop complex.inpcrd
quit
```

## Step 3: 质子化状态文件 — cpinutil.py

cpinutil.py 生成 `.cpin` 文件，定义可滴定残基的质子化状态空间。

```bash
cpinutil.py -p complex.prmtop -i cpin.input -o cpin.cpin
```

### cpinutil.py 输入文件

```ini
&cntrl
  cpin_type = SINGLE,           # SINGLE 或 PH_REMD
  output_level = 1,
  solvent_type = implicit,      # implicit 或 explicit
  procs_per_replica = 1,
/
```

对于 pH-REMD：

```ini
&cntrl
  cpin_type = PH_REMD,
  output_level = 1,
  solvent_type = explicit,      # 显式溶剂 CpHMD
  procs_per_replica = 4,
  num_cpus = 32,
/
```

### 关键参数

| 参数 | 说明 |
|------|------|
| `CPINType` | SINGLE: 单 pH 值; PH_REMD: 多 pH 副本交换 |
| `solvent_type` | implicit: GB 隐式; explicit: TIP3P 显式 |
| `procs_per_replica` | 每个 pH 副本使用的 CPU 数 |

## Step 4: CpHMD 模拟 — pmemd

### 隐式溶剂 CpHMD (icnstph=1)

```ini
Constant pH MD - Implicit Solvent
 &cntrl
  irest=0, ntx=1,
  nstlim=10000000, dt=0.002,
  ntc=2, ntf=1,
  ntt=3, gamma_ln=5.0, temp0=300.0,
  ntb=0,                  # 隐式溶剂无周期性
  cut=999.0,              # 隐式溶剂使用无穷截断
  igb=5,                  # GB-OBC2
  saltcon=0.150,
  icnstph=1,              # 隐式溶剂恒 pH
  ntcnstph=100,           # 每 100 步尝试一次质子化状态变化
  solvph=7.0,             # 模拟 pH 值
  cnstph_nstep_int=0,
 /
```

| 参数 | 说明 |
|------|------|
| `icnstph` | 1 = 隐式溶剂 CpHMD, 2 = 显式溶剂 CpHMD |
| `ntcnstph` | 质子化状态尝试频率（步数间隔） |
| `solvph` | 环境 pH 值 |

### 显式溶剂 CpHMD (icnstph=2)

```ini
Constant pH MD - Explicit Solvent
 &cntrl
  irest=0, ntx=1,
  nstlim=10000000, dt=0.002,
  ntc=2, ntf=1,
  ntt=3, gamma_ln=2.0, temp0=300.0,
  ntp=1, pres0=1.0, taup=2.0,
  ntb=2,
  cut=10.0,
  icnstph=2,              # 显式溶剂恒 pH
  ntcnstph=100,
  solvph=7.0,
  nstlim_out=1000,
 /
```

### pH-REMD 运行

pH-REMD 使用 pmemd.MPI 在多个 pH 值间进行副本交换：

```bash
mpirun -np 24 pmemd.MPI -O \
    -i cphremd.in -o cphremd.out \
    -p complex.prmtop -c complex.inpcrd \
    -r cphremd.rst -x cphremd.nc \
    -cpin cpin.cpin \
    -cprestart cphrestart \
    -inf cphremd.mdinfo \
    -rem 4
```

`-rem 4` 表示 pH-REMD 模式。每个副本运行在不同的 pH 值，副本间定期交换 pH 值。

pH-REMD 输入文件中 `solvph` 设置为初始 pH，实际各副本的 pH 由 `.cpin` 文件决定。

## Step 5: pKa 分析 — cphstats

```bash
# 提取质子化状态轨迹
cphstats -i cphrestart -p complex.prmtop \
    --ph_values 0.0,1.0,2.0,3.0,4.0,5.0,6.0,7.0,8.0,9.0,10.0,11.0,12.0 \
    -o protonation.dat
```

### 计算残基 pKa

```bash
# 生成各残基在不同 pH 下的质子化分数
cphstats -i cphrestart \
    --titration_curves \
    -o titration.dat
```

输出文件包含每个可滴定残基在不同 pH 下的质子化概率 S(pH)。拟合 Henderson-Hasselbalch 方程：

```
S(pH) = 1 / (1 + 10^(pH - pKa))
```

即可得到预测的 pKa 值。

### 可视化分析

```python
import numpy as np
import matplotlib.pyplot as plt

# 从 cphstats 输出读取质子化分数
ph_values = np.arange(0, 13)
# 示例: 残基 AS4-45 的质子化分数
fraction_protonated = [...]  # 从 titration.dat 读取

plt.plot(ph_values, fraction_protonated, 'o-')
plt.xlabel('pH')
plt.ylabel('Protonation Fraction')
plt.title('Titration Curve: AS4-45')
plt.axhline(0.5, ls='--', color='gray')
plt.grid(True)
plt.savefig('titration_curve.png')
```

## 实践建议

1. **隐式 vs 显式**：隐式溶剂 CpHMD 计算快 5-10 倍，适合初步筛选和 pKa 预测；显式溶剂更准确，适合研究 pH 依赖的构象变化。
2. **采样充分性**：每个质子化状态的转换应发生数百次以上才能收敛。建议总模拟时间不少于 50-100 ns。
3. **ntcnstph 选择**：隐式溶剂推荐 100 步；显式溶剂推荐 1000 步（需要更长间隔以允许溶剂弛豫）。
4. **pH 范围选择**：pH-REMD 的 pH 范围应覆盖目标残基的预期 pKa ± 3 个单位。
5. **模型 pH**：参考实验 pKa 数据（PROPKA 预测值）确定哪些残基需要可滴定处理；内部疏水残基通常应固定其质子化状态。
6. **力场选择**：推荐 ff14SB + GB-OBC2 (igb=5)，这是 AMBER CpHMD 最广泛验证的组合。
