# AlphaFold2 Best Practices and Troubleshooting

## Best Practices

### 1. Sequence Preparation

**Optimal Sequence Length**
- **Sweet spot**: 50-1000 residues
- **Short sequences (<50 aa)**: May have insufficient evolutionary information
- **Long sequences (>2000 aa)**: Require significant memory and compute time
- **Very long (>3000 aa)**: Consider domain splitting

**Sequence Quality**
```python
def validate_sequence(sequence: str) -> dict:
    """Validate protein sequence for AlphaFold2."""
    valid_aa = set('ACDEFGHIKLMNPQRSTVWY')
    
    issues = []
    if len(sequence) < 30:
        issues.append("Sequence too short (< 30 residues)")
    if len(sequence) > 2500:
        issues.append("Very long sequence, consider domain splitting")
    
    invalid_chars = set(sequence.upper()) - valid_aa
    if invalid_chars:
        issues.append(f"Invalid characters: {invalid_chars}")
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'length': len(sequence)
    }
```

### 2. Model Selection

**Model Presets**

| Preset | Use Case | Speed | Accuracy |
|--------|----------|-------|----------|
| `monomer` | Single chain, no templates | Fast | Good |
| `monomer_ptm` | Single chain with pTM score | Medium | Better |
| `monomer_casp14` | CASP14 configuration | Slow | Best |
| `multimer` | Protein complexes | Slow | Complex-specific |

**Recommendation for MDPilot:**
- Use `monomer_ptm` for single proteins (provides pTM confidence metric)
- Use `multimer` for protein-protein interactions
- Use `monomer` for high-throughput screening

### 3. Quality Assessment

**Interpreting pLDDT Scores**

```python
def assess_structure_quality(plddt_scores: np.ndarray) -> dict:
    """Comprehensive quality assessment."""
    return {
        'mean_plddt': np.mean(plddt_scores),
        'median_plddt': np.median(plddt_scores),
        'very_high_conf': np.sum(plddt_scores > 90) / len(plddt_scores),
        'confident': np.sum(plddt_scores > 70) / len(plddt_scores),
        'low_conf': np.sum(plddt_scores < 50) / len(plddt_scores),
        'suitable_for_md': np.mean(plddt_scores) > 70
    }

def identify_flexible_regions(plddt_scores: np.ndarray, threshold: float = 70) -> list:
    """Identify potentially flexible/disordered regions."""
    low_conf_regions = []
    in_region = False
    start = 0
    
    for i, score in enumerate(plddt_scores):
        if score < threshold and not in_region:
            start = i
            in_region = True
        elif score >= threshold and in_region:
            low_conf_regions.append((start, i))
            in_region = False
    
    if in_region:
        low_conf_regions.append((start, len(plddt_scores)))
    
    return low_conf_regions
```

**PAE (Predicted Aligned Error) Analysis**

```python
def analyze_pae(pae_matrix: np.ndarray) -> dict:
    """Analyze PAE for domain identification."""
    # Low PAE values indicate confident relative positioning
    mean_pae = np.mean(pae_matrix)
    
    # Identify potential domains (low intra-domain PAE)
    # High inter-domain PAE suggests independent domains
    
    return {
        'mean_pae': mean_pae,
        'well_defined': mean_pae < 5.0,  # Å
        'has_domains': np.std(pae_matrix) > 10.0
    }
```

### 4. Template Usage

**When to Use Templates**
- **Use templates**: Known homologs with experimental structures
- **Template-free**: Novel folds, low sequence identity (<30%)
- **max_template_date**: Set to avoid data leakage in benchmarking

```bash
# Disable templates for novel fold prediction
--max_template_date=1900-01-01

# Use recent templates
--max_template_date=2023-12-31
```

### 5. MSA Depth Optimization

**MSA Depth vs Speed Tradeoff**

```bash
# Default (highest accuracy, slowest)
--max_msa_clusters=512

# Balanced (good accuracy, faster)
--max_msa_clusters=256

# Fast (reduced accuracy)
--max_msa_clusters=128

# Very fast (significant accuracy loss)
--max_msa_clusters=64
```

**When to Reduce MSA Depth:**
- High-throughput screening
- Well-studied protein families (abundant homologs)
- Time-critical applications

**When to Keep Full MSA:**
- Novel proteins
- Low sequence identity to known proteins
- Publication-quality structures

### 6. Memory Management

**GPU Memory Optimization**

```python
def estimate_gpu_memory(sequence_length: int, msa_depth: int = 512) -> float:
    """Estimate GPU memory requirements (GB)."""
    # Rough estimation
    base_memory = 4.0  # GB
    sequence_factor = sequence_length / 1000 * 2.0
    msa_factor = msa_depth / 512 * 2.0
    
    return base_memory + sequence_factor + msa_factor

# Example
seq_len = 500
required_memory = estimate_gpu_memory(seq_len)
print(f"Estimated GPU memory: {required_memory:.1f} GB")
```

**Handling OOM Errors**

```bash
# Reduce MSA depth
--max_msa_clusters=128

# Disable GPU relaxation
--use_gpu_relax=false

# Use CPU for relaxation
--enable_gpu_relax=false
```

### 7. Multimer Predictions

**Best Practices for Complexes**

```python
def prepare_multimer_fasta(chains: dict) -> str:
    """
    Prepare FASTA for multimer prediction.
    
    Args:
        chains: Dict mapping chain IDs to sequences
        
    Returns:
        Formatted FASTA string
    """
    fasta_lines = []
    for chain_id, sequence in chains.items():
        fasta_lines.append(f">chain_{chain_id}")
        fasta_lines.append(sequence)
    
    return "\n".join(fasta_lines)

# Example: Homodimer
chains = {
    'A': 'MKTAYIAKQRQISFVKSHFSRQ...',
    'B': 'MKTAYIAKQRQISFVKSHFSRQ...'  # Same sequence
}
fasta = prepare_multimer_fasta(chains)
```

**Multimer Considerations:**
- Significantly slower than monomer predictions
- Requires more memory
- Use when protein-protein interactions are critical
- Consider stoichiometry (homodimers, heterodimers, etc.)

## Common Issues and Solutions

### Issue 1: Low Confidence Predictions

**Symptoms:**
- Mean pLDDT < 70
- Large regions with pLDDT < 50

**Possible Causes:**
1. Intrinsically disordered regions (IDRs)
2. Insufficient evolutionary information
3. Novel fold with few homologs
4. Sequence errors

**Solutions:**
```python
def handle_low_confidence(sequence: str, plddt_scores: np.ndarray):
    """Strategies for low confidence predictions."""
    
    # Identify problematic regions
    low_conf_regions = identify_flexible_regions(plddt_scores, threshold=50)
    
    if len(low_conf_regions) > 0:
        print("Low confidence regions detected:")
        for start, end in low_conf_regions:
            print(f"  Residues {start}-{end}")
            region_seq = sequence[start:end]
            
            # Check for disorder prediction
            # Consider removing these regions for MD
            # Or model them separately
    
    # Strategy 1: Domain splitting
    # Strategy 2: Disorder prediction tools (IUPred, etc.)
    # Strategy 3: Use experimental data if available
```

### Issue 2: Out of Memory (OOM)

**Solutions:**

1. **Reduce MSA depth**
```bash
--max_msa_clusters=128
```

2. **Disable GPU relaxation**
```bash
--use_gpu_relax=false
```

3. **Split long sequences**
```python
def split_long_sequence(sequence: str, max_length: int = 1500, overlap: int = 50):
    """Split long sequence into overlapping fragments."""
    fragments = []
    for i in range(0, len(sequence), max_length - overlap):
        fragment = sequence[i:i + max_length]
        if len(fragment) >= 50:  # Minimum fragment size
            fragments.append({
                'sequence': fragment,
                'start': i,
                'end': i + len(fragment)
            })
    return fragments
```

### Issue 3: Slow Predictions

**Solutions:**

1. **Use ColabFold** (3-5x faster)
```bash
colabfold_batch input.fasta output/ --num-recycle 3
```

2. **Reduce recycling iterations**
```bash
--num_recycle=3  # Default is 3, can reduce to 1 for speed
```

3. **Use reduced databases**
```bash
--db_preset=reduced_dbs
```

4. **Parallel processing**
```python
# Process multiple sequences in parallel
# Use separate GPU for each prediction if available
```

### Issue 4: Database Download Failures

**Solutions:**

```bash
# Download databases individually with retry
for db in bfd mgnify pdb70 uniclust30 uniref90; do
    while ! bash scripts/download_${db}.sh /data; do
        echo "Retrying $db download..."
        sleep 60
    done
done

# Use rsync for resumable downloads
rsync -avz --progress \
    rsync://ftp.ebi.ac.uk/pub/databases/alphafold/ \
    /path/to/databases/
```

### Issue 5: CUDA/GPU Issues

**Diagnostics:**

```bash
# Check GPU availability
nvidia-smi

# Check CUDA version
nvcc --version

# Test JAX GPU detection
python -c "import jax; print(jax.devices())"

# Check Docker GPU access
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

**Solutions:**

```bash
# Reinstall NVIDIA Docker runtime
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker

# Update JAX
pip install --upgrade "jax[cuda11_cudnn82]" -f \
    https://storage.googleapis.com/jax-releases/jax_cuda_releases.html
```

## Performance Benchmarks

### Typical Prediction Times (Single GPU - V100)

| Sequence Length | MSA Depth | Time |
|----------------|-----------|------|
| 100 aa | 512 | ~5 min |
| 300 aa | 512 | ~15 min |
| 500 aa | 512 | ~30 min |
| 1000 aa | 512 | ~2 hours |
| 2000 aa | 512 | ~8 hours |

### ColabFold Speed Comparison

| Sequence Length | AlphaFold2 | ColabFold | Speedup |
|----------------|------------|-----------|---------|
| 300 aa | 15 min | 3 min | 5x |
| 500 aa | 30 min | 6 min | 5x |
| 1000 aa | 2 hours | 25 min | 4.8x |

## Integration Checklist for MDPilot

- [ ] Install AlphaFold2 (Docker recommended)
- [ ] Download databases (or use ColabFold)
- [ ] Test prediction with sample sequence
- [ ] Implement quality assessment pipeline
- [ ] Set up batch processing for multiple sequences
- [ ] Configure memory limits and error handling
- [ ] Integrate with MD preparation workflow
- [ ] Document confidence thresholds for MD suitability
- [ ] Set up monitoring for long-running predictions
- [ ] Implement result caching to avoid re-prediction

## Additional Resources

- **AlphaFold FAQ**: https://github.com/deepmind/alphafold/blob/main/docs/faq.md
- **ColabFold**: https://github.com/sokrypton/ColabFold
- **AlphaFold DB**: https://alphafold.ebi.ac.uk
- **Community Forum**: https://github.com/deepmind/alphafold/discussions
