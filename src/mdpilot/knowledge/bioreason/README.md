# Bioreason (GogPT) Integration Guide

## Overview

Bioreason's GogPT is a protein language model that predicts Gene Ontology (GO) annotations from protein sequences. It leverages ESM2 (Evolutionary Scale Modeling 2) embeddings to understand protein function without requiring structural information.

## Key Capabilities

- **GO Annotation Prediction**: Predict Molecular Function (MF), Biological Process (BP), and Cellular Component (CC)
- **Sequence-Based**: Works directly from amino acid sequences
- **ESM2 Integration**: Uses state-of-the-art protein language model embeddings
- **High Throughput**: Fast predictions suitable for large-scale analysis
- **Confidence Scores**: Provides probability scores for each GO term prediction

## What is Gene Ontology (GO)?

Gene Ontology provides a standardized vocabulary for describing:

1. **Molecular Function (MF)**: Biochemical activities (e.g., "ATP binding", "kinase activity")
2. **Biological Process (BP)**: Biological programs (e.g., "cell division", "signal transduction")
3. **Cellular Component (CC)**: Cellular locations (e.g., "nucleus", "mitochondrion")

## GogPT Architecture

### Core Components

1. **ESM2 Encoder**: Generates contextualized protein embeddings
2. **GO Prediction Head**: Maps embeddings to GO term probabilities
3. **Hierarchical Modeling**: Respects GO term hierarchy and relationships

### Model Variants

- **GogPT-small**: Fast, suitable for screening
- **GogPT-base**: Balanced accuracy and speed
- **GogPT-large**: Highest accuracy, slower

## Quick Start

### Basic Usage

```python
from bioreason import GogPT

# Initialize model
model = GogPT.from_pretrained("bioreason/gogpt-base")

# Predict GO terms
sequence = "MKTAYIAKQRQISFVKSHFSRQ..."
predictions = model.predict(sequence)

# Access predictions by ontology
mf_terms = predictions['molecular_function']
bp_terms = predictions['biological_process']
cc_terms = predictions['cellular_component']

# Top predictions
for term in mf_terms[:5]:
    print(f"{term['go_id']}: {term['name']} (score: {term['score']:.3f})")
```

## Integration with MDPilot

GogPT enhances MDPilot workflows by:

1. **Functional Annotation**: Understand protein function before MD simulation
2. **Target Selection**: Prioritize proteins based on functional relevance
3. **Validation**: Verify predicted structures align with known functions
4. **Pathway Analysis**: Connect proteins to biological pathways
5. **Drug Target Identification**: Identify druggable functions

### Workflow Integration

```
Sequence → AlphaFold2 → Structure
    ↓
  GogPT → Function Annotation
    ↓
MD Simulation (informed by function)
```

## Key Features

### 1. Comprehensive GO Coverage

- **Molecular Function**: ~12,000 terms
- **Biological Process**: ~30,000 terms
- **Cellular Component**: ~4,000 terms

### 2. Confidence Scoring

- Probability scores (0-1) for each prediction
- Calibrated scores for reliable thresholding
- Multiple prediction modes (top-k, threshold-based)

### 3. Hierarchical Predictions

- Respects GO term parent-child relationships
- Propagates predictions through GO hierarchy
- Provides both specific and general annotations

## System Requirements

### Minimal
- Python 3.8+
- 8GB RAM
- CPU-only mode supported

### Recommended
- Python 3.9+
- 16GB+ RAM
- NVIDIA GPU with 8GB+ VRAM
- CUDA 11.0+

## Next Steps

- See [gogpt_architecture.md](gogpt_architecture.md) for technical details
- See [api_usage.md](api_usage.md) for comprehensive API documentation
- See [go_annotation.md](go_annotation.md) for GO annotation details
