---
name: alphafold2_predict
description: "Protein 3D structure prediction with AlphaFold2. Returns PDB + pLDDT confidence scores. Runs on lab02 via SSH+Celery."
triggers:
  - alphafold2
  - structure prediction
  - protein structure
  - AlphaFold
  - pLDDT
depends_on: []
node: lab02
exec_method: ssh_celery
exec_path: SSH+Celery (lab02:24122)
references:
  - alphafold2-guide
---

# alphafold2_predict

## When to use

- Protein structure prediction when no experimental structure is available.
- Returns: 3D coordinates (PDB format) + per-residue confidence scores (pLDDT, 0-100).
- Alternative: NMR or X-ray crystallography if experimental data is available.

## Node and Execution

- **Runs on:** lab02 (SSH + Celery, NOT local)
- **SSH:** host=127.0.0.1, port=24122, username=zhao, key=~/.ssh/id_ed25519
- **Celery:** broker=redis://localhost:6379/2, backend=redis://localhost:6379/3, task_timeout=14400s, poll_interval=5s
- **Work dir:** /home/2-BB/changeshengjie/project/mdpilot
- **Conda env:** af2_py310
- **GPU:** lab02 has 9x NVIDIA TITAN V (12GB VRAM each)

## Input Parameters

- `sequence` (required): single-letter amino acid code, max practical limit ~1000aa
- `job_name` (optional, default "prediction"): output file prefix
- `db_preset` (optional, default "full_dbs"):
  - `full_dbs`: full accuracy, 30min-2hr for 100aa, always available
  - `reduced_dbs`: fast mode, 5-10min for 100aa, requires small_bfd database
  - `casp14`: competition mode, 30-40min for 100aa

## Return Values

- `success`: bool
- `best_model`: path to best-ranked PDB file
- `avg_plddt`: average confidence score (0-100, >70 = good, >90 = high confidence)
- `output_dir`: output directory path
- `sequence_length`: int
- `num_models`: int (typically 5)
- `db_preset`: database preset used

## Typical Timing

- 100aa: ~30min (full_dbs), ~8min (reduced_dbs)
- 300aa: ~1hr (full_dbs)
- 800aa: ~2hr (full_dbs)

## Common Errors

- **Sequence too long (>1000aa):** AlphaFold2 may OOM. Split into domains.
- **GPU OOM:** System + sequence too large for 12GB VRAM. Try reduced_dbs.
- **Connection timeout:** SSH tunnel may have dropped. Check port 24122.
- **Celery task timeout:** For very long sequences, task_timeout may be too short (default 4hr).
