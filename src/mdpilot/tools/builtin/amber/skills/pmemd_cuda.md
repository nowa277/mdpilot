---
name: pmemd_cuda
description: "GPU-accelerated MD simulation with pmemd.cuda. 10-100x faster than sander. Preferred for all standard MD workflows."
triggers: [pmemd, pmemd.cuda, GPU, CUDA, production MD, MD simulation, molecular dynamics, minimization, heating, equilibration]
depends_on: [tleap]
node: lab03
exec_method: local_subprocess
exec_path: /home/6-AA/softwares/Amber24/amber24/bin/pmemd.cuda
references: [sander-pmemd]
---

# pmemd.cuda — GPU-Accelerated Molecular Dynamics

## When to Use

**ALWAYS prefer pmemd.cuda over sander** for standard MD workflows. It is 10-100x faster.

Only use sander when you need features pmemd.cuda does not support:
- QM/MM (`ifqnt != 0`)
- NMR restraints (`nmropt = 2`)
- Empirical Valence Bond (`ievb != 0`)
- Trajectory analysis with minimization (`imin = 5`)
- Energy decomposition (`idecomp != 0`)
- Polarizable force fields (`ipol != 0`)

## Execution Environment

- **Node:** lab03 (local subprocess, NOT SSH)
- **Exec path:** `/home/6-AA/softwares/Amber24/amber24/bin/pmemd.cuda`
- **GPU hardware:** 9x NVIDIA RTX 3090 (24GB VRAM each)
- **GPU selection:** `gpu_id` 0-8, auto-selects least loaded GPU
- **Timeout:** default 86400s (24h) for production runs

## CRITICAL: Input Config Must Be Pure ASCII

Input configuration files (`*.in`) MUST contain only ASCII characters. Chinese characters or any non-ASCII bytes will cause "Cannot match namelist object name" errors. Always validate input files before submission.

## Standard MD Workflow (21 Steps)

This workflow is based on verified scripts in `model/`. It follows a strict file chain: each step's `-r` (restart) output becomes the next step's `-c` (input coordinates).

### Phase 1: Energy Minimization (4 Steps)

Gradually release positional restraints: 10.0 -> 5.0 -> 1.0 -> 0 (free).

**Step 1 — Heavy restraint (restraint_wt=10.0)**

```
Minimization step 1 - heavy restraint
&cntrl
  imin = 1, maxcyc = 50000, ncyc = 20000,
  ntb = 1, igb = 0, cut = 10.0,
  ntr = 1, restraint_wt = 10.0,
  restraintmask = '!:WAT,Cl-,K+,Na+ & !@H=',
  ntpr = 100, ntwx = 100,
/
```

**Step 2 — Medium restraint (restraint_wt=5.0)**

```
Minimization step 2 - medium restraint
&cntrl
  imin = 1, maxcyc = 50000, ncyc = 20000,
  ntb = 1, igb = 0, cut = 10.0,
  ntr = 1, restraint_wt = 5.0,
  restraintmask = '!:WAT,Cl-,K+,Na+ & !@H=',
  ntpr = 100, ntwx = 100,
/
```

**Step 3 — Light restraint (restraint_wt=1.0)**

```
Minimization step 3 - light restraint
&cntrl
  imin = 1, maxcyc = 50000, ncyc = 20000,
  ntb = 1, igb = 0, cut = 10.0,
  ntr = 1, restraint_wt = 1.0,
  restraintmask = '!:WAT,Cl-,K+,Na+ & !@H=',
  ntpr = 100, ntwx = 100,
/
```

**Step 4 — Free minimization (ntr=0)**

```
Minimization step 4 - free
&cntrl
  imin = 1, maxcyc = 50000, ncyc = 20000,
  ntb = 1, igb = 0, cut = 10.0,
  ntr = 0,
  ntpr = 100, ntwx = 100,
/
```

### Phase 2: Heating NVT 0 to 310K (10 Steps, Each 20ps)

Linear temperature ramp. Each step increases by 31K. All steps use NVT (`ntb=1`, `ntp=0`).

- `nstlim = 10000` (10000 steps x 2fs = 20ps per step)
- `irest = 0, ntx = 1` for step 5 (cold start); `irest = 1, ntx = 5` for steps 6-14
- `ntt = 3` (Langevin thermostat), `gamma_ln = 2.0`, `tautp = 2.0`
- SHAKE on (`ntc = 2, ntf = 2, tol = 0.000001`)

**Step 5 — 0K to 31K (cold start)**

```
Heating 0 to 31K
&cntrl
  imin = 0, irest = 0, ntx = 1,
  nstlim = 10000, dt = 0.002,
  ntt = 3, gamma_ln = 2.0, tautp = 2.0,
  tempi = 0.0, temp0 = 31.0, ig = -1,
  ntb = 1, ntp = 0, cut = 10.0,
  ntc = 2, ntf = 2, tol = 0.000001,
  iwrap = 1, igb = 0,
  ntpr = 100, ntwx = 100,
/
```

**Step 6 — 31K to 62K**

```
Heating 31 to 62K
&cntrl
  imin = 0, irest = 1, ntx = 5,
  nstlim = 10000, dt = 0.002,
  ntt = 3, gamma_ln = 2.0, tautp = 2.0,
  tempi = 31.0, temp0 = 62.0, ig = -1,
  ntb = 1, ntp = 0, cut = 10.0,
  ntc = 2, ntf = 2, tol = 0.000001,
  iwrap = 1, igb = 0,
  ntpr = 100, ntwx = 100,
/
```

**Step 7 — 62K to 93K**

```
Heating 62 to 93K
&cntrl
  imin = 0, irest = 1, ntx = 5,
  nstlim = 10000, dt = 0.002,
  ntt = 3, gamma_ln = 2.0, tautp = 2.0,
  tempi = 62.0, temp0 = 93.0, ig = -1,
  ntb = 1, ntp = 0, cut = 10.0,
  ntc = 2, ntf = 2, tol = 0.000001,
  iwrap = 1, igb = 0,
  ntpr = 100, ntwx = 100,
/
```

**Step 8 — 93K to 124K**

```
Heating 93 to 124K
&cntrl
  imin = 0, irest = 1, ntx = 5,
  nstlim = 10000, dt = 0.002,
  ntt = 3, gamma_ln = 2.0, tautp = 2.0,
  tempi = 93.0, temp0 = 124.0, ig = -1,
  ntb = 1, ntp = 0, cut = 10.0,
  ntc = 2, ntf = 2, tol = 0.000001,
  iwrap = 1, igb = 0,
  ntpr = 100, ntwx = 100,
/
```

**Step 9 — 124K to 155K**

```
Heating 124 to 155K
&cntrl
  imin = 0, irest = 1, ntx = 5,
  nstlim = 10000, dt = 0.002,
  ntt = 3, gamma_ln = 2.0, tautp = 2.0,
  tempi = 124.0, temp0 = 155.0, ig = -1,
  ntb = 1, ntp = 0, cut = 10.0,
  ntc = 2, ntf = 2, tol = 0.000001,
  iwrap = 1, igb = 0,
  ntpr = 100, ntwx = 100,
/
```

**Step 10 — 155K to 186K**

```
Heating 155 to 186K
&cntrl
  imin = 0, irest = 1, ntx = 5,
  nstlim = 10000, dt = 0.002,
  ntt = 3, gamma_ln = 2.0, tautp = 2.0,
  tempi = 155.0, temp0 = 186.0, ig = -1,
  ntb = 1, ntp = 0, cut = 10.0,
  ntc = 2, ntf = 2, tol = 0.000001,
  iwrap = 1, igb = 0,
  ntpr = 100, ntwx = 100,
/
```

**Step 11 — 186K to 217K**

```
Heating 186 to 217K
&cntrl
  imin = 0, irest = 1, ntx = 5,
  nstlim = 10000, dt = 0.002,
  ntt = 3, gamma_ln = 2.0, tautp = 2.0,
  tempi = 186.0, temp0 = 217.0, ig = -1,
  ntb = 1, ntp = 0, cut = 10.0,
  ntc = 2, ntf = 2, tol = 0.000001,
  iwrap = 1, igb = 0,
  ntpr = 100, ntwx = 100,
/
```

**Step 12 — 217K to 248K**

```
Heating 217 to 248K
&cntrl
  imin = 0, irest = 1, ntx = 5,
  nstlim = 10000, dt = 0.002,
  ntt = 3, gamma_ln = 2.0, tautp = 2.0,
  tempi = 217.0, temp0 = 248.0, ig = -1,
  ntb = 1, ntp = 0, cut = 10.0,
  ntc = 2, ntf = 2, tol = 0.000001,
  iwrap = 1, igb = 0,
  ntpr = 100, ntwx = 100,
/
```

**Step 13 — 248K to 279K**

```
Heating 248 to 279K
&cntrl
  imin = 0, irest = 1, ntx = 5,
  nstlim = 10000, dt = 0.002,
  ntt = 3, gamma_ln = 2.0, tautp = 2.0,
  tempi = 248.0, temp0 = 279.0, ig = -1,
  ntb = 1, ntp = 0, cut = 10.0,
  ntc = 2, ntf = 2, tol = 0.000001,
  iwrap = 1, igb = 0,
  ntpr = 100, ntwx = 100,
/
```

**Step 14 — 279K to 310K (final heating)**

```
Heating 279 to 310K
&cntrl
  imin = 0, irest = 1, ntx = 5,
  nstlim = 10000, dt = 0.002,
  ntt = 3, gamma_ln = 2.0, tautp = 2.0,
  tempi = 279.0, temp0 = 310.0, ig = -1,
  ntb = 1, ntp = 0, cut = 10.0,
  ntc = 2, ntf = 2, tol = 0.000001,
  iwrap = 1, igb = 0,
  ntpr = 100, ntwx = 100,
/
```

### Phase 3: Equilibration NPT (4 Steps)

Switch to NPT (`ntb=2`, `ntp=1`) for pressure coupling. All steps use `irest=1, ntx=5` (restart from previous). Restraints decrease: 2.0 -> 0.5 -> 0.25 -> 0.05.

**Step 14equ — NPT equilibration, restraint_wt=2.0 (10ns)**

```
Equilibration NPT step 1
&cntrl
  imin = 0, irest = 1, ntx = 5,
  nstlim = 5000000, dt = 0.002,
  ntt = 3, gamma_ln = 2.0, temp0 = 310.0, ig = -1,
  ntb = 2, ntp = 1, taup = 2.0, cut = 10.0,
  ntc = 2, ntf = 2,
  ntr = 1, restraint_wt = 2.0,
  restraintmask = '!:WAT,Cl-,K+,Na+ & !@H=',
  iwrap = 1, ntpr = 500, ntwx = 500,
/
```

**Step 15equ — NPT equilibration, restraint_wt=0.5 (2ns)**

```
Equilibration NPT step 2
&cntrl
  imin = 0, irest = 1, ntx = 5,
  nstlim = 1000000, dt = 0.002,
  ntt = 3, gamma_ln = 2.0, temp0 = 310.0, ig = -1,
  ntb = 2, ntp = 1, taup = 2.0, cut = 10.0,
  ntc = 2, ntf = 2,
  ntr = 1, restraint_wt = 0.5,
  restraintmask = '!:WAT,Cl-,K+,Na+ & !@H=',
  iwrap = 1, ntpr = 500, ntwx = 500,
/
```

**Step 16equ — NPT equilibration, restraint_wt=0.25 (2ns)**

```
Equilibration NPT step 3
&cntrl
  imin = 0, irest = 1, ntx = 5,
  nstlim = 1000000, dt = 0.002,
  ntt = 3, gamma_ln = 2.0, temp0 = 310.0, ig = -1,
  ntb = 2, ntp = 1, taup = 2.0, cut = 12.0,
  ntc = 2, ntf = 2,
  ntr = 1, restraint_wt = 0.25,
  restraintmask = '!:WAT,Cl-,K+,Na+ & !@H=',
  iwrap = 1, ntpr = 500, ntwx = 500,
/
```

**Step 17equ — NPT equilibration, restraint_wt=0.05 (2ns)**

```
Equilibration NPT step 4
&cntrl
  imin = 0, irest = 1, ntx = 5,
  nstlim = 1000000, dt = 0.002,
  ntt = 3, gamma_ln = 2.0, temp0 = 310.0, ig = -1,
  ntb = 2, ntp = 1, taup = 2.0, cut = 12.0,
  ntc = 2, ntf = 2,
  ntr = 1, restraint_wt = 0.05,
  restraintmask = '!:WAT,Cl-,K+,Na+ & !@H=',
  iwrap = 1, ntpr = 500, ntwx = 500,
/
```

### Phase 4: Production MD (NPT, No Restraints)

Standard 250ns production run at 310K, 1 atm, cutoff 12A.

```
Production MD 250ns
&cntrl
  imin = 0, irest = 1, ntx = 5,
  nstlim = 125000000, dt = 0.002,
  ntt = 3, gamma_ln = 2.0, tautp = 2.0,
  temp0 = 310.0, tempi = 310.0, ig = -1,
  ntb = 2, ntp = 1, barostat = 2,
  pres0 = 1.0, taup = 2.0,
  ntc = 2, ntf = 2, cut = 12.0,
  iwrap = 1, ioutfm = 1, igb = 0, nmropt = 0,
  ntpr = 125000, ntwx = 125000, ntwr = 12500000,
/
```

Output frequency:
- `ntpr = 125000` — energy output every 250ps
- `ntwx = 125000` — trajectory frame every 250ps
- `ntwr = 12500000` — restart checkpoint every 25ns

**Segment strategy for long runs:** Split into 250ns segments. Each segment is identical except for input/output file names. The first segment uses the equilibration restart as input; each subsequent segment uses the previous segment's restart output. This provides natural checkpoint/restart capability.

## File Chain (CRITICAL)

The file chain connects all 21 steps:

```
tleap -> complex_solv.prmtop + complex_solv.inpcrd
  |
Step 1: -c complex_solv.inpcrd  -r min1.rst
Step 2: -c min1.rst             -r min2.rst
Step 3: -c min2.rst             -r min3.rst
Step 4: -c min3.rst             -r min4.rst
Step 5: -c min4.rst             -r heat1.rst   (cold start, irest=0)
Step 6: -c heat1.rst            -r heat2.rst
  ...
Step 14: -c heat9.rst           -r heat10.rst
Step 14equ: -c heat10.rst       -r equ1.rst
Step 15equ: -c equ1.rst         -r equ2.rst
Step 16equ: -c equ2.rst         -r equ3.rst
Step 17equ: -c equ3.rst         -r equ4.rst
Production: -c equ4.rst         -r prod.rst
```

Each step's `-r` (restart) output becomes the next step's `-c` (input coordinates). The topology file (`-p`) remains unchanged throughout.

## Parameters

| Parameter | Type | Description |
|---|---|---|
| `input_file` | str | Path to Fortran namelist input config (`.in`) |
| `output_file` | str | Path to MD output log (`.out`) |
| `topology_file` | str | Path to prmtop file |
| `coordinate_file` | str | Path to input coordinates (inpcrd or restart) |
| `restart_file` | str | Path for restart output |
| `trajectory_file` | str | Path for trajectory output (`.nc` or `.mdcrd`) |
| `reference_file` | str | Path to reference coordinates for position restraints |
| `mdinfo_file` | str | Path for mdinfo output |
| `gpu_id` | int | GPU device ID 0-8 (auto-selects least loaded if not specified) |
| `timeout` | int | Timeout in seconds (default 86400) |

## Common Errors

| Error | Cause | Fix |
|---|---|---|
| "Cannot match namelist object name" | Non-ASCII characters in input config | Remove all non-ASCII characters; input must be pure ASCII |
| SHAKE convergence failure | System too hot or bad contacts | Run longer minimization; reduce initial temperature ramp rate |
| NaN energy values | Bad atomic contacts / overlapping atoms | Use stronger restraints; redo minimization from step 1 |
| "prmtop not found" | Topology file missing | Run tleap first to generate prmtop |
| GPU out of memory (OOM) | System too large for single GPU | Reduce system size; use MPI pmemd.CUDA; reduce cutoff |
| "Box too small" | Solvent box smaller than 3x cutoff | Re-solvate with larger buffer in tleap; minimum box size must be >= 3x cutoff |
