#!/bin/bash
# Agent 交互系统优化验证脚本
# 用于验证所有 20 个任务的实施效果

set -e

echo "========================================"
echo "Agent 交互系统优化验证"
echo "日期: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查函数
check_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
}

check_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

# 1. 检查后端状态
echo "1. 检查后端服务..."
if ssh zhao@lab03 "ps aux | grep uvicorn | grep 18003 | grep -v grep" > /dev/null 2>&1; then
    check_pass "后端服务运行中 (lab03:18003)"
else
    check_fail "后端服务未运行"
    exit 1
fi
echo ""

# 2. 检查前端状态
echo "2. 检查前端服务..."
if pgrep -f "vite.*5173" > /dev/null 2>&1; then
    check_pass "前端服务运行中 (localhost:5173)"
else
    check_fail "前端服务未运行"
    exit 1
fi
echo ""

# 3. 验证后端代码变更
echo "3. 验证后端代码变更..."

# Task 1: Orchestrator tool_call_id
if grep -q '"tool_call_id": tool_id' src/mdpilot/agent/orchestrator.py; then
    check_pass "Task 1: Orchestrator 携带 tool_call_id"
else
    check_fail "Task 1: Orchestrator 未携带 tool_call_id"
fi

# Task 2: Per-stream orchestrator
if grep -q 'orchestrator = AgentOrchestrator()' src/mdpilot/api/services/agent_service.py; then
    check_pass "Task 2: Per-stream Orchestrator 实例化"
else
    check_fail "Task 2: Per-stream Orchestrator 未实现"
fi

# Task 3: Listener cleanup
if grep -q 'agent.events.off(event_type, callback)' src/mdpilot/api/services/agent_service.py; then
    check_pass "Task 3: Event Listener 清理"
else
    check_fail "Task 3: Event Listener 清理未实现"
fi

# Task 4: Think tag extraction
if grep -q '_THINK_RE = _re.compile' src/mdpilot/api/services/agent_service.py; then
    check_pass "Task 4: Think Tag 提取"
else
    check_fail "Task 4: Think Tag 提取未实现"
fi

# Task 6: TOOL_RESULT fields
if grep -q 'tool_call_id=tc.id' src/mdpilot/agent/react.py; then
    check_pass "Task 6: TOOL_RESULT 携带 tool_call_id"
else
    check_fail "Task 6: TOOL_RESULT 未携带 tool_call_id"
fi

# Task 7: sander exclude
if grep -q 'exclude=\["progress_callback"\]' src/mdpilot/tools/builtin/amber/sander.py; then
    check_pass "Task 7: sander_run 排除 progress_callback"
else
    check_fail "Task 7: sander_run 未排除 progress_callback"
fi

# Task 8: Budget simplification
if ! grep -q 'add_usage' src/mdpilot/agent/budget.py; then
    check_pass "Task 8: 移除成本追踪"
else
    check_fail "Task 8: 成本追踪仍存在"
fi
echo ""

# 4. 验证前端代码变更
echo "4. 验证前端代码变更..."

# Task 9: AgentBlock tool_call_id
if grep -q 'tool_call_id?: string' mdpilot-frontend/src/shared/types/api.gen.ts; then
    check_pass "Task 9: AgentBlock 扩展 tool_call_id"
else
    check_fail "Task 9: AgentBlock 未扩展 tool_call_id"
fi

# Task 9: upsertAgentBlock
if grep -q 'export function upsertAgentBlock' mdpilot-frontend/src/features/chat/hooks/messages-cache.ts; then
    check_pass "Task 9: upsertAgentBlock 函数实现"
else
    check_fail "Task 9: upsertAgentBlock 函数未实现"
fi

# Task 10: Zustand store
if grep -q 'useChatUiStore' mdpilot-frontend/src/features/chat/hooks/useAgentChat.ts; then
    check_pass "Task 10: useAgentChat 读取 Zustand Store"
else
    check_fail "Task 10: useAgentChat 未读取 Zustand Store"
fi

# Task 11: upsertAgentBlock usage
if grep -q 'upsertAgentBlock(qc, chatId, msgId, blockWithId)' mdpilot-frontend/src/features/chat/hooks/useAgentChat.ts; then
    check_pass "Task 11: useAgentChat 使用 upsertAgentBlock"
else
    check_fail "Task 11: useAgentChat 未使用 upsertAgentBlock"
fi

# Task 12: Workflow chat isolation
if grep -q 'activeChatId: string | null' mdpilot-frontend/src/features/workflow/store/workflow.store.ts; then
    check_pass "Task 12: Workflow Store Chat 隔离"
else
    check_fail "Task 12: Workflow Store Chat 隔离未实现"
fi

# Task 13: useWorkflowSync tool_call_id
if grep -q 'tool_call_id' mdpilot-frontend/src/features/workflow/hooks/useWorkflowSync.ts; then
    check_pass "Task 13: useWorkflowSync 使用 tool_call_id"
else
    check_fail "Task 13: useWorkflowSync 未使用 tool_call_id"
fi

# Task 14: useActiveChatSync
if [ -f "mdpilot-frontend/src/features/chat/hooks/useActiveChatSync.ts" ]; then
    check_pass "Task 14: useActiveChatSync hook 创建"
else
    check_fail "Task 14: useActiveChatSync hook 未创建"
fi

# Task 15: BioReasonCard duration fix
if grep -q '(tool.duration || 0) / 1000' mdpilot-frontend/src/features/workflow/components/BioReasonCard.tsx; then
    check_pass "Task 15: BioReasonCard ms→s 修复"
else
    check_fail "Task 15: BioReasonCard ms→s 未修复"
fi

# Task 16: ChatInput streaming
if ! grep -q 'disabled={disabled || isStreaming}' mdpilot-frontend/src/features/chat/components/ChatInput.tsx; then
    check_pass "Task 16: ChatInput Streaming 时允许输入"
else
    check_fail "Task 16: ChatInput Streaming 时仍禁用"
fi

# Task 17: MessageBubble React.memo
if grep -q 'React.memo' mdpilot-frontend/src/features/chat/components/MessageBubble.tsx; then
    check_pass "Task 17: MessageBubble React.memo"
else
    check_fail "Task 17: MessageBubble 未使用 React.memo"
fi

# Task 18: Elapsed time
if grep -q 'setInterval' mdpilot-frontend/src/features/workflow/components/BashCard.tsx; then
    check_pass "Task 18: ToolCard Running Elapsed Time"
else
    check_fail "Task 18: ToolCard Elapsed Time 未实现"
fi

echo ""

# 5. 验证死代码清理
echo "5. 验证死代码清理..."

if [ ! -f "src/mdpilot/agent/tool_handler.py" ]; then
    check_pass "Task 19: tool_handler.py 已删除"
else
    check_fail "Task 19: tool_handler.py 仍存在"
fi

if [ ! -f "src/mdpilot/agent/parallel_executor.py" ]; then
    check_pass "Task 19: parallel_executor.py 已删除"
else
    check_fail "Task 19: parallel_executor.py 仍存在"
fi

if [ ! -f "src/mdpilot/agent/session.py" ]; then
    check_pass "Task 19: session.py 已删除"
else
    check_fail "Task 19: session.py 仍存在"
fi

if [ ! -f "mdpilot-frontend/src/features/chat/components/AgentWorkflowDisplay.tsx" ]; then
    check_pass "Task 19: AgentWorkflowDisplay.tsx 已删除"
else
    check_fail "Task 19: AgentWorkflowDisplay.tsx 仍存在"
fi

echo ""

# 6. 检查提交历史
echo "6. 检查提交历史..."
COMMIT_COUNT=$(git log --oneline --since="2026-05-20" --grep="feat\|fix\|refactor\|chore\|perf\|docs" | wc -l)
if [ "$COMMIT_COUNT" -ge 18 ]; then
    check_pass "提交数量: $COMMIT_COUNT (预期 ≥18)"
else
    check_fail "提交数量: $COMMIT_COUNT (预期 ≥18)"
fi

echo ""

# 7. 代码统计
echo "7. 代码变更统计..."
git diff --stat 2d8849f..HEAD | tail -1

echo ""

# 8. 访问信息
echo "=================================="
echo "服务访问信息"
echo "============================"
echo ""
check_info "后端 API: http://10.50.103:18003"
check_info "前端界面: http://localhost:5173/workspace"
check_info "健康检查: http://10.10.50.103:18003/api/v1/health"
echo ""

# 9. 手动验证清单
echo "==================================="
echo "手动验证清单"
echo "===================================="
echo ""
echo "请在浏览器中打开 http://localhost:5173/workspace 并验证:"
echo ""
echo "□ 1. 工具块去重"
echo "   - 发送: '使用bash_run创建目录，然后用tleap生成拓扑'"
echo "   - 验证: 每个工具只显示一次"
echo "   - 验证: 状态从 running → completed 实时更新"
echo ""
echo "□ 2. Thinking 显示"
echo "   - 发送任意 prompt"
echo "   - 验证: 思考过程显示为可折叠 ThinkingBlock"
echo "   - 验证: llm_response 不包含 <think> 标签"
echo ""
echo "□ 3. Workflow 同步"
echo "   - 验证: Workflow 面板与 Chat 工具列表同步"
echo "   - 验证: 切换 Chat 后 Workflow 面板更新"
echo "   - 验证: 已完成工具显示真实持续时间（非 0.0s）"
echo "   - 验证: Running 工具显示 elapsed time 实时更新"
echo ""
echo "□ 4. ChatInput 可用性"
echo "   - 验证: Streaming 时 textarea 可输入"
echo "   - 验证: Send 按钮在 streaming 时禁用"
echo ""
echo "□ 5. 连续调用相同工具"
echo "   - 发送: '连续两次调用bash_run'"
echo "   - 验证: 两个工具分别显示，ID 不冲突"
echo ""

echo "==========================="
echo "验证完成"
echo "==========================="
