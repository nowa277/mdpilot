---
name: force-field
title: 力场选择指南
description: ff19SB、ff14SB、GAFF2 等力场选择与匹配规则
tags: [force-field, ff19sb, ff14sb, gaff2, ol15, ol3, lipid21]
triggers: [force field, 力场, ff19sb, ff14sb, GAFF, force field selection]
category: concept
command: /force-field
tools: []
---

# 力场选择指南

AMBER 力场与水模型、离子参数必须配套使用。错误搭配会导致模拟结果偏差或崩溃。

## 蛋白质

### ff19SB（推荐）
- 全新训练集，骨架 φ/ψ 二面角显著改善
- 与 OPC 水模型联合设计，必须搭配 OPC
- 适合全新项目、需要高精度结果的场景

### ff14SB
- 经过大量验证，文献覆盖广
- 搭配 TIP3P 水模型
- 适合需要与已有文献对比的项目

## 核酸

| 分子类型 | 力场 | 说明 |
|---------|------|------|
| DNA | OL15 | B-DNA 最优，修正糖折叠 |
| DNA | OL24 | 最新版，进一步改进 |
| RNA | OL3 | RNA 专用，修正 α/γ 二面角 |

## 脂质

- **LIPID21**: AMBER 官方脂质力场，支持 POPC、POPE、DOPC 等常见脂质
- 与 ff19SB/ff14SB 蛋白质力场兼容

## 小分子

- **GAFF2**: 通过 antechamber 参数化
- 流程：`antechamber` → `parmchk2` → `tleap`
- 支持大多数有机小分子、药物分子

## 碳水化合物

- **GLYCAM**: 糖类专用力场
- 注意版本兼容性，GLYCAM 与 AMBER 蛋白质力场有指定搭配

## 水模型匹配规则

| 力场 | 推荐水模型 | 离子参数 |
|------|-----------|---------|
| ff19SB | OPC | Li/Merz (12-6-4 LJ) |
| ff14SB | TIP3P | Joung-Cheatham |
| ff14SB + OL3/OL15 | TIP3P | Joung-Cheatham |

**绝对禁止**: ff19SB + TIP3P，这会丧失 ff19SB 的精度优势。

## tleap 加载命令

### ff19SB + OPC（蛋白质推荐）
```
source leaprc.protein.ff19SB
source leaprc.water.opc
```

### ff14SB + TIP3P（经典组合）
```
source leaprc.protein.ff14SB
source leaprc.water.tip3p
```

### ff14SB + OL15 + TIP3P（蛋白质-DNA）
```
source leaprc.protein.ff14SB
source leaprc.DNA.OL15
source leaprc.water.tip3p
```

### ff14SB + OL3 + TIP3P（蛋白质-RNA）
```
source leaprc.protein.ff14SB
source leaprc.RNA.OL3
source leaprc.water.tip3p
```

### 含 GAFF2 小分子
```
source leaprc.protein.ff19SB
source leaprc.water.opc
source leaprc.gaff2
mol = loadmol2 ligand.mol2
loadamberparams ligand.frcmod
```

## 常见错误

1. **ff19SB + TIP3P**: 丧失精度优势，不如直接用 ff14SB
2. **混合力场不加离子参数**: 离子-水相互作用取决于水模型
3. **GAFF2 不运行 parmchk2**: 会导致缺失参数，tleap 报错
4. **核酸用错力场**: OL3 是 RNA 专用，DNA 应选 OL15/OL24
