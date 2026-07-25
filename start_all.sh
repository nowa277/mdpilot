#!/bin/bash
# MDPilot 一键启动脚本

set -e

echo "=== MDPilot 启动脚本 ==="
echo ""

# 进入项目目录
cd /home/user/obsidian/project/MDPilot

# 检查 SSH 隧道
echo "[1/5] 检查 SSH 隧道..."
if ss -tuln | grep -q "24122" && ss -tuln | grep -q "24123"; then
    echo "✓ SSH 隧道已建立"
else
    echo "✗ SSH 隧道未建立，请先建立隧道"
    exit 1
fi

# 启动后端
echo "[2/5] 启动后端服务..."
./start_backend.sh > /tmp/backend.log 2>&1 &
sleep 3

if curl -s http://localhost:18003/health | grep -q "healthy"; then
    echo "✓ 后端启动成功"
else
    echo "✗ 后端启动失败，请查看日志: tail -50 /tmp/backend.log"
    exit 1
fi

# 启动前端
echo "[3/5] 启动前端服务..."
cd mdpilot-frontend
npx vite --host 0.0.0.0 --port 5173 > /tmp/frontend.log 2>&1 &
cd ..
sleep 5

if curl -s http://localhost:5173/ | grep -q "MDPilot"; then
    echo "✓ 前端启动成功"
else
    echo "✗ 前端启动失败，请查看日志: tail -50 /tmp/frontend.log"
    exit 1
fi

# 测试集群连接
echo "[4/5] 测试集群连接..."
if curl -s http://localhost:18003/api/nodes | grep -q "online"; then
    echo "✓ 集群连接正常"
else
    echo "⚠ 集群可能离线，请检查 SSH 隧道"
fi

# 显示访问信息
echo "[5/5] 启动完成！"
echo ""
echo "=== 访问地址 ==="
echo "前端: http://localhost:5173"
echo "后端: http://localhost:18003"
echo ""
echo "=== 日志文件 ==="
echo "后端日志: tail -f /tmp/backend.log"
echo "前端日志: tail -f /tmp/frontend.log"
echo ""
echo "=== 关闭服务 ==="
echo "pkill -f 'uvicorn.*mdpilot' && pkill -f 'vite'"
