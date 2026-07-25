#!/usr/bin/env python3
"""
Interactive script to update LLM configuration across all MDPilot files.

Updates:
- src/mdpilot/config/defaults.py
- src/mdpilot/config/settings.py
- src/mdpilot/config/schema.py
- src/mdpilot/llm/provider.py
- .mdpilot.yaml

Creates backups before modification.
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


class LLMConfigUpdater:
    def __init__(self, project_root: str):
      self.project_root = Path(project_root)
      self.backup_dir = self.project_root / "backups" / f"llm_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Files to update
        self.files = [
            "src/mdpilot/config/defaults.py",
        "src/mdpilot/config/settings.py",
        "src/mdpilot/config/schema.py",
          "src/mdpilot/llm/provider.py",
          ".mdpilot.yaml",
        ]

    def check_all_configs(self) -> Dict[str, Dict[str, str]]:
        """Check configuration in all files."""
        configs = {}

        # Check defaults.py
        defaults_file = self.project_root / "src/mdpilot/config/defaults.py"
        if defaults_file.exists():
            content = defaults_file.read_text()
         config = {}
        match = re.search(r'"model":\s*"([^"]+)"', content)
            if match:
          config['model'] = match.group(1)
       match = re.search(r'"api_key":\s*"([^"]+)"', content)
            if match:
                config['api_key'] = match.group(1)
            match = re.search(r'"base_url":\s*"([^"]+)"', content)
            if match:
                config['base_url'] = match.group(1)
            configs['defaults.py'] = config

        # Check settings.py
        settings_file = self.project_root / "src/mdpilot/config/settings.py"
        if settings_file.exists():
            content = settings_file.read_text()
          config = {}
            match = re.search(r'llm_model:\s*str\s*=\s*Field\(default="([^"]+)"\)', content)
            if match:
                config['model'] = match.group(1)
            match = re.search(r'llm_api_key:.*?Field\(default="([^"]+)"\)', content)
            if match:
        config['api_key'] = match.group(1)
            match = re.search(r'llm_base_url:.*?Field\(default="([^"]+)"\)', content)
          if match:
             config['base_url'] = match.group(1)
          configs['settings.py'] = config

        # Check schema.py
      schema_file = self.project_root / "src/mdpilot/config/schema.py"
        if schema_file.exists():
            content = schema_file.read_text()
        config = {}
            match = re.search(r'model:\s*str\s*=\s*"([^"]+)"', content)
            if match:
                config['model'] = match.group(1)
            match = re.search(r'api_key:.*?Field\(default="([^"]+)"\)', content)
            if match:
                config['api_key'] = match.group(1)
            match = re.search(r'base_url:.*?Field\(default="([^"]+)"\)', content)
            if match:
                config['base_url'] = match.group(1)
         configs['schema.py'] = config

        # Check provider.py
        provider_file = self.project_root / "src/mdpilot/llm/provider.py"
        if provider_file.exists():
            content = provider_file.read_text()
            config = {}
            match = re.search(r'model:\s*str\s*=\s*"([^"]+)"', content)
            if match:
                config['model'] = match.group(1)
         configs['provider.py'] = config

        # Check .mdpilot.yaml
      yaml_file = self.project_root / ".mdpilot.yaml"
        if yaml_file.exists():
          content = yaml_file.read_text()
            config = {}
            match = re.search(r'model:\s*([^\n]+)', content)
            if match:
          config['model'] = match.group(1).strip()
            match = re.search(r'api_key:\s*([^\n]+)', content)
            if match:
    config['api_key'] = match.group(1).strip()
            match = re.search(r'base_url:\s*([^\n]+)', content)
          if match:
                config['base_url'] = match.group(1).strip()
            configs['.mdpilot.yaml'] = config

        return configs

    def display_all_configs(self, configs: Dict[str, Dict[str, str]]):
     """Display configuration from all files."""
        print("=" * 80)
        print("当前各文件的 LLM 配置")
        print("=" * 80)
        print()

        for filename, config in configs.items():
       print(f"📄 {filename}")
       if config:
                model = config.get('model', 'N/A')
             api_key = config.get('api_key', 'N/A')
              base_url = config.get('base_url', 'N/A')

             # Mask API key
                if api_key != 'N/A' and len(api_key) > 20:
                    api_key_display = api_key[:20] + "..."
           else:
                    api_key_display = api_key

          print(f"  Model:    {model}")
          print(f"  API Key:  {api_key_display}")
              print(f"  Base URL: {base_url}")
            else:
                print("  ⚠ 未找到配置")
         print()

    def prompt_config(self) -> Dict[str, str]:
        """Prompt user for LLM configuration."""
        print("=" * 80)
        print("MDPilot LLM 配置更新工具")
        print("=" * 80)
        print()

        # Check and display all configs
      all_configs = self.check_all_configs()
        self.display_all_configs(all_configs)

        # Get primary config from defaults.py
        current = all_configs.get('defaults.py', {})

        # Ask if user wants to update
        print("=" * 80)
        update = input("是否需要更改配置? (y/N): ").strip().lower()
        if update != 'y':
         print("保持当前配置，退出")
            sys.exit(0)

        # Prompt for new values
        print()
        print("请输入新的配置 (直接回车保持当前值):")
     print()

        model = input(f"模型名称 [{current.get('model', 'MiniMax-M2.7-highspeed')}]: ").strip()
        if not model:
            model = current.get('model', 'MiniMax-M2.7-highspeed')

        api_key = input(f"API Key [{current.get('api_key', '')[:10]}...]: ").strip()
        if not api_key:
          api_key = current.get('api_key', '')

        base_url = input(f"Base URL [{current.get('base_url', 'https://minnimax.chat/v1')}]: ").strip()
        if not base_url:
            base_url = current.get('base_url', 'https://minnimax.chat/v1')

        # Confirm
     print()
        print("=" * 80)
        print("新配置:")
        print(f"  Model:    {model}")
        print(f"  API Key:  {api_key[:20]}...")
        print(f"  Base URL: {base_url}")
        print("=" * 80)
        print()

        confirm = input("确认更新? (y/N): ").strip().lower()
        if confirm != 'y':
            print("取消更新")
            sys.exit(0)

        return {
            'model': model,
            'api_key': api_key,
            'base_url': base_url,
      }

    def create_backups(self):
        """Create backups of all files."""
     self.backup_dir.mkdir(parents=True, exist_ok=True)
        print(f"创建备份到: {self.backup_dir}")

      for file_path in self.files:
            src = self.project_root / file_path
      if src.exists():
                dst = self.backup_dir / file_path
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(src.read_text())
                print(f"  ✓ {file_path}")
        print()

    def update_defaults_py(self, config: Dict[str, str]):
        """Update src/mdpilot/config/defaults.py"""
        file_path = self.project_root / "src/mdpilot/config/defaults.py"
        content = file_path.read_text()

        # Update provider section
        content = re.sub(
            r'"model":\s*"[^"]*"',
          f'"model": "{config["model"]}"',
            content
        )
        content = re.sub(
            r'"api_key":\s*"[^"]*"',
            f'"api_key": "{config["api_key"]}"',
            content
        )
      content = re.sub(
            r'"base_url":\s*"[^"]*"',
         f'"base_url": "{config["base_url"]}"',
            content
        )

        file_path.write_text(content)

    def update_settings_py(self, config: Dict[str, str]):
      """Update src/mdpilot/config/settings.py"""
        file_path = self.project_root / "src/mdpilot/config/settings.py"
        content = file_path.read_text()

        # Update default values
        content = re.sub(
            r'llm_model:\s*str\s*=\s*Field\(default="[^"]*"\)',
          f'llm_model: str = Field(default="{config["model"]}")',
            content
        )
        content = re.sub(
            r'llm_api_key:\s*Optional\[SecretStr\]\s*=\s*Field\(default="[^"]*"\)',
            f'llm_api_key: Optional[SecretStr] = Field(default="{config["api_key"]}")',
            content
        )
        content = re.sub(
            r'llm_base_url:\s*Optional\[str\]\s*=\s*Field\(default="[^"]*"\)',
       f'llm_base_url: Optional[str] = Field(default="{config["base_url"]}")',
          content
        )

        file_path.write_text(content)

  def update_schema_py(self, config: Dict[str, str]):
        """Update src/mdpilot/config/schema.py"""
      file_path = self.project_root / "src/mdpilot/config/schema.py"
        content = file_path.read_text()

     # Update ProviderConfig defaults
        content = re.sub(
          r'model:\s*str\s*=\s*"[^"]*"',
            f'model: str = "{config["model"]}"',
            content
        )
        content = re.sub(
            r'api_key:\s*SecretStr\s*\|\s*None\s*=\s*Field\(default="[^"]*"\)',
        f'api_key: SecretStr | None = Field(default="{config["api_key"]}")',
            content
        )
     content = re.sub(
            r'base_url:\s*str\s*\|\s*None\s*=\s*Field\(default="[^"]*"\)',
            f'base_url: str | None = Field(default="{config["base_url"]}")',
            content
        )

        file_path.write_text(content)

    def update_provider_py(self, config: Dict[str, str]):
        """Update src/mdpilot/llm/provider.py"""
        file_path = self.project_root / "src/mdpilot/llm/provider.py"
        content = file_path.read_text()

        # Update __init__ default parameters
        content = re.sub(
            r'model:\s*str\s*=\s*"[^"]*"',
            f'model: str = "{config["model"]}"',
         content
        )

        file_path.write_text(content)

    def update_mdpilot_yaml(self, config: Dict[str, str]):
        """Update .mdpilot.yaml"""
        file_path = self.project_root / ".mdpilot.yaml"
      if not file_path.exists():
            print(f"  ⚠ {file_path} 不存在，跳过")
            return

      content = file_path.read_text()

        # Update provider section
        content = re.sub(
            r'model:\s*[^\n]+',
            f'model: {config["model"]}',
        content
        )
        content = re.sub(
            r'api_key:\s*[^\n]+',
            f'api_key: {config["api_key"]}',
            content
        )
        content = re.sub(
          r'base_url:\s*[^\n]+',
            f'base_url: {config["base_url"]}',
         content
        )

        file_path.write_text(content)

    def update_all(self, config: Dict[str, str]):
        """Update all configuration files."""
        print("更新配置文件:")

        try:
            self.update_defaults_py(config)
            print("  ✓ src/mdpilot/config/defaults.py")
        except Exception as e:
         print(f"  ✗ src/mdpilot/config/defaults.py: {e}")

        try:
          self.update_settings_py(config)
            print("  ✓ src/mdpilot/config/settings.py")
        except Exception as e:
            print(f"  ✗ src/mdpilot/config/settings.py: {e}")

        try:
            self.update_schema_py(config)
            print("  ✓ src/mdpilot/config/schema.py")
        except Exception as e:
            print(f"  ✗ src/mdpilot/config/schema.py: {e}")

     try:
            self.update_provider_py(config)
            print("  ✓ src/mdpilot/llm/provider.py")
        except Exception as e:
            print(f"  ✗ src/mdpilot/llm/provider.py: {e}")

        try:
            self.update_mdpilot_yaml(config)
            print("  ✓ .mdpilot.yaml")
        except Exception as e:
            print(f"  ✗ .mdpilot.yaml: {e}")

        print()

    def run(self):
    """Main execution flow."""
        # Prompt for config
        config = self.prompt_config()

     # Create backups
        self.create_backups()

        # Update files
        self.update_all(config)

        print("=" * 80)
        print("✓ 配置更新完成!")
        print(f"备份位置: {self.backup_dir}")
        print()
        print("请重启后端服务以应用新配置:")
        print("  ssh zhao@lab03 'bash /tmp/start_backend.sh'")
        print("=" * 80)


def main():
    # Detect project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    if not (project_root / "src/mdpilot").exists():
        print("错误: 无法找到 MDPilot 项目根目录")
        print(f"当前路径: {project_root}")
        sys.exit(1)

    updater = LLMConfigUpdater(str(project_root))
    updater.run()


if __name__ == "__main__":
    main()
