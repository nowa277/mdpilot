# MDPilot

An AI-powered molecular dynamics assistant that automates AMBER simulations, protein structure prediction (AlphaFold2), and bio-molecular reasoning through a multi-paradigm agent architecture.

## Overview

MDPilot provides an intelligent interface for computational chemistry workflows. Users interact through natural language — describing what they want to simulate, analyze, or optimize — and the system autonomously plans, executes, and monitors molecular dynamics simulations on remote HPC clusters.

**Key capabilities:**

- Multi-step MD simulation workflows (system preparation → minimization → equilibration → production)
- AlphaFold2 protein structure prediction
- Bio-molecular reasoning and analysis
- GPU cluster monitoring across multiple nodes
- Three agent paradigms: ReAct, Plan-and-Solve, and Reflection

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    React Frontend (Vite)                      │
│  Chat · Workflow Panel · Cluster Monitor · AlphaFold2 Card   │
└──────────────────────────┬───────────────────────────────────┘
                           │ SSE / WebSocket / REST
┌──────────────────────────▼───────────────────────────────────┐
│                    FastAPI Backend                            │
│  Routers · Services · Auth · SSE Streaming                   │
├──────────────────────────────────────────────────────────────┤
│                  Agent Layer                                  │
│  ┌─────────┐ ┌──────────────┐ ┌────────────┐                │
│  │  ReAct   │ │ PlanAndSolve │ │ Reflection │                │
│  │ (simple) │ │ (workflows)  │ │ (optimize) │                │
│  └────┬─────┘ └──────┬───────┘ └─────┬──────┘                │
│       └──────────────┼───────────────┘                        │
│              AgentBase (shared infrastructure)                │
│  LLM Caller · Tool Dispatcher · Context · Knowledge · Budget │
├──────────────────────────────────────────────────────────────┤
│  Tool Registry                                               │
│  AMBER (tleap, sander, pmemd, cpptraj) · AlphaFold2 ·       │
│  BioReason · Bash · SSH · File Ops · PDB · H++ · PROPKA     │
├──────────────────────────────────────────────────────────────┤
│  Integrations                                                │
│  Remote Tool Client · Celery Workers · SSH Executor          │
├──────────────────────────────────────────────────────────────┤
│  Database (SQLAlchemy async ORM)                             │
│  Chat · Message · Task · AgentSession                        │
└──────────────────────────────────────────────────────────────┘
```

## Agent Paradigms

| Paradigm | Class | When | Behavior |
|----------|-------|------|----------|
| **ReAct** | `ReActAgent` | Simple chat, Q&A | Single LLM call with tool use |
| **Plan-and-Solve** | `PlanAndSolveAgent` | Multi-step workflows (MD, AF2) | Decompose → plan steps → execute sequentially |
| **Reflection** | `ReflectionAgent` | Optimization, review, comparison | Execute → critique → revise loop |

The `AgentRouter` automatically selects the paradigm based on prompt analysis via `TaskClassifier`.

## Tech Stack

**Backend (Python 3.10+):**
- FastAPI + Uvicorn (async web server)
- SQLAlchemy 2.0 async ORM (SQLite dev / PostgreSQL prod)
- LiteLLM (multi-provider LLM gateway)
- Pydantic v2 (validation & settings)
- AsyncSSH (remote execution)
- Celery + Redis (distributed task queue)
- Alembic (database migrations)

**Frontend (TypeScript):**
- React 18 + Vite
- Tailwind CSS + Radix UI
- Zustand (state management)
- MSW (mock service worker for development)
- Vitest + Testing Library

## Project Structure

```
src/mdpilot/
├── agent/               # Multi-paradigm agent core
│   ├── base.py          # AgentBase abstract class
│   ├── react_agent.py   # ReAct paradigm
│   ├── plan_solve.py    # Plan-and-Solve paradigm
│   ├── reflection.py    # Reflection paradigm
│   ├── router.py        # Agent paradigm router
│   ├── task_classifier.py
│   └── knowledge_injector.py
├── api/                 # FastAPI application
│   ├── app.py           # App factory
│   ├── routers/         # REST & SSE endpoints
│   ├── services/        # Business logic
│   ├── models/          # Request/response schemas
│   └── websockets/      # WS endpoints
├── tools/               # Tool registry & built-in tools
│   ├── registry.py      # Tool registration
│   ├── dispatcher.py    # Tool execution dispatch
│   └── builtin/         # AMBER, AF2, BioReason, Bash, etc.
├── integrations/        # Remote service clients
│   ├── alphafold2/      # AlphaFold2 Celery client
│   ├── bioreason/       # BioReason Celery client
│   └── base/            # Remote tool client base
├── database/            # Async ORM layer
│   ├── models/          # SQLAlchemy models
│   ├── repositories/    # Data access layer
│   └── engine.py        # Async engine factory
├── coordination/        # Workflow coordination layer
├── knowledge/           # Knowledge base index
├── config/              # Configuration & settings
├── llm/                 # LLM provider abstraction
├── cli/                 # CLI commands
├── tui/                 # Terminal UI (Textual)
├── workflows/           # MD workflow definitions
└── pipelines/           # Data processing pipelines

mdpilot-frontend/src/
├── app/                 # App shell, layouts, router
├── features/
│   ├── chat/            # Chat interface & SSE parsing
│   ├── cluster/         # GPU cluster monitoring
│   └── workflow/        # Workflow panel & tool cards
├── shared/              # API client, hooks, utilities
└── mocks/               # MSW handlers & fixtures

tests/                   # 200+ tests (pytest)
```

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 20+ with pnpm
- AMBER (optional, for simulation features)
- Redis + Celery worker (optional, for remote tools)

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/nowa277/mdpilot.git
cd mdpilot

# Create virtual environment
python -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your LLM API key and settings

# Initialize database
mdpilot db upgrade

# Start the server
uvicorn mdpilot.api.app:create_app --factory --host 0.0.0.0 --port 18003
```

### Frontend Setup

```bash
cd mdpilot-frontend

# Install dependencies
pnpm install

# Configure environment
cp .env.example .env
# Edit .env with your API endpoint

# Start dev server
pnpm dev
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MDPILOT_API_KEY` | LLM provider API key | Required |
| `MDPILOT_BASE_URL` | Custom API endpoint | Provider default |
| `MDPILOT_MODEL` | LLM model name | `claude-sonnet-4-20250514` |
| `MDPILOT_DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///./mdpilot.db` |

See `.env.example` for the complete list.

## API Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health check |
| `/api/v1/chats` | GET/POST | Chat CRUD |
| `/api/v1/chats/{id}/messages` | GET/POST | Message history |
| `/api/v1/agent/chat` | POST | Agent SSE stream |
| `/api/v1/agent/task` | POST | Async task submission |
| `/api/v1/bioreason/*` | POST | BioReason endpoints |
| `/api/v1/alphafold2/*` | POST | AlphaFold2 endpoints |

The agent chat endpoint returns Server-Sent Events (SSE) with structured event types: `thinking`, `tool_call`, `tool_result`, `iteration_start`, `plan_step`, `text_delta`, and `done`.

## Testing

```bash
# Backend tests
pytest                                    # Run all tests
pytest tests/agent/                       # Agent tests only
pytest tests/ -m "not slow"              # Skip slow integration tests

# Frontend tests
cd mdpilot-frontend
pnpm test                                # Run all Vitest tests
pnpm test:cov                            # With coverage
```

## Remote Cluster Setup

MDPilot executes simulations on remote HPC nodes via SSH. Configure cluster nodes in the application settings:

- Each node needs a running Celery worker for distributed tasks
- Redis serves as the Celery message broker
- The SSH executor handles file transfer and command execution

## License

Apache-2.0
