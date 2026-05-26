---
name: md-nucleic
title: 核酸 MD
description: DNA/RNA 模拟工作流，使用 OL15/OL24/OL3 专用力场
tags: [md, nucleic, dna, rna, ol15, ol3, nucleic-acid]
triggers: [nucleic md, dna simulation, rna simulation, 核酸模拟, DNA模拟, RNA模拟]
category: workflow
command: /md-nucleic
tools:
  - name: pdb4amber, node: lab03, exec: local_subprocess
  - name: tleap, node: lab03, exec: local_subprocess
  - name: pmemd_cuda, node: lab03, exec: local_subprocess
  - name: cpptraj, node: lab03, exec: local_subprocess
---

# 核酸 MD 工作流

## 1. 结构准备

```bash
pdb4amber -i nucleic.pdb -o nucleic_clean.pdb
```

核酸特殊处理:
- 末端处理: 5' 端加 OE/OH 封闭, 3' 端加 O3'/OH 封闭 (tleap 自动处理)
- 检查磷酸骨架完整性 (缺失磷酸的残基需补全)
- 确认碱基配对: Watson-Crick (A-T/U, G-C) 和非经典配对
- 非标准碱基 (修饰碱基、核苷酸类似物) 需单独参数化 (antechamber 或 MCPB)
- RNA 结构注意 2'-OH 的存在

## 2. 力场选择

| 分子类型 | 力场 | leaprc |
|----------|------|--------|
| dsDNA | OL15 | `leaprc.DNA.OL15` |
| ssDNA | OL24 | `leaprc.DNA.OL24` |
| RNA | OL3 | `leaprc.RNA.OL3` |
| DNA/RNA 杂合 | OL15 (DNA) + OL3 (RNA) | 分别 source |
| 蛋白-核酸复合物 | ff19SB + OL15/OL3 | 组合使用 |

离子模型: **ionlj** (对应 OPC 水模型的 Joung-Cheatham 离子参数)

## 3. 离子放置

核酸的高电荷密度 (每核苷酸 -1e) 对离子环境极为敏感。

### 基本中和

```tleap
source leaprc.DNA.OL15
source leaprc.water.opc
source leaprc.constants

dna = loadPDB nucleic_clean.pdb
solvateBox dna OPCBOX 12.0
addIons dna Na+ 0
addIons dna Cl- 0
addIonsRand dna Na+ 0.15M Cl- 0.15M
saveAmberParm dna prmtop inpcrd
quit
```

缓冲距离 12 A (比蛋白的 10 A 更大, 确保周期性镜像间足够间隔)。

### Mg2+ 特殊处理 (RNA 必须)

RNA 折叠和催化依赖 Mg2+:

```tleap
# 先中和单电荷
addIons dna Na+ 0
# 添加 Mg2+ (通常 2-10 mM)
addIonsRand dna Mg2+ 5 Cl- 10
# 补充 NaCl 至 0.15 M
addIonsRand dna Na+ 0.15M Cl- 0.15M
```

重要: Mg2+ 的 12-6-4 LJ 势已内置于 Amber 离子参数 (ion_types = "12-6-4"), 无需额外 frcmod。但在模拟中需确保 Mg2+ 不与磷酸骨架原子初始重叠。

## 4. 能量最小化 — 多阶段

**阶段 1**: 10 kcal 限制核酸重原子 + 离子限制 (20 kcal), 优化水

**阶段 2**: 5 kcal 限制核酸骨架, 5 kcal 限制离子, 放松碱基和水

**阶段 3**: 2 kcal 限制骨架, 无离子限制

**阶段 4**: 无限制, 全面最小化

核酸体系最小化步数通常需要 30k-50k 步。检查结构是否保持正确碱基配对。

## 5. 加热 — 两阶段

### 阶段 1: 0→100K (NVT, 50ps, dt=0.001)

```
 &cntrl
  imin=0, irest=0, ntx=1,
  nstlim=50000, dt=0.001,
  ntc=2, ntf=2,
  ntt=3, gamma_ln=3.0,
  tempi=0.0, temp0=100.0,
  ntr=1, restraint_wt=10.0,
  restraintmask='@P,OP1,OP2,O5\',C5\',C4\',C3\',C2\',C1\'',
  ntp=0,
  cut=10.0,
 /
```

限制磷酸骨架原子; 1 fs 时间步保证初始稳定。

### 阶段 2: 100→300K (NVT, 100ps, dt=0.002)

```
 &cntrl
  imin=0, irest=1, ntx=5,
  nstlim=50000, dt=0.002,
  ntc=2, ntf=2,
  ntt=3, gamma_ln=2.0,
  temp0=300.0,
  ntr=1, restraint_wt=5.0,
  restraintmask='@P,O5\',C5\',C4\',C3\',O3\'',
  ntp=0,
  cut=10.0,
 /
```

## 6. 平衡 — 长时间缓慢释放

核酸高电荷导致平衡过程缓慢, 需要比蛋白更长的平衡时间:

| 阶段 | 时长 | 骨架限制 | 系综 |
|------|------|----------|------|
| 密度平衡 | 500ps | 5 kcal | NPT |
| 平衡 1 | 1ns | 2 kcal | NPT |
| 平衡 2 | 2ns | 0.5 kcal | NPT |
| 平衡 3 | 5ns | 无 | NPT |

总平衡 8-10 ns。判断标准:
- 碱基配对距离稳定
- RMSD 收敛 (RNA 通常比 DNA 慢)
- 离子分布达到平衡 (Mg2+ 需特别关注)

```
 &cntrl
  imin=0, irest=1, ntx=5,
  nstlim=250000, dt=0.002,
  ntc=2, ntf=2,
  ntt=3, gamma_ln=2.0, temp0=300.0,
  ntp=1, pres0=1.0, taup=5.0,
  cut=10.0,
 /
```

## 7. 成品模拟

```
 &cntrl
  imin=0, irest=1, ntx=5,
  nstlim=5000000, dt=0.002,
  ntc=2, ntf=2,
  ntt=3, gamma_ln=1.0, temp0=300.0,
  ntp=1, pres0=1.0, taup=10.0,
  ntwx=2500, ntpr=1000,
  cut=10.0,
 /
```

推荐时长:
- DNA: 200-500 ns
- RNA: 500 ns - 1 us (RNA 构象空间更大)
- 蛋白-核酸复合物: 500 ns+

## 8. 分析 — 核酸专有

```
cpptraj -p prmtop
trajin prod.nc
autoimage

# 骨架 RMSD
rms first @P,O5\',C5\',C4\',C3\',O3\' out backbone_rmsd.dat

# 碱基对 RMSD (保持碱基配对)
rms first :1,2&@N1,N3,C2,C4,C5,C6,C8 out bp_rmsd.dat

# 骨架扭角 (alpha, beta, gamma, delta, epsilon, zeta)
multidihedral out dihedrals.dat alpha beta gamma delta epsilon zeta

# 糖折叠 (C2\'-endo vs C3\'-endo)
multidihedral out pucker.dat nu0 nu1 nu2 nu3 nu4 type pucker

# 碱基对参数 (剪切、拉伸、交错、滚动、倾斜、扭转)
nastruct nastruct.out out nastruct.dat

# 碱基对氢键
hbond out bp_hbond.dat : nucleic donor : nucleic acceptor

# 沟槽宽度 (DNA)
distance out major_groove.dat :1@N7 :14@N7  # 示例: major groove

# 离子分布 (径向分布函数)
radial out na_rdf.dat 0.5 15.0 : nucleic@P Na+

# 回转半径
radgyr out rg.dat : nucleic&!@H
go
quit
```

关键指标:
- **骨架扭角**: 判断 A-form (RNA) vs B-form (DNA) 构象
- **糖折叠**: C3\'-endo (A-form) vs C2\'-endo (B-form); RNA 通常保持 C3\'-endo
- **碱基对参数**: nastruct 输出可与 3DNA/X3DNA 对比
- **氢键持续性**: Watson-Crick 配对稳定性; RNA 非经典配对 (G-U wobble) 需特别关注
- **离子 RDF**: Na+ 在磷酸骨架附近的分布; Mg2+ 内壳层配位
- **RMSD 平台**: DNA 通常 <3 A; RNA 可能 >5 A (尤其是柔性 loop 区域)
