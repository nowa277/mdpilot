---
name: fix-crash
title: 模拟崩溃修复
description: SHAKE 失败、NaN、vlimit 错误、CUDA 错误等模拟崩溃问题
tags: [crash, shake, nan, vlimit, cuda, gpu, error]
triggers: [simulation crash, SHAKE failure, 模拟崩溃, NaN, vlimit, CUDA error]
category: troubleshooting
command: /fix-crash
tools:
  - name: pmemd_cuda, node: lab03, exec: local_subprocess
  - name: cpptraj, node: lab03, exec: local_subprocess
---

# 模拟崩溃修复指南

## 1. SHAKE 失败

**典型错误信息：**
```
Coordinate resetting (SHAKE) cannot be accomplished,
deviation is too large
```

**原因分析：**
- 氢原子运动步长过大，超过 SHAKE 容差
- 初始结构中存在原子重叠或不良接触
- 能量最小化不充分
- 时间步长过大

**解决方案（按优先级）：**

```bash
# 方案1：减小时间步长（2fs → 1fs）
# md.in 中修改
&cntrl
  dt = 0.001,        # 从 0.002 改为 0.001
  ntc = 2,           # 启用 SHAKE
  ntf = 2,           # 不计算 SHAKE 约束键的力
/

# 方案2：加强能量最小化
&cntrl
  imin = 1,
  maxcyc = 20000,         # 增加最小化步数
  ncyc = 5000,            # 切换到共轭梯度前的最速下降步数
  ntr = 1,                # 使用位置限制
  restraintmask = '!@H=', # 限制非氢原子
  restraint_wt = 10.0,    # 较强的限制力
/

# 方案3：检查并修复初始结构
cpptraj -p prmtop <<EOF
trajin inpcrd
check :1-9999 reportfile check.dat
EOF
# 查看报告中的原子重叠
```

**SHAKE 相关参数调优：**
```bash
# 增大 SHAKE 容差（谨慎使用）
&cntrl
  ntc = 2,
  ntf = 2,
  dt = 0.002,
  shake_tol = 0.0001,   # 默认 0.00001，可适当放宽
/
```

## 2. vlimit 速度超限

**典型错误信息：**
```
vlimit exceeded for step    XXXX; vmax =    XX.XXX
```

**原因分析：**
- 原子速度过大，通常由不良接触引起
- 初始温度过高
- 时间步长与体系不匹配

**解决方案：**

```bash
# 方案1：降低初始温度
&cntrl
  tempi = 0.0,        # 不赋予初始速度
  temp0 = 300.0,      # 目标温度
  ntt = 3,            # Langevin 控温
  gamma_ln = 1.0,     # 碰撞频率
/

# 方案2：更温和的加热方案
# 阶段1：0 → 100K（50ps）
&cntrl
  nstlim = 25000, dt = 0.002,
  tempi = 0.0, temp0 = 100.0,
  ntt = 3, gamma_ln = 5.0,    # 较大 gamma 增强控温
/

# 阶段2：100 → 300K（50ps）
&cntrl
  nstlim = 25000, dt = 0.002,
  tempi = 100.0, temp0 = 300.0,
  ntt = 3, gamma_ln = 2.0,
/

# 方案3：减小时间步长
dt = 0.001   # 1fs 步长，更稳定
```

## 3. NaN 值 / 灾难性失败

**典型错误信息：**
```
NaN detected in energy for step XXXX
CATASTROPHIC ERROR: Energy is NaN
```

**原因分析：**
- 原子重叠导致极大的排斥力
- 参数错误（键参数、电荷异常）
- 浮点溢出

**解决方案：**

```bash
# Step 1: 从上一个正常检查点重启
# 检查可用的 rst 文件
ls -la *.rst*

# 使用最后正常的 rst 文件重启
&cntrl
  irest = 1,          # 从 rst 文件重启
  ntx = 5,            # 读取坐标和速度
  nstlim = 500000,    # 剩余步数
/
```

```bash
# Step 2: 重新最小化（如果重启也失败）
# 从 rst 文件重新最小化
&cntrl
  imin = 1,
  maxcyc = 50000,
  ncyc = 10000,
  ntr = 1,
  restraintmask = '!@H=',
  restraint_wt = 50.0,     # 强限制
  ntx = 1,                 # 只读坐标
  irest = 0,
/

# 逐步放松限制
# 50 → 25 → 10 → 5 → 1 → 0 kcal/mol/A^2
```

```bash
# Step 3: 检查能量
cpptraj -p prmtop <<EOF
trajin md.nc
energy etot out energy_check.dat
EOF
# 查看能量在崩溃前是否单调上升
```

## 4. CUDA/GPU 错误

**典型错误信息：**
```
CUDA error: out of memory
cudaMalloc failed: out of memory
CUDA (GPU) version not available
```

**GPU 内存溢出：**

```bash
# 检查 GPU 内存
nvidia-smi

# 方案1：减少 PME 网格大小
&ewald
  nfft1 = 96,    # 减小（通常 64/96/128）
  nfft2 = 96,
  nfft3 = 96,
/

# 方案2：使用混合 CPU/GPU 模式
pmemd -O -i md.in -o md.out -p prmtop -c inpcrd -r rst -x nc \
      -AllowSmallBox

# 方案3：缩小溶剂盒子
# 重新建系统，使用 10A 缓冲层而非 12A

# 方案4：使用 CPU 版本（慢但无 GPU 限制）
pmemd.MPI -O -i md.in -o md.out -p prmtop -c inpcrd -r rst -x nc
```

**GPU 驱动问题：**
```bash
# 检查驱动和 CUDA 版本
nvidia-smi
nvcc --version

# 常见兼容性问题：
# - CUDA toolkit 版本与 Amber 编译版本不匹配
# - 驱动过旧
# - GPU 架构不支持（需 Kepler 或更新）

# 指定 GPU
export CUDA_VISIBLE_DEVICES=0    # 使用 GPU 0
```

## 5. 能量爆炸

**典型错误信息：**
```
Energy for step XXXX is   9999999.9999  (extremely high)
```

**原因分析：**
- 不良接触（原子重叠）
- 参数错误
- 溶剂盒子太小

**解决方案：**

```bash
# Step 1: 重新最小化
# 先强限制最小化
&cntrl
  imin = 1,
  maxcyc = 10000,
  ntr = 1,
  restraintmask = ':1-200',   # 限制蛋白质
  restraint_wt = 100.0,       # 非常强的限制
/
# 然后逐步放松

# Step 2: 检查原子重叠
cpptraj -p prmtop <<EOF
trajin inpcrd
check :1-9999 reportfile overlap.dat offset 0.8
EOF
# offset 0.8 A 以内的原子对会被报告

# Step 3: 检查盒子大小
cpptraj -p prmtop <<EOF
trajin inpcrd
box
EOF
# 确认盒子尺寸大于 cutoff + 2*buffer
```

## 6. 温度漂移

**症状：**
- 温度持续偏离目标值
- 温度波动异常大

**解决方案：**

```bash
# 使用 Langevin 控温器（最稳定）
&cntrl
  ntt = 3,            # Langevin dynamics
  gamma_ln = 1.0,     # 碰撞频率 (ps^-1)
  temp0 = 300.0,
  tempi = 300.0,
/

# gamma_ln 推荐值：
# 蛋白质模拟：1.0 - 2.0
# 膜蛋白模拟：1.0
# 自由能计算：2.0 - 5.0

# 避免 ntt=1（弱耦合，可能导致温度跳跃）
```

## 7. 密度问题

**症状：**
- 密度持续偏离预期值
- 盒子大小异常变化

**解决方案：**

```bash
# NPT 控压参数
&cntrl
  ntp = 1,            # 各向同性压力耦合
  pres0 = 1.0,        # 目标压力 (bar)
  taup = 2.0,         # 压力弛豫时间 (ps)
/

# 膜蛋白使用半各向同性
&cntrl
  ntp = 2,            # 半各向同性（XY 独立于 Z）
  pres0 = 1.0,
  taup = 2.0,
/

# taup 推荐值：
# 标准体系：1.0 - 5.0 ps
# 膜蛋白：5.0 - 10.0 ps（Z 方向更大的 taup）
```

## 8. 重启程序

从检查点文件重启模拟的标准流程：

```bash
# 检查可用的重启文件
ls -la *.rst* *.chk

# 方法1：从 rst 文件重启（推荐）
&cntrl
  irest = 1,          # 重启
  ntx = 5,            # 读取坐标和速度
  nstlim = <剩余步数>,
  dt = 0.002,
  ntxo = 2,           # NetCDF 格式输出
/

pmemd.cuda -O -i restart.in -o md_continued.out -p prmtop \
  -c md.rst -r md_continued.rst -x md_continued.nc

# 方法2：从崩溃的 nc 文件提取最后帧重启
cpptraj -p prmtop <<EOF
trajin md.nc lastframe
trajout restart.rst
EOF
```

## 9. 系统性调试工作流

```
模拟崩溃
    │
    ├─ 检查 md.out 最后 50 行
    │   └─ 确认错误类型（SHAKE/NaN/CUDA/能量）
    │
    ├─ 检查能量轨迹
    │   └─ energy 总能量是否单调上升 → 不良接触
    │   └─ 能量突然跳变 → 参数/原子重叠
    │   └─ 能量正常但崩溃 → SHAKE/步长问题
    │
    ├─ 检查结构
    │   └─ 原子重叠 → 重新最小化
    │   └─ 盒子变形 → 检查控压参数
    │   └─ 原子飞出 → 检查 PBC/截断
    │
    └─ 修复策略
        ├─ 减小 dt (2fs → 1fs)
        ├─ 加强最小化
        ├─ 更温和的加热
        ├─ 降低 SHAKE 容差要求
        └─ 从早期检查点重启
```

## 崩溃类型速查表

| 崩溃类型 | 关键词 | 优先操作 |
|---------|--------|---------|
| SHAKE 失败 | `SHAKE` `deviation` | 减小 dt / 加强最小化 |
| vlimit | `vlimit` `vmax` | 降温加热 / 减小 dt |
| NaN | `NaN` `CATASTROPHIC` | 从检查点重启 / 重新最小化 |
| GPU 内存 | `out of memory` `cudaMalloc` | 减小体系 / CPU 运行 |
| 能量爆炸 | `9999999` | 检查重叠 / 重新最小化 |
| 温度异常 | 温度偏离 | 检查 ntt/gamma_ln |
| 密度异常 | 密度偏离 | 检查 ntp/taup |
