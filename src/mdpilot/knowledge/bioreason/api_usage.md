# GogPT API Usage and Examples

## Installation

### Via pip

```bash
pip install bioreason-gogpt
```

### From source

```bash
git clone https://github.com/bioreason/gogpt.git
cd gogpt
pip install -e .
```

### Dependencies

```bash
# Core dependencies
pip install torch transformers numpy pandas

# Optional for visualization
pip install matplotlib seaborn networkx
```

## Basic API Usage

### Single Sequence Prediction

```python
from bioreason import GogPT

# Load model
model = GogPT.from_pretrained("bioreason/gogpt-base")

# Predict GO terms
sequence = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLKSTVEAIWAGIKATEAAVSEEFGLAPFLPDQIHFVHSQELLSRYPDLDAKGRERAIAKDLGAVFLVGIGGKLSDGHRHDVRAPDYDDWSTPSELGHAGLNGDILVWNPVLEDAFELSSMGIRVDADTLKHQLALTGDEDRLELEWHQALLRGEMPQTIGGGIGQSRLTMLLLQLPHIGQVQAGVWPAAVRESVPSLL"

predictions = model.predict(sequence)

# Access predictions
print(f"Molecular Function predictions: {len(predictions['molecular_function'])}")
print(f"Biological Process predictions: {len(predictions['biological_process'])}")
print(f"Cellular Component predictions: {len(predictions['cellular_component'])}")
```

### Filtering by Confidence

```python
# Get high-confidence predictions only
def filter_by_confidence(predictions, threshold=0.5):
    """Filter predictions by confidence threshold."""
    filtered = {}
    for ontology, terms in predictions.items():
        filtered[ontology] = [
            term for term in terms 
            if term['score'] >= threshold
        ]
    return filtered

high_conf_predictions = filter_by_confidence(predictions, threshold=0.7)

# Display top predictions
for term in high_conf_predictions['molecular_function'][:10]:
    print(f"{term['go_id']}: {term['name']}")
    print(f"  Score: {term['score']:.3f}")
    print(f"  Evidence: {term.get('evidence', 'predicted')}")
```

### Top-K Predictions

```python
# Get top 10 predictions per ontology
top_k_predictions = model.predict(
    sequence,
    top_k=10,
    threshold=0.3  # Minimum confidence
)

# Format output
def format_predictions(predictions):
    """Format predictions for display."""
    output = []
    for ontology, terms in predictions.items():
        output.append(f"\n{ontology.upper().replace('_', ' ')}:")
        for i, term in enumerate(terms, 1):
            output.append(
                f"  {i}. {term['name']} ({term['go_id']}) - {term['score']:.3f}"
            )
    return "\n".join(output)

print(format_predictions(top_k_predictions))
```

## Batch Processing

### Processing Multiple Sequences

```python
from typing import List, Dict
import pandas as pd

class BatchGogPT:
    """Batch processing wrapper for GogPT."""
    
    def __init__(self, model_name: str = "bioreason/gogpt-base"):
        self.model = GogPT.from_pretrained(model_name)
    
    def predict_batch(
        self,
        sequences: List[str],
        batch_size: int = 32,
        top_k: int = 10
    ) -> List[Dict]:
        """
        Predict GO terms for multiple sequences.
        
        Args:
            sequences: List of protein sequences
            batch_size: Number of sequences per batch
            top_k: Number of top predictions to return
            
        Returns:
            List of prediction dictionaries
        """
        results = []
        
        for i in range(0, len(sequences), batch_size):
            batch = sequences[i:i + batch_size]
            batch_predictions = self.model.predict_batch(
                batch,
                top_k=top_k
            )
            results.extend(batch_predictions)
        
        return results
    
    def predict_from_fasta(
        self,
        fasta_path: str,
        output_path: str = None,
        top_k: int = 10
    ) -> pd.DataFrame:
        """
        Predict GO terms from FASTA file.
        
        Args:
            fasta_path: Path to FASTA file
            output_path: Optional path to save results
            top_k: Number of top predictions per ontology
            
        Returns:
            DataFrame with predictions
        """
        from Bio import SeqIO
        
        # Read sequences
        sequences = []
        seq_ids = []
        
        for record in SeqIO.parse(fasta_path, "fasta"):
            sequences.append(str(record.seq))
            seq_ids.append(record.id)
        
        # Predict
        predictions = self.predict_batch(sequences, top_k=top_k)
        
        # Format as DataFrame
        rows = []
        for seq_id, pred in zip(seq_ids, predictions):
            for ontology, terms in pred.items():
                for term in terms:
                    rows.append({
                        'sequence_id': seq_id,
                        'ontology': ontology,
                        'go_id': term['go_id'],
                        'go_name': term['name'],
                        'score': term['score']
                    })
        
        df = pd.DataFrame(rows)
        
        if output_path:
            df.to_csv(output_path, index=False)
        
        return df

# Usage
batch_processor = BatchGogPT()
results_df = batch_processor.predict_from_fasta(
    "proteins.fasta",
    output_path="go_predictions.csv",
    top_k=10
)

print(f"Processed {len(results_df['sequence_id'].unique())} sequences")
```

## Advanced Features

### Hierarchical Predictions

```python
def get_hierarchical_predictions(predictions, go_graph):
    """
    Get predictions with GO hierarchy information.
    
    Args:
        predictions: GogPT predictions
        go_graph: GO hierarchy graph (from goatools)
        
    Returns:
        Predictions with parent/child relationships
    """
    from goatools import obo_parser
    
    # Load GO hierarchy
    go_obo = obo_parser.GODag("go-basic.obo")
    
    enriched_predictions = {}
    
    for ontology, terms in predictions.items():
        enriched_terms = []
        
        for term in terms:
            go_id = term['go_id']
            go_term = go_obo.get(go_id)
            
            if go_term:
                enriched_term = term.copy()
                enriched_term['parents'] = [
                    p.id for p in go_term.parents
                ]
                enriched_term['children'] = [
                    c.id for c in go_term.children
                ]
                enriched_term['level'] = go_term.level
                enriched_terms.append(enriched_term)
        
        enriched_predictions[ontology] = enriched_terms
    
    return enriched_predictions
```

### Confidence Calibration

```python
def calibrate_scores(predictions, calibration_data=None):
    """
    Calibrate prediction scores for better probability estimates.
    
    Args:
        predictions: Raw GogPT predictions
        calibration_data: Optional calibration dataset
        
    Returns:
        Predictions with calibrated scores
    """
    from sklearn.calibration import CalibratedClassifierCV
    
    # Apply temperature scaling or Platt scaling
    # This requires a validation set with known annotations
    
    calibrated_predictions = {}
    
    for ontology, terms in predictions.items():
        calibrated_terms = []
        
        for term in terms:
            # Apply calibration
            calibrated_score = apply_calibration(
                term['score'],
                calibration_data
            )
            
            calibrated_term = term.copy()
            calibrated_term['calibrated_score'] = calibrated_score
            calibrated_terms.append(calibrated_term)
        
        calibrated_predictions[ontology] = calibrated_terms
    
    return calibrated_predictions
```

### Ensemble Predictions

```python
class EnsembleGogPT:
    """Ensemble of multiple GogPT models."""
    
    def __init__(self, model_names: List[str]):
        self.models = [
            GogPT.from_pretrained(name) 
            for name in model_names
        ]
    
    def predict(self, sequence: str, aggregation: str = 'mean') -> Dict:
        """
        Predict using ensemble of models.
        
        Args:
            sequence: Protein sequence
            aggregation: How to combine predictions ('mean', 'max', 'vote')
            
        Returns:
            Aggregated predictions
        """
        all_predictions = [
            model.predict(sequence) 
            for model in self.models
        ]
        
        # Aggregate predictions
        if aggregation == 'mean':
            return self._aggregate_mean(all_predictions)
        elif aggregation == 'max':
            return self._aggregate_max(all_predictions)
        elif aggregation == 'vote':
            return self._aggregate_vote(all_predictions)
    
    def _aggregate_mean(self, predictions_list):
        """Average scores across models."""
        aggregated = {}
        
        for ontology in predictions_list[0].keys():
            # Collect all GO terms
            all_terms = {}
            
            for predictions in predictions_list:
                for term in predictions[ontology]:
                    go_id = term['go_id']
                    if go_id not in all_terms:
                        all_terms[go_id] = {
                            'go_id': go_id,
                            'name': term['name'],
                            'scores': []
                        }
                    all_terms[go_id]['scores'].append(term['score'])
            
            # Average scores
            aggregated_terms = []
            for go_id, data in all_terms.items():
                aggregated_terms.append({
                    'go_id': go_id,
                    'name': data['name'],
                    'score': sum(data['scores']) / len(data['scores']),
                    'std': np.std(data['scores'])
                })
            
            # Sort by score
            aggregated_terms.sort(key=lambda x: x['score'], reverse=True)
            aggregated[ontology] = aggregated_terms
        
        return aggregated

# Usage
ensemble = EnsembleGogPT([
    "bioreason/gogpt-base",
    "bioreason/gogpt-large"
])

ensemble_predictions = ensemble.predict(sequence, aggregation='mean')
```

## Integration with MDPilot

### Structure-Function Validation

```python
class StructureFunctionValidator:
    """Validate AlphaFold2 structures with GogPT predictions."""
    
    def __init__(self, gogpt_model):
        self.gogpt = gogpt_model
    
    def validate_structure(
        self,
        sequence: str,
        structure_path: str,
        plddt_scores: np.ndarray
    ) -> Dict:
        """
        Validate structure against functional predictions.
        
        Args:
            sequence: Protein sequence
            structure_path: Path to PDB file
            plddt_scores: AlphaFold2 confidence scores
            
        Returns:
            Validation report
        """
        # Get GO predictions
        go_predictions = self.gogpt.predict(sequence)
        
        # Analyze structure
        structure_features = self._analyze_structure(structure_path)
        
        # Check consistency
        validation = {
            'membrane_protein': self._check_membrane(
                go_predictions, structure_features
            ),
            'metal_binding': self._check_metal_binding(
                go_predictions, structure_features
            ),
            'domain_structure': self._check_domains(
                go_predictions, structure_features, plddt_scores
            )
        }
        
        return validation
    
    def _check_membrane(self, go_predictions, structure_features):
        """Check if membrane protein prediction matches structure."""
        # Check for membrane-related GO terms
        cc_terms = go_predictions['cellular_component']
        is_membrane = any(
            'membrane' in term['name'].lower()
            for term in cc_terms
            if term['score'] > 0.5
        )
        
        # Check for transmembrane helices in structure
        has_tm_helices = structure_features.get('tm_helices', 0) > 0
        
        return {
            'predicted_membrane': is_membrane,
            'has_tm_structure': has_tm_helices,
            'consistent': is_membrane == has_tm_helices
        }
    
    def _analyze_structure(self, structure_path):
        """Extract structural features from PDB."""
        from Bio.PDB import PDBParser
        
        parser = PDBParser(QUIET=True)
        structure = parser.get_structure('protein', structure_path)
        
        # Analyze structure
        features = {
            'num_residues': len(list(structure.get_residues())),
            'num_chains': len(list(structure.get_chains())),
            # Add more structural analysis
        }
        
        return features

# Usage
validator = StructureFunctionValidator(model)
validation_report = validator.validate_structure(
    sequence=sequence,
    structure_path="alphafold_prediction.pdb",
    plddt_scores=plddt_scores
)

print(f"Membrane protein consistency: {validation_report['membrane_protein']['consistent']}")
```

### MD Simulation Setup

```python
def setup_md_from_function(sequence, go_predictions):
    """Configure MD simulation based on functional predictions."""
    
    config = {
        'simulation_type': 'standard',
        'force_field': 'amber14',
        'water_model': 'tip3p',
        'ions': [],
        'constraints': []
    }
    
    # Check cellular component
    cc_terms = go_predictions['cellular_component']
    
    if any('membrane' in t['name'].lower() for t in cc_terms if t['score'] > 0.5):
        config['simulation_type'] = 'membrane'
        config['lipid_composition'] = 'POPC'
    
    # Check molecular function
    mf_terms = go_predictions['molecular_function']
    
    if any('metal' in t['name'].lower() for t in mf_terms if t['score'] > 0.5):
        config['ions'].append('Zn2+')
        config['ions'].append('Mg2+')
    
    if any('DNA binding' in t['name'] for t in mf_terms if t['score'] > 0.5):
        config['add_dna'] = True
    
    # Check biological process
    bp_terms = go_predictions['biological_process']
    
    if any('conformational change' in t['name'].lower() for t in bp_terms if t['score'] > 0.5):
        config['enhanced_sampling'] = 'metadynamics'
    
    return config

# Usage
predictions = model.predict(sequence)
md_config = setup_md_from_function(sequence, predictions)

print(f"MD Configuration:")
print(f"  Type: {md_config['simulation_type']}")
print(f"  Enhanced sampling: {md_config.get('enhanced_sampling', 'none')}")
```

## Output Formats

### JSON Output

```python
import json

# Save predictions as JSON
with open('predictions.json', 'w') as f:
    json.dump(predictions, f, indent=2)

# Load predictions
with open('predictions.json', 'r') as f:
    loaded_predictions = json.load(f)
```

### CSV Output

```python
import csv

def predictions_to_csv(predictions, output_path):
    """Export predictions to CSV format."""
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Ontology', 'GO_ID', 'GO_Name', 'Score'])
        
        for ontology, terms in predictions.items():
            for term in terms:
                writer.writerow([
                    ontology,
                    term['go_id'],
                    term['name'],
                    term['score']
                ])

predictions_to_csv(predictions, 'predictions.csv')
```

### GAF Format (Gene Association File)

```python
def predictions_to_gaf(predictions, protein_id, output_path):
    """Export predictions in GAF 2.2 format."""
    with open(output_path, 'w') as f:
        f.write("!gaf-version: 2.2\n")
        
        for ontology, terms in predictions.items():
            for term in terms:
                if term['score'] > 0.5:  # Only confident predictions
                    # GAF format line
                    line = [
                        "UniProtKB",  # DB
                        protein_id,  # DB_Object_ID
                        protein_id,  # DB_Object_Symbol
                        "",  # Qualifier
                        term['go_id'],  # GO_ID
                        "PMID:00000000",  # DB_Reference
                        "IEA",  # Evidence Code (Inferred from Electronic Annotation)
                        "",  # With/From
                        ontology[0].upper(),  # Aspect (F/P/C)
                        "",  # DB_Object_Name
                        "",  # DB_Object_Synonym
                        "protein",  # DB_Object_Type
                        "taxon:9606",  # Taxon
                        "20260511",  # Date
                        "GogPT"  # Assigned_By
                    ]
                    f.write("\t".join(line) + "\n")

predictions_to_gaf(predictions, "P12345", "predictions.gaf")
```

## Error Handling

```python
def safe_predict(model, sequence, max_retries=3):
    """Prediction with error handling and retries."""
    for attempt in range(max_retries):
        try:
            return model.predict(sequence)
        except Exception as e:
            if "out of memory" in str(e).lower():
                # Clear cache and retry
                torch.cuda.empty_cache()
            elif attempt == max_retries - 1:
                raise
            else:
                print(f"Retry {attempt + 1}/{max_retries}")
    
    raise RuntimeError("Prediction failed after all retries")
```
