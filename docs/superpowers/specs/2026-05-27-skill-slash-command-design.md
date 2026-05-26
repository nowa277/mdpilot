# Skill 系统重构 + 斜杠命令交互设计

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 MDPilot 的 skill 体系从工具级自动匹配重构为面向用户的工作流级斜杠命令，前端支持 `/` 触发 + Tab 补全 + `+` 按钮分类面板。

**Architecture:** 新建独立的 `src/mdpilot/skills/` 目录存放 17 个面向用户的 skill（工作流/AI服务/概念/排错四类），保留现有 `src/mdpilot/tools/builtin/skills/` 供 agent 自动匹配。前端新增 `SlashCommandMenu` 组件替代 `SkillSelector`，输入框检测 `/` 向上弹窗、`+` 按钮展开分类面板，选中后以 `/command` 形式插入输入框。

**Tech Stack:** Python (FastAPI, dataclass), TypeScript (React, TanStack Query), Tailwind CSS

---

## 1. Skill 目录结构

```
src/mdpilot/skills/
├── workflows/           # 工作流 (8)
│   ├── md-protein.md
│   ├── md-ligand.md
│   ├── md-membrane.md
│   ├── md-nucleic.md
│   ├── free-energy.md
│   ├── enhanced-sampling.md
│   ├── md-metallo.md
│   └── md-constant-ph.md
├── ai-services/         # AI 服务 (2)
│   ├── alphafold2.md
│   └── bioreason.md
├── concepts/            # 概念参考 (3)
│   ├── force-field.md
│   ├── water-model.md
│   └── equilibration.md
└── troubleshooting/     # 排错 (4)
    ├── fix-pdb.md
    ├── fix-leap.md
    ├── fix-crash.md
    └── fix-analysis.md
```

## 2. Skill Frontmatter 规范

每个 `.md` 文件包含规范的 YAML frontmatter：

```yaml
---
name: md-protein
title: 标准蛋白 MD 模拟
description: 能量最小化 → 加热 → 平衡 → 成品模拟的完整蛋白 MD 工作流
tags: [md, protein, simulation, amber, minimization, equilibration, production]
triggers: [standard md, protein md, 蛋白模拟, MD simulation]
category: workflow
command: /md-protein
tools:
  - name: pdb4amber
    node: lab03
    exec: local_subprocess
  - name: reduce
    node: lab03
    exec: local_subprocess
  - name: tleap
    node: lab03
    exec: local_subprocess
  - name: pmemd_cuda
    node: lab03
    exec: local_subprocess
  - name: cpptraj
    node: lab03
    exec: local_subprocess
---
```

**字段说明：**
- `name`: 唯一标识，小写+连字符
- `title`: 中文显示名
- `description`: 一句话功能说明
- `tags`: 搜索关键词（英文小写）
- `triggers`: 触发关键词（含中英文）
- `category`: `workflow` | `ai-service` | `concept` | `troubleshooting`
- `command`: 斜杠命令标识符
- `tools`: 依赖的 builtin tool 列表，每个含 `name`/`node`/`exec`

**命名规则：**
- MD 工作流统一 `/md-*` 前缀
- 排错统一 `/fix-*` 前缀
- 概念/AI 服务无特殊前缀
- 命令长度 3-18 字符

**tools 路径来源：** subagent 写入时读取 project memory 中的 `[[remote-tool-architecture]]` 和 `[[remote-service-ops]]`，以及 `knowledge/3-workflows/` 下的源文件确定每个工作流的工具链和执行节点。

## 3. 完整 Skill 清单

### 工作流 (workflow)

| 命令 | 名称 | 描述 |
|------|------|------|
| `/md-protein` | 标准蛋白 MD 模拟 | 能量最小化 → 加热 → 平衡 → 成品模拟 |
| `/md-ligand` | 蛋白-配体复合物 MD | 含配体参数化 (antechamber → parmchk2 → tleap) |
| `/md-membrane` | 膜蛋白 MD | 含膜构建 (packmol-memgen) 与平衡 |
| `/md-nucleic` | 核酸 MD | DNA/RNA 模拟 |
| `/free-energy` | 自由能计算 | MM/PBSA, TI, FEP |
| `/enhanced-sampling` | 增强采样 | aMD, GaMD, REMD, SGLD |
| `/md-metallo` | 金属蛋白建模 | MCPB.py 金属位点建模 |
| `/md-constant-ph` | 恒 pH MD | 恒 pH 分子动力学 |

### AI 服务 (ai-service)

| 命令 | 名称 | 描述 |
|------|------|------|
| `/alphafold2` | 结构预测 | AlphaFold2 蛋白质三维结构预测 (lab02) |
| `/bioreason` | 功能注释 | BioReason-Pro 蛋白功能注释 (lab06) |

### 概念参考 (concept)

| 命令 | 名称 | 描述 |
|------|------|------|
| `/force-field` | 力场选择指南 | ff19SB, ff14SB, GAFF2 等 |
| `/water-model` | 水模型对比 | TIP3P, OPC, OPC3 等 |
| `/equilibration` | 系统平衡策略 | heating, density, NVT, NPT |

### 排错 (troubleshooting)

| 命令 | 名称 | 描述 |
|------|------|------|
| `/fix-pdb` | PDB 文件修复 | PDB 格式问题排查 |
| `/fix-leap` | LEaP 错误排查 | tleap 常见错误 |
| `/fix-crash` | 模拟崩溃修复 | SHAKE, NaN, vlimit 错误 |
| `/fix-analysis` | 轨迹分析问题 | cpptraj 分析异常 |

## 4. 后端改动

### 4.1 `SkillMeta` 新增字段

```python
@dataclass
class SkillMeta:
    name: str
    title: str
    description: str
    tags: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    source: str = "user"
    file_path: Path | None = None
    category: str = ""          # 新增: workflow | ai-service | concept | troubleshooting
    command: str = ""           # 新增: /md-protein
    tools: list[dict] = field(default_factory=list)  # 新增: 依赖的 builtin tools
    _l2_cache: str | None = field(default=None, repr=False)
```

### 4.2 `UnifiedSkillRegistry.discover_all` 增加扫描路径

```python
# 现有路径（工具级，不暴露给用户）:
#   src/mdpilot/tools/builtin/  → 12 个 builtin skill

# 新增路径（面向用户，斜杠命令可选）:
skills_dir = Path(__file__).resolve().parent.parent / "skills"
if skills_dir.is_dir():
    count += self._scan_dir(skills_dir, source="skill")
```

### 4.3 `_load_l1` 解析新字段

从 frontmatter 解析 `category`、`command`、`tools` 字段。`tools` 存储为 `list[dict]`。

### 4.4 API 改动

`GET /api/v1/skills` 响应新增字段：

```json
{
  "name": "md-protein",
  "title": "标准蛋白 MD 模拟",
  "description": "能量最小化 → 加热 → 平衡 → 成品模拟的完整蛋白 MD 工作流",
  "tags": ["md", "protein", "simulation"],
  "source": "skill",
  "category": "workflow",
  "command": "/md-protein",
  "tools": [
    {"name": "pdb4amber", "node": "lab03", "exec": "local_subprocess"}
  ]
}
```

新增可选查询参数 `category` 过滤：`GET /api/v1/skills?category=workflow`

### 4.5 `_inject_context` 不变

现有逻辑已支持 `active_skills`，前端传 `["md-protein"]` 即可匹配新 skill。

## 5. 前端改动

### 5.1 删除旧组件

- 删除 `SkillSelector.tsx`

### 5.2 新建 `SlashCommandMenu.tsx`

两个入口，共享同一个组件：

**入口 1：输入 `/` 触发**
- 检测 textarea 值以 `/` 开头时，在输入框正上方弹出搜索式紧凑列表
- 列表按 category 分组显示
- 支持输入过滤（输入 `/md` 自动过滤匹配项）
- 弹窗位置：`bottom: 100%`，向上弹出，输入框位置不动

**入口 2：点击 `+` 按钮**
- 输入框左侧内嵌 `+` 按钮
- 点击后弹出分类卡片面板（向上弹出）
- 顶部有 Tab 切换：工作流 / AI 服务 / 概念 / 排错
- 卡片以 3 列网格展示，每个卡片显示 command + description

**共同行为：**
- 选中 skill → 弹窗关闭 → 输入框内容替换为 `/command ` + 光标等待用户输入
- 发送时解析：提取 `/command` 作为 `active_skills`，空格后内容作为 `prompt`

### 5.3 键盘交互

- `↑↓` 在候选列表中移动高亮
- `Tab` 补全当前输入到第一个匹配项，再次 Tab 循环
- `Enter` 确认选中
- `Esc` 关闭弹窗

### 5.4 `ChatInput.tsx` 改造

- `onSubmit` 签名不变：`(content: string, activeSkills?: string[]) => void`
- 新增斜杠命令解析逻辑：
  ```typescript
  function parseSlashCommand(input: string): { command: string | null; prompt: string } {
    if (!input.startsWith('/')) return { command: null, prompt: input };
    const spaceIdx = input.indexOf(' ');
    if (spaceIdx === -1) return { command: input.slice(1), prompt: '' };
    return { command: input.slice(1, spaceIdx), prompt: input.slice(spaceIdx + 1) };
  }
  ```
- 删除 `activeSkills` state（改为从输入内容解析）
- 内嵌 `+` 按钮替代原来的 Skills 按钮

### 5.5 `SkillInfo` 类型更新

```typescript
export interface SkillInfo {
  name: string;
  title: string;
  description: string;
  tags: string[];
  source: string;
  category: string;       // 新增
  command: string;        // 新增
  tools: ToolRef[];       // 新增
}

export interface ToolRef {
  name: string;
  node: string;
  exec: string;
}
```

### 5.6 `fetchSkills` API 不变

调用 `GET /api/v1/skills`，返回数据自动包含新字段。

## 6. 数据流

```
用户输入: /md-protein 帮我跑一下 1aki 的模拟
                    ↓
ChatInput.parseSlashCommand():
  command = "md-protein"
  prompt  = "帮我跑一下 1aki 的模拟"
                    ↓
ChatInput.onSubmit(content, activeSkills=["md-protein"])
                    ↓
ChatPane.sendAgent(content, activeSkills)
                    ↓
useAgentChat.send(prompt, activeSkills=["md-protein"])
                    ↓
POST /api/v1/agent/stream
  { prompt, active_skills: ["md-protein"] }
                    ↓
AgentService.execute_with_stream → agent._active_skills = ["md-protein"]
                    ↓
Agent._inject_context(prompt, active_skills=["md-protein"])
  → UnifiedSkillRegistry.build_context()
    → 加载 md-protein.md L2 全文（含 tools 依赖链 + 执行节点）
    → 注入 system prompt "## Active Skills" 段
  → KnowledgeInjector.inject()
    → 知识库索引摘要
                    ↓
Agent system prompt 4 段式结构:
  Section 1: 静态身份
  Section 2: Active Skills (md-protein L2 全文 + tools 路径)
  Section 3: Auto-matched Skills
  Section 4: Knowledge Base 索引摘要
```

发送后输入框清空，不保留斜杠命令。

## 7. 视觉规范

遵循 MDPilot 现有设计系统：
- 背景色：`--bg-0: #07090e` ~ `--bg-3: #161b28`
- 强调色：`--accent-1: #00cfaa`（teal）
- 分类标签色：工作流=teal, AI服务=purple(#8b5cf6), 概念=blue(#3b82f6), 排错=amber(#fbbf24)
- 弹窗：glass panel 风格，`backdrop-filter: blur(24px)`，边框 `rgba(148,163,184,0.12)`
- 字体：代码用 `JetBrains Mono`，UI 用 `Inter`
- 弹窗动画：`0.15s ease-out` 向上滑入
