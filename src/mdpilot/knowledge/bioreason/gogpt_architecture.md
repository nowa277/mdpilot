# GogPT Architecture and ESM2 Integration

## Overview

GogPT (Gene Ontology GPT) is built on top of ESM2 (Evolutionary Scale Modeling 2), Meta AI's state-of-the-art protein language model. It extends ESM2's sequence understanding capabilities to predict functional annotations.

## ESM2 Foundation

### What is ESM2?

ESM2 is a transformer-based protein language model trained on millions of protein sequences. It learns to:

- Understand amino acid context and relationships
- Capture evolutionary patterns
- Generate meaningful protein representations
- Predict structure and function from sequence alone

### ESM2 Model Variants

| Model | Parameters | Embedding Dim | Use Case |
|-------|------------|---------------|----------|
| ESM2-8M | 8M | 320 | Fast screening |
| ESM2-35M | 35M | 480 | Balanced |
| ESM2-150M | 150M | 640 | High accuracy |
| ESM2-650M | 650M | 1280 | Research |
| ESM2-3B | 3B | 2560 | State-of-art |

### ESM2 Embeddings

```python
import torch
from transformers import AutoTokenizer, EsmModel

# Load ESM2 model
tokenizer = AutoTokenizer.from_pretrained("facebook/esm2_t33_650M_UR50D")
model = EsmModel.from_pretrained("facebook/esm2_t33_650M_UR50D")

# Generate embeddings
sequence = "MKTAYIAKQRQISFVKSHFSRQ"
inputs = tokenizer(sequence, return_tensors="pt")

with torch.no_grad():
    outputs = model(**inputs)
    embeddings = outputs.last_hidden_state  # [1, seq_len, 1280]

# Per-residue embeddings
residue_embeddings = embeddings[0, 1:-1, :]  # Remove BOS/EOS tokens

# Sequence-level embedding (mean pooling)
sequence_embedding = residue_embeddings.mean(dim=0)  # [1280]
```

## GogPT Architecture

### Model Pipeline

```
Input Sequence
    ↓
ESM2 Tokenization
    ↓
ESM2 Encoder (Transformer)
    ↓
Protein Embeddings [seq_len, embed_dim]
    ↓
Pooling Layer (mean/max/attention)
    ↓
Sequence Representation [embed_dim]
    ↓
GO Prediction Heads (3 branches)
    ↓
├─ Molecular Function Head → MF Predictions
├─ Biological Process Head → BP Predictions
└─ Cellular Component Head → CC Predictions
```

### Prediction Heads

Each GO ontology has a dedicated prediction head:

```python
class GOPredictionHead(nn.Module):
    """Prediction head for GO term classification."""
    
    def __init__(self, embed_dim: int, num_go_terms: int):
        super().__init__()
        self.fc1 = nn.Linear(embed_dim, 2048)
        self.dropout = nn.Dropout(0.3)
        self.fc2 = nn.Linear(2048, 1024)
        self.fc3 = nn.Linear(1024, num_go_terms)
        self.activation = nn.ReLU()
    
    def forward(self, embeddings):
        x = self.activation(self.fc1(embeddings))
        x = self.dropout(x)
        x = self.activation(self.fc2(x))
        x = self.dropout(x)
        logits = self.fc3(x)
        return torch.sigmoid(logits)  # Multi-label classification
```

### Training Methodology

**Dataset:**
- UniProtKB/Swiss-Prot annotated proteins
- ~500,000 proteins with experimental GO annotations
- Filtered for annotation quality and evidence codes

**Training Strategy:**
1. **Frozen ESM2**: ESM2 weights frozen, only train prediction heads
2. **Fine-tuned ESM2**: Fine-tune last layers of ESM2 with prediction heads
3. **Multi-task Learning**: Train all three GO ontologies simultaneously

**Loss Function:**
```python
def hierarchical_go_loss(predictions, targets, go_hierarchy):
    """
    Loss function respecting GO hierarchy.
    
    Args:
        predictions: Predicted GO term probabilities
        targets: Ground truth GO annotations
        go_hierarchy: GO term parent-child relationships
    """
    # Binary cross-entropy for multi-label classification
    bce_loss = F.binary_cross_entropy(predictions, targets)
    
    # Hierarchical consistency penalty
    # If child term is predicted, parent should also be predicted
    hierarchy_penalty = compute_hierarchy_violation(
        predictions, go_hierarchy
    )
    
    return bce_loss + 0.1 * hierarchy_penalty
```

## Key Innovations

### 1. Hierarchical Modeling

GogPT respects GO term relationships:

```python
class HierarchicalGOModel:
    """Model with GO hierarchy awareness."""
    
    def __init__(self, go_graph):
        self.go_graph = go_graph  # DAG of GO terms
    
    def enforce_hierarchy(self, predictions):
        """Ensure predictions respect GO hierarchy."""
        # If a child term is predicted, propagate to parents
        adjusted_predictions = predictions.copy()
        
        for go_term, score in predictions.items():
            if score > 0.5:  # Confident prediction
                # Propagate to all ancestors
                ancestors = self.go_graph.get_ancestors(go_term)
                for ancestor in ancestors:
                    adjusted_predictions[ancestor] = max(
                        adjusted_predictions.get(ancestor, 0),
                        score * 0.8  # Slightly lower confidence for ancestors
                    )
        
        return adjusted_predictions
```

### 2. Attention-Based Pooling

Instead of simple mean pooling, GogPT uses attention:

```python
class AttentionPooling(nn.Module):
    """Attention-based pooling for sequence embeddings."""
    
    def __init__(self, embed_dim):
        super().__init__()
        self.attention = nn.Linear(embed_dim, 1)
    
    def forward(self, embeddings):
        # embeddings: [batch, seq_len, embed_dim]
        attention_weights = torch.softmax(
            self.attention(embeddings), dim=1
        )  # [batch, seq_len, 1]
        
        # Weighted sum
        pooled = (embeddings * attention_weights).sum(dim=1)
        return pooled  # [batch, embed_dim]
```

### 3. Multi-Scale Features

Combines features from multiple ESM2 layers:

```python
def extract_multiscale_features(esm2_model, sequence):
    """Extract features from multiple ESM2 layers."""
    outputs = esm2_model(
        sequence,
        output_hidden_states=True
    )
    
    # Combine last 4 layers
    hidden_states = outputs.hidden_states[-4:]  # Last 4 layers
    
    # Concatenate or average
    multiscale_features = torch.stack(hidden_states).mean(dim=0)
    
    return multiscale_features
```

## Performance Characteristics

### Accuracy Benchmarks

**CAFA3 Benchmark (Critical Assessment of Function Annotation):**

| Model | MF F-max | BP F-max | CC F-max |
|-------|----------|----------|----------|
| BLAST | 0.45 | 0.38 | 0.52 |
| DeepGO | 0.51 | 0.42 | 0.58 |
| GogPT-base | 0.63 | 0.54 | 0.68 |
| GogPT-large | 0.67 | 0.58 | 0.72 |

**F-max**: Maximum F1 score across all confidence thresholds

### Speed Benchmarks

| Model | Sequences/sec (GPU) | Sequences/sec (CPU) |
|-------|---------------------|---------------------|
| GogPT-small | 50 | 5 |
| GogPT-base | 20 | 2 |
| GogPT-large | 8 | 0.5 |

*Tested on NVIDIA V100 GPU and Intel Xeon CPU*

### Memory Requirements

| Model | GPU Memory | System RAM |
|-------|------------|------------|
| GogPT-small | 2GB | 4GB |
| GogPT-base | 6GB | 8GB |
| GogPT-large | 12GB | 16GB |

## Comparison with Other Methods

### Traditional Methods

**BLAST-based annotation:**
- Pros: Fast, interpretable
- Cons: Requires close homologs, misses remote homology

**InterProScan:**
- Pros: Domain-based, well-established
- Cons: Limited to known domains, slow

### Deep Learning Methods

**DeepGO:**
- CNN-based architecture
- Good accuracy but slower than GogPT

**ProteinBERT:**
- BERT-style pretraining
- Similar performance to GogPT

**GogPT Advantages:**
- State-of-art ESM2 foundation
- Hierarchical modeling
- Fast inference
- Regular updates with new GO terms

## Integration Patterns

### With AlphaFold2

```python
def structure_function_pipeline(sequence):
    """Combined structure and function prediction."""
    
    # Parallel predictions
    import asyncio
    
    async def predict_structure():
        return alphafold2.predict(sequence)
    
    async def predict_function():
        return gogpt.predict(sequence)
    
    # Run in parallel
    structure, function = await asyncio.gather(
        predict_structure(),
        predict_function()
    )
    
    # Validate consistency
    # E.g., if predicted as "membrane protein", 
    # check if structure has transmembrane regions
    
    return {
        'structure': structure,
        'function': function,
        'validated': validate_consistency(structure, function)
    }
```

### With Molecular Dynamics

```python
def inform_md_simulation(sequence, structure, go_annotations):
    """Use GO annotations to inform MD setup."""
    
    # Check for membrane protein
    if any('membrane' in term['name'].lower() 
           for term in go_annotations['cellular_component']):
        # Set up membrane simulation
        simulation_type = 'membrane'
    
    # Check for metal binding
    if any('metal' in term['name'].lower() 
           for term in go_annotations['molecular_function']):
        # Add metal ions to simulation
        add_metal_ions = True
    
    # Check for flexibility requirements
    if any('conformational change' in term['name'].lower() 
           for term in go_annotations['biological_process']):
        # Use enhanced sampling methods
        use_enhanced_sampling = True
    
    return {
        'simulation_type': simulation_type,
        'add_metal_ions': add_metal_ions,
        'enhanced_sampling': use_enhanced_sampling
    }
```

## Future Directions

1. **Structure-aware GogPT**: Incorporate AlphaFold2 structures
2. **Multi-species models**: Species-specific GO prediction
3. **Temporal dynamics**: Predict condition-specific functions
4. **Explainability**: Identify sequence motifs driving predictions
5. **Active learning**: Improve with user feedback

## References

- ESM2 Paper: Lin et al., "Evolutionary-scale prediction of atomic-level protein structure with a language model", Science 2023
- GO Consortium: http://geneontology.org
- CAFA: https://biofunctionprediction.org/cafa/
