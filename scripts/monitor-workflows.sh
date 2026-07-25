#!/bin/bash
# Workflow 测试监控脚本
# 用于实时监控后端日志，捕获工具执行和错误信息

set -euo pipefail

BACKEND_HOST="zhao@lab03"
BACKEND_LOG="/home/3-FF/changshengjie/project/mdpilot/backend.log"
REPORT_FILE="docs/WORKFLOW_TEST_RESULTS.md"

echo "🔍 MDPilot Workflow 监控启动"
echo "================================"
echo "后端: $BACKEND_HOST"
echo "日志: $BACKEND_LOG"
echo "报告: $REPORT_FILE"
echo ""
echo "监控内容:"
echo "  - 工具调用 (tool_started, tool_completed, tool_failed)"
echo "  - 错误信息 (ERROR, error)"
echo "  - LLM API 调用"
echo "  - 数据库连接"
echo ""
echo "按 Ctrl+C 停止监控"
echo "====================="
echo ""

# 创建临时文件记录监控数据
TEMP_LOG="/tmp/mdpilot-monitor-$(date +%s).log"

# 清理函数
cleanup() {
    echo ""
    echo "==========="
    echo "📊 监控统计"
    echo "======================"

    if [ -f "$TEMP_LOG" ]; then
        echo "工具调用统计:"
        grep -c "tool_started" "$TEMP_LOG" 2>/dev/null | xargs -I {} echo "  - tool_started: {}" || echo "  - tool_started: 0"
        grep -c "tool_completed" "$TEMP_LOG" 2>/dev/null | xargs -I {} echo "  - tool_completed: {}" || echo "  - tool_completed: 0"
        grep -c "tool_failed" "$TEMP_LOG" 2>/dev/null | xargs -I {} echo "  - tool_failed: {}" || echo "  - tool_failed: 0"

        echo ""
        echo "错误统计:"
        grep -ci "error" "$TEMP_LOG" 2>/dev/null | xargs -I {} echo "  - 错误数: {}" || echo "  - 错误数: 0"

        echo ""
        echo "完整日志保存在: $TEMP_LOG"
    fi

    exit 0
}

trap cleanup INT TERM

# 开始监控
ssh "$BACKEND_HOST" "tail -f $BACKEND_LOG" | while IFS= read -r line; do
    # 记录到临时文件
    echo "$line" >> "$TEMP_LOG"

    # 提取时间戳
    timestamp=$(echo "$line" | grep -oP '\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}' || echo "")

    # 高亮显示关键事件
    if echo "$line" | grep -q "tool_started"; then
        tool_name=$(echo "$line" | grep -oP '"tool":\s*"\K[^"]+' || echo "unknown")
        tool_call_id=$(echo "$line" | grep -oP '"tool_call_id":\s*"\K[^"]+' || echo "")
        echo "🔧 [$timestamp] Tool Started: $tool_name (ID: ${tool_call_id:0:8}...)"

    elif echo "$line" | grep -q "tool_completed"; then
        tool_name=$(echo "$line" | grep -oP '"tool":\s*"\K[^"]+' || echo "unknown")
        tool_call_id=$(echo "$line" | grep -oP '"tool_call_id":\s*"\K[^"]+' || echo "")
        echo "✅ [$timestamp] Tool Completed: $tool_name (ID: ${tool_call_id:0:8}...)"

    elif echo "$line" | grep -q "tool_failed"; then
        tool_name=$(echo "$line" | grep -oP '"tool":\s*"\K[^"]+' || echo "unknown")
     tool_call_id=$(echo "$line" | grep -oP '"tool_call_id":\s*"\K[^"]+' || echo "")
        error=$(echo "$line" | grep -oP '"error":\s*"\K[^"]+' || echo "")
        echo "❌ [$timestamp] Tool Failed: $tool_name (ID: ${tool_call_id:0:8}...)"
        echo "   Error: ${error:0:100}"

    elif echo "$line" | grep -iq "error"; then
        # 过滤掉历史错误（12:05:05之前的）
        if [ -n "$timestamp" ] && [[ "$timestamp" > "2026-05-20T19:42:00" ]]; then
            echo "⚠️  [$timestamp] ERROR: ${line:0:150}"
        fi

    elif echo "$line" | grep -q "Bad request to openai"; then
        if [ -n "$timestamp" ] && [[ "$timestamp" > "2026-05-20T19:42:00" ]]; then
            echo "🚨 [$timestamp] LLM API Error: ${line:0:150}"
        fi

    elif echo "$line" | grep -q "garbage collector.*connection"; then
        echo "⚠️  [$timestamp] Database Connection Leak: ${line:0:150}"

    elif echo "$line" | grep -q "POST /api/v1/agent/stream"; then
        echo "📡 [$timestamp] Agent Stream Request"

    elif echo "$line" | grep -q "thinking"; then
        echo "💭 [$timestamp] Thinking Event"
    fi
done
