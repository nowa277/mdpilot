# Slash Command Skill Injection Fix — Processing Report

**Date:** 2026-05-27
**Scope:** Fix agent ignoring injected skill knowledge and calling `list_knowledge` instead

---

## Problem

When user sends `/force-field 推荐一个蛋白质模拟的力场`, the agent calls `list_knowledge` / `search_knowledge` tools instead of using the force-field knowledge already injected into the system prompt. The injection pipeline was technically correct (skill content WAS appended to the system prompt), but two issues caused the LLM to ignore it:

1. **System prompt encourages tool usage** — `base.py:156-162` says "Proactively use these tools when you encounter domain-specific questions — do not wait to be told."
2. **No logging** — injection succeeded silently, impossible to diagnose in production.

## Root Cause Analysis

The system prompt in `AgentBase._build_system_prompt()` includes:
```
## Knowledge Base
You have access to a comprehensive AMBER knowledge base...
1. Use `search_knowledge` to find relevant documents
2. Use `read_knowledge` to load detailed documentation
4. **Proactively** use these tools when you encounter domain-specific questions
```

This instruction is always present and overrides the injected skill content. Even though `build_context()` in `skills.py` correctly appends the force-field knowledge as `## Active Skills` in the system prompt, the LLM sees the "use knowledge tools" instruction and prioritizes it.

## Changes Made

### 1. System prompt instruction when skills injected (3 agent files)

**Files:** `react_agent.py`, `plan_solve.py`, `reflection.py`

When `active_skills` are provided and injection produces content, append to system prompt:
```
## Important: Pre-loaded Knowledge
The knowledge above has been pre-loaded for this query. Do NOT call list_knowledge,
search_knowledge, or read_knowledge — the information is already available in your context.
Answer directly using the injected content.
```

Applied to all three agent classes: `ReActAgent` (both coordination and legacy paths), `PlanAndSolveAgent`, and `ReflectionAgent`.

### 2. `active_skills` as proper parameter (robustness fix)

**Files:** `react_agent.py`, `plan_solve.py`, `reflection.py`, `agent_service.py`

- Added `active_skills: list[str] | None = None` parameter to all `run()` signatures
- Removed `agent._active_skills = active_skills` monkey-patch from `agent_service.py`
- Pass through `agent.run(..., active_skills=active_skills)` explicitly

### 3. Diagnostic logging

**File:** `skills.py`

Added logging in `build_context()`:
- `logger.info` when active_skills are requested
- `logger.info` when each skill is successfully injected (with char count)
- `logger.warning` when a skill name lookup fails

**File:** `react_agent.py`

Added `self._logger.info("react_inject_context", ...)` in both execution paths.

### 4. DB message display fix

**File:** `agent.py` (router)

User messages stored in DB now include the command prefix. Before: `content=request.prompt` (e.g., "推荐蛋白质力场"). After: if `active_skills` is non-empty, stores `f"/{active_skills[0]} {prompt}"` (e.g., "/force-field 推荐蛋白质力场"). This ensures the slash command display survives page refresh.

### 5. E2E test enhancement

**File:** `e2e/slash-command.spec.ts`

Test #3 ("agent responds with force-field knowledge injected") now also verifies that the agent did NOT call `list_knowledge`, `search_knowledge`, or `read_knowledge` during the request, by monitoring SSE events.

## Files Changed

| File | Lines Changed | Summary |
|------|---------------|---------|
| `src/mdpilot/agent/react_agent.py` | +49/-3 | `active_skills` param in `run()`, injection instruction, logging |
| `src/mdpilot/agent/plan_solve.py` | +16/-1 | `active_skills` param + injection instruction |
| `src/mdpilot/agent/reflection.py` | +16/-1 | `active_skills` param + injection instruction |
| `src/mdpilot/agent/skills.py` | +7 | Diagnostic logging in `build_context()` |
| `src/mdpilot/api/services/agent_service.py` | +4/-1 | Pass `active_skills` through `run()` instead of monkey-patch |
| `src/mdpilot/api/routers/agent.py` | +5/-1 | Store display content with command prefix in DB |
| `mdpilot-frontend/e2e/slash-command.spec.ts` | +27 | Verify no knowledge tool calls when skills injected |

## Code Review

### Round 1 (Self-review during implementation)

- Found `PlanAndSolveAgent` and `ReflectionAgent` also needed `active_skills` parameter and injection instruction
- Verified `_run_with_coordination` correctly handles `skill_instruction` within the `if injected or skill_ctx` block
- Confirmed `active_skills=[]` (empty list) doesn't trigger the instruction because `if active_skills and injected` requires both truthy

### Round 2 (Cross-file consistency)

- All three agent subclasses now have consistent `active_skills` handling
- `agent_service.py` no longer has monkey-patch — `active_skills` flows through the proper method chain
- `agent.py` DB storage handles edge case: bare command with empty prompt → `f"/force-field ".strip()` = `/force-field`
- E2E test SSE parsing uses `page.on("response")` to intercept tool_call events

## E2E Test Results

```
Running 5 tests using 1 worker

  ✓  Tab completion: type / → filter force → Tab fills input (2.7s)
  ✓  send /force-field with text → message bubble shows /force-field prefix (3.0s)
  ✓  agent responds with force-field knowledge injected (16.5s)
  ✓  ArrowDown/ArrowUp navigate menu, Escape closes (2.5s)
  ✓  bare /command without prompt falls back to skill execution message (3.2s)

  5 passed (28.4s)
```

All 5 tests pass. Test #3 confirmed the agent used injected force-field knowledge directly without calling `list_knowledge`.

## Verification Checklist

- [x] Python files compile without errors
- [x] Backend health check passes (`/health` → `{"status":"healthy"}`)
- [x] All 5 E2E slash command tests pass
- [x] `active_skills` flows through proper parameter chain (no monkey-patch)
- [x] Injection instruction applied to all 3 agent subclasses
- [x] Logging added at injection points
- [x] DB stores display content with command prefix
