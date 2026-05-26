# AlphaFold2 API Reference

## Python API Usage

AlphaFold2 can be integrated programmatically into Python workflows. This guide covers common integration patterns for MDPilot.

## Basic Structure Prediction

### Using AlphaFold2 Directly

```python
import os
from alphafold.common import protein
from alphafold.data import pipeline
from alphafold.model import data, config, model

# Load model configuration
model_name = 'model_1_ptm'
cfg = config.model_config(model_name)

# Initialize model
model_runner = model.RunModel(cfg, params)

# Prepare input features
feature_dict = {
    'aatype': aatype,
    'residue_index': residue_index,
    'msa': msa,
    'num_alignments': num_alignments,
    # ... additional features
}

# Run prediction
prediction_result = model_runner.predict(feature_dict)

# Extract structure
unrelaxed_protein = protein.from_prediction(
    features=feature_dict,
    result=prediction_result
)

# Save PDB
pdb_string = protein.to_pdb(unrelaxed_protein)
with open('output.pdb', 'w') as f:
    f.write(pdb_string)
```

### Using Docker API (Recommended)

```python
import subprocess
import json
from pathlib import Path

class AlphaFold2Runner:
    """Wrapper for AlphaFold2 Docker execution."""
    
    def __init__(self, data_dir: str, docker_image: str = "ghcr.io/deepmind/alphafold:latest"):
        self.data_dir = Path(data_dir)
        self.docker_image = docker_image
    
    def predict_structure(
        self,
        fasta_path: str,
        output_dir: str,
        max_template_date: str = "2023-01-01",
        model_preset: str = "monomer_ptm",
        use_gpu: bool = True
    ) -> dict:
        """
        Run AlphaFold2 prediction.
        
        Args:
            fasta_path: Path to input FASTA file
            output_dir: Directory for output files
            max_template_date: Cutoff date for template search
            model_preset: Model type (monomer, monomer_ptm, multimer)
            use_gpu: Whether to use GPU acceleration
            
        Returns:
            Dictionary with prediction results and paths
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        cmd = [
            "docker", "run",
            "--rm",
            "-v", f"{self.data_dir}:/data",
            "-v", f"{Path(fasta_path).parent}:/input",
            "-v", f"{output_dir}:/output",
        ]
        
        if use_gpu:
            cmd.extend(["--gpus", "all"])
        
        cmd.extend([
            self.docker_image,
            f"--fasta_paths=/input/{Path(fasta_path).name}",
            f"--max_template_date={max_template_date}",
            f"--model_preset={model_preset}",
            "--data_dir=/data",
            "--output_dir=/output",
        ])
        
        # Run prediction
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"AlphaFold2 failed: {result.stderr}")
        
        # Parse results
        return self._parse_results(output_dir)
    
    def _parse_results(self, output_dir: Path) -> dict:
        """Parse AlphaFold2 output files."""
        results = {
            "pdb_files": list(output_dir.glob("*.pdb")),
            "confidence_scores": {},
            "pae_matrices": {}
        }
        
        # Load ranking and confidence data
        ranking_file = output_dir / "ranking_debug.json"
        if ranking_file.exists():
            with open(ranking_file) as f:
                results["ranking"] = json.load(f)
        
        # Load per-model results
        for result_file in output_dir.glob("result_*.pkl"):
            model_name = result_file.stem
            # Parse pickle file for detailed results
            # results["confidence_scores"][model_name] = ...
        
        return results

# Usage example
runner = AlphaFold2Runner(data_dir="/path/to/databases")
results = runner.predict_structure(
    fasta_path="protein.fasta",
    output_dir="predictions/",
    model_preset="monomer_ptm"
)

print(f"Generated {len(results['pdb_files'])} structures")
```

## Working with Predictions

### Loading and Analyzing PDB Files

```python
from Bio.PDB import PDBParser
import numpy as np

def load_alphafold_prediction(pdb_path: str) -> dict:
    """
    Load AlphaFold2 prediction with confidence scores.
    
    Returns:
        Dictionary with structure and pLDDT scores
    """
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure('protein', pdb_path)
    
    # Extract pLDDT scores from B-factor column
    plddt_scores = []
    for model in structure:
        for chain in model:
            for residue in chain:
                for atom in residue:
                    if atom.name == 'CA':  # Use CA atoms
                        plddt_scores.append(atom.bfactor)
    
    return {
        'structure': structure,
        'plddt_scores': np.array(plddt_scores),
        'mean_plddt': np.mean(plddt_scores),
        'confident_residues': np.sum(np.array(plddt_scores) > 70)
    }

# Usage
prediction = load_alphafold_prediction("ranked_0.pdb")
print(f"Mean pLDDT: {prediction['mean_plddt']:.2f}")
print(f"Confident residues: {prediction['confident_residues']}")
```

### Extracting PAE (Predicted Aligned Error)

```python
import json
import numpy as np
import matplotlib.pyplot as plt

def load_pae_matrix(json_path: str) -> np.ndarray:
    """Load PAE matrix from AlphaFold2 output."""
    with open(json_path) as f:
        data = json.load(f)
    
    pae = np.array(data[0]['predicted_aligned_error'])
    return pae

def plot_pae(pae_matrix: np.ndarray, output_path: str = None):
    """Visualize PAE matrix."""
    plt.figure(figsize=(10, 8))
    plt.imshow(pae_matrix, cmap='viridis_r', vmin=0, vmax=30)
    plt.colorbar(label='Expected position error (Å)')
    plt.xlabel('Scored residue')
    plt.ylabel('Aligned residue')
    plt.title('Predicted Aligned Error (PAE)')
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

# Usage
pae = load_pae_matrix("result_model_1_ptm_pred_0.json")
plot_pae(pae, "pae_plot.png")
```

## Batch Processing

### Processing Multiple Sequences

```python
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import logging

class BatchAlphaFold:
    """Batch processing for multiple sequences."""
    
    def __init__(self, runner: AlphaFold2Runner, max_workers: int = 4):
        self.runner = runner
        self.max_workers = max_workers
        self.logger = logging.getLogger(__name__)
    
    def process_batch(
        self,
        fasta_files: list[str],
        output_base_dir: str
    ) -> dict:
        """
        Process multiple FASTA files in parallel.
        
        Args:
            fasta_files: List of FASTA file paths
            output_base_dir: Base directory for outputs
            
        Returns:
            Dictionary mapping input files to results
        """
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            
            for fasta_file in fasta_files:
                fasta_path = Path(fasta_file)
                output_dir = Path(output_base_dir) / fasta_path.stem
                
                future = executor.submit(
                    self._safe_predict,
                    fasta_file,
                    str(output_dir)
                )
                futures[future] = fasta_file
            
            for future in futures:
                fasta_file = futures[future]
                try:
                    result = future.result()
                    results[fasta_file] = result
                    self.logger.info(f"Completed: {fasta_file}")
                except Exception as e:
                    self.logger.error(f"Failed {fasta_file}: {e}")
                    results[fasta_file] = {"error": str(e)}
        
        return results
    
    def _safe_predict(self, fasta_path: str, output_dir: str) -> dict:
        """Wrapper with error handling."""
        try:
            return self.runner.predict_structure(fasta_path, output_dir)
        except Exception as e:
            return {"error": str(e)}

# Usage
runner = AlphaFold2Runner(data_dir="/path/to/databases")
batch = BatchAlphaFold(runner, max_workers=2)

fasta_files = ["protein1.fasta", "protein2.fasta", "protein3.fasta"]
results = batch.process_batch(fasta_files, "batch_predictions/")
```

## Integration with MDPilot

### MDPilot Structure Preparation Pipeline

```python
class MDPilotAlphaFoldIntegration:
    """Integration layer for MDPilot."""
    
    def __init__(self, alphafold_runner: AlphaFold2Runner):
        self.af_runner = alphafold_runner
    
    def prepare_structure_for_md(
        self,
        sequence: str,
        output_dir: str,
        min_plddt: float = 70.0
    ) -> dict:
        """
        Predict structure and prepare for MD simulation.
        
        Args:
            sequence: Amino acid sequence
            output_dir: Output directory
            min_plddt: Minimum pLDDT threshold for confident regions
            
        Returns:
            Dictionary with structure path and quality metrics
        """
        # Write FASTA
        fasta_path = Path(output_dir) / "input.fasta"
        with open(fasta_path, 'w') as f:
            f.write(f">protein\n{sequence}\n")
        
        # Run prediction
        results = self.af_runner.predict_structure(
            str(fasta_path),
            output_dir
        )
        
        # Analyze best model
        best_pdb = results['pdb_files'][0]  # Ranked by confidence
        analysis = load_alphafold_prediction(str(best_pdb))
        
        # Quality assessment
        quality = {
            'mean_plddt': analysis['mean_plddt'],
            'confident_fraction': analysis['confident_residues'] / len(sequence),
            'suitable_for_md': analysis['mean_plddt'] >= min_plddt
        }
        
        return {
            'structure_path': str(best_pdb),
            'quality': quality,
            'plddt_scores': analysis['plddt_scores']
        }

# Usage in MDPilot workflow
integration = MDPilotAlphaFoldIntegration(runner)
result = integration.prepare_structure_for_md(
    sequence="MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLKSTVEAIWAGIKATEAAVSEEFGLAPFLPDQIHFVHSQELLSRYPDLDAKGRERAIAKDLGAVFLVGIGGKLSDGHRHDVRAPDYDDWSTPSELGHAGLNGDILVWNPVLEDAFELSSMGIRVDADTLKHQLALTGDEDRLELEWHQALLRGEMPQTIGGGIGQSRLTMLLLQLPHIGQVQAGVWPAAVRESVPSLL",
    output_dir="mdpilot_structures/protein1"
)

if result['quality']['suitable_for_md']:
    print(f"Structure ready for MD: {result['structure_path']}")
else:
    print(f"Low confidence structure (pLDDT: {result['quality']['mean_plddt']:.1f})")
```

## Input/Output Formats

### FASTA Input Format

```
>protein_name optional_description
MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVK
ALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWE
```

### PDB Output Structure

- **Coordinates**: Standard PDB format
- **B-factor column**: Contains pLDDT scores (0-100)
- **Models**: Multiple models ranked by confidence

### JSON Output Files

- `ranking_debug.json`: Model ranking information
- `result_model_X_ptm_pred_0.json`: Detailed predictions including PAE
- `timings.json`: Performance metrics

## Error Handling

```python
def robust_prediction(runner, fasta_path, output_dir, max_retries=3):
    """Prediction with retry logic."""
    for attempt in range(max_retries):
        try:
            return runner.predict_structure(fasta_path, output_dir)
        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                # Reduce MSA depth and retry
                print(f"OOM error, reducing MSA depth (attempt {attempt + 1})")
                # Implement MSA reduction logic
            elif attempt == max_retries - 1:
                raise
            else:
                print(f"Retry {attempt + 1}/{max_retries}")
    
    raise RuntimeError("Prediction failed after all retries")
```
