---
name: pdb4amber
description: "PDB file preparation for AMBER: renumber residues, add hydrogens via reduce, handle disulfide bonds, generate cleaned output."
triggers: [pdb4amber, PDB preparation, clean PDB, prepare structure]
depends_on: []
node: lab03
exec_method: local_subprocess
exec_path: $AMBERHOME/bin/pdb4amber
references: [pdb4amber-guide]
---

# pdb4amber — PDB File Preparation for AMBER

## When to Use

Use pdb4amber as the **FIRST step** in any AMBER workflow, before tleap. Always run it on raw PDB files downloaded from RCSB PDB or any other source. pdb4amber cleans and prepares the structure so that downstream tools (tleap, pmemd.cuda) can process it correctly.

## Execution Environment

- **Node:** lab03 (local subprocess)
- **Exec path:** `$AMBERHOME/bin/pdb4amber`
- **Timeout:** default 120s (2 minutes)
- **No dependencies:** pdb4amber does not require any prior AMBER tools

## Workflow Position

```
Raw PDB file (from RCSB, AlphaFold, etc.)
    |
    v
pdb4amber (clean + add H)
    |
    v
antechamber (if ligands)
    |
    v
tleap (build prmtop + inpcrd)
    |
    v
pmemd_cuda / sander (run MD)
    |
    v
cpptraj (analyze trajectory)
```

## Parameters

| Parameter | Type | Description |
|---|---|---|
| `input_pdb` | str | Path to input PDB file |
| `output` | str | Output PDB file path (default: `{stem}_clean.pdb`) |
| `reduce` | bool | Add H atoms via reduce tool (default: True) |
| `add_missing_atoms` | bool | Add missing heavy atoms for incomplete structures |
| `no_conect` | bool | Remove CONECT records from output |
| `no_remarks` | bool | Remove REMARK records from output |
| `strip_headers` | bool | Remove header records from output |
| `workdir` | str | Working directory |
| `timeout` | int | Timeout in seconds (default 120) |

## Key Flags

| Flag | Description |
|---|---|
| `--reduce` | Run reduce to add hydrogen atoms and optimize H-bond network (default enabled) |
| `--add-missing-atoms` | Add missing heavy atoms for residues with incomplete side chains |
| `--noter` | Remove TER lines from output (sometimes causes issues in tleap) |
| `--no-conect` | Remove CONECT records |
| `--no-rehash` | Do not renumber residues |

## Example Usage

Basic cleaning with hydrogen addition:

```bash
pdb4amber -i raw.pdb -o clean.pdb --reduce
```

Full preparation for a structure with missing atoms:

```bash
pdb4amber -i raw.pdb -o clean.pdb --reduce --add-missing-atoms
```

Strip all non-essential records:

```bash
pdb4amber -i raw.pdb -o clean.pdb --reduce --no-conect --no-rehash
```

## What pdb4amber Does

1. **Renumbers residues** sequentially (fixes insertion codes, chain breaks)
2. **Adds hydrogen atoms** via the reduce tool (when `--reduce` is enabled)
3. **Detects disulfide bonds** from S-S distance criteria
4. **Removes alternate locations** (keeps first occupancy)
5. **Generates clean output** compatible with tleap

## Common Errors

| Error | Cause | Fix |
|---|---|---|
| "reduce not found" | `AMBERHOME` environment variable not set | Set `AMBERHOME` to Amber installation root |
| Residue name mismatch after pdb4amber | Non-standard residue names in source PDB | Check PDB header; may need manual residue renaming before pdb4amber |
| "No atoms in structure" | Empty or corrupted PDB file | Verify PDB file is not empty; check for ATOM/HETATM records |
| Multiple MODEL entries | NMR ensemble structure | Select a single model before running pdb4amber |
| "Duplicate atom names" | PDB has naming conflicts | pdb4amber usually resolves this; if not, manually inspect the PDB |
