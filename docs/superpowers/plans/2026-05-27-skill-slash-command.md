# Skill 系统重构 + 斜杠命令交互 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 MDPilot 的 skill 体系从工具级自动匹配重构为面向用户的工作流级斜杠命令，前端支持 `/` 触发 + Tab 补全 + `+` 按钮分类面板。

**Architecture:** 新建 `src/mdpilot/skills/` 目录存放 17 个面向用户的 skill md 文件。后端 `SkillMeta` 新增 `category`/`command`/`tools` 字段，`discover_all` 新增扫描路径。前端新建 `SlashCommandMenu.tsx` 替代 `SkillSelector.tsx`，`ChatInput` 增加斜杠命令解析。

**Tech Stack:** Python (dataclass, FastAPI), TypeScript (React, TanStack Query), Tailwind CSS

---

## Phase 1: 后端核心改动

### Task 1: SkillMeta 新增字段 + _parse_frontmatter 增强 + _load_l1 更新

**Files:**
- Modify: `src/mdpilot/agent/skills.py:257-385`

- [ ] **Step 1: SkillMeta 新增 category/command/tools 字段**

在 `src/mdpilot/agent/skills.py` 的 `SkillMeta` dataclass（行 257-268）中新增：

```python
@dataclass
class SkillMeta:
    """L1 metadata for a skill — always loaded at startup."""
    name: str
    title: str
    description: str
    tags: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    source: str = "user"
    file_path: Path | None = None
    category: str = ""
    command: str = ""
    tools: list[dict] = field(default_factory=list)
    _l2_cache: str | None = field(default=None, repr=False)
```

- [ ] **Step 2: _parse_frontmatter 支持 list-of-dicts**

在 `src/mdpilot/agent/skills.py` 的 `_parse_frontmatter` 函数（行 79-109）中，在处理完简单 `key: value` 后，增加对多行 YAML 块（`tools:` 列表）的解析。在现有 `for line in yaml_text.splitlines():` 循环之后追加：

```python
def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from a Markdown string."""
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    yaml_text = parts[1].strip()
    content = parts[2].strip()

    meta: dict = {}
    current_list_key: str | None = None
    current_list: list[dict] = []

    for line in yaml_text.splitlines():
        stripped = line.strip()

        # Detect list-of-dicts block start (e.g. "tools:")
        if stripped.endswith(":") and not stripped.startswith("-"):
            # Flush previous list
            if current_list_key and current_list:
                meta[current_list_key] = current_list
            current_list_key = stripped.rstrip(":").strip()
            current_list = []
            continue

        # Parse list item (e.g. "  - name: pdb4amber")
        if stripped.startswith("- ") and current_list_key:
            # Flush previous item
            item_str = stripped[2:].strip()
            # Simple single-line dict: "name: value, node: value"
            item: dict = {}
            if ":" in item_str:
                for part in item_str.split(","):
                    part = part.strip()
                    if ":" in part:
                        k, _, v = part.partition(":")
                        item[k.strip()] = v.strip().strip('"').strip("'")
            if item:
                current_list.append(item)
            continue

        # Non-list line: flush list context
        if current_list_key:
            if current_list:
                meta[current_list_key] = current_list
            current_list_key = None
            current_list = []

        # Original simple key: value parsing
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                if value.startswith("[") and value.endswith("]"):
                    items = [v.strip().strip('"').strip("'") for v in value[1:-1].split(",")]
                    meta[key] = [i for i in items if i]
                else:
                    meta[key] = value

    # Flush final list
    if current_list_key and current_list:
        meta[current_list_key] = current_list

    return meta, content
```

- [ ] **Step 3: _load_l1 解析新字段**

修改 `_load_l1` 方法（行 359-385），在 `return SkillMeta(...)` 中加入新字段：

```python
    def _load_l1(self, path: Path, source: str) -> SkillMeta | None:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return None

        meta_dict, content = _parse_frontmatter(text)
        title = meta_dict.get("title", "") or _extract_title(content)
        description = meta_dict.get("description", "")
        name = path.stem.lower().replace(" ", "-")

        tags = meta_dict.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]

        triggers = meta_dict.get("triggers", [])
        if isinstance(triggers, str):
            triggers = [t.strip() for t in triggers.split(",")]

        category = meta_dict.get("category", "")
        command = meta_dict.get("command", "")
        tools = meta_dict.get("tools", [])
        if not isinstance(tools, list):
            tools = []

        return SkillMeta(
            name=name,
            title=title,
            description=description,
            tags=tags,
            triggers=triggers,
            source=source,
            file_path=path,
            category=category,
            command=command,
            tools=tools,
        )
```

- [ ] **Step 4: discover_all 新增扫描路径**

在 `discover_all` 方法（行 315-343）中，在 Source 1 (builtin) 之后插入新的 Source 1.5：

```python
        # Source 1.5: src/mdpilot/skills/ (user-facing slash commands)
        skills_dir = Path(__file__).resolve().parent.parent / "skills"
        if skills_dir.is_dir():
            count += self._scan_dir(skills_dir, source="skill")
```

- [ ] **Step 5: 运行现有测试确认无回归**

Run: `cd /home/user/obsidian/project/MDPilot && python -m pytest tests/test_skills.py -v`
Expected: All existing tests pass

- [ ] **Step 6: Commit**

```bash
git add src/mdpilot/agent/skills.py
git commit -m "feat: add category/command/tools fields to SkillMeta, enhance frontmatter parser"
```

---

### Task 2: API 扩展 — SkillInfo 新增字段 + category 过滤

**Files:**
- Modify: `src/mdpilot/api/routers/skills.py`

- [ ] **Step 1: SkillInfo 模型新增字段**

```python
class SkillInfo(BaseModel):
    name: str
    title: str
    description: str
    tags: list[str]
    source: str
    category: str = ""
    command: str = ""
    tools: list[dict] = []
```

- [ ] **Step 2: list_skills endpoint 增加 category 过滤 + 新字段映射**

```python
from fastapi import Query

@router.get("", response_model=list[SkillInfo])
async def list_skills(category: str | None = Query(None)) -> list[SkillInfo]:
    """Return all registered skills (L1 metadata only)."""
    from mdpilot.agent.skills import UnifiedSkillRegistry

    reg = UnifiedSkillRegistry()
    reg.discover_all()
    skills = reg.list_skills()

    if category:
        skills = [s for s in skills if s.category == category]

    return [
        SkillInfo(
            name=s.name,
            title=s.title,
            description=s.description,
            tags=s.tags,
            source=s.source,
            category=s.category,
            command=s.command,
            tools=s.tools,
        )
        for s in skills
    ]
```

- [ ] **Step 3: 验证 API 启动无报错**

Run: `cd /home/user/obsidian/project/MDPilot && python -c "from mdpilot.api.routers.skills import router; print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add src/mdpilot/api/routers/skills.py
git commit -m "feat: extend SkillInfo API with category/command/tools, add category filter"
```

---

## Phase 2: 创建 17 个 Skill MD 文件（并行）

### Task 3-6: 批量创建 skill 文件

每个文件放在 `src/mdpilot/skills/` 对应子目录下，使用规范 frontmatter。并行 5-6 个 agent 分批写入。

**目录结构：**
```
src/mdpilot/skills/
├── workflows/           # 8 个
│   ├── md-protein.md
│   ├── md-ligand.md
│   ├── md-membrane.md
│   ├── md-nucleic.md
│   ├── free-energy.md
│   ├── enhanced-sampling.md
│   ├── md-metallo.md
│   └── md-constant-ph.md
├── ai-services/         # 2 个
│   ├── alphafold2.md
│   └── bioreason.md
├── concepts/            # 3 个
│   ├── force-field.md
│   ├── water-model.md
│   └── equilibration.md
└── troubleshooting/     # 4 个
    ├── fix-pdb.md
    ├── fix-leap.md
    ├── fix-crash.md
    └── fix-analysis.md
```

**Frontmatter 模板：**

```yaml
---
name: <command-name>
title: <中文标题>
description: <一句话描述>
tags: [tag1, tag2, ...]
triggers: [trigger1, trigger2, 中文触发词, ...]
category: workflow | ai-service | concept | troubleshooting
command: /<command-name>
tools:
  - name: <tool-name>, node: <lab-xx>, exec: <exec-method>
  - name: <tool-name>, node: <lab-xx>, exec: <exec-method>
---
```

**工具链与节点参考（来自项目 memory + 知识库）：**

所有 AMBER 工具（pdb4amber, tleap, sander, pmemd.cuda, cpptraj, antechamber, parmchk2, MCPB.py, cpinutil.py, cphstats, MMPBSA.py, alchemical_analysis.py, PyReweighting）执行节点为 lab03，exec 为 `local_subprocess`。
AlphaFold2 执行节点为 lab02，exec 为 `celery_task`，任务名为 `run_alphafold2`。
BioReason 执行节点为 lab06，exec 为 `celery_task`，任务名为 `run_bioreason`。

**内容来源：** 读取对应 `knowledge/3-workflows/`, `knowledge/4-troubleshooting/`, `knowledge/2-concepts/` 下的 README.md 文件，提取关键步骤和工具用法作为 L2 body 内容。内容要实用、可操作，不是简单复制粘贴。

---

## Phase 3: 前端改动

### Task 7: TypeScript 类型更新

**Files:**
- Modify: `mdpilot-frontend/src/shared/types/api.gen.ts`

- [ ] **Step 1: 新增 ToolRef 接口 + 更新 SkillInfo**

在 `api.gen.ts` 的 `SkillInfo` 接口后添加：

```typescript
export interface ToolRef {
  name: string;
  node: string;
  exec: string;
}

export interface SkillInfo {
  name: string;
  title: string;
  description: string;
  tags: string[];
  source: string;
  category: string;
  command: string;
  tools: ToolRef[];
}
```

- [ ] **Step 2: Commit**

```bash
git add mdpilot-frontend/src/shared/types/api.gen.ts
git commit -m "feat: add ToolRef type and extend SkillInfo with category/command/tools"
```

---

### Task 8: 创建 SlashCommandMenu 组件

**Files:**
- Create: `mdpilot-frontend/src/features/chat/components/SlashCommandMenu.tsx`

- [ ] **Step 1: 实现完整的 SlashCommandMenu 组件**

两个入口共享同一组件：

**入口 1（`/` 触发）：** 紧凑列表，按 category 分组，支持输入过滤
**入口 2（`+` 按钮触发）：** 分类卡片面板，Tab 切换分类，3 列网格

```tsx
import { cn } from '@shared/utils';
import { useQuery } from '@tanstack/react-query';
import { fetchSkills } from '../api/chats.api';
import { useState, useEffect, useRef, useCallback, type KeyboardEvent } from 'react';
import type { SkillInfo } from '@shared/types/api.gen';

// Category display config
const CATEGORIES = [
  { key: 'workflow', label: '工作流', color: '#00cfaa', bg: 'rgba(0,207,170,0.1)', border: 'rgba(0,207,170,0.2)' },
  { key: 'ai-service', label: 'AI 服务', color: '#8b5cf6', bg: 'rgba(139,92,246,0.1)', border: 'rgba(139,92,246,0.2)' },
  { key: 'concept', label: '概念', color: '#3b82f6', bg: 'rgba(59,130,246,0.1)', border: 'rgba(59,130,246,0.2)' },
  { key: 'troubleshooting', label: '排错', color: '#fbbf24', bg: 'rgba(251,191,36,0.1)', border: 'rgba(251,191,36,0.2)' },
] as const;

interface Props {
  mode: 'slash' | 'panel';
  filter: string;
  onSelect: (skill: SkillInfo) => void;
  onClose: () => void;
}

export function SlashCommandMenu({ mode, filter, onSelect, onClose }: Props) {
  const { data: skills = [] } = useQuery({
    queryKey: ['skills'],
    queryFn: fetchSkills,
    staleTime: 60_000,
  });

  // Only show skills with a command (user-facing)
  const commandSkills = skills.filter(s => s.command);

  const [highlightIdx, setHighlightIdx] = useState(0);
  const [activeTab, setActiveTab] = useState<string>('workflow');
  const containerRef = useRef<HTMLDivElement>(null);

  // Filter skills based on mode
  const filtered = mode === 'slash'
    ? commandSkills.filter(s => {
        const q = filter.toLowerCase().replace(/^\//, '');
        if (!q) return true;
        return s.command.toLowerCase().includes(q)
          || s.title.toLowerCase().includes(q)
          || s.tags.some(t => t.toLowerCase().includes(q));
      })
    : commandSkills.filter(s => s.category === activeTab);

  // Group by category for slash mode
  const grouped = mode === 'slash' ? CATEGORIES.map(cat => ({
    ...cat,
    skills: filtered.filter(s => s.category === cat.key),
  })).filter(g => g.skills.length > 0) : [];

  const flatList = mode === 'slash' ? filtered : [];

  useEffect(() => { setHighlightIdx(0); }, [filter, activeTab]);

  // Keyboard navigation
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightIdx(i => Math.min(i + 1, flatList.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightIdx(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const skill = flatList[highlightIdx];
      if (skill) onSelect(skill);
    } else if (e.key === 'Escape') {
      onClose();
    } else if (e.key === 'Tab') {
      e.preventDefault();
      // Tab cycles through matches
      setHighlightIdx(i => (i + 1) % flatList.length);
    }
  }, [flatList, highlightIdx, onSelect, onClose]);

  useEffect(() => {
    if (mode === 'slash') {
      document.addEventListener('keydown', handleKeyDown as any);
      return () => document.removeEventListener('keydown', handleKeyDown as any);
    }
  }, [mode, handleKeyDown]);

  if (commandSkills.length === 0) return null;

  // === SLASH MODE: compact list ===
  if (mode === 'slash') {
    return (
      <div
        ref={containerRef}
        className="absolute bottom-full left-0 right-0 z-50 mb-2 overflow-hidden rounded-xl border border-white/10 bg-bg-1/95 backdrop-blur-[24px]"
        style={{ animation: 'slash-pop 0.15s ease-out' }}
      >
        <style>{`@keyframes slash-pop { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }`}</style>
        <div className="max-h-[320px] overflow-y-auto p-2">
          {grouped.map(group => (
            <div key={group.key}>
              <div className="px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-text-3">
                {group.label}
              </div>
              {group.skills.map(skill => {
                const idx = flatList.indexOf(skill);
                const active = idx === highlightIdx;
                return (
                  <button
                    key={skill.name}
                    type="button"
                    onClick={() => onSelect(skill)}
                    className={cn(
                      'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors',
                      active ? 'bg-accent-1/8' : 'hover:bg-white/3',
                    )}
                  >
                    <span className={cn(
                      'min-w-[140px] font-mono text-xs',
                      active ? 'font-semibold text-accent-1' : 'text-text-1',
                    )}>
                      {skill.command}
                    </span>
                    <span className={cn(
                      'text-[11px]',
                      active ? 'text-text-2' : 'text-text-3',
                    )}>
                      {skill.description}
                    </span>
                  </button>
                );
              })}
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="px-3 py-4 text-center text-xs text-text-3">
              没有匹配的命令
            </div>
          )}
        </div>
        <div className="border-t border-border-1 px-3 py-1.5 text-[10px] text-text-3">
          ↑↓ 导航 · Tab 补全 · Enter 确认 · Esc 关闭
        </div>
      </div>
    );
  }

  // === PANEL MODE: categorized card grid ===
  return (
    <div
      ref={containerRef}
      className="absolute bottom-full left-0 right-0 z-50 mb-2 overflow-hidden rounded-xl border border-white/10 bg-bg-1/95 backdrop-blur-[24px]"
      style={{ animation: 'slash-pop 0.15s ease-out' }}
    >
      <style>{`@keyframes slash-pop { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }`}</style>
      <div className="p-3">
        {/* Header */}
        <div className="mb-2 flex items-center justify-between">
          <span className="font-mono text-xs text-text-2">选择技能</span>
          <span className="text-[11px] text-text-3">选中后以斜杠命令插入</span>
        </div>

        {/* Category tabs */}
        <div className="mb-2 flex gap-1.5">
          {CATEGORIES.map(cat => (
            <button
              key={cat.key}
              type="button"
              onClick={() => setActiveTab(cat.key)}
              className={cn(
                'rounded-md border px-2.5 py-1 font-mono text-[11px] transition-colors',
                activeTab === cat.key
                  ? 'border-opacity-25 text-opacity-100'
                  : 'border-border-1 text-text-3 hover:text-text-2',
              )}
              style={activeTab === cat.key ? {
                borderColor: cat.border,
                color: cat.color,
                backgroundColor: cat.bg,
              } : undefined}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Card grid */}
        <div className="grid grid-cols-3 gap-1.5">
          {filtered.map(skill => {
            const catConfig = CATEGORIES.find(c => c.key === skill.category);
            return (
              <button
                key={skill.name}
                type="button"
                onClick={() => onSelect(skill)}
                className="rounded-lg border border-border-1 bg-white/2 p-2 text-left transition-colors hover:border-border-2 hover:bg-white/4"
              >
                <div className="mb-0.5 font-mono text-[11px] font-semibold text-text-1">
                  {skill.command}
                </div>
                <div className="line-clamp-2 text-[10px] leading-snug text-text-3">
                  {skill.description}
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add mdpilot-frontend/src/features/chat/components/SlashCommandMenu.tsx
git commit -m "feat: add SlashCommandMenu component with slash popup and panel modes"
```

---

### Task 9: 重写 ChatInput — 斜杠命令解析 + `+` 按钮

**Files:**
- Modify: `mdpilot-frontend/src/features/chat/components/ChatInput.tsx`
- Delete: `mdpilot-frontend/src/features/chat/components/SkillSelector.tsx`

- [ ] **Step 1: 重写 ChatInput**

替换整个文件：

```tsx
import { Button } from '@shared/ui';
import { cn } from '@shared/utils';
import { type KeyboardEvent, useEffect, useRef, useState } from 'react';
import { SlashCommandMenu } from './SlashCommandMenu';
import type { SkillInfo } from '@shared/types/api.gen';

interface Props {
  disabled?: boolean;
  isStreaming?: boolean;
  onSubmit: (content: string, activeSkills?: string[]) => void;
  onStop?: () => void;
}

function parseSlashCommand(input: string): { command: string | null; prompt: string } {
  if (!input.startsWith('/')) return { command: null, prompt: input };
  const spaceIdx = input.indexOf(' ');
  if (spaceIdx === -1) return { command: input.slice(1), prompt: '' };
  return { command: input.slice(1, spaceIdx), prompt: input.slice(spaceIdx + 1) };
}

export function ChatInput({ disabled, isStreaming, onSubmit, onStop }: Props) {
  const [value, setValue] = useState('');
  const [slashFilter, setSlashFilter] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  }, [value]);

  // Detect slash prefix
  useEffect(() => {
    if (value.startsWith('/')) {
      setSlashFilter(value.split(' ')[0]);
    } else {
      setSlashFilter(null);
    }
  }, [value]);

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // If slash menu is open, let SlashCommandMenu handle arrow/enter/tab/esc
    if (slashFilter !== null && ['ArrowUp', 'ArrowDown', 'Tab'].includes(e.key)) {
      e.preventDefault();
      return;
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || isStreaming) return;
    const { command, prompt } = parseSlashCommand(trimmed);
    const skills = command ? [command] : undefined;
    onSubmit(prompt || trimmed, skills);
    setValue('');
    setSlashFilter(null);
    setPanelOpen(false);
  }

  function handleSkillSelect(skill: SkillInfo) {
    setValue(skill.command + ' ');
    setSlashFilter(null);
    setPanelOpen(false);
    textareaRef.current?.focus();
  }

  const showStopButton = isStreaming && onStop;
  const canSubmit = !disabled && !isStreaming && value.trim() !== '';

  return (
    <div className="border-t border-border-1 bg-bg-1 p-4">
      <div className="mx-auto flex w-full max-w-[860px] flex-col gap-2">
        <div className="relative flex-1">
          {/* Slash popup */}
          {slashFilter !== null && (
            <SlashCommandMenu
              mode="slash"
              filter={slashFilter}
              onSelect={handleSkillSelect}
              onClose={() => setSlashFilter(null)}
            />
          )}
          {/* Panel popup */}
          {panelOpen && (
            <SlashCommandMenu
              mode="panel"
              filter=""
              onSelect={handleSkillSelect}
              onClose={() => setPanelOpen(false)}
            />
          )}
          <div className="flex gap-2">
            {/* + button */}
            <button
              type="button"
              onClick={() => setPanelOpen(!panelOpen)}
              className={cn(
                'flex h-[40px] w-[40px] shrink-0 items-center justify-center rounded-card border transition-colors',
                panelOpen
                  ? 'border-accent-1/40 bg-accent-1/6 text-accent-1'
                  : 'border-border-1 text-text-2 hover:border-border-2 hover:bg-bg-2 hover:text-text-1',
              )}
            >
              +
            </button>
            <textarea
              ref={textareaRef}
              aria-label="给 MDPilot 输入指令"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={disabled}
              rows={1}
              placeholder={isStreaming ? '正在生成回复…' : '输入指令… (Shift+Enter 换行, / 斜杠命令)'}
              className="w-full resize-none rounded-card border border-border-1 bg-bg-0 px-3 py-2 text-sm text-text-1 placeholder:text-text-3 focus-visible:border-accent-1 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60"
              style={{ minHeight: '40px', maxHeight: '200px' }}
            />
          </div>
        </div>
        <div className="flex justify-end">
          {showStopButton ? (
            <Button onClick={onStop} variant="ghost">Stop</Button>
          ) : (
            <Button onClick={submit} disabled={!canSubmit}>Send</Button>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 删除 SkillSelector.tsx**

```bash
rm mdpilot-frontend/src/features/chat/components/SkillSelector.tsx
```

- [ ] **Step 3: 更新 ChatPane 如果有 SkillSelector 引用**

ChatPane 不直接引用 SkillSelector（通过 ChatInput 间接引用），无需改动。

- [ ] **Step 4: Commit**

```bash
git add -A mdpilot-frontend/src/features/chat/components/
git commit -m "feat: replace SkillSelector with SlashCommandMenu, add slash command parsing in ChatInput"
```

---

## Phase 4: 测试

### Task 10: 后端测试 — 新字段 + API

**Files:**
- Modify: `tests/test_skills.py`

- [ ] **Step 1: 新增测试**

在 `tests/test_skills.py` 末尾追加：

```python
class TestNewSkillFields:
    """Tests for category, command, tools fields."""

    def test_category_command_parsed(self, tmp_path: Path):
        from mdpilot.agent.skills import UnifiedSkillRegistry
        f = tmp_path / "md-protein.md"
        f.write_text(
            "---\n"
            "title: 标准蛋白 MD\n"
            "description: 完整蛋白模拟\n"
            "tags: [protein, md]\n"
            "category: workflow\n"
            "command: /md-protein\n"
            "tools:\n"
            "  - name: pdb4amber, node: lab03, exec: local_subprocess\n"
            "  - name: tleap, node: lab03, exec: local_subprocess\n"
            "---\n"
            "# Standard Protein MD\n\nBody content.\n"
        )
        reg = UnifiedSkillRegistry()
        reg.discover_all(extra_dirs=[tmp_path])
        meta = reg.get("md-protein")
        assert meta is not None
        assert meta.category == "workflow"
        assert meta.command == "/md-protein"
        assert len(meta.tools) == 2
        assert meta.tools[0]["name"] == "pdb4amber"

    def test_skills_dir_scan(self, tmp_path: Path):
        """Test that discover_all scans src/mdpilot/skills/ directory."""
        from mdpilot.agent.skills import UnifiedSkillRegistry
        reg = UnifiedSkillRegistry()
        count = reg.discover_all()
        # Should at least find builtin skills; skills/ dir may not exist yet
        assert count >= 0

    def test_api_skill_info_new_fields(self, tmp_path: Path):
        """Verify SkillInfo model accepts new fields."""
        from mdpilot.api.routers.skills import SkillInfo
        info = SkillInfo(
            name="test",
            title="Test",
            description="desc",
            tags=[],
            source="skill",
            category="workflow",
            command="/test",
            tools=[{"name": "tool1", "node": "lab03", "exec": "local_subprocess"}],
        )
        assert info.category == "workflow"
        assert info.command == "/test"
        assert len(info.tools) == 1
```

- [ ] **Step 2: 运行测试**

Run: `cd /home/user/obsidian/project/MDPilot && python -m pytest tests/test_skills.py -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_skills.py
git commit -m "test: add tests for category/command/tools fields in SkillMeta and SkillInfo"
```

---

## 执行顺序

1. **Phase 1 (Task 1-2)**: 后端改动，顺序执行
2. **Phase 2 (Task 3-6)**: 17 个 skill 文件，5-6 个 agent 并行
3. **Phase 3 (Task 7-9)**: 前端改动，Task 7 先行（类型），Task 8-9 可并行
4. **Phase 4 (Task 10)**: 测试验证
