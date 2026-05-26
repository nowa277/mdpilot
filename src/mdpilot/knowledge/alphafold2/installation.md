# AlphaFold2 Installation Guide

## Installation Methods

### 1. Google Colab (Recommended for Testing)

**Advantages:**
- No local installation required
- Free GPU access
- Pre-configured environment
- Ideal for testing and small-scale predictions

**Limitations:**
- Session time limits
- Cannot use full databases
- Internet dependency

**Usage:**
```
1. Visit AlphaFold Colab notebook
2. Upload FASTA sequence
3. Run cells sequentially
4. Download PDB results
```

### 2. Docker Installation (Recommended for Production)

**Advantages:**
- Isolated environment
- Reproducible setup
- Easier dependency management
- Works on any Docker-compatible system

**Prerequisites:**
- Docker 19.03+
- NVIDIA Docker runtime
- NVIDIA GPU with CUDA support

**Installation Steps:**

```bash
# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker

# Pull AlphaFold Docker image
docker pull ghcr.io/deepmind/alphafold:latest

# Download genetic databases (required)
# Full databases: ~2.2TB
# Reduced databases: ~500GB (reduced_dbs option)
bash scripts/download_all_data.sh /path/to/databases
```

**Running Predictions:**

```bash
docker run --gpus all \
  -v /path/to/databases:/data \
  -v /path/to/input:/input \
  -v /path/to/output:/output \
  ghcr.io/deepmind/alphafold:latest \
  --fasta_paths=/input/sequence.fasta \
  --max_template_date=2023-01-01 \
  --data_dir=/data \
  --output_dir=/output
```

### 3. Local Installation (Advanced)

**Prerequisites:**
- Python 3.8+
- CUDA 11.1+
- cuDNN 8.0.4+
- GCC 9.3+

**Installation:**

```bash
# Clone repository
git clone https://github.com/deepmind/alphafold.git
cd alphafold

# Create conda environment
conda create -n alphafold python=3.8
conda activate alphafold

# Install dependencies
pip install -r requirements.txt

# Install JAX with GPU support
pip install --upgrade "jax[cuda11_cudnn82]" -f \
  https://storage.googleapis.com/jax-releases/jax_cuda_releases.html

# Download databases
bash scripts/download_all_data.sh /path/to/databases

# Download model parameters
bash scripts/download_alphafold_params.sh /path/to/params
```

### 4. ColabFold (Lightweight Alternative)

**Advantages:**
- Faster than AlphaFold2 (uses MMseqs2 for MSA)
- Smaller database requirements
- Easier local installation
- Compatible with AlphaFold2 models

**Installation:**

```bash
# Install via pip
pip install colabfold[alphafold]

# Download databases (much smaller)
colabfold_search --download-database /path/to/colabfold_db
```

**Usage:**

```bash
colabfold_batch input.fasta output_dir/
```

## Database Options

### Full Databases (~2.2TB)
- BFD (Big Fantastic Database)
- MGnify
- PDB70
- UniRef90
- UniProt

**Best for:** Maximum accuracy, research applications

### Reduced Databases (~500GB)
- Small BFD
- MGnify (reduced)
- PDB70
- UniRef90 (reduced)

**Best for:** Production systems with storage constraints

### ColabFold Databases (~100GB)
- MMseqs2 databases
- Faster search, slightly lower accuracy

**Best for:** High-throughput applications

## Troubleshooting

### GPU Memory Issues

```bash
# Reduce model size
--model_preset=monomer_ptm  # Instead of monomer

# Use reduced precision
--use_gpu_relax=false
```

### Database Download Failures

```bash
# Download databases individually
bash scripts/download_bfd.sh /path/to/databases
bash scripts/download_mgnify.sh /path/to/databases
bash scripts/download_pdb70.sh /path/to/databases
```

### CUDA Errors

```bash
# Verify CUDA installation
nvidia-smi

# Check JAX GPU detection
python -c "import jax; print(jax.devices())"
```

## Performance Optimization

### Hardware Recommendations

| Component | Minimum | Recommended | Optimal |
|-----------|---------|-------------|---------|
| GPU VRAM | 8GB | 16GB | 24GB+ |
| System RAM | 32GB | 64GB | 128GB+ |
| Storage | 500GB | 2.5TB | 5TB+ |
| CPU Cores | 8 | 16 | 32+ |

### Speed Optimization

1. **Use ColabFold**: 3-5x faster MSA generation
2. **Reduce MSA depth**: `--max_msa_clusters=128` (default: 512)
3. **Skip relaxation**: `--use_gpu_relax=false` for faster results
4. **Use reduced databases**: Trade accuracy for speed
5. **Batch processing**: Process multiple sequences in parallel

## Integration with MDPilot

### Recommended Setup for MDPilot

```python
# Use Docker for isolation and reproducibility
# Mount MDPilot workspace for seamless integration

docker run --gpus all \
  -v /path/to/mdpilot/data:/data \
  -v /path/to/mdpilot/structures:/output \
  ghcr.io/deepmind/alphafold:latest \
  --fasta_paths=/data/sequences.fasta \
  --output_dir=/output
```

### Python API Integration

See [api_reference.md](api_reference.md) for programmatic access patterns.
