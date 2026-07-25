#!/usr/bin/env python3
"""
MDPilot 一键启动脚本

功能：
1. 启动后端（lab03）
2. 建立 SSH 隧道
3. 验证连接
4. 启动前端

使用：
    python start_mdpilot.py
"""

import subprocess
import sys
import time
import json
from pathlib import Path
from typing import Tuple, Optional

# 配置
BACKEND_HOST = "lab03"
BACKEND_DIR = "/home/3-FF/changshengjie/project/mdpilot"
BACKEND_VENV = ".venv"
BACKEND_PORT = 18003
BACKEND_LOG = "/tmp/mdpilot-uvicorn.log"

FRONTEND_DIR = Path(__file__).parent / "mdpilot-frontend"
FRONTEND_PORT = 5173

# 颜色输出
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_step(step: int, message: str):
    """打印步骤信息"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}[{step}/5] {message}{Colors.RESET}")

def print_success(message: str):
    """打印成功信息"""
    print(f"{Colors.GREEN}✅ {message}{Colors.RESET}")

def print_warning(message: str):
    """打印警告信息"""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.RESET}")

def print_error(message: str):
    """打印错误信息"""
    print(f"{Colors.RED}❌ {message}{Colors.RESET}")

def run_command(cmd: str, check: bool = True, capture: bool = True) -> Tuple[int, str, str]:
    """执行命令并返回结果"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=check,
            capture_output=capture,
            text=True,
            timeout=30
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return e.returncode, e.stdout, e.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timeout"
    except Exception as e:
        return -1, "", str(e)

def check_ssh_connection() -> bool:
    """检查 SSH 连接"""
    print("  检查 SSH 连接...")
    code, _, _ = run_command(f"ssh -o ConnectTimeout=5 {BACKEND_HOST} 'echo ok'")
    if code == 0:
        print_success(f"SSH 连接正常 ({BACKEND_HOST})")
        return True
    else:
        print_error(f"无法连接到 {BACKEND_HOST}")
        print("  请检查：")
        print("  1. SSH 配置是否正确")
        print("  2. 网络连接是否正常")
        print(f"  3. 是否可以执行: ssh {BACKEND_HOST}")
        return False

def check_backend_running() -> bool:
    """检查后端是否已在运行"""
    print("  检查后端进程...")
    cmd = f"ssh {BACKEND_HOST} 'ps aux | grep uvicorn | grep mdpilot | grep -v grep'"
    code, stdout, _ = run_command(cmd, check=False)

    if code == 0 and stdout.strip():
        print_warning("后端已在运行")
        return True
    return False

def start_backend() -> bool:
    """启动后端"""
    print_step(1, "启动后端")

    if not check_ssh_connection():
        return False

    if check_backend_running():
        print("  跳过启动，使用现有进程")
        return True

    print("  启动 Uvicorn 服务...")
    cmd = (
        f"ssh {BACKEND_HOST} 'cd {BACKEND_DIR} && "
        f"source {BACKEND_VENV}/bin/activate && "
        f"nohup python -m uvicorn mdpilot.api.app:create_app --factory "
        f"--host 0.0.0.0 --port {BACKEND_PORT} "
        f"> {BACKEND_LOG} 2>&1 &'"
    )

    code, _, stderr = run_command(cmd, check=False)
    if code != 0:
        print_error(f"后端启动失败: {stderr}")
        return False

    print("  等待后端启动...")
    time.sleep(3)

    # 验证后端进程
    if check_backend_running():
        print_success("后端启动成功")
        return True
    else:
        print_error("后端启动失败，请检查日志")
        print(f"  日志位置: {BACKEND_HOST}:{BACKEND_LOG}")
        print(f"  查看日志: ssh {BACKEND_HOST} 'tail -50 {BACKEND_LOG}'")
        return False

def check_tunnel_exists() -> bool:
    """检查 SSH 隧道是否存在"""
    cmd = f"ps aux | grep 'ssh.*{BACKEND_PORT}' | grep -v grep"
    code, stdout, _ = run_command(cmd, check=False)
    return code == 0 and stdout.strip()

def create_ssh_tunnel() -> bool:
    """建立 SSH 隧道"""
    print_step(2, "建立 SSH 隧道")

    if check_tunnel_exists():
        print_warning("SSH 隧道已存在")
        return True

    print(f"  创建隧道: localhost:{BACKEND_PORT} -> {BACKEND_HOST}:{BACKEND_PORT}")
    cmd = f"ssh -f -N -L {BACKEND_PORT}:localhost:{BACKEND_PORT} {BACKEND_HOST}"

    code, _, stderr = run_command(cmd, check=False)
    if code != 0:
        print_error(f"隧道创建失败: {stderr}")
        return False

    time.sleep(1)

    if check_tunnel_exists():
        print_success("SSH 隧道创建成功")
        return True
    else:
        print_error("SSH 隧道创建失败")
        return False

def verify_backend_connection() -> bool:
    """验证后端连接"""
    print_step(3, "验证后端连接")

    print(f"  测试健康检查: http://localhost:{BACKEND_PORT}/health")
    cmd = f"curl -s -m 5 http://localhost:{BACKEND_PORT}/health"

    for attempt in range(3):
        code, stdout, _ = run_command(cmd, check=False)

        if code == 0:
            try:
                data = json.loads(stdout)
                if data.get("status") == "healthy":
                    print_success("后端连接正常")
                    return True
            except json.JSONDecodeError:
                pass

        if attempt < 2:
            print(f"  重试 ({attempt + 1}/3)...")
            time.sleep(2)

    print_error("后端连接失败")
    print("  请检查：")
    print(f"  1. 后端是否正在运行: ssh {BACKEND_HOST} 'ps aux | grep uvicorn'")
    print(f"  2. SSH 隧道是否正常: ps aux | grep 'ssh.*{BACKEND_PORT}'")
    print(f"  3. 端口是否被占用: lsof -i :{BACKEND_PORT}")
    return False

def check_frontend_dependencies() -> bool:
    """检查前端依赖"""
    print("  检查 Node.js 和 pnpm...")

    # 检查 Node.js
    code, stdout, _ = run_command("node --version", check=False)
    if code != 0:
        print_error("Node.js 未安装")
        return False
    node_version = stdout.strip()
    print(f"    Node.js: {node_version}")

    # 检查 pnpm
    code, stdout, _ = run_command("pnpm --version", check=False)
    if code != 0:
        print_error("pnpm 未安装")
        print("  安装: npm install -g pnpm")
        return False
    pnpm_version = stdout.strip()
    print(f"    pnpm: {pnpm_version}")

    # 检查依赖是否安装
    node_modules = FRONTEND_DIR / "node_modules"
    if not node_modules.exists():
        print_warning("前端依赖未安装")
        print("  正在安装依赖...")
        code, _, stderr = run_command(f"cd {FRONTEND_DIR} && pnpm install", check=False)
        if code != 0:
            print_error(f"依赖安装失败: {stderr}")
            return False
        print_success("依赖安装完成")

    return True

def start_frontend() -> bool:
    """启动前端"""
    print_step(4, "启动前端")

    if not FRONTEND_DIR.exists():
        print_error(f"前端目录不存在: {FRONTEND_DIR}")
        return False

    if not check_frontend_dependencies():
        return False

    print(f"  启动 Vite 开发服务器...")
    print(f"  前端地址: http://localhost:{FRONTEND_PORT}")
    print(f"\n{Colors.YELLOW}提示: 按 Ctrl+C 停止前端服务{Colors.RESET}\n")

    try:
        # 前端需要在前台运行，所以不捕获输出
        subprocess.run(
            f"cd {FRONTEND_DIR} && pnpm dev",
            shell=True,
            check=True
        )
    except KeyboardInterrupt:
        print("\n\n前端服务已停止")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"前端启动失败: {e}")
        return False

def show_summary():
    """显示启动摘要"""
    print_step(5, "启动完成")
    print("\n" + "="*60)
    print(f"{Colors.BOLD}MDPilot 已启动{Colors.RESET}")
    print("="*60)
    print(f"\n{Colors.GREEN}前端地址:{Colors.RESET}")
    print(f"  • 主页:     http://localhost:{FRONTEND_PORT}/")
    print(f"  • 工作区:   http://localhost:{FRONTEND_PORT}/workspace")
    print(f"  • 集群监控: http://localhost:{FRONTEND_PORT}/cluster")
    print(f"\n{Colors.GREEN}后端地址:{Colors.RESET}")
    print(f"  • API:      http://localhost:{BACKEND_PORT}")
    print(f"  • 健康检查: http://localhost:{BACKEND_PORT}/health")
    print(f"  • 文档:     http://localhost:{BACKEND_PORT}/docs")
    print(f"\n{Colors.YELLOW}停止服务:{Colors.RESET}")
    print(f"  • 前端: 按 Ctrl+C")
    print(f"  • 后端: ssh {BACKEND_HOST} \"pkill -f 'uvicorn.*mdpilot'\"")
    print(f"  • 隧道: pkill -f 'ssh.*{BACKEND_PORT}.*{BACKEND_HOST}'")
    print("\n" + "="*60 + "\n")

def main():
    """主函数"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}MDPilot 启动脚本{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")

    # 1. 启动后端
    if not start_backend():
        print_error("\n启动失败：后端启动失败")
        print("\n运行诊断脚本获取详细信息:")
        print(f"  python {Path(__file__).parent / 'diagnose_mdpilot.py'}")
        sys.exit(1)

    # 2. 建立 SSH 隧道
    if not create_ssh_tunnel():
        print_error("\n启动失败：SSH 隧道创建失败")
        sys.exit(1)

    # 3. 验证后端连接
    if not verify_backend_connection():
        print_error("\n启动失败：后端连接验证失败")
        print("\n运行诊断脚本获取详细信息:")
        print(f"  python {Path(__file__).parent / 'diagnose_mdpilot.py'}")
        sys.exit(1)

    # 4. 显示摘要
    show_summary()

    # 5. 启动前端（阻塞）
    start_frontend()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n启动已取消")
        sys.exit(0)
    except Exception as e:
        print_error(f"\n未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
