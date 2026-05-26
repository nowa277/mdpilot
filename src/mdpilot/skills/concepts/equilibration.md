---
name: equilibration
title: 系统平衡策略
description: 能量最小化、加热、密度平衡、成品模拟的阶段参数配置
tags: [equilibration, minimization, heating, npt, nvt, density]
triggers: [equilibration, 平衡, minimization, 最小化, heating, 加热]
category: concept
command: /equilibration
tools: []
---

# 系统平衡策略

AMBER 分子动力学模拟采用分阶段平衡协议，逐步释放约束，确保体系稳定。

## 五阶段协议

### 阶段 1: 能量最小化 (Minimization)

**目的**: 消除初始结构中的不良接触、原子重叠

| 步骤 | 约束 | 步数 | 说明 |
|------|------|------|------|
| Min1 | 骨架 10 kcal/mol/A² | 5000 | 固定骨架，优化侧链和溶剂 |
| Min2 | 骨架 5 kcal/mol/A² | 5000 | 逐步放松骨架 |
| Min3 | 无约束 | 10000 | 全原子自由优化 |

**关键参数**:
```
imin=1, maxcyc=5000, ncyc=2500,
ntr=1, restraint_wt=10.0, restraintmask='@CA,C,N,O'
```

**判断标准**: 能量持续下降并趋于平坦，无能量暴涨。

### 阶段 2: NVT 加热 (Heating)

**目的**: 将体系从 0K 加热至目标温度 (通常 300K)

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| 系综 | NVT | 固定体积，避免真空泡 |
| 温度范围 | 0 → 300K | 线性升温 |
| 时长 | 100 ps | 足够慢以避免水泡 |
| 时间步 | 1 fs | 加热阶段用小步长 |
| 恒温器 | Langevin (gamma_ln=1.0) | 平滑升温 |
| 骨架约束 | 5 kcal/mol/A² | 防止蛋白质变形 |

**关键参数**:
```
irest=0, ntx=1,
tempi=0.0, temp0=300.0,
ntt=3, gamma_ln=1.0,
ntr=1, restraint_wt=5.0, restraintmask='@CA,C,N,O'
dt=0.001, nstlim=100000
```

**注意**: SHAKE 在加热阶段通常关闭 (ntc=1, ntf=1)，使用 1 fs 步长。

### 阶段 3: NPT 密度平衡 (Density Equilibration)

**目的**: 将密度调整至正确值，体系体积达到平衡

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| 系综 | NPT | 允许体积变化 |
| 压力 | 1 bar | 标准大气压 |
| 恒压器 | Berendsen (taup=1.0) 或 Monte Carlo | Berendsen 平衡更快 |
| 时长 | 200-500 ps | 密度收敛需要时间 |
| 时间步 | 1→2 fs | 可以在此阶段切换 |
| 骨架约束 | 2 kcal/mol/A² | 逐步放松 |

**关键参数**:
```
ntp=1, pres0=1.0, taup=1.0,
ntt=3, gamma_ln=2.0,
temp0=300.0,
ntr=1, restraint_wt=2.0, restraintmask='@CA,C,N,O'
```

**判断标准**: 密度曲线趋于平坦，体积波动稳定。

### 阶段 4: 无约束 NPT 平衡 (Unrestrained Equilibration)

**目的**: 释放所有约束，确认体系真正稳定

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| 系综 | NPT | 继续密度平衡 |
| 恒压器 | Monte Carlo (taup=1.0) | 切换到更准确的 MC |
| 时长 | 500 ps - 1 ns | 足够长以观察弛豫 |
| 约束 | 无 (或 0.1 kcal/mol/A² 渐退) | 完全释放 |

**判断标准**:
- 温度稳定在目标值 +/- 2K
- 密度收敛至预期值
- 总能量无漂移
- RMSD 趋于平坦

### 阶段 5: 成品模拟 (Production)

**目的**: 数据采集

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| 系综 | NPT | 保持恒温恒压 |
| 恒温器 | Langevin (gamma_ln=1.0-2.0) | 推荐 |
| 恒压器 | Monte Carlo (taup=1.0-2.0) | 推荐 |
| 时间步 | 2 fs (SHAKE) | 必须开启 SHAKE |
| 时长 | 视体系而定 | 见下方指南 |
| 坐标输出 | 每 10 ps (ntpr=5000) | 轨迹分析 |
| 能量输出 | 每 1 ps (ntwr=500) | 监控稳定性 |

**SHAKE 设置**:
```
ntc=2, ntf=2  # SHAKE on hydrogen bonds
dt=0.002      # 2 fs timestep
```

## 时长指南

| 体系类型 | 平衡总时长 | 成品模拟时长 |
|---------|-----------|------------|
| 小蛋白 (< 200 aa) | 500 ps | 100-500 ns |
| 中等蛋白 (200-500 aa) | 1 ns | 200 ns - 1 us |
| 大蛋白/复合物 | 1-2 ns | 200 ns - 1 us |
| 膜蛋白 | 2-5 ns | 500 ns - 1 us |
| DNA/RNA | 1-2 ns | 200 ns - 1 us |
| 自由能计算 | 2-5 ns/λ 窗口 | 2-5 ns/λ 窗口 |

## 监控指标

平衡过程中应持续监控：

1. **温度 (TEMP)**: 应稳定在 temp0 +/- 2K
2. **密度 (DENSITY)**: 应收敛至 ~1.0 g/mL（水溶液）
3. **总能量 (Etot)**: 应无系统性漂移
4. **RMSD**: 蛋白骨架 RMSD 应趋于平坦
5. **压力 (PRESS)**: 波动很大是正常的，平均值应接近 1 bar
6. **体积 (VOLUME)**: NPT 下应收敛

## 常见问题

### 能量暴涨
- **原因**: 不良接触未充分最小化
- **解决**: 增加最小化步数，加大约束力，减小时间步

### 密度不收敛
- **原因**: 加热太快或恒压器耦合太弱
- **解决**: 延长加热时间，减小 taup 值

### 蛋白质变形
- **原因**: 约束释放太快
- **解决**: 增加中间约束阶段 (5→2→0.5→0)

### 水泡形成
- **原因**: NPT 加热（体积膨胀产生真空）
- **解决**: 加热必须在 NVT 下进行

### RMSD 持续上升
- **原因**: 力场/水模型不匹配，或初始结构质量差
- **解决**: 检查力场搭配，验证初始结构

## 完整配置示例 (pmemd)

```
# Stage 1: Minimization
imin=1, maxcyc=10000, ncyc=5000,
ntr=1, restraint_wt=10.0, restraintmask='@CA,C,N,O',
cut=10.0, ntb=1, ntc=1, ntf=1,

# Stage 2: NVT Heating
irest=0, ntx=1,
tempi=0.0, temp0=300.0,
ntt=3, gamma_ln=1.0,
dt=0.001, nstlim=100000,
ntc=1, ntf=1, ntb=1,
ntr=1, restraint_wt=5.0, restraintmask='@CA,C,N,O',
cut=10.0,

# Stage 3: NPT Density
irest=1, ntx=5,
temp0=300.0,
ntt=3, gamma_ln=2.0,
ntp=1, pres0=1.0, taup=1.0,
dt=0.002, nstlim=250000,
ntc=2, ntf=2,
ntr=1, restraint_wt=2.0, restraintmask='@CA,C,N,O',
cut=10.0,

# Stage 5: Production
irest=1, ntx=5,
temp0=300.0,
ntt=3, gamma_ln=1.0,
ntp=1, pres0=1.0, taup=2.0,
dt=0.002, nstlim=500000000,
ntc=2, ntf=2,
cut=10.0, iwrap=1,
ntwx=5000, ntpr=5000, ntwr=500,
```
