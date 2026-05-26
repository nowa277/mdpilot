---
name: bash_run
description: "Execute bash commands on lab03. Dangerous patterns (rm -rf /, sudo, curl|bash) are blocked by security validation. Use ssh_exec for remote nodes."
triggers:
  - bash
  - shell
  - command
  - run command
  - execute
depends_on: []
node: lab03
exec_method: local_subprocess
exec_path: /bin/bash
references: []
---

### When to use
- Run shell commands on lab03 (the AMBER MD server where MDPilot backend runs)
- For remote nodes (lab02/lab06), use `ssh_exec` instead
- For file operations, prefer `file_read`/`file_write`/`file_search` tools

### Security
- **Blocked patterns:** `rm -rf /`, `sudo`, `curl|bash`, disk write to system dirs, fork bombs, `chmod 777`
- All commands are logged for audit trail
- Only runs on lab03 (local machine)

### Parameters
- `command` (required): the bash command string
- `timeout` (optional, default 60): max seconds before killing process
- `workdir` (optional): working directory for command execution

### Output
- Combined stdout + stderr as string
- Non-zero exit codes are included in output
- Timeout: `TimeoutError` raised after timeout expires

### Tips
- Increase timeout for long-running jobs: AMBER minimization may need 300+, production 3600+
- Use `workdir` to ensure commands run in correct project directory
- Pipe commands with `&&` for sequential execution

### Common Errors
- "dangerous pattern" → restructure command to avoid blocked pattern
- Timeout → increase timeout parameter
- "command not found" → check executable is in PATH or use absolute path
