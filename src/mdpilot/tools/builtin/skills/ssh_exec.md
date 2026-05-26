---
name: ssh_exec
description: "Execute commands on remote compute nodes (lab02/lab03/lab06) via SSH. Default workdir is the node's changshengjie directory."
triggers:
  - ssh
  - remote
  - lab02
  - lab06
  - remote execute
  - remote command
depends_on: []
node: multi
exec_method: ssh
exec_path: asyncssh
references: []
---

### When to use
- Run commands on remote compute nodes when data/tools are on different machines
- Use for: checking remote files, running remote scripts, monitoring GPU status on other nodes
- For lab03 local commands, use `bash_run` instead (no SSH overhead)

### Available Nodes

| Node | Role | GPU | VRAM | Writable Directory |
|------|------|-----|------|--------------------|
| lab02 | AlphaFold2 structure prediction | 9× NVIDIA TITAN V | 12GB each | /home/2-BB/changshengjie |
| lab03 | AMBER MD (primary), MDPilot backend | 4× GTX 1080Ti | 11GB each | /home/3-FF/changshengjie |
| lab06 | BioReason function annotation | 9× NVIDIA RTX 3090 | 24GB each | /home/6-FF/changshengjie |

### Connection Details
- **Username:** zhao (all nodes)
- **SSH key:** ~/.ssh/id_ed25519
- **Default workdir:** node's changshengjie directory (see table above)
- Write ONLY within changshengjie directories. Read-only elsewhere.

### Parameters
- `node` (required): target node ID — "lab02", "lab03", or "lab06"
- `command` (required): bash command to execute on remote node
- `workdir` (optional): override default workdir
- `timeout` (optional, default 600): max seconds to wait

### Common Errors
- "Unknown node" → check node name is exactly "lab02", "lab03", or "lab06"
- Connection refused → SSH tunnel may be down, check port forwarding
- Permission denied → trying to write outside changshengjie directory
- Timeout → increase timeout for long-running remote jobs
