#!/bin/bash
# MDPilot Backend Startup Script
# 确保使用正确的LLM配置启动后端

PROJECT_DIR="/home/user/obsidian/project/MDPilot"
LOG_FILE="/tmp/mdpilot-backend.log"
PID_FILE="/tmp/mdpilot-backend.pid"

# 加载环境变量
source ~/.bashrc

# 检查是否已经在运行
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Backend is already running (PID: $OLD_PID)"
        exit 0
    fi
fi

# 停止旧进程
pkill -f "uvicorn mdpilot.api.app" 2>/dev/null
sleep 2

# 启动后端
cd "$PROJECT_DIR"
python3 -m uvicorn mdpilot.api.app:create_app --factory --host 0.0.0.0 --port 18003 > "$LOG_FILE" 2>&1 &
NEW_PID=$!

# 保存PID
echo "$NEW_PID" > "$PID_FILE"

# 等待启动
sleep 5

# 验证启动
if curl -s http://127.0.0.1:18003/health | grep -q "healthy"; then
    echo "✅ Backend started successfully (PID: $NEW_PID)"
    echo "   Log: $LOG_FILE"
    echo "   Config: MiniMax-M2.7-highspeed"
else
    echo "❌ Backend failed to start"
    echo "   Check log: $LOG_FILE"
    exit 1
fi
