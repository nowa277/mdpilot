---
name: enhanced-sampling
title: 增强采样
description: aMD、GaMD、REMD、SGLD 等增强采样方法
tags: [enhanced-sampling, amd, gamd, remd, sgld, accelerated]
triggers: [enhanced sampling, 增强采样, accelerated md, GaMD, REMD]
category: workflow
command: /enhanced-sampling
tools:
  - name: pmemd_cuda, node: lab03, exec: local_subprocess
  - name: pmemd_mpi, node: lab03, exec: local_subprocess
  - name: cpptraj, node: lab03, exec: local_subprocess
---

# 增强采样

本 Skill 覆盖 AMBER 中主要的增强采样方法：aMD、GaMD、REMD 和 SGLD。这些方法用于克服常规 MD 中常见的采样不足问题，探索更广阔的构象空间。

## 方法选择指南

| 场景 | 推荐方法 | 优势 | 备注 |
|------|----------|------|------|
| 蛋白质构象变化探索 | aMD (dual-boost) | 实现简单，加速明显 | 需要重新加权 |
| 精确自由能面重构 | GaMD | 高斯化增强分布，易重加权 | 推荐首选 |
| 跨越高能垒 (折叠/去折叠) | T-REMD | 物理意义明确 | 计算资源消耗大 |
| pH 依赖构象变化 | pH-REMD | 结合 pH 效应 | 需要特殊准备 |
| 快速构象搜索 | SGLD | 低摩擦限，加速明显 | 适合初步探索 |

## aMD — 加速分子动力学

### 原理

在势能面上添加增强势：

```
V*(r) = V(r)                        当 V(r) >= E
V*(r) = V(r) + (E - V(r))²/(α + E - V(r))   当 V(r) < E
```

E 为阈值能量，α 为影响势能形状的参数。

### Dual-Boost 参数确定

aMD 通常使用 dual-boost：对总势能和二面角势能分别加 boost。

1. **先运行短时间常规 MD**（1-5 ns），获取平均势能。

```bash
# 从 mdout 中提取平均势能
grep "Etot" mdout.out | tail -100 | awk '{sum+=$3; n++} END {print sum/n}'
```

2. **计算 boost 参数**：

```
E_dihedral = <V_dihedral> + 4 * N_residues    (或 3.5 * N_residues)
alpha_dihedral = 4 * N_residues * 0.2          (或 N_residues * 0.2)

E_total = <V_total> + 0.2 * N_atoms
alpha_total = N_atoms * 0.2
```

### pmemd 输入参数

```ini
Accelerated MD (dual boost)
 &cntrl
  irest=1, ntx=5,
  nstlim=2500000, dt=0.002,
  ntc=2, ntf=1,
  ntt=3, gamma_ln=2.0, temp0=300.0,
  ntp=1, pres0=1.0, taup=2.0,
  ntb=2,
  cut=10.0,
  iamd=3,
  ethresh_d=V_dihedral_mean + boost_d,
  alpha_d=alpha_dihedral,
  ethresh_p=V_total_mean + boost_p,
  alpha_p=alpha_total,
 /
```

`iamd=1` 为仅总势能 boost，`iamd=2` 为仅二面角 boost，`iamd=3` 为 dual-boost。

### aMD 轨迹重加权

```python
# Maclaurin 展开重加权 (近似)
import numpy as np
# 从 amd.log 或 mdout 提取 boost 能量
# weight_i = exp(beta * delta_V_i)
weights = np.exp(beta * boost_energies)
# 归一化
weights /= weights.sum()
```

## GaMD — 高斯加速分子动力学

### 原理

GaMD 在 aMD 基础上增加高斯分布约束，使增强势的分布接近高斯分布，极大简化了重加权过程。

### Gamd 输入变量

```ini
Gaussian Accelerated MD
 &cntrl
  irest=1, ntx=5,
  nstlim=5000000, dt=0.002,
  ntc=2, ntf=1,
  ntt=3, gamma_ln=2.0, temp0=300.0,
  ntp=1, pres0=1.0, taup=2.0,
  ntb=2,
  cut=10.0,
  iamd=3,
  ethresh_d=-1.0,        # 自动确定
  alpha_d=-1.0,           # 自动确定
  ethresh_p=-1.0,         # 自动确定
  alpha_p=-1.0,           # 自动确定
 /
 &gamd
  igamd=2,               # 1=basic, 2=upper-bound (推荐)
  ntcmd=200000,          # conventional MD 步数用于统计
  ntleb=200000,          # 上界估计步数
  ntavg=5000,            # 更新 boost 参数的平均间隔
  dtavg=5000,            # 更新间隔
 /
```

- `igamd=1`：基本 GaMD (lower bound)
- `igamd=2`：上界 GaMD（推荐，boost 更强更稳定）

### GaMD 重加权 — PyReweighting

```bash
# 使用 AMBER 自带的 PyReweighting 模块
python PyReweighting.py -i gamd.nc -p complex.prmtop \
    -s 5000 -t 300.0 \
    --EMmap emmap.dat --cutoff 10.0
```

PyReweighting 支持：
- 1D/2D/3D 自由能面重构
- Maclaurin 展开或精确重加权
- Cumulant expansion（推荐，对高斯分布最优）

## REMD — 副本交换分子动力学

### 温度副本交换 (T-REMD)

#### 温度列表生成

使用 AMBER 工具或经验公式确定温度列表：

```python
# 使用 AMBER 的 remd templategen 或手动计算
# 目标交换率 ~20-30%
# T_list = [300, 310, 320, 332, 345, 358, 372, 387, 403, 420]
# 交换率取决于 ΔT，通常 5-15 K (小体系) 或 2-5 K (大体系)
```

#### pmemd.MPI 输入文件

```ini
T-REMD
 &cntrl
  irest=1, ntx=5,
  nstlim=500000, dt=0.002,
  ntc=2, ntf=1,
  ntt=3, gamma_ln=2.0, temp0=300.0,
  ntp=1, pres0=1.0, taup=2.0,
  ntb=2,
  cut=10.0,
  numexchg=1000,        # 交换次数
 /
```

#### 运行命令

```bash
mpirun -np 12 pmemd.MPI -O -i remin-0.in -o rem.out \
    -p complex.prmtop -c complex.inpcrd \
    -r rem#.rst -x rem#.nc \
    -inf rem.mdinfo -rem 3
```

`-rem 3` 表示温度副本交换。`#` 被替换为副本编号。

#### 交换率分析

```bash
# 使用 cpptraj 分析
cpptraj -p complex.prmtop <<EOF
remlog rem.log
trajin rem0.nc
...
EOF
```

目标交换率 20-30%。过低需减小 ΔT，过高则浪费计算资源。

### pH 副本交换 (pH-REMD)

详见 `/md-constant-ph` Skill。使用不同的 pH 值代替温度进行副本交换。

## SGLD — 自引导 Langevin 动力学

### 原理

SGLD 在 Langevin 动力学中引入局部平均力作为引导，加速低频运动。

```ini
Self-Guided Langevin Dynamics
 &cntrl
  irest=1, ntx=5,
  nstlim=5000000, dt=0.002,
  ntc=2, ntf=1,
  ntt=3, gamma_ln=2.0, temp0=300.0,
  ntp=1, pres0=1.0, taup=2.0,
  ntb=2,
  cut=10.0,
  isgld=1,              # 启用 SGLD
  sgft=0.2,             # 引导因子 (0.1-1.0)
  tempsg=300.0,         # 引导温度
 /
```

- `isgld=1`：基本 SGLD
- `isgld=2`：SGLD with guiding averaging
- `sgft`：引导因子，值越大加速越强但精度降低

SGLD 适合快速构象搜索和初步探索，不推荐用于精确自由能计算。

## 实践建议

1. **先常规 MD 后增强采样**：先运行 5-10 ns 常规 MD 确认体系稳定，再切换到增强采样。
2. **GaMD > aMD**：GaMD 的重加权更可靠，推荐优先使用。
3. **REMD 副本数**：至少 2 倍于独立构象数；过多副本浪费资源。
4. **分析时去除平衡期**：增强采样的前 10-20% 数据通常丢弃。
5. **收敛性检查**：对独立运行的多个轨迹比较自由能面或分布，确认收敛。
