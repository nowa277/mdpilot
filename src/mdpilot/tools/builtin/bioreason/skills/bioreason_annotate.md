---
name: bioreason_annotate
description: "Protein function annotation with BioReason-Pro. Returns GO terms (MF, BP, CC) with confidence scores. Runs on lab06 via SSH+Celery."
triggers:
  - bioreason
  - GO annotation
  - function prediction
  - GO terms
  - gene ontology
depends_on: []
node: lab06
exec_method: ssh_celery
exec_path: SSH+Celery (lab06:24123)
references: []
---

# bioreason_annotate

## When to use

- Predict protein molecular function (MF), biological process (BP), cellular component (CC).
- Returns GO terms with confidence scores.
- Useful for: novel proteins, variant functional impact, protein characterization.

## Node and Execution

- **Runs on:** lab06 (SSH + Celery, NOT local)
- **SSH:** host=127.0.0.1, port=24123, username=zhao, key=~/.ssh/id_ed25519
- **Celery:** broker=redis://localhost:6379/0, backend=redis://localhost:6379/1, task_timeout=300s, poll_interval=2s
- **Work dir:** /home/6-FF/luo/BioReason-Pro
- **Conda env:** bioreason
- **GPU:** lab06 has 9x RTX 3090 (24GB VRAM)
- **Environment:** HF_HUB_OFFLINE=1, single GPU serial processing

## Input Parameters

- `sequence` (required): single-letter amino acid code
- `organism` (optional, default "Homo sapiens (Human)"): organism name in format "Species name (Common name)"
  - Examples: "Homo sapiens (Human)", "Mus musculus (Mouse)", "Escherichia coli (E. coli)"

## Return Values

- `go_terms`: dict with three categories:
  - `MF`: list of {id, name, score} (Molecular Function)
  - `BP`: list of {id, name, score} (Biological Process)
  - `CC`: list of {id, name, score} (Cellular Component)
- `metadata`: dict with organism, sequence_length, mode

## Typical Timing

- 10-60 seconds per sequence (very fast)
- Mostly I/O bound (model loading + inference)

## Common Errors

- **Empty sequence:** Validate input before calling.
- **Organism not found:** Check format is "Species name (Common name)".
- **Connection timeout:** SSH tunnel on port 24123 may have dropped.
- **HF_HUB_OFFLINE error:** HuggingFace cache may be corrupted on lab06.
