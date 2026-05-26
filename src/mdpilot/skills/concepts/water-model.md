---
name: water-model
title: 水模型对比
description: TIP3P、OPC、OPC3 等水模型选择与力场匹配
tags: [water-model, tip3p, opc, opc3, solvation, solvent]
triggers: [water model, 水模型, TIP3P, OPC, solvent, 溶剂模型]
category: concept
command: /water-model
tools: []
---

# 水模型对比

水模型直接影响密度、扩散系数、蛋白质稳定性、自由能精度等关键模拟指标。

## 模型概览

### TIP3P
- **位点数**: 3（刚性）
- **优点**: 计算最快，文献验证最充分，NAMD/CHARMM 兼容性好
- **缺点**: 体相性质差（密度偏低 ~0.98 g/mL，扩散偏快），介电常数偏高
- **适合**: 膜蛋白体系、复杂多组分体系、需要与 CHARMM 力场联用的场景
- **搭配**: ff14SB

### TIP4P-Ew
- **位点数**: 4（刚性，Ewald 优化）
- **优点**: 比 TIP3P 改善密度和扩散，专为 Ewald 求和优化
- **缺点**: 比 TIP3P 慢约 15-20%
- **适合**: 对体相性质有要求但不想用 OPC 的场景

### OPC（推荐）
- **位点数**: 4（刚性）
- **优点**: 最佳体相性质（密度、介电常数、扩散系数、热力学性质），专为 ff19SB 设计
- **缺点**: 比 TIP3P 慢约 15-20%
- **适合**: 高精度模拟、自由能计算、蛋白质折叠、与 ff19SB 联用
- **搭配**: ff19SB

### OPC3
- **位点数**: 3（刚性）
- **优点**: 3 位点模型中精度最佳，速度与 TIP3P 相当
- **缺点**: 精度仍不及 OPC
- **适合**: 对计算效率敏感但需要比 TIP3P 更好的性质

## 性能对比

| 性质 | 实验 | TIP3P | TIP4P-Ew | OPC | OPC3 |
|------|------|-------|----------|-----|------|
| 密度 (g/mL) | 0.997 | 0.98 | 1.00 | 0.997 | 0.998 |
| 扩散 (10⁻⁵ cm²/s) | 2.3 | 5.2 | 2.4 | 2.3 | 2.3 |
| 介电常数 | 78.4 | 92 | 62 | 78.5 | 78.5 |
| 焓 of vaporization | 10.5 | 10.4 | 10.5 | 10.5 | 10.5 |
| 计算开销 | 1x | 1x | ~1.2x | ~1.2x | ~1x |

## 匹配规则

水模型选择取决于力场，**不能自由组合**：

```
力场          →  水模型    →  离子参数
─────────────────────────────────────────
ff19SB       →  OPC       →  Li/Merz (12-6-4 LJ)
ff14SB       →  TIP3P     →  Joung-Cheatham
ff14SB+OL15  →  TIP3P     →  Joung-Cheatham
ff14SB+OL3   →  TIP3P     →  Joung-Cheatham
```

## 对模拟的影响

### 密度收敛
- TIP3P 密度偏低 ~1.5%，可能影响 NPT 平衡
- OPC 密度准确，收敛更快更稳定

### 扩散系数
- TIP3P 扩散偏快 ~2 倍，影响动力学分析
- OPC 扩散接近实验值，适合研究动力学行为

### 蛋白质稳定性
- ff19SB + OPC 组合对骨架 φ/ψ 分布最准确
- ff14SB + TIP3P 在稳定蛋白质中差异不大，但对柔性区域有影响

### 自由能精度
- 自由能微扰 (FEP/TI) 对水模型敏感
- 推荐 OPC 以获得最佳收敛和精度
- TIP3P 在相对自由能中也可接受，但绝对自由能偏差更大

## tleap 加载

```
# OPC
source leaprc.water.opc

# TIP3P
source leaprc.water.tip3p

# TIP4P-Ew
source leaprc.water.tip4pew

# OPC3
source leaprc.water.opc3
```

## 选择建议

1. **新项目、追求精度**: ff19SB + OPC
2. **需要与文献对比**: ff14SB + TIP3P
3. **膜蛋白/多组分体系**: ff14SB + TIP3P（兼容性好）
4. **自由能计算**: ff19SB + OPC（精度优先）
5. **大规模筛选**: ff14SB + TIP3P（速度优先）
