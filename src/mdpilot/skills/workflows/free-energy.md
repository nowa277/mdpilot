---
name: free-energy
title: 自由能计算
description: MM/PBSA、TI、FEP 等结合自由能计算方法
tags: [free-energy, mmpbsa, ti, fep, binding, thermodynamic]
triggers: [free energy, mmpbsa, 自由能, 结合能, FEP, TI]
category: workflow
command: /free-energy
tools:
  - name: pmemd_cuda, node: lab03, exec: local_subprocess
  - name: tleap, node: lab03, exec: local_subprocess
  - name: mmpbsa_py, node: lab03, exec: local_subprocess
  - name: cpptraj, node: lab03, exec: local_subprocess
---

# 自由能计算

本 Skill 覆盖 AMBER 中主要的结合自由能计算方法：端点法（MM/PBSA、MM/GBSA）和炼金术法（TI、FEP）。

## 方法选择指南

| 场景 | 推荐方法 | 精度 | 计算成本 |
|------|----------|------|----------|
| 大规模虚拟筛选 / 排序 | MM/GBSA | 中 | 低 |
| 药物优化 SAR 分析 | MM/PBSA | 中高 | 中 |
| 精确结合自由能 | TI / FEP | 高 | 高 |
| 突变扫描 ( Ala scan ) | MM/PBSA per-residue | 中 | 中 |

## MM/PBSA 与 MM/GBSA 端点法

### 基本原理

结合自由能分解为：

```
ΔG_bind = G_complex - (G_receptor + G_ligand)
        = ΔE_MM + ΔG_sol - TΔS
```

其中 ΔE_MM 为分子力学能（真空），ΔG_sol 为溶剂化自由能（极性 + 非极性），TΔS 为构象熵。

### MMPBSA.py 使用流程

1. **准备轨迹**：从平衡后的 MD 轨迹中提取快照，去除溶剂和离子。

```bash
# cpptraj 去溶剂
cpptraj -p complex.prmtop <<EOF
trajin prod.nc
strip :WAT,Cl-,Na+
trajout snapshot.nc netcdf
EOF
```

2. **编写 MMPBSA.in 输入文件**：

```ini
# MM/GBSA (GB-OBC2 model)
&general
   startframe=1, endframe=1000, interval=5,
   verbose=2,
/
&gb
   igb=5, saltcon=0.150,
/
```

```ini
# MM/PBSA (3-trajectory protocol)
&general
   startframe=1, endframe=1000, interval=5,
   verbose=2,
/
&pb
   istrng=0.150, fillratio=4.0, inp=1,
   radiopt=0,
/
```

3. **运行计算**：

```bash
MMPBSA.py -O -i mmpbsa.in -sp complex_solvated.prmtop \
    -cp complex.prmtop -rp receptor.prmtop -lp ligand.prmtop \
    -y snapshot.nc
```

### Decoy 生成与验证

为验证 MM/PBSA 区分正确结合pose与decoy的能力：

- 使用 `cpptraj` 的 `cluster` 命令生成代表性构象
- 对每个 cluster 中心计算 MM/PBSA 能量
- 绘制 enrichment plot 评估区分能力

### Per-residue 能量分解

```ini
&general
   startframe=1, endframe=500, interval=5,
   verbose=2,
/
&gb
   igb=5, saltcon=0.150,
/
&decomp
   idecomp=2, print_residue_with_name=1,
   csv_format=1,
/
```

`idecomp=1` 为按残基对分解，`idecomp=2` 为按单个残基分解。输出 CSV 可直接用于热图绘制。

## TI / FEP 炼金术法

### 基本原理

通过逐步将一个配体（或侧链）"突变"为另一个，沿 λ 反应坐标积分自由能导数：

```
ΔG = ∫₀¹ ⟨∂V/∂λ⟩_λ dλ
```

### 双拓扑 (Dual Topology)

在 AMBER 中使用 `tleap` 的 `loadAmberParams` 和 `addIons` 构建 dual-topology 系统。两个配体/残基同时存在于体系中，通过 λ 控制从状态 A 到状态 B 的切换。

### Softcore 势能

避免端点奇点问题，使用 softcore 势能：

```
V_sc = λ (1-λ) / (α + λ (1-λ)) × correction_term
```

关键参数（`&cntrl` 中设置）：

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| `icfe` | 1 | 启用 free energy 计算 |
| `ifsc` | 1 | 启用 softcore 势能 |
| `scalpha` | 0.5 | softcore alpha 参数 |
| `scbeta` | 0.0 | softcore beta 参数 |
| `logdvdl` | 1 | 输出 dV/dλ 到 mdout |

### Lambda Windows

```bash
# 生成 λ = 0.0, 0.1, 0.2, ..., 1.0 共 11 个窗口
for i in $(seq 0 10); do
    lambda=$(echo "scale=4; $i / 10" | bc)
    # 编辑 pmemd 输入文件中 clambda 值
    sed "s/clambda = .*/clambda = $lambda/" ti.tmpl > ti_lambda${i}.in
done
```

推荐窗口数：

- **小扰动**（烷基链增长、卤素替换）：9-11 个窗口
- **大扰动**（环替换、完全不同骨架）：15-21 个窗口

### TI 输入文件示例

```ini
Single topology TI
 &cntrl
  irest=0, ntx=1,
  nstlim=500000, dt=0.002,
  ntc=2, ntf=1,
  ntt=3, gamma_ln=2.0, temp0=300.0,
  ntp=1, pres0=1.0, taup=2.0,
  ntb=2,
  cut=10.0,
  icfe=1, clambda=0.5,
  ifsc=1, scalpha=0.5,
  logdvdl=1,
 /
```

### 分析 TI 数据

使用 `analyze_ti.py`（AMBER 工具）或手动积分：

```python
import numpy as np
# 从各 lambda 窗口的 mdout 中提取 <dV/dl> 值
lambdas = [0.0, 0.1, 0.2, ..., 1.0]
dvdl_means = [mean_dvdl_for_each_window]
deltaG = np.trapz(dvdl_means, lambdas)
```

## 实践建议

1. **轨迹预处理**：确保 RMSD 收敛后再取样；使用足够的平衡时间（至少 2-5 ns）。
2. **熵计算**：正则模分析（Nmode）计算成本高，仅在需要绝对自由能时使用；对 SAR 排序，TΔS 通常近似为常数可省略。
3. **内坐标一致性**：MM/PBSA 3-trajectory 方法要求 receptor 和 ligand 轨迹来自复合物模拟拆分，1-trajectory 方法更稳定但忽略构象变化。
4. **TI 收敛检查**：每个 λ 窗口需确认 <dV/dλ> 收敛；前向/后向 BAR 分析可验证滞后性。
5. **误差估计**：使用 block averaging 或 bootstrap 方法报告统计误差。
