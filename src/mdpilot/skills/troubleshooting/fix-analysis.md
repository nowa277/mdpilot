---
name: fix-analysis
title: 轨迹分析问题
description: cpptraj 分析异常、内存溢出、拓扑不匹配等问题
tags: [analysis, cpptraj, trajectory, rmsd, error]
triggers: [analysis error, cpptraj error, 分析错误, 轨迹问题, RMSD异常]
category: troubleshooting
command: /fix-analysis
tools:
  - name: cpptraj, node: lab03, exec: local_subprocess
---

# 轨迹分析问题排查指南

## 1. 大轨迹文件内存溢出

**典型错误信息：**
```
Error: Out of memory
Allocation failed
Killed
```

**原因分析：**
- 轨迹文件过大（多个 GB 的 NetCDF 文件）
- 一次性加载所有帧到内存
- 分析（如聚类）需要 N*N 距离矩阵

**解决方案：**

```bash
# 方案1：分块处理（chunk-based processing）
cpptraj -p prmtop <<EOF
trajin traj.nc
# 每次只处理一部分帧
strip :WAT
trajout stripped.nc netcdf
EOF

# 方案2：先剥离溶剂再分析
cpptraj -p prmtop <<EOF
trajin traj.nc
strip :WAT
strip :Na+ :Cl-
rmsd :1-200@CA out rmsd_backbone.dat
EOF

# 方案3：使用帧步长（stride）
cpptraj -p prmtop <<EOF
trajin traj.nc 1 last 10   # 每10帧取1帧
strip :WAT
rmsd :1-200@CA out rmsd_sampled.dat
EOF

# 方案4：使用 runanalysis 分步执行
cpptraj -p prmtop <<EOF
trajin traj.nc
strip :WAT
runanalysis rmsd :1-200@CA out rmsd.dat
EOF
```

**内存估算：**
```
每帧内存 ≈ 原子数 * 3 * 8 bytes（双精度坐标）
100,000 原子 * 3 * 8 = 2.4 MB/帧
10,000 帧 = 24 GB（仅坐标）
```

**推荐策略：**
1. 先 `strip` 溶剂和离子
2. 使用 stride 降低帧数
3. 逐项分析，避免一次加载多个分析命令
4. 将中间结果写入文件而非保存在内存

## 2. AMBER Mask 语法错误

**典型错误信息：**
```
Error: Could not parse mask [:1-100@CA
Error: Invalid atom selection
```

**Mask 语法参考：**

```
残基选择：
  :1         → 残基 1
  :1-100     → 残基 1 到 100
  :ALA       → 所有丙氨酸
  :1,5,10    → 残基 1, 5, 10
  :1-10,20-30 → 残基 1-10 和 20-30

原子选择：
  @CA        → 所有 CA 原子
  @CA,CB     → CA 和 CB 原子
  @H=        → 所有氢原子（通配符）

组合选择：
  :1-100@CA     → 残基 1-100 的 CA 原子
  :1-100@CA,CB  → 残基 1-100 的 CA 和 CB 原子

排除选择：
  !:WAT      → 非水残基
  !@H=       → 非氢原子

距离选择：
  :1-100<@5.0   → 距离残基 1-100 在 5.0 A 内的原子

通配符：
  *          → 所有
  :*         → 所有残基
  @*         → 所有原子
```

**常见错误：**
```bash
# 错误：中文括号
rms [:1-100@CA]   ← 错误
rms :1-100@CA     ← 正确

# 错误：空格
rms :1-100 @CA    ← 错误（mask 中间有空格）
rms :1-100@CA     ← 正确

# 错误：范围格式
rms :1_100@CA     ← 错误
rms :1-100@CA     ← 正确
```

## 3. NetCDF 文件损坏

**典型错误信息：**
```
Error: Could not open trajectory file
NetCDF: HDF error
Error reading frame X from trajectory
```

**诊断方法：**

```bash
# 使用 ncdump 检查文件头
ncdump -h traj.nc

# 检查文件完整性
ncdump traj.nc > /dev/null
# 如果报错，文件可能损坏

# 检查帧数
ncdump -v frame traj.nc | tail -20
```

**修复策略：**

```bash
# 方案1：跳过损坏的帧
cpptraj -p prmtop <<EOF
trajin traj.nc 1 9000    # 只读取已知正常的帧范围
trajout recovered.nc netcdf
EOF

# 方案2：逐段读取找到损坏位置
# 先试读前半部分
cpptraj -p prmtop <<EOF
trajin traj.nc 1 5000
trajout test1.nc netcdf
EOF

# 再试读后半部分
cpptraj -p prmtop <<EOF
trajin traj.nc 5001 last
trajout test2.nc netcdf
EOF
# 二分法定位损坏帧

# 方案3：从多个文件拼接恢复
cpptraj -p prmtop <<EOF
trajin traj_part1.nc
trajin traj_part2.nc
trajout recovered.nc netcdf
EOF
```

## 4. RMSD 计算常见问题

**典型问题：**
- RMSD 值异常大（>10 A）
- RMSD 不收敛
- 参考帧选择不当

**正确计算流程：**

```bash
# 标准蛋白质 backbone RMSD
cpptraj -p prmtop <<EOF
trajin traj.nc
autoimage              # 处理周期性边界条件
rmsd :1-200@CA,C,N,O out rmsd_backbone.dat \
  refname protein_ref ref prmtop
EOF

# 使用平均结构作为参考
cpptraj -p prmtop <<EOF
trajin traj.nc
autoimage
average avg.pdb :1-200@CA,C,N,O
run
rmsd :1-200@CA,C,N,O ref avg.pdb out rmsd_vs_avg.dat
EOF

# 配体 RMSD（需先对齐蛋白质）
cpptraj -p prmtop <<EOF
trajin traj.nc
autoimage
rmsd first :1-200@CA,C,N,O     # 先对齐蛋白质
rmsd first :201 out ligand_rmsd.dat nofit   # 计算配体 RMSD，不再拟合
EOF
```

**关键注意事项：**
1. **autoimage 必须在 rmsd 之前**：处理 PBC 导致的分子跨边界问题
2. **backbone vs all-atom**：蛋白质 RMSD 通常使用 backbone（@CA,C,N,O），不用全部原子
3. **参考结构**：`first`（第一帧）、`reference`（外部文件）、`average`（平均结构）
4. **nofit**：计算纯位移 RMSD，不做最小二乘拟合

## 5. 拓扑/轨迹不匹配

**典型错误信息：**
```
Error: Number of atoms in trajectory (50000) does not match
       number of atoms in topology (100000)
```

**原因分析：**
- 拓扑文件是完整系统，但轨迹已经去除了溶剂
- 使用了 strip 后的轨迹但未更新拓扑
- 多次 strip 操作导致不匹配

**解决方案：**

```bash
# 生成去除溶剂后的拓扑文件
cpptraj -p full.prmtop <<EOF
strip :WAT
strip :Na+ :Cl-
parmwrite out stripped.prmtop
EOF

# 然后使用匹配的拓扑和轨迹
cpptraj -p stripped.prmtop <<EOF
trajin stripped_traj.nc
rmsd :1-200@CA out rmsd.dat
EOF

# 或者在同一次 cpptraj 运行中完成
cpptraj -p full.prmtop <<EOF
trajin full_traj.nc
strip :WAT
strip :Na+ :Cl-
parmwrite out no_solvent.prmtop   # 输出匹配的拓扑
rmsd :1-200@CA out rmsd.dat
EOF
```

**验证匹配：**
```bash
# 检查拓扑中的原子数
cpptraj -p prmtop <<EOF
parminfo
EOF

# 检查轨迹中的原子数
cpptraj -p prmtop <<EOF
trajin traj.nc 1 1
trajinfo
EOF
```

## 6. 聚类分析内存不足

**典型错误信息：**
```
Error: Cluster: Could not allocate memory for distance matrix
```

**原因分析：**
- 聚类需要 N*N 的距离矩阵
- 10,000 帧 * 10,000 帧 * 8 bytes = 800 MB
- 100,000 帧需要 80 GB

**解决方案：**

```bash
# 方案1：使用 stride 降低帧数
cpptraj -p prmtop <<EOF
trajin traj.nc 1 last 20   # 每20帧取1帧
cluster out cluster.dat summary summary.dat \
  reps representative repout rep.pdb \
  :1-200@CA epsilon 2.0
EOF

# 方案2：先随机抽样
cpptraj -p prmtop <<EOF
trajin traj.nc
random 1000 seed 12345     # 随机选1000帧
cluster out cluster.dat \
  :1-200@CA epsilon 2.0
EOF

# 方案3：使用基于密度的聚类（无需全部距离矩阵）
# DBSCAN 方法
cluster dbscan minpoints 5 epsilon 2.0 \
  :1-200@CA out cluster.dat

# 方案4：使用 hierarchical（层次聚类，内存效率更好）
cluster hieragglo epsilon 2.0 \
  :1-200@CA out cluster.dat
```

## 7. PDB 格式原子数限制

**典型错误信息：**
```
Error: Atom number exceeds PDB format limit (99999)
```

**原因分析：**
- PDB 格式原子编号最多5位（列 7-11）
- 超过 99,999 个原子时编号溢出

**解决方案：**

```bash
# 输出为 NetCDF 格式（无原子数限制）
cpptraj -p prmtop <<EOF
trajin traj.nc
trajout output.nc netcdf    # 使用 NetCDF 而非 PDB
EOF

# 如必须输出 PDB，先 strip 溶剂
cpptraj -p prmtop <<EOF
trajin traj.nc
strip :WAT
trajout output.pdb
EOF

# 使用 PDBx/mmCIF 格式（支持更多原子）
cpptraj -p prmtop <<EOF
trajin traj.nc
trajout output.cif
EOF
```

## 8. 分析速度优化

**慢速分析的原因：**
- 每帧都处理溶剂原子
- 一次性加载所有分析命令
- 频繁的 I/O 操作

**优化策略：**

```bash
# 1. 先预处理：去溶剂 + autoimage，保存中间轨迹
cpptraj -p prmtop <<EOF
trajin traj.nc
autoimage
strip :WAT
strip :Na+ :Cl-
trajout processed.nc netcdf
EOF

# 2. 使用预处理后的轨迹进行分析
cpptraj -p stripped.prmtop <<EOF
trajin processed.nc
rmsd :1-200@CA out rmsd.dat
radgyr :1-200 out rg.dat
distance :201@CA :100@CA out dist.dat
EOF

# 3. 合并多个分析到一次运行（减少 I/O）
cpptraj -p stripped.prmtop <<EOF
trajin processed.nc
rmsd :1-200@CA out rmsd.dat
radgyr :1-200 out rg.dat
hbond :1-200 out hbond.dat series
molsurf :1-200 out sasa.dat
EOF
```

**并行化分析（手动）：**
```bash
# 将轨迹分成多段，并行处理
cpptraj -p prmtop <<EOF
trajin traj.nc 1 2500
rmsd :1-200@CA out rmsd_part1.dat
EOF
&

cpptraj -p prmtop <<EOF
trajin traj.nc 2501 5000
rmsd :1-200@CA out rmsd_part2.dat
EOF
&

# 合并结果
cat rmsd_part1.dat rmsd_part2.dat > rmsd_all.dat
```

## 问题速查表

| 问题 | 症状 | 解决方案 |
|------|------|---------|
| 内存不足 | OOM killed | strip 溶剂 + stride |
| Mask 错误 | parse error | 检查语法/空格/括号 |
| NetCDF 损坏 | read error | ncdump 诊断 + 二分恢复 |
| RMSD 异常大 | >10 A | autoimage + 正确参考 |
| 拓扑不匹配 | atom count error | parmstrip/parmwrite |
| 聚类 OOM | distance matrix | stride + 随机抽样 |
| 原子数溢出 | PDB limit | NetCDF 输出 |
| 分析太慢 | 耗时过长 | 预处理去溶剂 + 并行 |
