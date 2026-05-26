---
name: reduce
description: "Add/remove hydrogens from PDB files. Build mode adds H atoms and optimizes H-bond networks (HIS protonation). Trim mode removes all H atoms."
triggers: [reduce, hydrogen, protonation, add hydrogen, remove hydrogen, HIS]
depends_on: []
node: lab03
exec_method: local_subprocess
exec_path: $AMBERHOME/bin/reduce
references: []
---

# reduce — Hydrogen Addition and Removal

## When to Use

Use reduce to optimize the hydrogen bonding network before MD simulations, or to remove hydrogens for structural comparison. reduce is particularly important for:

- **Adding hydrogen atoms** to structures that lack them (e.g., X-ray crystal structures)
- **Optimizing H-bond networks** — automatically determines the best orientation for Asn, Gln, and His side chains
- **Determining HIS protonation state** — assigns HID (delta-protonated), HIE (epsilon-protonated), or HIP (doubly protonated) based on local H-bond environment
- **Removing all hydrogen atoms** — for comparison with H-free structures

Note: `pdb4amber --reduce` calls reduce internally. Use the standalone reduce tool when you need fine-grained control over H-bond optimization.

## Execution Environment

- **Node:** lab03 (local subprocess)
- **Exec path:** `$AMBERHOME/bin/reduce`
- **Timeout:** default 120s (2 minutes)
- **No dependencies:** standalone tool

## Modes

| Mode | Description | Output Naming |
|---|---|---|
| `build` | Add hydrogen atoms and optimize H-bond network (default) | `{stem}_H.pdb` |
| `trim` | Remove all hydrogen atoms from the structure | `{stem}_noH.pdb` |

## HIS Protonation

In `build` mode with `flip=True` (default), reduce analyzes the local hydrogen bonding environment around each histidine residue and assigns the optimal protonation state:

- **HID** — proton on ND1 (delta nitrogen)
- **HIE** — proton on NE2 (epsilon nitrogen)
- **HIP** — protons on both ND1 and NE2 (positively charged)

This is critical for MD accuracy because incorrect HIS protonation can distort active site geometry and hydrogen bonding patterns.

## Parameters

| Parameter | Type | Description |
|---|---|---|
| `input_pdb` | str | Path to input PDB file |
| `output` | str | Path to output PDB file (default: `{stem}_H.pdb` or `{stem}_noH.pdb`) |
| `mode` | str | `build` (add H, default) or `trim` (remove H) |
| `flip` | bool | Optimize ASN/GLN/HIS sidechain orientations based on H-bond network (default: True) |
| `quiet` | bool | Suppress informational output (default: False) |
| `workdir` | str | Working directory |
| `timeout` | int | Timeout in seconds (default 120) |

## Example Commands

### Build mode — add hydrogens with H-bond optimization

```bash
reduce -BUILD -flip input.pdb > input_H.pdb
```

### Build mode — add hydrogens without flipping

```bash
reduce -BUILD -NOFLIP input.pdb > input_H.pdb
```

### Trim mode — remove all hydrogens

```bash
reduce -Trim input.pdb > input_noH.pdb
```

## Common Errors

| Error | Cause | Fix |
|---|---|---|
| "reduce not found" | `AMBERHOME` not set | Set AMBERHOME environment variable to Amber installation root |
| Wrong atom count after build | Duplicate atoms or alternate locations in input PDB | Remove alternate locations; run pdb4amber first to clean structure |
| "Invalid PDB format" | Malformed PDB file | Check ATOM/HETATM record formatting; ensure proper column alignment |
| Unexpected HIS protonation | H-bond network analysis gives non-intuitive result | Inspect local environment; consider manual assignment if reduce's choice conflicts with known biochemistry |
| "Unable to open DB file" | Reduce data files missing | Check `$AMBERHOME/dat/reduce_wwPDB_het_dict.txt` exists |
