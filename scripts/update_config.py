#!/usr/bin/env python3
import re, sys
from pathlib import Path

root = Path("/home/3-FF/changshengjie/project/mdpilot")
defaults = root / "src/mdpilot/config/defaults.py"

content = defaults.read_text()
m = re.search(r'"model":\s*"([^"]+)"', content)
k = re.search(r'"api_key":\s*"([^"]+)"', content)
u = re.search(r'"base_url":\s*"([^"]+)"', content)

print("="*60)
print("当前配置:")
print(f"  Model: {m.group(1) if m else 'N/A'}")
print(f"  API Key: {k.group(1)[:20] + '...' if k else 'N/A'}")
print(f"  Base URL: {u.group(1) if u else 'N/A'}")
print("="*60)

ans = input("\n是否需要更改? (y/N): ").strip().lower()
if ans != 'y':
    print("退出")
    sys.exit(0)

print("\n请输入新配置 (直接回车保持当前值):")
new_m = input(f"模型 [{m.group(1) if m else ''}]: ").strip() or (m.group(1) if m else "")
new_k = input(f"API Key [{k.group(1)[:10] if k else ''}...]: ").strip() or (k.group(1) if k else "")
new_u = input(f"Base URL [{u.group(1) if u else ''}]: ").strip() or (u.group(1) if u else "")
print(f"\n新配置:\n  Model: {new_m}\n  API Key: {new_k[:20]}...\n  Base URL: {new_u}")
if input("\n确认? (y/N): ").strip().lower() != 'y':
    print("取消")
    sys.exit(0)

content = re.sub(r'"model":\s*"[^"]*"', f'"model": "{new_m}"', content)
content = re.sub(r'"api_key":\s*"[^"]*"', f'"api_key": "{new_k}"', content)
content = re.sub(r'"base_url":\s*"[^"]*"', f'"base_url": "{new_u}"', content)
defaults.write_text(content)
print("\n✓ 已更新 defaults.py")
