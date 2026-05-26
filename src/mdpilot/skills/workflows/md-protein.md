---
name: md-protein
title: 标准蛋白 MD 模拟
description: 能量最小化 → 加热 → 平衡 → 成品模拟的完整蛋白 MD 工作流
tags: [md, protein, simulation, amber, minimization, equilibration, production]
triggers: [standard md, protein md, 蛋白模拟, MD simulation, 蛋白质模拟]
category: workflow
command: /md-protein
tools:
  - name: pdb4amber, node: lab03, exec: local_subprocess
  - name: reduce, node: lab03, exec: local_subprocess
  - name: tleap, node: lab03, exec: local_subprocess
  - name: pmemd_cuda, node: lab03, exec: local_subprocess
  - name: cpptraj, node: lab03, exec: local_subprocess
---

# 标准蛋白 MD 模拟工作流

## 1. PDB 准备

```bash
# 清理 PDB 并添加氢原子
pdb4amber -i protein.pdb -o protein_clean.pdb --reduce
```

检查要点:
- 缺失残基 (Modeller 补全或截断)
- 缺失重原子
- 组氨酸质子化状态 (HIS/HIE/HID/HIP): 活性位点需手动确认，其余由 Reduce 自动判断
- 非标准残基处理 (金属离子、辅因子、二硫键)

## 2. 体系构建 (tleap)

```bash
tleap -f build.leap
```

```tleap
source leaprc.protein.ff19SB
source leaprc.water.opc
protein = loadPDB protein_clean.pdb
solvateBox protein OPCBOX 10.0
addIons protein Na+ 0
addIons protein Cl- 0
addIonsRand protein Na+ 0.15M Cl- 0.15M
saveAmberParm protein prmtop inpcrd
quit
```

- 力场: ff19SB + OPC 水模型 (ff14SB + TIP3P 为备选)
- 溶剂盒: 正十二面体 (更节省原子数) 或长方体, 10 Å 缓冲
- 中和电荷后加 0.15 M NaCl (Joung-Cheatham 离子参数已内置于 ff19SB)

## 3. 能量最小化 — 三阶段

**阶段 1**: 10 kcal/mol/A² 蛋白重原子限制

```
minimization stage 1
 &cntrl
  imin=1, maxcyc=10000, ncyc=5000,
  ntr=1, restraint_wt=10.0,
  restraintmask='@CA,C,N,O',
  cut=10.0,
 /
```

**阶段 2**: 5 kcal/mol/A² 限制, 10000 步

**阶段 3**: 无限制, 10000 步

每个阶段后检查能量是否收敛; 若 Eptot 仍在大幅下降则延长步数。

## 4. 加热 (NVT, 0→300K, 100ps)

```
Heating 0->300K (NVT)
 &cntrl
  imin=0, irest=0, ntx=1,
  nstlim=50000, dt=0.002,
  ntc=2, ntf=2,
  ntt=3, gamma_ln=2.0,
  tempi=0.0, temp0=300.0,
  ntr=1, restraint_wt=5.0,
  restraintmask='@CA,C,N',
  ntp=0,
  cut=10.0,
 /
```

Langevin 恒温器 (ntt=3) + SHAKE (ntc=2, 氢键约束) + 骨架弱限制 5 kcal。

## 5. 密度平衡 (NPT, 200ps)

```
 &cntrl
  imin=0, irest=1, ntx=5,
  nstlim=100000, dt=0.002,
  ntc=2, ntf=2,
  ntt=3, gamma_ln=2.0, temp0=300.0,
  ntp=1, pres0=1.0, taup=2.0,
  ntr=1, restraint_wt=2.0,
  restraintmask='@CA,C,N',
  cut=10.0,
 /
```

各向同性恒压 (ntp=1), 1 bar, 弛豫时间 2 ps, 逐步放松骨架限制。

## 6. 平衡 (NPT, 无限制, 1-5ns)

```
 &cntrl
  imin=0, irest=1, ntx=5,
  nstlim=500000, dt=0.002,
  ntc=2, ntf=2,
  ntt=3, gamma_ln=2.0, temp0=300.0,
  ntp=1, pres0=1.0, taup=2.0,
  cut=10.0,
 /
```

移除所有限制。检查密度、温度、能量是否平稳; RMSD 是否收敛平台。

## 7. 成品模拟

```
 &cntrl
  imin=0, irest=1, ntx=5,
  nstlim=5000000, dt=0.002,
  ntc=2, ntf=2,
  ntt=3, gamma_ln=2.0, temp0=300.0,
  ntp=1, pres0=1.0, taup=5.0,
  ntwx=5000, ntpr=1000, ntwr=50000,
  cut=10.0,
 /
```

- 典型: 100-500 ns (nstlim 按需调整)
- 轨迹输出: 每 10 ps (ntwx=5000)
- 压缩弛豫: taup=5.0 (成品阶段放宽以减少耦合干扰)

## 8. 分析 (cpptraj)

```
cpptraj -p prmtop
trajin prod.nc
rms first @CA out rmsd_ca.dat
rms first : protein&!@H out rmsd_backbone.dat
atomicfluct out rmsf.dat @CA byatom
radgyr out rog.dat : protein&!@H
average avg.pdb : protein&!@H
hbond : protein donor : protein acceptor out hbond.dat
strip :WAT
autoimage
trajout prod_strip.nc
go
quit
```

关键指标:
- **C-alpha RMSD**: 判断蛋白整体稳定性 (<2-3 Å 通常正常)
- **RMSF**: 识别柔性区域 (loop、末端)
- **回转半径 (Rg)**: 折叠状态监控
- **氢键**: 二级结构稳定性
- **平均结构**: 生成代表性构象用于后续对接/分析
