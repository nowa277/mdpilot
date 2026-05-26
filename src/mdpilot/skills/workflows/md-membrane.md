---
name: md-membrane
title: 膜蛋白 MD
description: 含膜构建 (packmol-memgen/CHARMM-GUI) 与半各向同性平衡的膜蛋白 MD 工作流
tags: [md, membrane, lipid, bilayer, packmol, membrane-protein]
triggers: [membrane md, 膜蛋白, lipid bilayer, 脂质双层, 嵌入膜]
category: workflow
command: /md-membrane
tools:
  - name: pdb4amber, node: lab03, exec: local_subprocess
  - name: tleap, node: lab03, exec: local_subprocess
  - name: pmemd_cuda, node: lab03, exec: local_subprocess
  - name: cpptraj, node: lab03, exec: local_subprocess
---

# 膜蛋白 MD 工作流

## 1. 蛋白准备与定向

```bash
pdb4amber -i membrane_protein.pdb -o protein_clean.pdb --reduce
```

膜蛋白特殊检查:
- 确认跨膜区段 (TM helices) 完整无缺失
- 检查膜内残基疏水性 (应为 Leu/Ile/Val/Phe/Ala 等)
- N/C 末端处理: 膜内末端需 ACE/NME 封闭
- 膜蛋白晶体中的去垢剂分子 (BOG/LMG 等) 需移除
- 配体/辅因子: 视黄醛 (RET)、血红素 (HEM) 等需保留并参数化

蛋白定向: 使用 Orientations of Proteins in Membranes (OPM) 数据库或 PPM server 确定蛋白相对于膜平面的正确朝向。膜法线默认沿 Z 轴。

## 2. 膜构建

### 方案 A: packmol-memgen (推荐, Amber 原生)

```bash
packmol-memgen --pdb protein_clean.pdb \
               --lipid POPC \
               --xpad 15 --ypad 15 \
               --salt --saltcon 0.15 \
               --ratio 1.0
```

常用脂质: POPC (哺乳动物), POPE/POPG (细菌, 3:1 比例), DPPC (饱和), DLPC (短链)

### 方案 B: CHARMM-GUI Membrane Builder

上传蛋白 PDB → 选择脂质组成 → 生成 Amber 格式拓扑文件。适合复杂脂质混合物 (如胆固醇 + 多种磷脂)。

### 方案 C: tleap 手动构建

```tleap
source leaprc.protein.ff19SB
source leaprc.lipid21
source leaprc.water.opc

protein = loadPDB protein_clean.pdb
# 预置膜坐标 (来自 packmol-memgen 或 CHARMM-GUI)
lipid = loadPDB lipid_membrane.pdb

complex = combine { protein lipid }
solvateBox complex OPCBOX 10.0 iso
addIons complex Na+ 0
addIons complex Cl- 0
addIonsRand complex Na+ 0.15M Cl- 0.15M

saveAmberParm complex prmtop inpcrd
quit
```

注意: `solvateBox ... iso` 沿膜平面上方/下方添加水层, 避免水分子进入膜内部。

## 3. 能量最小化 — 膜敏感

**阶段 1**: 脂质 + 蛋白重原子强限制 (10 kcal), 仅优化水 + 离子

**阶段 2**: 蛋白骨架限制 (5 kcal), 脂质限制 (5 kcal), 放松水/离子/尾端

**阶段 3**: 蛋白骨架限制 (2 kcal), 脂质自由放松

**阶段 4**: 无限制, 全面最小化

膜体系通常需要更多步数 (总计 50k-80k 步) 因原子数多且脂质尾端初始堆积可能不合理。

## 4. 两阶段加热

### 阶段 1: 0→100K (NVT, 50ps)

```
 &cntrl
  imin=0, irest=0, ntx=1,
  nstlim=25000, dt=0.001,
  ntc=2, ntf=2,
  ntt=3, gamma_ln=3.0,
  tempi=0.0, temp0=100.0,
  ntr=1, restraint_wt=10.0,
  restraintmask='@CA,C,N,O & : protein',
  ntp=0,
  cut=10.0,
 /
```

注意: **dt=0.001** (1 fs), 膜体系初始加热使用更短时间步以保证稳定。

### 阶段 2: 100→300K (NVT, 100ps)

```
 &cntrl
  imin=0, irest=1, ntx=5,
  nstlim=50000, dt=0.002,
  ntc=2, ntf=2,
  ntt=3, gamma_ln=2.0,
  temp0=300.0,
  ntr=1, restraint_wt=5.0,
  restraintmask='@CA,C,N & : protein',
  ntp=0,
  cut=10.0,
 /
```

## 5. 半各向同性平衡 (关键步骤)

```
 &cntrl
  imin=0, irest=1, ntx=5,
  nstlim=250000, dt=0.002,
  ntc=2, ntf=2,
  ntt=3, gamma_ln=2.0, temp0=300.0,
  ntp=3, pres0=1.0, taup=10.0,
  ntr=1, restraint_wt=1.0,
  restraintmask='@CA,C,N & : protein',
  cut=10.0,
 /
```

- **ntp=3**: 半各向同性恒压 (XY 方向独立缩放, Z 方向独立缩放)
- **taup=10.0**: 压缩弛豫时间较长, 避免膜面积波动过大

逐步释放限制:
1. 500ps: 蛋白骨架 5 kcal, 脂质头部 2 kcal
2. 1ns: 蛋白骨架 2 kcal, 脂质无限制
3. 2ns: 蛋白骨架 0.5 kcal
4. 2ns: 无限制

总平衡时间建议 5-10 ns, 比可溶蛋白长得多。判断标准: 膜面积 (XY box dimensions) 趋于稳定, 面积/脂质收敛至实验值附近 (如 POPC: 64-68 A^2)。

## 6. 成品模拟

```
 &cntr
  imin=0, irest=1, ntx=5,
  nstlim=5000000, dt=0.002,
  ntc=2, ntf=2,
  ntt=3, gamma_ln=1.0, temp0=300.0,
  ntp=3, pres0=1.0, taup=20.0,
  ntwx=5000, ntpr=1000,
  cut=10.0,
 /
```

- **gamma_ln=1.0**: 成品阶段减小碰撞频率, 减少对膜动力学的人为干扰
- **taup=20.0**: 进一步放松压力耦合
- 典型时长: 200-1000 ns; 离子通道等功能性模拟建议 1 us+

## 7. 盒子尺寸监控

膜体系必须持续监控盒子维度:

```
cpptraj -p prmtop
trajin prod.nc
autoimage
vol out volume.dat
outtraj box_dims.dat info  # X, Y, Z dimensions
go
quit
```

警告信号:
- Z 轴急剧缩小 → 水层不够, 蛋白跨周期边界自相互作用
- XY 面积持续漂移 → 膜未平衡
- 面积/脂质偏离实验值 >10% → 检查力场参数

## 8. 分析 — 膜蛋白专有

```
cpptraj -p prmtop
trajin prod.nc
autoimage

# 蛋白 RMSD
rms first @CA out protein_rmsd.dat

# 跨膜区 vs 胞外区 RMSF
atomicfluct out rmsf_tm.dat : protein&: protein<:5 rmsf out rmsf_extra.dat

# 膜厚度
distance out membrane_thickness.dat \
  :LIPID@P :LIPID@P upper lower

# 脂质序参数
lipidscd out scd.dat :LIPID

# 蛋白-脂质接触
contacts lipid_contacts.dat : protein :LIPID distance 4.0

# 水孔道 (通道蛋白)
watershell out watershell.dat : protein lower 3.5 upper 5.0
go
quit
```

关键指标:
- **面积/脂质**: 与实验值对比 (POPC ~64 A^2, POPE ~56 A^2)
- **膜厚度**: 约 37-42 A (取决于脂质类型)
- **序参数 SCD**: 脂质尾端有序度, 应与 NMR 实验数据吻合
- **蛋白倾斜角**: 跨膜螺旋相对于膜法线的角度
- **通道水分子**: 离子通道的水渗透通量
