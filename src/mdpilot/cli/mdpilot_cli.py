#!/usr/bin/env python3
"""MDPilot CLI - 命令行接口

支持自然语言命令，可被其他编程代理直接调用。
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from mdpilot.agent.react import ReActLoop
from mdpilot.config.loader import load_config


def main():
    # Default: launch TUI if no arguments
    if len(sys.argv) == 1:
        # Use Textual TUI (better compatibility)
        try:
            from mdpilot.tui_pyratatui.app_textual import main_textual
            asyncio.run(main_textual())
        except Exception as e:
            print(f"❌ TUI failed to start: {e}")
            print("\n💡 If TUI doesn't work, try command mode:")
            print("   mdpilot --command 'your task here'")
            import traceback
            traceback.print_exc()
        return
    
    # Test mode: verify TUI components without TTY
    if len(sys.argv) == 2 and sys.argv[1] == "--test-tui":
        print("🧪 Testing TUI components (no TTY required)...\n")
        from mdpilot.tui_pyratatui.state import AppState, Message
        from mdpilot.tui_pyratatui.theme import Theme
        from mdpilot.tui_pyratatui.components.welcome_panel import WelcomePanel
        from mdpilot.tui_pyratatui.components.input_area import InputArea
        from mdpilot.tui_pyratatui.utils.mascot_loader import load_mascot_pixels, get_mascot_dimensions
        
        # Test state
        print("✅ State management:")
        state = AppState()
        print(f"   - Initial messages: {len(state.messages)}")
        print(f"   - Model: {state.model_name}")
        print(f"   - Connected: {state.connected}")
        
        # Test theme
        print("\n✅ Theme system:")
        theme = Theme()
        print(f"   - Primary color: RGB{theme.primary}")
        print(f"   - Background: RGB{theme.background}")
        
        # Test mascot
        print("\n✅ Mascot loader:")
        pixels = load_mascot_pixels()
        width, height = get_mascot_dimensions()
        non_transparent = sum(1 for row in pixels for p in row if p is not None)
        print(f"   - Dimensions: {width}×{height}")
        print(f"   - Pixels: {non_transparent} non-transparent")
        
        # Test components
        print("\n✅ Components:")
        welcome = WelcomePanel(state, theme)
        input_area = InputArea(state, theme)
        print(f"   - WelcomePanel initialized")
        print(f"   - InputArea initialized")
        
        # Test message flow
        print("\n✅ Message flow:")
        state.ui.input_buffer = "Test message"
        input_area._send_message()
        print(f"   - Messages after send: {len(state.messages)}")
        print(f"   - Message content: '{state.messages[0].content}'")
        print(f"   - Input cleared: {state.ui.input_buffer == ''}")
        
        print("\n🎉 All TUI components working correctly!")
        print("\n💡 To run the actual TUI, use a real terminal:")
        print("   ssh user@host")
        print("   mdpilot")
        return
    
    parser = argparse.ArgumentParser(
        description="MDPilot - AI-powered AMBER molecular dynamics automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Launch TUI (default)
  mdpilot

  # 自然语言命令
  mdpilot --command "Download PDB 1AKI and prepare it for MD simulation"

  # 完整工作流
  mdpilot --command "Build a complete MD system for protein 1AKI with ff19SB force field"

  # 指定输出目录
  mdpilot --command "Prepare 1AKI for simulation" --output-dir ./my_project

  # JSON 输出（适合编程调用）
  mdpilot --command "Check if pdb4amber is available" --json

  # 详细模式
  mdpilot --command "Run minimization on system.prmtop" --verbose
        """,
    )

    parser.add_argument(
        "--command",
        type=str,
        help="Natural language command describing what you want to do",
    )

    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default="./amber_output",
        help="Output directory for generated files (default: ./amber_output)",
    )

    parser.add_argument(
        "--model",
        "-m",
        type=str,
        help="LLM model to use (default: from config)",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format (for programmatic use)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=20,
        help="Maximum agent iterations (default: 20)",
    )

    parser.add_argument(
        "--config",
        type=str,
        help="Path to config file",
    )

    args = parser.parse_args()
    
    # If no command provided, show error
    if not args.command:
        parser.error("--command is required when using CLI mode")
    
    # 加载配置
    try:
        # 准备 CLI 覆盖参数
        cli_overrides = {}
        if args.model:
            cli_overrides["provider"] = {"model": args.model}
        if args.max_iterations:
            cli_overrides["agent"] = {"max_iterations": args.max_iterations}

        # 加载配置（如果指定了 config 路径，使用 project_dir）
        project_dir = Path(args.config).parent if args.config else None
        config = load_config(cli_overrides=cli_overrides, project_dir=project_dir)
    except Exception as e:
        if args.json:
            print(json.dumps({"error": f"Failed to load config: {e}"}))
        else:
            print(f"❌ Error: Failed to load config: {e}", file=sys.stderr)
        sys.exit(1)

    # 创建输出目录
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 初始化 ReActLoop
    try:
        loop = ReActLoop(config)
    except Exception as e:
        if args.json:
            print(json.dumps({"error": f"Failed to initialize agent: {e}"}))
        else:
            print(f"❌ Error: Failed to initialize agent: {e}", file=sys.stderr)
        sys.exit(1)

    # 执行命令
    if not args.json:
        print(f"🤖 MDPilot")
        print(f"📝 Command: {args.command}")
        print(f"📁 Output: {output_dir}")
        print(f"🔧 Model: {config.provider.model}")
        print()

    try:
        # 增强命令上下文
        enhanced_command = f"""
Task: {args.command}

Working directory: {output_dir}

Please execute this task step by step. If you need to download PDB files,
prepare systems, or run simulations, use the appropriate AMBER tools.

Report progress and final results clearly.
"""

        # 运行异步任务
        result = asyncio.run(loop.run(enhanced_command, stream=False))

        if args.json:
            output = {
                "success": True,
                "command": args.command,
                "result": result,
                "output_dir": str(output_dir),
                "iterations": loop.iteration,
                "max_iterations": loop.max_iterations,
            }
            print(json.dumps(output, indent=2))
        else:
            print("\n" + "=" * 60)
            print("✅ Task completed!")
            print("=" * 60)
            print(result)
            print()
            print(f"📊 Iterations: {loop.iteration}/{loop.max_iterations}")
            print(f"📁 Output directory: {output_dir}")

    except KeyboardInterrupt:
        if args.json:
            print(json.dumps({"error": "Interrupted by user"}))
        else:
            print("\n⚠️  Interrupted by user", file=sys.stderr)
        sys.exit(130)

    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}))
        else:
            print(f"\n❌ Error: {e}", file=sys.stderr)
            if args.verbose:
                import traceback

                traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
