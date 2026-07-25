#!/bin/bash

set -e

echo "=== 端到端测试前置检查 ==="

if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "错误: MDPilot API 未运行"
    echo "请先启动: uvicorn mdpilot.api.app:app --reload"
    exit 1
fi

if ! ssh -o ConnectTimeout=5 lab06 "echo ok" > /dev/null 2>&1; then
    echo "错误: 无法连接到六号机"
    exit 1
fi

if ! ssh lab06 "/home/6-FF/luo/miniconda/bin/redis-cli ping" | grep -q PONG; then
    echo "错误: 六号机 Redis 未运行"
    exit 1
fi

if ! ssh lab06 "ps aux | grep -v grep | grep 'celery.*worker'" > /dev/null; then
    echo "错误: 六号机 Celery Worker 未运行"
    exit 1
fi

echo "✓ 所有前置条件满足"
echo ""
echo "=== 运行端到端测试 ==="

pytest tests/e2e/ -v -m e2e --tb=short

echo ""
echo "=== 测试完成 ==="
