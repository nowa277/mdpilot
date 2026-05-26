---
name: file_ops
description: "File operations on lab03: read (with line range), write (changshengjie only), and glob search. Sensitive files are blocked."
triggers:
  - file
  - read file
  - write file
  - search file
  - file operations
depends_on: []
node: lab03
exec_method: local
exec_path: python pathlib
references: []
---

### Overview
Three tools for file I/O on lab03. All operations are governed by FileAccessPolicy.

### file_read
- Read text file contents with optional line range
- **Parameters:** `path` (required), `offset` (default 1, 1-indexed), `limit` (default 500 lines)
- **Security:** Sensitive files blocked (.key, .pem, .token, .env, credentials)
- **Output:** file contents as string, with line count if truncated
- **Example:** `file_read(path="/home/3-FF/changshengjie/project/md.out", offset=1, limit=50)`

### file_write
- Write text content to file, creating parent directories as needed
- **Parameters:** `path` (required), `content` (required)
- **Security:** ONLY within /home/3-FF/changshengjie/ directory
- **Output:** success message with byte count, or access denied error
- **Example:** `file_write(path="/home/3-FF/changshengjie/project/md.in", content="...")`

### file_search
- Search for files matching a glob pattern
- **Parameters:** `pattern` (required, e.g. "*.pdb", "**/*.py"), `directory` (default ".")
- **Output:** newline-separated list of matching paths (max 100 results)
- **Example:** `file_search(pattern="*.prmtop", directory="/home/3-FF/changshengjie/project")`

### Common Errors
- "Access denied by policy" → path is outside changshengjie directory or is a sensitive file
- "File not found" → check absolute path, use file_search to locate files
- "Write access denied" → only changshengjie directory is writable
- "No files matching" → check glob pattern and directory
