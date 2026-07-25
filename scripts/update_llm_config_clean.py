#!/usr/bin/env python3
import re, sys
from datetime import datetime
from pathlib import Path
from typing import Dict

class LLMConfigUpdater:
    def __init__(self, root: str):
        self.root = Path(root)
        self.backup = self.root / "backups" / f"llm_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.files = ["src/mdpilot/config/defaults.py", "src/mdpilot/config/settings.py", 
               "src/mdpilot/config/schema.py", "src/mdpilot/llm/provider.py", ".mdpilot.yaml"]
    
    def check(self) -> Dict:
        cfg = {}
        for name, path in [("defaults.py", "src/mdpilot/config/defaults.py"),
                    ("settings.py", "src/mdpilot/config/settings.py"),
                   ("schema.py", "src/mdpilot/config/schema.py"),
                      ("provider.py", "src/mdpilot/llm/provider.py"),
                        (".mdpilot.yaml", ".mdpilot.yaml")]:
            f = self.root / path
          if not f.exists(): continue
            txt = f.read_text()
          c = {}
            if m := re.search(r'"model":\s*"([^"]+)"', txt): c['model'] = m.group(1)
            if m := re.search(r'"api_key":\s*"([^"]+)"', txt): c['api_key'] = m.group(1)
            if m := re.search(r'"base_url":\s*"([^"]+)"', txt): c['base_url'] = m.group(1)
          if m := re.search(r'llm_model:\s*str\s*=\s*Field\(default="([^"]+)"\)', txt): c['model'] = m.group(1)
            if m := re.search(r'llm_api_key:.*?Field\(default="([^"]+)"\)', txt): c['api_key'] = m.group(1)
            if m := re.search(r'llm_base_url:.*?Field\(default="([^"]+)"\)', txt): c['base_url'] = m.group(1)
            if m := re.search(r'model:\s*str\s*=\s*"([^"]+)"', txt): c['model'] = m.group(1)
            if m := re.search(r'api_key:.*?Field\(default="([^"]+)"\)', txt): c['api_key'] = m.group(1)
            if m := re.search(r'base_url:.*?Field\(default="([^"]+)"\)', txt): c['base_url'] = m.group(1)
      if m := re.search(r'model:\s*([^\n]+)', txt): c['model'] = m.group(1).strip()
            if m := re.search(r'api_key:\s*([^\n]+)', txt): c['api_key'] = m.group(1).strip()
       if m := re.search(r'base_url:\s*([^\n]+)', txt): c['base_url'] = m.group(1).strip()
            cfg[name] = c
        return cfg
    
    def show(self, cfg: Dict):
        print("="*80, "\n当前各文件的 LLM 配置\n", "="*80, "\n", sep="")
      for name, c in cfg.items():
            print(f"📄 {name}")
            if c:
                m, k, u = c.get('model','N/A'), c.get('api_key','N/A'), c.get('base_url','N/A')
            kd = k[:20]+"..." if k!='N/A' and len(k)>20 else k
                print(f"  Model: {m}\n  API Key: {kd}\n  Base URL: {u}")
            else: print("  ⚠ 未找到配置")
            print()
    
    def prompt(self) -> Dict:
        print("="*80, "\nMDPilot LLM 配置更新工具\n", "="*80, "\n", sep="")
      cfg = self.check()
        self.show(cfg)
        cur = cfg.get('defaults.py', {})
        print("="*80)
        if input("是否需要更改配置? (y/N): ").strip().lower() != 'y':
            print("保持当前配置，退出"); sys.exit(0)
        print("\n请输入新的配置 (直接回车保持当前值):\n")
        m = input(f"模型名称 [{cur.get('model','MiniMax-M2.7-highspeed')}]: ").strip() or cur.get('model','MiniMax-M2.7-highspeed')
        k = input(f"API Key [{cur.get('api_key','')[:10]}...]: ").strip() or cur.get('api_key','')
        u = input(f"Base URL [{cur.get('base_url','https://minnimax.chat/v1')}]: ").strip() or cur.get('base_url','https://minnimax.chat/v1')
        print(f"\n{'='*80}\n新配置:\n  Model: {m}\n  API Key: {k[:20]}...\n  Base URL: {u}\n{'='*80}\n")
     if input("确认更新? (y/N): ").strip().lower() != 'y':
            print("取消更新"); sys.exit(0)
        return {'model': m, 'api_key': k, 'base_url': u}
    
    def backup(self):
        self.backup.mkdir(parents=True, exist_ok=True)
        print(f"创建备份到: {self.backup}")
        for fp in self.files:
            src = self.root / fp
            if src.exists():
                dst = self.backup / fp
          dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(src.read_text())
              print(f"  ✓ {fp}")
        print()
    
    def update(self, c: Dict):
        print("更新配置文件:")
        for name, path, patterns in [
            ("defaults.py", "src/mdpilot/config/defaults.py", [(r'"model":\s*"[^"]*"', f'"model": "{c["model"]}"'),
                                             (r'"api_key":\s*"[^"]*"', f'"api_key": "{c["api_key"]}"'),
                                         (r'"base_url":\s*"[^"]*"', f'"base_url": "{c["base_url"]}"')]),
         ("settings.py", "src/mdpilot/config/settings.py", [(r'llm_model:\s*str\s*=\s*Field\(default="[^"]*"\)', f'llm_model: str = Field(default="{c["model"]}")'),
                                  (r'llm_api_key:\s*Optional\[SecretStr\]\s*=\s*Field\(default="[^"]*"\)', f'llm_api_key: Optional[SecretStr] = Field(default="{c["api_key"]}")'),
                                                    (r'llm_base_url:\s*Optional\[str\]\s*=\s*Field\(default="[^"]*"\)', f'llm_base_url: Optional[str] = Field(default="{c["base_url"]}")')]),
            ("schema.py", "src/mdpilot/config/schema.py", [(r'model:\s*str\s*=\s*"[^"]*"', f'model: str = "{c["model"]}"'),
                                  (r'api_key:\s*SecretStr\s*\|\s*None\s*=\s*Field\(default="[^"]*"\)', f'api_key: SecretStr | None = Field(default="{c["api_key"]}")'),
                                                (r'base_url:\s*str\s*\|\s*None\s*=\s*Field\(default="[^"]*"\)', f'base_url: str | None = Field(default="{c["base_url"]}")')]),
            ("provider.py", "src/mdpilot/llm/provider.py", [(r'model:\s*str\s*=\s*"[^"]*"', f'model: str = "{c["model"]}"')]),
            (".mdpilot.yaml", ".mdpilot.yaml", [(r'model:\s*[^\n]+', f'model: {c["model"]}'),
                                     (r'api_key:\s*[^\n]+', f'api_key: {c["api_key"]}'),
                                       (r'base_url:\s*[^\n]+', f'base_url: {c["base_url"]}')])
        ]:
        try:
             fp = self.root / path
              if not fp.exists() and name == ".mdpilot.yaml":
                    print(f"  ⚠ {path} 不存在，跳过"); continue
                txt = fp.read_text()
                for pat, repl in patterns: txt = re.sub(pat, repl, txt)
                fp.write_text(txt)
                print(f"  ✓ {path}")
         except Exception as e: print(f"  ✗ {path}: {e}")
        print()
    
    def run(self):
        c = self.prompt()
        self.backup()
        self.update(c)
        print(f"{'='*80}\n✓ 配置更新完成!\n备份位置: {self.backup}\n\n请重启后端服务以应用新配置:\n  ssh zhao@lab03 'bash /tmp/start_backend.sh'\n{'='*80}")

if __name__ == "__main__":
    root = Path(__file__).parent.parent
    if not (root / "src/mdpilot").exists():
        print(f"错误: 无法找到 MDPilot 项目根目录\n当前路径: {root}"); sys.exit(1)
    LLMConfigUpdater(str(root)).run()
