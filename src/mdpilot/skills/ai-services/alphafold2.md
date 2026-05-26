---
name: alphafold2
title: 结构预测
description: AlphaFold2 蛋白质三维结构预测 (lab02 GPU 节点)
tags: [alphafold2, structure-prediction, protein-structure, af2]
triggers: [alphafold, structure prediction, 结构预测, AF2, 折叠预测]
category: ai-service
command: /alphafold2
tools:
  - name: run_alphafold2, node: lab02, exec: celery_task
---

# AlphaFold2 结构预测

AlphaFold2 蛋白质三维结构预测服务，运行于 lab02 GPU 节点，通过 Celery 异步任务调度执行。

## 输入要求

- **FASTA 序列**：标准 FASTA 格式的氨基酸序列（单链或多链）
- **UniProt ID**：提供 UniProt 登录号，系统自动获取对应序列
- 序列长度建议 ≤ 2000 残基；超长序列需分域处理

## 输出

| 输出项 | 说明 |
|--------|------|
| PDB 模型 | 按模型置信度排名的 5 个 PDB 文件（ranked_0 ~ ranked_4） |
| pLDDT 分数 | 每残基置信度分数（0-100），嵌入 PDB B-factor 列 |
| PAE 矩阵 | 预测对齐误差矩阵，反映域间相对位置可靠性 |
| MSA 文件 | 多序列比对结果（A3M / STO 格式） |

## 执行流程

1. 序列验证与格式检查
2. MSA 生成（JackHMMER / HHblits 搜索 UniRef / BFD 数据库）
3. 结构模板搜索（PDB70 / PDB 模板库）
4. 模型推理（5 个 recycles，生成 5 个候选模型）
5. 结果排序与输出

## 运行时间

| 序列长度 | 预计时间（lab02 A100） |
|----------|----------------------|
| < 300 aa | 10-20 分钟 |
| 300-700 aa | 30-60 分钟 |
| 700-1500 aa | 1-3 小时 |
| > 1500 aa | 3-8+ 小时 |

## 从预测到 MD 模拟

预测结构可直接作为 MD 模拟的起始构型，推荐流程：

1. **结构清洗**：使用 `pdb4amber` 处理非标准残基、氢原子、端基
   ```
   pdb4amber -i ranked_0.pdb -o cleaned.pdb
   ```
2. **缺失环修复**：若 pLDDT 显示低置信度区域（< 70），可用 MODELLER 补全缺失环
3. **质子化状态**：根据 H++ 或 PDB2PQR 预测正确质子化状态
4. **力场适配**：清洗后的结构可直接用于 tleap/AMBER 体系构建

## 注意事项

- pLDDT > 90 的区域结构高度可靠，可放心用于 MD
- pLDDT 70-90 区域骨架可信，侧链需关注
- pLDDT < 70 区域（通常为柔性环或无序区）建议补模或截断处理
- 多链蛋白的 PAE 矩阵可用于判断链间相对取向可靠性
