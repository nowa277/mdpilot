<!--
+-----------------------------------------------------------------------+
|  DreamSeed 种梦计划 — AI创造者大赛  官方 README 模板                  |
|                                                                       |
|  使用说明：                                                            |
|  1. 将本模板放在参赛仓库根目录 README.md 的顶部                        |
|  2. 头图使用 DreamField 官方公开活动图片地址                          |
|  3. 请保留 DREAMFIELD_README_HEADER_START / END 标识                  |
|  4. 分割线以下供创作者自由编写项目内容                                  |
+-----------------------------------------------------------------------+
-->

<!-- DREAMFIELD_README_HEADER_START -->

<p align="center">
  <a href="https://www.dreamfield.top">
    <img src="https://www.dreamfield.top/dream-field/contest-readme/assets/dreamseed-readme-banner.png" alt="DreamSeed 种梦计划参赛作品" width="100%" />
  </a>
</p>

<!-- DREAMFIELD_README_HEADER_END -->


<div align="center">

# MDPilot

**AI 驱动的分子动力学助手**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![AMBER](https://img.shields.io/badge/AMBER-24-orange?logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDE2IDE2Ij48dGV4dCB4PSIyIiB5PSIxMiIgZm9udC1zaXplPSIxMiIgZmlsbD0id2hpdGUiPkE8L3RleHQ+PC9zdmc+)](https://ambermd.org)
[![AlphaFold2](https://img.shields.io/badge/AlphaFold2-2.4+-4285F4?logo=google&logoColor=white)](https://github.com/google-deepmind/alphafold)
[![BioReason](https://img.shields.io/badge/BioReason-goGPT-8B5CF6)](https://github.com/bowang-lab/BioReason-Pro)
[![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)

智能多 Agent 系统，通过自然语言交互自动化 AMBER 分子动力学模拟、AlphaFold2 结构预测和生物分子推理。

[功能特性](#-功能特性) · [系统架构](#-系统架构) · [快速开始](#-快速开始) · [API 概览](#-api-概览)

</div>

---

<p align="center">
<img src="photos&videos/display_02.gif" alt="MDPilot 演示" width="720" />
</p>

## 功能特性

- **自然语言 MD 工作流** — 用自然语言描述模拟目标，MDPilot 自动规划、执行和监控全流程：体系准备、能量最小化、平衡和生产 MD。
- **AlphaFold2 集成** — 直接在对话中提交蛋白质结构预测任务到远程 GPU 集群。
- **生物分子推理** — 基于 BioReason 实现突变注释、结构-功能分析和领域专业知识推理。
- **多范式 Agent** — 三种专用 Agent 架构（ReAct、Plan-and-Solve、Reflection），根据任务复杂度自动选择。
- **远程 HPC 编排** — 通过 SSH + Celery 在多节点 GPU 集群上执行模拟，支持实时监控。
- **实时流式 UI** — 基于 SSE 的对话界面，实时展示 Agent 思考过程、工具执行和工作流进度。
- **完整工具集** — 20+ 内置工具，覆盖 AMBER（tleap、sander、pmemd、cpptraj、antechamber）、PDB 操作、PROPKA pKa 预测、H++ 质子化和更多功能。
- **双界面** — React Web UI 和终端 UI（Textual/Ratatui）。

## 系统架构

```text
┌─────────────────────────────────────────────────────────────────────┐
│                    React 前端 (Vite + Radix)                        │
│                                                                     │
│   对话面板           工作流面板           集群监控                    │
│   · SSE 流式传输    · 工具卡片           · GPU 使用率环形图          │
│   · Markdown 渲染   · 进度条             · 节点健康状态              │
│   · 代码高亮        · AlphaFold2 卡片    · 实时 WebSocket            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  SSE / WebSocket / REST
┌──────────────────────────────▼──────────────────────────────────────┐
│                       FastAPI 后端                                   │
│                                                                     │
│   Routers ─── Services ─── Auth ─── Middleware                       │
│   · /agent/chat (SSE)                                               │
│   · /bioreason/*  /alphafold2/*                                     │
│   · /chats  /tasks  /health                                         │
├─────────────────────────────────────────────────────────────────────┤
│                        Agent 层                                      │
│                                                                     │
│   ┌───────────┐  ┌────────────────┐  ┌────────────┐                │
│   │   ReAct   │  │ Plan-and-Solve │  │ Reflection │                │
│   │  (简单)   │  │   (工作流)     │  │  (优化)    │                │
│   └─────┬─────┘  └───────┬────────┘  └─────┬──────┘                │
│         └────────────────┼──────────────────┘                       │
│                AgentBase（共享基础设施）                               │
│                                                                     │
│   LLMCaller · ToolDispatcher · ContextManager · BudgetTracker       │
│   SkillRegistry · Checkpoint · DependencyGraph · ParallelExecutor   │
│   KnowledgeInjector · ErrorClassifier · RecoveryCoordinator         │
├─────────────────────────────────────────────────────────────────────┤
│                       工具注册表                                      │
│                                                                     │
│   AMBER ─ tleap · sander · pmemd · cpptraj · antechamber · pdb4amber│
│   AlphaFold2 · BioReason · PDB（获取/清理/信息）                     │
│   PROPKA · H++ · Bash · 文件操作 · SSH · 知识库 · 向导              │
├─────────────────────────────────────────────────────────────────────┤
│                     集成层                                           │
│                                                                     │
│   RemoteToolClient ── Celery Workers ── SSH Executor                │
│   AlphaFold2 客户端          BioReason 客户端                       │
├─────────────────────────────────────────────────────────────────────┤
│              数据库（SQLAlchemy 2.0 异步 ORM）                        │
│                                                                     │
│   Chat · Message · Task · AgentSession                              │
└─────────────────────────────────────────────────────────────────────┘
```

## Agent 范式

| 范式               | 类名                 | 触发条件                      | 行为                                                    |
|:-------------------|:---------------------|:------------------------------|:--------------------------------------------------------|
| **ReAct**          | `ReActAgent`         | 简单问答、单工具任务          | 推理 → 执行 → 观察循环，支持工具调用                     |
| **Plan-and-Solve** | `PlanAndSolveAgent`  | 多步工作流（MD、AF2）         | 分解任务 → 生成计划 → 按序执行步骤                       |
| **Reflection**     | `ReflectionAgent`    | 优化、调试                    | 执行 → 评价 → 修正循环，支持自我评估                     |

`AgentRouter` 使用 `TaskClassifier` 为每个用户请求自动选择最优范式。所有 Agent 共享 `AgentBase` 基类，提供 LLM 调用、工具分发、上下文压缩、预算追踪、错误恢复和技能加载等功能。

<p align="center">
<img src="photos&videos/workflow_display.png" alt="工作流面板 — 工具执行与进度追踪" width="720" />
</p>

## 技术栈

<table>
<tr><th>后端</th><th>前端</th></tr>
<tr>
<td>

- **FastAPI** + Uvicorn（异步 Web 框架）
- **SQLAlchemy 2.0** 异步 ORM
- **LiteLLM**（多提供商 LLM 网关）
- **Pydantic v2**（数据校验与配置）
- **AsyncSSH**（远程执行）
- **Celery** + Redis（分布式任务）
- **Alembic**（数据库迁移）
- **Textual** / **PyRatatui**（终端 UI）

</td>
<td>

- **React 18** + Vite
- **Tailwind CSS** + Radix UI
- **Zustand**（状态管理）
- **SSE** 流式传输与事件解析
- **WebSocket** 实时更新
- **MSW**（Mock Service Worker）
- **Vitest** + Testing Library
- **Playwright**（端到端测试）

</td>
</tr>
</table>

## 项目结构

```text
src/mdpilot/                          # 后端（196 个 Python 模块）
├── agent/                            # 多范式 Agent 核心
│   ├── base.py                       # AgentBase — 共享基础设施
│   ├── react_agent.py                # ReAct 范式
│   ├── plan_solve.py                 # Plan-and-Solve 范式
│   ├── reflection.py                 # Reflection 范式
│   ├── router.py                     # 范式路由器
│   ├── task_classifier.py            # 任务 → 范式映射
│   ├── orchestrator.py               # 多 Agent 编排
│   ├── skills.py                     # 动态技能加载
│   ├── knowledge_injector.py         # 领域知识注入
│   ├── context_compressor.py         # 上下文窗口管理
│   ├── parallel_executor.py          # 并行工具执行
│   ├── dependency_graph.py           # 工具依赖解析
│   ├── checkpoint.py                 # 状态持久化与恢复
│   ├── error_classifier.py           # 错误分类
│   ├── recovery_coordinator.py       # 故障恢复策略
│   ├── budget.py                     # Token/成本预算追踪
│   └── monitoring.py                 # Agent 指标与可观测性
├── api/                              # FastAPI 应用层
│   ├── app.py                        # 应用工厂与生命周期
│   ├── routers/                      # REST、SSE 与 WebSocket 端点
│   ├── services/                     # 业务逻辑层
│   ├── models/                       # Pydantic 请求/响应模型
│   ├── middleware/                    # 日志与 CORS 中间件
│   └── websockets/                   # WebSocket 处理器
├── tools/                            # 工具注册表与内置工具
│   ├── registry.py                   # 自动发现工具注册
│   ├── dispatcher.py                 # 工具执行分发
│   ├── security.py                   # 工具沙箱与权限控制
│   ├── wizards/                      # 交互式工具向导
│   │   ├── engine.py                 # 向导执行引擎
│   │   └── manifests/                # YAML 向导定义
│   └── builtin/                      # 20+ 内置工具
│       ├── amber/                    # tleap、sander、pmemd、cpptraj、antechamber、pdb4amber、reduce
│       ├── alphafold2/               # 结构预测
│       ├── bioreason/                # 生物分子推理
│       ├── pdb/                      # PDB 获取、清理、信息
│       ├── hplusplus.py              # H++ 质子化服务器
│       ├── propka.py                 # PROPKA pKa 预测
│       ├── bash.py                   # Shell 命令执行
│       ├── file_ops.py               # 文件 I/O 操作
│       └── ssh_tools.py              # 远程 SSH 命令
├── integrations/                     # 远程服务客户端
│   ├── alphafold2/                   # AlphaFold2 Celery 客户端
│   ├── bioreason/                    # BioReason Celery 客户端
│   └── base/                         # 远程工具客户端基类
├── coordination/                     # 工作流协调层
│   ├── execution_planner.py          # 执行计划生成
│   ├── plan_generator.py             # 计划步骤分解
│   ├── plan_validator.py             # 计划正确性验证
│   ├── resource_guard.py             # 资源限制执行
│   └── validators/                   # 多层级验证器
├── database/                         # 异步 ORM 数据层
│   ├── models/                       # SQLAlchemy 模型（Chat、Message、Task、Session）
│   ├── repositories/                 # 类型化数据访问层
│   ├── engine.py                     # 异步引擎工厂
│   └── session.py                    # 会话管理
├── workflows/                        # MD 工作流定义
│   ├── standard_protein.py           # 标准蛋白质 MD 工作流
│   ├── protonation.py                # 质子化状态处理
│   ├── build_recorder.py             # 构建步骤记录
│   └── validator.py                  # 工作流验证
├── knowledge/                        # 领域知识库
│   ├── index.py                      # 知识检索索引
│   └── loader.py                     # 知识源加载器
├── llm/                              # LLM 提供商抽象层
│   ├── provider.py                   # 多提供商 LLM 接口
│   └── fallback.py                   # 提供商回退链
├── config/                           # 配置系统
├── cli/                              # CLI 命令（Typer）
├── tui/                              # Textual 终端 UI
├── tui_pyratatui/                    # PyRatatui 终端 UI
├── ui/                               # Rich 进度与结果面板
├── pipelines/                        # 数据处理管道
└── plan_legacy/                      # 旧版计划执行器

mdpilot-frontend/src/                 # 前端（159 个 TypeScript 模块）
├── app/                              # 应用外壳、布局、路由
│   ├── App.tsx                       # 根组件
│   ├── router.tsx                    # 路由配置
│   ├── layouts/                      # WorkspaceLayout、Sidebar、Topbar、RightPanel
│   └── providers.tsx                 # 上下文 Provider
├── features/
│   ├── chat/                         # 对话功能模块
│   │   ├── components/               # ChatPane、MessageList、AgentBlock、ToolCard、Markdown
│   │   ├── hooks/                    # useAgentChat、useChatSocket、useSendMessage
│   │   ├── store/                    # Zustand 对话状态
│   │   └── api/                      # SSE 解析、API 调用
│   ├── workflow/                     # 工作流面板功能
│   │   ├── components/               # ToolCard、AlphaFold2Card、AmberCard、ProgressBar
│   │   ├── hooks/                    # useWorkflowSync
│   │   └── store/                    # Zustand 工作流状态
│   └── cluster/                      # GPU 集群监控
│       ├── components/               # ClusterMonitorPage、NodeCard、GpuRing
│       ├── hooks/                    # useNodes
│       └── api/                      # 节点状态 API
├── shared/                           # 共享工具
│   ├── api/                          # Axios 实例、错误处理、健康检查
│   ├── ws/                           # WebSocket 客户端（自动重连）
│   ├── hooks/                        # 共享 React Hooks
│   ├── ui/                           # 可复用 UI 组件（Button、ScrollArea 等）
│   ├── utils/                        # 时间格式化、类名、路径工具
│   ├── config/                       # 环境配置
│   └── types/                        # 共享 TypeScript 类型
├── components/                       # 全局组件（背景效果）
└── mocks/                            # MSW 处理器、测试数据、Mock WebSocket 服务器

tests/                                # 测试套件（204 个测试文件）
```

## 快速开始

### 前置条件

- Python 3.10+
- Node.js 20+ 及 pnpm
- AMBER（可选，用于模拟功能）
- Redis + Celery Worker（可选，用于分布式远程工具）

### 后端

```bash
git clone https://github.com/nowa277/mdpilot.git
cd mdpilot

python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# 编辑 .env — 设置 MDPILOT_API_KEY 及其他配置

mdpilot db upgrade                    # 初始化数据库

uvicorn mdpilot.api.app:create_app --factory --host 0.0.0.0 --port 18003
```

### 前端

```bash
cd mdpilot-frontend
pnpm install

cp .env.example .env
# 编辑 .env — 设置 VITE_API_URL 为后端地址

pnpm dev
```

### 环境变量

| 变量名                    | 说明               | 默认值                             |
|:--------------------------|:-------------------|:-----------------------------------|
| `MDPILOT_API_KEY`         | LLM 提供商 API 密钥 | *必填*                             |
| `MDPILOT_BASE_URL`        | 自定义 API 端点    | 提供商默认值                       |
| `MDPILOT_MODEL`           | LLM 模型名称       | `claude-sonnet-4-20250514`         |
| `MDPILOT_DATABASE_URL`    | 数据库连接字符串   | `sqlite+aiosqlite:///./mdpilot.db` |

完整变量列表请参见 `.env.example`。

## API 概览

| 端点                          | 方法    | 说明               |
|:------------------------------|:--------|:-------------------|
| `/health`                     | GET     | 服务健康检查       |
| `/api/v1/chats`               | GET/POST| 对话 CRUD          |
| `/api/v1/chats/{id}/messages` | GET/POST| 消息历史           |
| `/api/v1/agent/chat`          | POST    | Agent SSE 流       |
| `/api/v1/agent/task`          | POST    | 异步任务提交       |
| `/api/v1/bioreason/*`         | POST    | BioReason 端点     |
| `/api/v1/alphafold2/*`        | POST    | AlphaFold2 端点    |

Agent 对话端点返回 **Server-Sent Events**，结构化事件类型如下：

| 事件          | 说明                       |
|:--------------|:---------------------------|
| `thinking`    | Agent 推理步骤              |
| `tool_call`   | 工具调用（含参数）          |
| `tool_result` | 工具执行输出               |
| `plan_step`   | Plan-and-Solve 步骤更新    |
| `text_delta`  | 流式文本响应               |
| `done`        | 流结束                     |

## 远程集群配置

MDPilot 通过 SSH 在远程 HPC 节点上执行模拟：

1. **配置节点** — 在应用设置中添加集群节点地址、SSH 凭据和 conda 路径。
2. **Celery Workers** — 每个计算节点运行 Celery Worker，用于分布式任务执行（AlphaFold2、BioReason）。
3. **Redis Broker** — 作为 Celery 消息代理，连接后端与远程 Worker。
4. **SSH Executor** — 处理文件传输（SFTP）和命令执行，用于 AMBER 模拟。

<p align="center">
<img src="photos&videos/cluster_display.png" alt="集群监控 — GPU 使用率与节点健康状态" width="720" />
</p>

## 测试

```bash
# 后端
pytest                                # 运行所有测试
pytest tests/agent/                   # Agent 模块测试
pytest tests/ -m "not slow"          # 跳过慢速集成测试

# 前端
cd mdpilot-frontend
pnpm test                            # Vitest 单元测试
pnpm test:cov                        # 含覆盖率报告
```

## 项目统计

| 指标                  | 数量  |
|:----------------------|:------|
| 后端 Python 模块      | 196   |
| 前端 TypeScript 模块  | 159   |
| 测试文件              | 204   |
| 内置工具              | 20+   |
| Agent 范式            | 3     |

## 致谢

MDPilot 基于以下开源项目和服务构建：

| 项目          | 说明                 | 参考                                                                                                        |
|:--------------|:---------------------|:------------------------------------------------------------------------------------------------------------|
| **AMBER**     | 分子动力学模拟套件   | [ambermd.org](https://ambermd.org) · [Case et al., 2024](https://doi.org/10.1021/acs.jctc.4c00050)          |
| **AlphaFold2**| 蛋白质结构预测       | [DeepMind](https://github.com/google-deepmind/alphafold) · [Jumper et al., 2021](https://doi.org/10.1038/s41586-021-03819-2) |
| **BioReason** | 生物分子推理引擎     | [github.com/bowang-lab/BioReason-Pro](https://github.com/bowang-lab/BioReason-Pro)                           |

## 许可证

[Apache-2.0](LICENSE)
