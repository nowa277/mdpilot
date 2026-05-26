---
name: tleap
description: "Build AMBER topology (prmtop) and coordinate (inpcrd) files. System preparation: load force fields, add solvent, add ions, save AmberParm."
triggers: [tleap, topology, prmtop, inpcrd, solvate, system preparation, force field]
depends_on: [pdb4amber]
node: lab03
exec_method: local_subprocess
exec_path: $AMBERHOME/bin/tleap
references: [tleap-guide]
---

# tleap — AMBER System Preparation

## When to Use

Use tleap **BEFORE** any MD simulation (pmemd.cuda or sander) and **AFTER** pdb4amber has cleaned the input PDB. tleap creates the two essential files every AMBER simulation needs:

- `*.prmtop` — topology file (force field parameters, atom types, bonds, angles, etc.)
- `*.inpcrd` — initial coordinates file

## Execution Environment

- **Node:** lab03 (local subprocess)
- **Exec path:** `$AMBERHOME/bin/tleap`
- **Timeout:** default 300s (5 minutes)
- **Input:** tleap script file (`.leap` or inline commands)

## Workflow Position

```
pdb4amber (clean PDB)
    |
    v
antechamber (if ligands exist → .mol2 + .frcmod)
    |
    v
tleap (build prmtop + inpcrd)
    |
    v
pmemd_cuda / sander (run MD)
```

## Script Syntax Templates

### Protein-Only System (Simplest Case)

```
source leaprc.protein.ff14SB
mol = loadPDB complex_clean.pdb
check mol
saveAmberParm mol complex.prmtop complex.inpcrd
quit
```

### Protein + Ligand System

```
source leaprc.protein.ff14SB
source leaprc.gaff2
loadamberprep lig.prepc
loadamberparams lig.frcmod
mol = loadPDB complex_clean.pdb
check mol
saveAmberParm mol complex.prmtop complex.inpcrd
quit
```

### Full System: Protein + Ligand + Solvation + Ions

```
source leaprc.protein.ff14SB
source leaprc.gaff2
loadamberprep lig.prepc
loadamberparams lig.frcmod
mol = loadPDB complex_clean.pdb
check mol
solvateOct mol TIP3PBOX 10.0
addIons mol Cl- 0
addIons2 mol Na+ 0
saveAmberParm mol complex_solv.prmtop complex_solv.inpcrd
quit
```

### Key Commands Reference

| Command | Description |
|---|---|
| `source leaprc.protein.ff14SB` | Load ff14SB protein force field |
| `source leaprc.protein.ff19SB` | Load ff19SB protein force field (pairs with OPC water) |
| `source leaprc.gaff2` | Load GAFF2 small molecule force field |
| `loadamberprep file.prepc` | Load residue definition (from antechamber) |
| `loadamberparams file.frcmod` | Load missing force field parameters (from parmchk2) |
| `mol = loadPDB file.pdb` | Load PDB structure into variable `mol` |
| `check mol` | Validate structure (missing atoms, weird geometries) |
| `solvateOct mol TIP3PBOX 10.0` | Solvate in TIP3P water, octahedral box, 10A buffer |
| `solvateBox mol TIP3PBOX 10.0` | Solvate in TIP3P water, rectangular box, 10A buffer |
| `addIons mol Cl- 0` | Add Cl- ions to neutralize (0 = auto-calculate) |
| `addIons2 mol Na+ 0` | Add Na+ ions (addIons2 avoids replacing existing ions) |
| `saveAmberParm mol top.prm coor.inp` | Save topology and coordinates |
| `quit` | Exit tleap |

## Force Field Selection

| Force Field | Use Case |
|---|---|
| `ff14SB` | Standard proteins (default, most tested) |
| `ff19SB` | Newer protein FF, pairs with OPC water model |
| `ff14SB + gaff2` | Protein + ligand systems |
| `ff19SB + gaff2` | Protein + ligand with OPC water |

## Parameters

| Parameter | Type | Description |
|---|---|---|
| `input_script` | str | Multiline tleap command script |
| `workdir` | str | Working directory where PDB and output files are located |
| `timeout` | int | Timeout in seconds (default 300) |

## Common Errors

| Error | Cause | Fix |
|---|---|---|
| "Could not find residue template" | PDB residue names do not match force field | Check PDB residue names; run pdb4amber first; for ligands, run antechamber to generate `.prepc` |
| "FATAL: Atom type missing" | Ligand atom types not in force field | Run antechamber + parmchk2 first to generate `.frcmod` with missing parameters |
| "Total charge not zero" | System net charge is non-zero after ion addition | Adjust ion count; check ligand charge; use `addIons2` for additional ions beyond neutralization |
| "Warning: There is a duplicate bond" | Duplicate atom entries in PDB | Run pdb4amber to clean structure |
| "check mol" reports missing atoms | Incomplete side chains or backbone | Use `--add-missing-atoms` flag in pdb4amber |
