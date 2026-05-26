#!/usr/bin/env python3
"""Amber CLI Shortcuts - 简化的命令行接口

提供用户友好的快捷命令，涵盖核心功能。
"""

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

from mdpilot.agent.react import ReActLoop
from mdpilot.config.loader import load_config


def run_chat(command: str, output_dir: str = "./amber_output",
             model: Optional[str] = None, verbose: bool = False,
             max_iterations: int = 20) -> int:
    """运行单次对话命令"""
    try:
        cli_overrides = {}
        if model:
            cli_overrides["provider"] = {"model": model}
        if max_iterations:
            cli_overrides["agent"] = {"max_iterations": max_iterations}

        config = load_config(cli_overrides=cli_overrides)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        loop = ReActLoop(config)

        if not verbose:
            print(f"🤖 Amber-Agent")
            print(f"📝 {command}")
            print()

        enhanced_command = f"""
Task: {command}

Working directory: {output_path}

Please execute this task step by step. Use appropriate AMBER tools as needed.
Report progress and final results clearly.
"""

        result = asyncio.run(loop.run(enhanced_command, stream=False))

        print("\n" + "=" * 60)
        print("✅ Task completed!")
        print("=" * 60)
        print(result)
        print()
        print(f"📊 Iterations: {loop.iteration}/{loop.max_iterations}")
        print(f"📁 Output: {output_path}")

        return 0

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


def run_prepare(pdb_input: str, output_dir: str = "./amber_output",
                force_field: str = "ff19SB", water_model: str = "tip3p",
                verbose: bool = False) -> int:
    """准备蛋白质系统（预设工作流）"""
    command = f"""
Please prepare a protein system for MD simulation:

Input: {pdb_input}
Force field: {force_field}
Water model: {water_model}

Steps:
1. Download or load the PDB file (if it's a PDB ID like 1AKI)
2. Clean the structure with pdb4amber
3. Build the system with tleap using {force_field} and {water_model}
4. Generate topology (.prmtop) and coordinate (.inpcrd) files
5. Validate the system

Please report the final system details (atom count, box size, etc.)
"""
    return run_chat(command, output_dir, verbose=verbose)


def run_simulate(system: str, output_dir: str = "./amber_output",
                 steps: int = 10000, verbose: bool = False) -> int:
    """运行 MD 模拟（预设工作流）"""
    system_path = Path(system)
    if not system_path.exists():
        print(f"❌ Error: System file not found: {system}", file=sys.stderr)
        return 1

    command = f"""
Please run a molecular dynamics simulation:

System: {system}
Steps: {steps}

Workflow:
1. Energy minimization (500 steps)
2. Heating (0-300K, 20ps)
3. Equilibration (NPT, 50ps)
4. Production run ({steps} steps)

Use sander or pmemd if available. Generate trajectory files and analysis.
"""
    return run_chat(command, output_dir, verbose=verbose)


def run_analyze(trajectory: str, topology: str, output_dir: str = "./amber_output",
                verbose: bool = False) -> int:
    """分析轨迹（预设工作流）"""
    traj_path = Path(trajectory)
    top_path = Path(topology)

    if not traj_path.exists():
        print(f"❌ Error: Trajectory file not found: {trajectory}", file=sys.stderr)
        return 1
    if not top_path.exists():
        print(f"❌ Error: Topology file not found: {topology}", file=sys.stderr)
        return 1

    command = f"""
Please analyze the MD trajectory:

Trajectory: {trajectory}
Topology: {topology}

Analysis:
1. RMSD calculation
2. RMSF per residue
3. Radius of gyration
4. Hydrogen bonds
5. Secondary structure (if applicable)

Use cpptraj for analysis and generate plots if possible.
"""
    return run_chat(command, output_dir, verbose=verbose)


def run_test(test_type: str = "all", verbose: bool = False) -> int:
    """运行测试"""
    print(f"🧪 Running {test_type} tests...")
    print()

    cmd_map = {
        "all": ["pytest", "tests/", "-v"],
        "unit": ["pytest", "tests/", "-v", "-m", "not integration and not slow"],
        "integration": ["pytest", "tests/integration/", "-v", "-m", "integration"],
        "fast": ["pytest", "tests/", "-v", "-m", "not slow"],
    }

    cmd = cmd_map.get(test_type, cmd_map["all"])
    if verbose:
        cmd.append("-vv")

    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except FileNotFoundError:
        print("❌ Error: pytest not found. Install with: pip install -e '.[dev]'",
              file=sys.stderr)
        return 1


def run_benchmark(save_baseline: Optional[str] = None,
                  compare: Optional[str] = None,
                  verbose: bool = False) -> int:
    """运行性能基准测试"""
    print("⚡ Running benchmarks...")
    print()

    cmd = ["pytest", "benchmarks/", "-v", "--benchmark-only"]

    if save_baseline:
        cmd.extend(["--benchmark-save", save_baseline])
        print(f"💾 Saving baseline: {save_baseline}")

    if compare:
        cmd.extend(["--benchmark-compare", compare])
        print(f"📊 Comparing with: {compare}")

    if verbose:
        cmd.append("-vv")

    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except FileNotFoundError:
        print("❌ Error: pytest not found. Install with: pip install -e '.[dev]'",
              file=sys.stderr)
        return 1


def run_profile(name: str, output_dir: str = "./profiling/results",
                verbose: bool = False) -> int:
    """运行性能分析"""
    print(f"📊 Running profiling: {name}")
    print()

    cmd = ["python", "-m", "profiling.analyze_workflow", name]

    if output_dir:
        cmd.extend(["--output-dir", output_dir])

    if verbose:
        cmd.append("--verbose")

    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1


def main():
    """主入口点 - 简化的 amber 命令"""
    parser = argparse.ArgumentParser(
        prog="amber",
        description="Amber-Agent - Simplified CLI for AMBER molecular dynamics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 直接对话（最简单）
  amber --chat "请帮我处理这个蛋白构建为一个tleap后的体系"
  amber -c "Download PDB 1AKI and prepare it for simulation"

  # 预设工作流
  amber prepare 1AKI                    # 准备蛋白质
  amber prepare 1AKI --ff ff19SB        # 指定力场
  amber simulate system.prmtop          # 运行模拟
  amber analyze prod.nc system.prmtop   # 分析轨迹

  # 测试和基准
  amber test                            # 运行所有测试
  amber test unit                       # 只运行单元测试
  amber test integration                # 只运行集成测试
  amber benchmark                       # 运行基准测试
  amber benchmark --save v1.0.0         # 保存性能基线
  amber profile my_workflow             # 性能分析

  # 完整命令（兼容旧版）
  amber run "Build MD system for 1AKI"

  # 交互模式（未来支持）
  amber                                 # 启动交互式 REPL
        """,
    )

    # 创建子命令
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --chat / -c 快捷方式（作为顶层参数）
    parser.add_argument(
        "--chat", "-c",
        type=str,
        metavar="MESSAGE",
        help="Direct chat mode: amber --chat 'your message'"
    )

    # run 命令（显式）
    run_parser = subparsers.add_parser("run", help="Run a natural language command")
    run_parser.add_argument("message", type=str, help="Natural language command")
    run_parser.add_argument("--output-dir", "-o", default="./amber_output",
                           help="Output directory")
    run_parser.add_argument("--model", "-m", help="LLM model to use")
    run_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    run_parser.add_argument("--max-iterations", type=int, default=20,
                           help="Maximum agent iterations")

    # prepare 命令
    prepare_parser = subparsers.add_parser("prepare",
                                          help="Prepare protein system (preset workflow)")
    prepare_parser.add_argument("pdb", type=str, help="PDB file or PDB ID (e.g., 1AKI)")
    prepare_parser.add_argument("--output-dir", "-o", default="./amber_output",
                               help="Output directory")
    prepare_parser.add_argument("--ff", "--force-field", default="ff19SB",
                               help="Force field (default: ff19SB)")
    prepare_parser.add_argument("--water", default="tip3p",
                               help="Water model (default: tip3p)")
    prepare_parser.add_argument("--verbose", "-v", action="store_true")

    # simulate 命令
    sim_parser = subparsers.add_parser("simulate",
                                       help="Run MD simulation (preset workflow)")
    sim_parser.add_argument("system", type=str, help="System topology file (.prmtop)")
    sim_parser.add_argument("--output-dir", "-o", default="./amber_output",
                           help="Output directory")
    sim_parser.add_argument("--steps", type=int, default=10000,
                           help="Production steps (default: 10000)")
    sim_parser.add_argument("--verbose", "-v", action="store_true")

    # analyze 命令
    analyze_parser = subparsers.add_parser("analyze",
                                          help="Analyze trajectory (preset workflow)")
    analyze_parser.add_argument("trajectory", type=str, help="Trajectory file (.nc)")
    analyze_parser.add_argument("topology", type=str, help="Topology file (.prmtop)")
    analyze_parser.add_argument("--output-dir", "-o", default="./amber_output",
                               help="Output directory")
    analyze_parser.add_argument("--verbose", "-v", action="store_true")

    # test 命令
    test_parser = subparsers.add_parser("test", help="Run tests")
    test_parser.add_argument("type", nargs="?", default="all",
                            choices=["all", "unit", "integration", "fast"],
                            help="Test type (default: all)")
    test_parser.add_argument("--verbose", "-v", action="store_true")

    # benchmark 命令
    bench_parser = subparsers.add_parser("benchmark", help="Run performance benchmarks")
    bench_parser.add_argument("--save", type=str, metavar="NAME",
                             help="Save performance baseline")
    bench_parser.add_argument("--compare", type=str, metavar="NAME",
                             help="Compare with baseline")
    bench_parser.add_argument("--verbose", "-v", action="store_true")

    # profile 命令
    profile_parser = subparsers.add_parser("profile", help="Run performance profiling")
    profile_parser.add_argument("name", type=str, help="Workflow name")
    profile_parser.add_argument("--output-dir", "-o", default="./profiling/results",
                               help="Output directory")
    profile_parser.add_argument("--verbose", "-v", action="store_true")

    # 解析参数
    args = parser.parse_args()

    # 处理 --chat 快捷方式
    if args.chat:
        return run_chat(args.chat, verbose=getattr(args, 'verbose', False))

    # 处理子命令
    if args.command == "run":
        return run_chat(args.message, args.output_dir, args.model,
                       args.verbose, args.max_iterations)

    elif args.command == "prepare":
        return run_prepare(args.pdb, args.output_dir, args.ff,
                          args.water, args.verbose)

    elif args.command == "simulate":
        return run_simulate(args.system, args.output_dir,
                           args.steps, args.verbose)

    elif args.command == "analyze":
        return run_analyze(args.trajectory, args.topology,
                          args.output_dir, args.verbose)

    elif args.command == "test":
        return run_test(args.type, args.verbose)

    elif args.command == "benchmark":
        return run_benchmark(args.save, args.compare, args.verbose)

    elif args.command == "profile":
        return run_profile(args.name, args.output_dir, args.verbose)

    else:
        # 无参数 - 显示帮助或启动交互模式
        parser.print_help()
        print("\n💡 Tip: Use 'amber --chat \"your message\"' for quick commands")
        print("💡 Tip: Use 'amber prepare 1AKI' for preset workflows")
        return 0


if __name__ == "__main__":
    sys.exit(main())
