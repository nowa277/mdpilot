---
name: sander
description: "General-purpose MD engine. Use ONLY when pmemd_cuda cannot handle the task (QM/MM, NMR, imin=5). Prefer pmemd_cuda for standard workflows."
triggers: [sander, QM/MM, NMR refinement, EVB, energy decomposition, trajectory analysis]
depends_on: [tleap]
node: lab03
exec_method: local_subprocess
exec_path: /home/6-AA/softwares/Amber24/amber24/bin/sander
references: [sander-pmemd]
---

# sander — General-Purpose MD Engine

## When to Use

Use sander **ONLY** when pmemd.cuda cannot handle the task. sander supports specialized features not available in pmemd.cuda:

- **QM/MM** (`ifqnt != 0`) — quantum mechanics/molecular mechanics coupled simulations
- **NMR refinement** (`nmropt = 2`) — NMR restraint-driven simulations
- **Empirical Valence Bond** (`ievb != 0`) — EVB free energy calculations
- **Trajectory analysis via minimization** (`imin = 5`) — retrospective energy analysis
- **Energy decomposition** (`idecomp != 0`) — per-residue or per-atom energy breakdowns
- **Polarizable force fields** (`ipol != 0`) — induced dipole or Drude oscillator models

**For ALL standard MD workflows** (minimization, heating, equilibration, production) — use `pmemd_cuda` instead. It is 10-100x faster.

## Execution Environment

- **Node:** lab03 (local subprocess, NOT SSH)
- **Exec path:** `/home/6-AA/softwares/Amber24/amber24/bin/sander`
- **Timeout:** default 3600s (1 hour)
- **No GPU:** sander runs on CPU only. This is one reason it is much slower than pmemd.cuda.

## Input Config Format

sander uses the same Fortran namelist format as pmemd.cuda. The `&cntrl ... /` block is identical. See the `pmemd_cuda` SKILL for complete templates covering minimization, heating, equilibration, and production MD.

For QM/MM, additional namelist blocks are required (`&qmmm`, `&qm_theory`), for example:

```
QM/MM minimization
&cntrl
  imin = 1, maxcyc = 5000, ncyc = 2500,
  ntb = 1, igb = 0, cut = 10.0,
  ifqnt = 1,
/
&qmmm
  qmmask = ':LIG',
  qmcharge = 0,
  qm_theory = 'PM6',
  qmcut = 10.0,
/
```

## Parameters

| Parameter | Type | Description |
|---|---|---|
| `input_config` | str | Multiline Fortran namelist configuration (can be inline or file path) |
| `prmtop` | str | Path to topology file |
| `inpcrd` | str | Path to input coordinates (inpcrd or restart file) |
| `output` | str | Path to output log file |
| `trajectory` | str | Path to trajectory output file |
| `use_pmemd` | bool | If True, route to pmemd.cuda instead (for standard MD configs) |
| `nproc` | int | Number of CPU cores (default 1) |
| `workdir` | str | Working directory for the simulation |
| `timeout` | int | Timeout in seconds (default 3600) |

## Common Errors

| Error | Cause | Fix |
|---|---|---|
| Return code 2 | Syntax error in namelist or missing input files | Check namelist formatting; verify all file paths exist |
| Timeout | sander is CPU-only and very slow for production MD | Switch to pmemd.cuda for standard MD; sander should only be used for specialized features |
| "FATAL: only pmemd supports GPU" | Tried to use GPU flags with sander | Remove `-gpu` flag or switch to pmemd.cuda |
