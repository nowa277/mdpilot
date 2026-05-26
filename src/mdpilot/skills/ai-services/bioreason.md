---
name: bioreason
title: 功能注释
description: BioReason-Pro 蛋白功能注释与 GO terms 预测 (lab06)
tags: [bioreason, function-annotation, go-terms, protein-function]
triggers: [bioreason, function annotation, 功能注释, GO terms, protein function]
category: ai-service
command: /bioreason
tools:
  - name: run_bioreason, node: lab06, exec: celery_task
---

# BioReason-Pro 功能注释

BioReason-Pro 蛋白功能注释服务，运行于 lab06 节点，通过 Celery 异步任务调度执行。

## 输入要求

- **蛋白质序列**：FASTA 格式氨基酸序列
- **PDB 结构**：上传 PDB 文件，系统提取序列后执行注释（同时利用结构信息提升预测精度）

两种输入均可，同时提供序列和结构可获得更全面的功能注释。

## 输出

| 输出项 | 说明 |
|--------|------|
| GO 分子功能 (MF) | Gene Ontology Molecular Function terms + 置信度分数 |
| GO 生物过程 (BP) | Gene Ontology Biological Process terms + 置信度分数 |
| GO 细胞组分 (CC) | Gene Ontology Cellular Component terms + 置信度分数 |
| EC 编号 | Enzyme Commission 编号及催化反应注释 |
| 通路关联 | KEGG / Reactome 通路映射 |

置信度分数范围 0-1，推荐阈值 ≥ 0.5 作为可信注释。

## 执行流程

1. 序列特征提取（进化保守性、理化性质）
2. 结构特征提取（若提供 PDB：表面口袋、活性位点几何）
3. 多模型集成预测 GO terms
4. 酶功能与通路关联推断
5. 结果汇总与置信度排序

## 运行时间

通常 5-15 分钟完成注释，取决于输入序列长度及是否附带结构信息。

## 功能注释指导 MD 模拟

注释结果可直接指导模拟方案设计：

### 活性位点识别
- GO 分子功能 term（如 "ATP binding"、"catalytic activity"）结合结构分析定位活性位点残基
- EC 编号提供底物/产物信息，用于对接或 MD 体系准备

### 功能域定位
- 注释中的功能域边界可用于：
  - 截取功能域单独模拟（减少体系规模）
  - 设置位置限制（restraint）时保护功能关键区域

### 突变研究设计
- 高置信度功能注释残基优先作为突变扫描目标
- 结合 pLDDT 与功能分数交叉筛选关键残基

### 别构位点探索
- 距离活性位点较远但 BP/CC 注释关联的残基可能是别构调控位点
- 可设为 metadynamics CV 或目标残基进行增强采样

## 注意事项

- 注释结果为计算预测，建议与实验数据（UniProt 注释、文献）交叉验证
- EC 编号预测精度通常高于 GO BP terms，优先采信高置信度 EC 注释
- 对于研究较少的蛋白，GO 注释可能不完整，可结合同源蛋白注释补充
