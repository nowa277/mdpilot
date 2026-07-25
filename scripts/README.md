# MDPilot Scripts

## update_llm_config.py

交互式脚本，用于一键更新 MDPilot 的 LLM 配置。

### 功能

- **自动检查所有配置文件** - 显示 5 个文件的当前配置
- **询问是否需要更改** - 可以只查看配置而不修改
- 交互式提示输入新的配置（API Key、Base URL、模型名称）
- 自动更新所有相关配置文件：
  - `src/mdpilot/config/defaults.py`
  - `src/mdpilot/config/settings.py`
  - `src/mdpilot/config/schema.py`
  - `src/mdpilot/llm/provider.py`
  - `.mdpilot.yaml`
- 自动创建备份（保存在 `backups/llm_config_YYYYMMDD_HHMMSS/`）
- 显示当前配置，支持保持现有值（直接回车）

### 使用方法

**在 lab03 上运行：**

```bash
cd /home/3-FF/changshengjie/project/mdpilot
./scripts/update_llm_config.py
```

**或使用 Python 3 直接运行：**

```bash
cd /home/3-FF/changshengjie/project/mdpilot
python3 scripts/update_llm_config.py
```

### 使用示例

#### 场景1: 查看当前配置（不修改）

```
$ ./scripts/update_llm_config.py
=================================================
MDPilot LLM 配置更新工具
================================================

当前各文件的 LLM 配置
==========================================================

📄 defaults.py
  Model:    MiniMax-M2.7-highspeed
  API Key:  gw-2a2beea0-7fb3-490...
  Base URL: https://minnimax.chat/v1

📄 settings.py
  Model:    MiniMax-M2.7-highspeed
  API Key:  gw-2a2beea0-7fb3-490...
  Base URL: https://minnimax.chat/v1

📄 schema.py
  Model:    MiniMax-M2.7-highspeed
  API Key:  gw-2a2beea0-7fb3-490...
  Base URL: https://minnimax.chat/v1

📄 provider.py
  Model:    MiniMax-M2.7-highspeed

📄 .mdpilot.yaml
  Model:    MiniMax-M2.7-highspeed
  API Key:  gw-2a2beea0-7fb3-490...
  Base URL: https://minnimax.chat/v1

==============================================
是否需要更改配置? (y/N): n
保持当前配置，退出
```

#### 场景2: 更新配置

```
$ ./scripts/update_llm_config.py
===========================================
MDPilot LLM 配置更新工具
====================================================

当前各文件的 LLM 配置
=======================================================

📄 defaults.py
  Model:    MiniMax-M2.7-highspeed
  API Key:  gw-2a2beea0-7fb3-490...
  Base URL: https://minnimax.chat/v1

📄 settings.py
  Model:    MiniMax-M2.7-highspeed
  API Key:  gw-2a2beea0-7fb3-490...
  Base URL: https://minnimax.chat/v1

📄 schema.py
  Model:    MiniMax-M2.7-highspeed
  API Key:  gw-2a2beea0-7fb3-490...
  Base URL: https://minnimax.chat/v1

📄 provider.py
  Model:    MiniMax-M2.7-highspeed

📄 .mdpilot.yaml
  Model:    MiniMax-M2.7-highspeed
  API Key:  gw-2a2beea0-7fb3-490...
  Base URL: https://minnimax.chat/v1

=============================================
是否需要更改配置? (y/N): y

请输入新的配置 (直接回车保持当前值):

模型名称 [MiniMax-M2.7-highspeed]: claude-3-5-sonnet-20241022
API Key [gw-2a2beea...]: sk-ant-xxxxxxxxxxxxx
Base URL [https://minnimax.chat/v1]: https://api.anthropic.com

========================================================
新配置:
  Model:    claude-3-5-sonnet-20241022
  API Key:  sk-ant-xxxxxxxxxx...
  Base URL: https://api.anthropic.com
====================================================

确认更新? (y/N): y

创建备份到: /home/3-FF/changshengjie/project/mdpilot/backups/llm_config_20260519_023456
  ✓ src/mdpilot/config/defaults.py
  ✓ src/mdpilot/config/settings.py
  ✓ src/mdpilot/config/schema.py
  ✓ src/mdpilot/llm/provider.py
  ✓ .mdpilot.yaml

更新配置文件:
  ✓ src/mdpilot/config/defaults.py
  ✓ src/mdpilot/config/settings.py
  ✓ src/mdpilot/config/schema.py
  ✓ src/mdpilot/llm/provider.py
  ✓ .mdpilot.yaml

=============================================
✓ 配置更新完成!
备份位置: /home/3-FF/changshengjie/project/mdpilot/backups/llm_config_20260519_023456

请重启后端服务以应用新配置:
  ssh zhao@lab03 'bash /tmp/start_backend.sh'
========================================================
```

### 注意事项

1. **自动检查配置**：脚本会先检查所有 5 个配置文件并显示当前值
2. **可以只查看**：如果只想查看配置，输入 `n` 即可退出
3. **自动备份**：脚本会在 `backups/` 目录下创建带时间戳的备份
4. **保持现有值**：如果某个配置项直接回车，将保持当前值不变
5. **需要重启**：更新配置后需要重启后端服务才能生效
6. **权限要求**：需要对项目目录有写权限

### 恢复备份

如果需要恢复到之前的配置：

```bash
cd /home/3-FF/changshengjie/project/mdpilot

# 查看可用的备份
ls -lt backups/

# 恢复指定备份（替换时间戳）
cp -r backups/llm_config_20260519_023456/* .
```

### 支持的配置项

- **模型名称** (model): LLM 模型标识符
  - 示例: `MiniMax-M2.7-highspeed`, `claude-3-5-sonnet-20241022`, `gpt-4`
  
- **API Key** (api_key): LLM 服务的认证密钥
  - 示例: `gw-2a2beea0-7fb3-4902-b986-c7c12a60ace9`, `sk-ant-xxxxx`
  
- **Base URL** (base_url): LLM API 端点
  - 示例: `https://minnimax.chat/v1`, `https://api.anthropic.com`, `https://api.openai.com/v1`

### 工作流程

1. **检查配置** - 读取所有 5 个配置文件
2. **显示配置** - 以表格形式展示每个文件的配置
3. **询问是否更改** - 用户可以选择退出（只查看）或继续修改
4. **输入新值** - 交互式提示，支持保持现有值
5. **确认更新** - 显示新配置，要求确认
6. **创建备份** - 备份所有将要修改的文件
7. **更新文件** - 批量更新所有配置文件
8. **提示重启** - 提醒用户重启后端服务

### 常见使用场景

#### 只查看配置
```bash
./scripts/update_llm_config.py
# 输入 n 退出
```

#### 切换到 Claude API
```bash
./scripts/update_llm_config.py
# 输入 y 继续
# Model: claude-3-5-sonnet-20241022
# API Key: sk-ant-xxxxxxxxxx
# Base URL: https://api.anthropic.com
```

#### 只更新 API Key
```bash
./scripts/update_llm_config.py
# 输入 y 继续
# Model: [直接回车]
# API Key: gw-new-key-xxxxx
# Base URL: [直接回车]
```

#### 切换到 OpenAI
```bash
./scripts/update_llm_config.py
# 输入 y 继续
# Model: gpt-4-turbo-preview
# API Key: sk-xxxxxxxx
# Base URL: https://api.openai.com/v1
```
