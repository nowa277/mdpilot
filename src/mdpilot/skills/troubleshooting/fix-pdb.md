---
name: fix-pdb
title: PDB 文件修复
description: PDB 格式问题排查与修复，包括缺失原子、交替构象、组氨酸质子化
tags: [pdb, fix, structure, preparation, cleaning]
triggers: [pdb fix, pdb error, PDB修复, 结构问题, pdb问题]
category: troubleshooting
command: /fix-pdb
tools:
  - name: pdb4amber, node: lab03, exec: local_subprocess
  - name: reduce, node: lab03, exec: local_subprocess
---

# PDB 文件修复指南

## 1. 缺失残基/原子

**检测方法：**
- 查看 PDB 文件中的 `REMARK 465`（缺失残基）和 `REMARK 470`（缺失原子）
- 使用 `pdb4amber --dry` 检查输出日志
- 用 PyMOL/ChimeraX 可视化检查结构中的"断链"

**解决方案：**

| 方法 | 适用场景 | 命令 |
|------|---------|------|
| MODELLER | 大段缺失残基（loop区） | `modeller` 建模补全 |
| pdbfixer | 少量缺失原子/残基 | `pdbfixer input.pdb` |
| tleap | 仅缺侧链氢/重原子 | `tleap` 自动补全 |

**MODELLER 示例：**
```python
from modeller import *
from modeller.automodel import *
env = environ()
env.io.atom_files_directory = ['.']
a = automodel(env, alnfile='alignment.ali', knowns='template', sequence='target')
a.starting_model = 1
a.ending_model = 1
a.make()
```

## 2. 交替构象（Alternate Conformations）

PDB 文件中同一原子位置存在多个构象（altLoc 标识 A/B/C）。

**处理方式：**

```bash
# 方法1：保留最高占有率构象（推荐）
pdb4amber -i input.pdb -o output.pdb --altloc occupancy

# 方法2：保留第一个构象
pdb4amber -i input.pdb -o output.pdb --altloc first

# 方法3：手动检查后选择
# 在 ChimeraX 中查看各构象，根据生物学意义选择
```

**注意事项：**
- 不要直接删除 altLoc 行，会导致原子编号不连续
- 配体通常有交替构象，需确认生物学相关构象
- pdb4amber 处理后会自动重新编号

## 3. 插入码（Insertion Codes）

某些残基有插入码（如 45A、45B），常见于抗体 CDR 区。

**处理方式：**
- `pdb4amber` 自动处理插入码，重新编号残基
- 手动处理：删除插入码残基或重新编号

```bash
pdb4amber -i input.pdb -o output.pdb
# 输出日志会报告处理的插入码残基
```

## 4. 组氨酸质子化

组氨酸（HIS）有三种质子化状态，对静电计算和氢键网络影响重大。

| 残基名 | 质子化位置 | 适用场景 |
|--------|-----------|---------|
| HID (HSD) | Delta-N | 默认状态 |
| HIE (HSE) | Epsilon-N | 接近酸性环境 |
| HIP (HSP) | 双质子化（+1电荷） | 接近碱性环境/催化活性位点 |

**PROPKA 预测 pKa：**
```bash
# 使用 pdb2pqr 调用 PROPKA
pdb2pqr --with-ph 7.4 --ff AMBER input.pdb output.pqr
# 查看 output.propka 文件中各 HIS 的预测 pKa

# 判断规则：
# pKa > 7.4 → HIP（双质子化）
# pKa < 7.4 → HID 或 HIE（根据局部氢键网络判断）
```

**reduce 自动添加氢：**
```bash
# 自动根据局部环境选择质子化状态
reduce -BUILD -DB /path/to/reduce_wwPDB_het_dict.txt input.pdb > output.pdb

# pdb4amber 集成 reduce
pdb4amber -i input.pdb -o output.pdb --reduce
```

## 5. 二硫键

半胱氨酸（CYS）形成二硫键需转换为 CYX。

**处理步骤：**

```bash
# 方法1：手动将 CYS 改为 CYX
sed -i 's/CYS/CYX/g' input.pdb

# 方法2：在 tleap 中自动检测
# tleap 会根据距离自动创建二硫键
```

**tleap 中手动指定二硫键：**
```tclap
# 加载结构后
bond m.cys45.SG m.cys98.SG
```

**验证二硫键：**
- 检查 S-S 距离应在 2.0-2.1 A
- 使用 `cpptraj` 计算距离确认

## 6. 非标准残基

| 原始残基 | 标准替换 | 说明 |
|---------|---------|------|
| MSE (硒代蛋氨酸) | MET | 常见于表达系统引入 |
| SEP (磷酸化丝氨酸) | SER 或专用参数 | 需要额外参数文件 |
| TPO (磷酸化苏氨酸) | THR 或专用参数 | 需要额外参数文件 |
| PTR (磷酸化酪氨酸) | TYR 或专用参数 | 需要额外参数文件 |
| CSO (羟甲基半胱氨酸) | CYS | 翻译后修饰 |

**pdb4amber 自动处理：**
```bash
# MSE → MET 自动转换
pdb4amber -i input.pdb -o output.pdb
```

**磷酸化残基处理：**
```bash
# 方法1：替换为标准残基（丢失磷酸基团）
sed -i 's/SEP/SER/g' input.pdb

# 方法2：使用专用参数（保留磷酸基团）
# 需要加载磷酸化氨基酸的 frcmod/off 文件
# 参考 AMBER 力场扩展参数
```

## 7. NMR 多模型

NMR 结构文件包含多个模型（MODEL/ENDMDL）。

```bash
# 提取第一个模型
grep -A 10000 "^MODEL        1" input.pdb | grep -B 10000 "^ENDMDL" | head -n -1 > model1.pdb

# 或使用 pdb4amber（默认取第一个模型）
pdb4amber -i input.pdb -o output.pdb --model 1
```

## 8. 完整清洗工作流

```bash
# Step 1: pdb4amber 基础清洗
pdb4amber -i raw.pdb -o cleaned.pdb --reduce --dry --altloc occupancy

# Step 2: 检查输出日志
# 关注：缺失残基、非标准残基、交替构象处理结果

# Step 3: 手动检查
# - 确认组氨酸质子化状态（如需精确控制）
# - 确认二硫键配对
# - 确认配体/辅因子完整性

# Step 4: tleap 建立拓扑
#   source leaprc.protein.ff14SB
#   source leaprc.water.opc
#   mol = loadPDB cleaned.pdb
#   check mol          # 检查问题
#   savePDB mol check.pdb
#   saveAmberParm mol prmtop inpcrd
```

## 常见问题速查

| 错误现象 | 可能原因 | 解决方案 |
|---------|---------|---------|
| tleap 报 "unknown residue" | 非标准残基名 | pdb4amber 或手动替换 |
| 原子重叠 | 交替构象未处理 | `--altloc occupancy` |
| 氢键网络异常 | 组氨酸质子化错误 | PROPKA 预测 + 手动指定 |
| 链断裂 | 缺失残基/原子 | MODELLER 补全 |
| 电荷不匹配 | 非标准残基未处理 | 检查并替换/添加参数 |
