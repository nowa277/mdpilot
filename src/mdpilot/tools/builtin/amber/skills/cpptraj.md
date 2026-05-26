---
name: cpptraj
description: "Trajectory analysis: RMSD, RMSF, distances, angles, dihedrals, hydrogen bonds, clustering, PCA. Accepts multiline command script."
triggers: [cpptraj, RMSD, RMSF, trajectory analysis, distance, hbond, cluster, PCA]
depends_on: [pmemd_cuda]
node: lab03
exec_method: local_subprocess
exec_path: $AMBERHOME/bin/cpptraj
references: [cpptraj-guide]
---

# cpptraj — Trajectory Analysis

## When to Use

Use cpptraj **AFTER** MD simulation has produced trajectory files (`.nc` or `.mdcrd`). cpptraj performs all standard trajectory analyses: RMSD, RMSF, distances, angles, dihedrals, hydrogen bonds, clustering, PCA, and more.

## Execution Environment

- **Node:** lab03 (local subprocess)
- **Exec path:** `$AMBERHOME/bin/cpptraj`
- **Timeout:** default 600s (10 minutes)
- **Input:** Multiline command script or individual commands

## Workflow Position

```
pmemd_cuda / sander (produce trajectory)
    |
    v
cpptraj (analyze trajectory)
```

## Command Templates

### Basic RMSD (backbone, relative to first frame)

```
trajin md.nc
rms first :1-256&!@H=
run
```

### RMSF (per-atom fluctuation)

```
trajin md.nc
atomicfluct out rmsf.dat :1-256&!@H= byatom
run
```

### Distance (CA-CA distance over time)

```
trajin md.nc
distance d1 :1@CA :256@CA out dist.dat
run
```

### Angle

```
trajin md.nc
angle a1 :1@CA :128@CA :256@CA out angle.dat
run
```

### Dihedral

```
trajin md.nc
dihedral d1 :2@N :2@CA :2@C :3@N out dihed.dat
run
```

### Hydrogen Bonds

```
trajin md.nc
hbond out hbond.dat :1-256 solventdonor :WAT solventacceptor :WAT
run
```

### Clustering (DBSCAN-like, epsilon 2.0)

```
trajin md.nc
cluster out cluster.dat summary summary.dat repout rep repfmt pdb epsilon 2.0
run
```

### PCA (Principal Component Analysis)

```
trajin md.nc
rms first
createcrd CRD1
run
crdaction CRD1 matrix covar name mymat :1-256&!@H=
crdaction CRD1 diagmatrix mymat vecs 5 name myevecs
crdaction CRD1 projection myevecs out pca.dat :1-256&!@H=
```

This produces:
- `pca.dat` — projection of each frame onto the first 5 eigenvectors
- Eigenvector data for mode visualization

## Post-Processing Workflow (Clean Trajectory for Visualization)

Removes water and ions, autoimages, and aligns — producing a compact trajectory for visualization in VMD/PyMOL.

```
parm complex_solv.prmtop
trajin md.nc
autoimage
rms first :1-256&!@H=
strip :WAT,Cl-,K+,Na+
trajout clean.nc netcdf
parmwrite out clean.prmtop
run
```

This produces:
- `clean.nc` — stripped and aligned trajectory
- `clean.prmtop` — matching stripped topology

## Key Commands Reference

| Command | Description |
|---|---|
| `parm top.prmtop` | Load topology |
| `trajin traj.nc [start] [stop] [offset]` | Load trajectory (optional stride) |
| `trajout file.nc netcdf` | Write output trajectory |
| `rms [reference] mask` | RMSD alignment |
| `atomicfluct out file.dat mask byatom` | RMSF calculation |
| `distance name mask1 mask2 out file` | Distance measurement |
| `angle name mask1 mask2 mask3 out file` | Angle measurement |
| `dihedral name m1 m2 m3 m4 out file` | Dihedral measurement |
| `hbond out file mask` | Hydrogen bond analysis |
| `cluster ...` | Clustering analysis |
| `strip mask` | Remove atoms from trajectory |
| `autoimage` | Center and image periodic boundary |
| `createcrd name` | Store coordinates for matrix analysis |
| `parmwrite out file.prmtop` | Write stripped topology |
| `run` | Execute queued commands |

## Parameters

| Parameter | Type | Description |
|---|---|---|
| `input_script` | str | Multiline cpptraj command script |
| `workdir` | str | Working directory containing trajectory and topology files |
| `timeout` | int | Timeout in seconds (default 600) |

## Common Errors

| Error | Cause | Fix |
|---|---|---|
| "No trajectories loaded" | `trajin` path is wrong or file missing | Check trajectory file path and existence |
| "Frame too large / memory error" | Trajectory too large for memory | Strip water first; use stride in trajin (`trajin md.nc 1 last 10`) |
| "Parm file not found" | Topology file path incorrect | Verify prmtop path; use `parm` command explicitly |
| "Mask selects 0 atoms" | Atom selection syntax error | Check Amber mask syntax; verify residue/atom numbering |
