# Gene Ontology (GO) Annotation Guide

## What is Gene Ontology?

Gene Ontology (GO) is a comprehensive, structured vocabulary for describing gene and protein functions across all species. It provides a standardized way to annotate biological knowledge.

## Three GO Ontologies

### 1. Molecular Function (MF)

**Definition**: Biochemical activities at the molecular level

**Examples:**
- `GO:0005524` - ATP binding
- `GO:0004672` - protein kinase activity
- `GO:0003677` - DNA binding
- `GO:0016491` - oxidoreductase activity
- `GO:0008270` - zinc ion binding

**Characteristics:**
- Describes what a protein does biochemically
- Independent of when, where, or why it acts
- Often corresponds to single protein domains
- Can be measured in vitro

**Use in MDPilot:**
- Identify catalytic residues for MD simulations
- Predict substrate binding sites
- Inform force field parameterization
- Guide ligand docking studies

### 2. Biological Process (BP)

**Definition**: Larger biological programs accomplished by multiple molecular activities

**Examples:**
- `GO:0006412` - translation
- `GO:0006468` - protein phosphorylation
- `GO:0007165` - signal transduction
- `GO:0006281` - DNA repair
- `GO:0051301` - cell division

**Characteristics:**
- Describes biological objectives
- Often involves multiple gene products
- Has a defined beginning and end
- Context-dependent

**Use in MDPilot:**
- Understand protein's biological context
- Identify interaction partners
- Predict regulatory mechanisms
- Guide pathway analysis

### 3. Cellular Component (CC)

**Definition**: Locations where gene products are active

**Examples:**
- `GO:0005634` - nucleus
- `GO:0005886` - plasma membrane
- `GO:0005739` - mitochondrion
- `GO:0005576` - extracellular region
- `GO:0016020` - membrane

**Characteristics:**
- Describes subcellular localization
- Can be organelles, complexes, or regions
- May indicate protein trafficking
- Important for understanding function

**Use in MDPilot:**
- Determine simulation environment (membrane, solvent, etc.)
- Predict post-translational modifications
- Identify protein-protein interaction contexts
- Guide system setup for MD

## GO Term Structure

### Hierarchical Organization

GO terms are organized as a Directed Acyclic Graph (DAG):

```
GO:0003674 (molecular_function) [root]
    ├─ GO:0003824 (catalytic activity)
    │   ├─ GO:0016740 (transferase activity)
    │   │   ├─ GO:0016301 (kinase activity)
    │   │   │   └─ GO:0004672 (protein kinase activity)
    │   │   │       └─ GO:0004674 (protein serine/threonine kinase activity)
    │   │   └─ GO:0016772 (transferase activity, transferring phosphorus)
    │   └─ GO:0016787 (hydrolase activity)
    └─ GO:0005488 (binding)
        ├─ GO:0043167 (ion binding)
        │   └─ GO:0046872 (metal ion binding)
        │       └─ GO:0008270 (zinc ion binding)
        └─ GO:0097159 (organic cyclic compound binding)
```

### GO Term Anatomy

```
GO:0004672 - protein kinase activity
│
├─ GO ID: Unique identifier
├─ Name: Human-readable term
├─ Namespace: molecular_function, biological_process, or cellular_component
├─ Definition: "Catalyzes the phosphorylation of proteins"
├─ Parents: [GO:0016301, GO:0016772]
├─ Children: [GO:0004674, GO:0004713, ...]
└─ Relationships: is_a, part_of, regulates, etc.
```

## GO Evidence Codes

### Experimental Evidence (Most Reliable)

| Code | Name | Description |
|------|------|-------------|
| EXP | Inferred from Experiment | Direct experimental evidence |
| IDA | Inferred from Direct Assay | Direct assay of function |
| IPI | Inferred from Physical Interaction | Protein-protein interaction |
| IMP | Inferred from Mutant Phenotype | Mutation affects function |
| IGI | Inferred from Genetic Interaction | Genetic interaction data |
| IEP | Inferred from Expression Pattern | Expression pattern evidence |

### Computational Evidence

| Code | Name | Description |
|------|------|-------------|
| ISS | Inferred from Sequence Similarity | Homology-based |
| ISO | Inferred from Sequence Orthology | Ortholog annotation |
| ISA | Inferred from Sequence Alignment | Alignment-based |
| ISM | Inferred from Sequence Model | Domain/motif based |
| IEA | Inferred from Electronic Annotation | Automated prediction |

**GogPT predictions use IEA evidence code**

## Working with GO Annotations

### Loading GO Hierarchy

```python
from goatools import obo_parser

# Download GO ontology
# wget http://purl.obolibrary.org/obo/go-basic.obo

# Load GO DAG
go_dag = obo_parser.GODag("go-basic.obo")

# Access GO term
go_term = go_dag["GO:0004672"]
print(f"Name: {go_term.name}")
print(f"Namespace: {go_term.namespace}")
print(f"Definition: {go_term.defn}")
print(f"Parents: {[p.id for p in go_term.parents]}")
print(f"Children: {[c.id for c in go_term.children]}")
```

### Navigating GO Hierarchy

```python
def get_all_ancestors(go_id, go_dag):
    """Get all ancestor terms (parent, grandparent, etc.)."""
    ancestors = set()
    
    def recurse(term_id):
        if term_id in go_dag:
            term = go_dag[term_id]
            for parent in term.parents:
                ancestors.add(parent.id)
                recurse(parent.id)
    
    recurse(go_id)
    return ancestors

def get_all_descendants(go_id, go_dag):
    """Get all descendant terms (children, grandchildren, etc.)."""
    descendants = set()
    
    def recurse(term_id):
        if term_id in go_dag:
            term = go_dag[term_id]
            for child in term.children:
                descendants.add(child.id)
                recurse(child.id)
    
    recurse(go_id)
    return descendants

# Usage
kinase_ancestors = get_all_ancestors("GO:0004672", go_dag)
print(f"Protein kinase has {len(kinase_ancestors)} ancestor terms")
```

### GO Term Enrichment Analysis

```python
from goatools.goea.go_enrichment_ns import GOEnrichmentStudyNS

def perform_go_enrichment(
    study_genes,
    population_genes,
    gene_to_go_mapping,
    go_dag
):
    """
    Perform GO enrichment analysis.
    
    Args:
        study_genes: List of genes of interest
        population_genes: Background gene set
        gene_to_go_mapping: Dict mapping genes to GO terms
        go_dag: GO DAG object
        
    Returns:
        Enrichment results
    """
    goeaobj = GOEnrichmentStudyNS(
        population_genes,
        gene_to_go_mapping,
        go_dag,
        propagate_counts=True,
        alpha=0.05,
        methods=['fdr_bh']
    )
    
    results = goeaobj.run_study(study_genes)
    
    # Filter significant results
    significant = [r for r in results if r.p_fdr_bh < 0.05]
    
    return significant

# Usage
enriched_terms = perform_go_enrichment(
    study_genes=['GENE1', 'GENE2', 'GENE3'],
    population_genes=all_genes,
    gene_to_go_mapping=gene_go_map,
    go_dag=go_dag
)

for result in enriched_terms[:10]:
    print(f"{result.GO}: {result.name} (p={result.p_fdr_bh:.2e})")
```

## Interpreting GogPT Predictions

### Confidence Thresholds

| Score Range | Interpretation | Recommended Action |
|-------------|----------------|-------------------|
| 0.9 - 1.0 | Very high confidence | Trust prediction |
| 0.7 - 0.9 | High confidence | Likely correct |
| 0.5 - 0.7 | Moderate confidence | Validate if critical |
| 0.3 - 0.5 | Low confidence | Use with caution |
| 0.0 - 0.3 | Very low confidence | Likely incorrect |

### Prediction Analysis

```python
def analyze_go_predictions(predictions, go_dag):
    """Comprehensive analysis of GO predictions."""
    
    analysis = {
        'summary': {},
        'high_confidence': {},
        'functional_categories': {},
        'specificity': {}
    }
    
    for ontology, terms in predictions.items():
        # Count predictions by confidence
        high_conf = [t for t in terms if t['score'] > 0.7]
        moderate_conf = [t for t in terms if 0.5 <= t['score'] <= 0.7]
        
        analysis['summary'][ontology] = {
            'total': len(terms),
            'high_confidence': len(high_conf),
            'moderate_confidence': len(moderate_conf)
        }
        
        # Identify most specific terms (deepest in hierarchy)
        if high_conf:
            specific_terms = []
            for term in high_conf:
                go_term = go_dag.get(term['go_id'])
                if go_term:
                    term['level'] = go_term.level
                    specific_terms.append(term)
            
            # Sort by level (deeper = more specific)
            specific_terms.sort(key=lambda x: x.get('level', 0), reverse=True)
            analysis['specificity'][ontology] = specific_terms[:5]
    
    return analysis

# Usage
analysis = analyze_go_predictions(predictions, go_dag)

print(f"Molecular Function: {analysis['summary']['molecular_function']['high_confidence']} high-confidence predictions")
print(f"Most specific MF term: {analysis['specificity']['molecular_function'][0]['name']}")
```

### Functional Similarity

```python
from goatools.semantic import semantic_similarity

def compute_functional_similarity(go_terms1, go_terms2, go_dag):
    """
    Compute functional similarity between two sets of GO terms.
    
    Uses Resnik semantic similarity.
    """
    similarities = []
    
    for term1 in go_terms1:
        for term2 in go_terms2:
            sim = semantic_similarity(term1, term2, go_dag)
            similarities.append(sim)
    
    if similarities:
        return max(similarities)  # Best match
    return 0.0

# Compare two proteins
protein1_go = ['GO:0004672', 'GO:0005524', 'GO:0005634']
protein2_go = ['GO:0004674', 'GO:0005524', 'GO:0005737']

similarity = compute_functional_similarity(protein1_go, protein2_go, go_dag)
print(f"Functional similarity: {similarity:.3f}")
```

## Integration with MDPilot Workflows

### Functional Annotation Pipeline

```python
class FunctionalAnnotationPipeline:
    """Complete functional annotation pipeline."""
    
    def __init__(self, gogpt_model, go_dag):
        self.gogpt = gogpt_model
        self.go_dag = go_dag
    
    def annotate_protein(self, sequence, protein_id=None):
        """
        Complete functional annotation.
        
        Returns:
            Comprehensive annotation report
        """
        # Predict GO terms
        predictions = self.gogpt.predict(sequence)
        
        # Analyze predictions
        analysis = analyze_go_predictions(predictions, self.go_dag)
        
        # Extract key functions
        key_functions = self._extract_key_functions(predictions)
        
        # Determine simulation requirements
        sim_requirements = self._determine_simulation_requirements(
            predictions
        )
        
        return {
            'protein_id': protein_id,
            'predictions': predictions,
            'analysis': analysis,
            'key_functions': key_functions,
            'simulation_requirements': sim_requirements
        }
    
    def _extract_key_functions(self, predictions):
        """Extract most important functional annotations."""
        key_functions = {}
        
        # Molecular function - highest confidence
        mf_terms = predictions['molecular_function']
        if mf_terms:
            key_functions['primary_activity'] = mf_terms[0]
        
        # Biological process - most specific
        bp_terms = predictions['biological_process']
        specific_bp = [t for t in bp_terms if t['score'] > 0.6]
        if specific_bp:
            key_functions['biological_role'] = specific_bp[0]
        
        # Cellular component - localization
        cc_terms = predictions['cellular_component']
        if cc_terms:
            key_functions['localization'] = cc_terms[0]
        
        return key_functions
    
    def _determine_simulation_requirements(self, predictions):
        """Determine MD simulation requirements from GO annotations."""
        requirements = {
            'environment': 'aqueous',
            'cofactors': [],
            'special_considerations': []
        }
        
        # Check cellular component
        cc_terms = predictions['cellular_component']
        for term in cc_terms:
            if term['score'] > 0.5:
                if 'membrane' in term['name'].lower():
                    requirements['environment'] = 'membrane'
                elif 'nucleus' in term['name'].lower():
                    requirements['special_considerations'].append(
                        'nuclear_protein'
                    )
        
        # Check molecular function for cofactors
        mf_terms = predictions['molecular_function']
        for term in mf_terms:
            if term['score'] > 0.5:
                if 'metal' in term['name'].lower():
                    requirements['cofactors'].append('metal_ions')
                if 'ATP' in term['name']:
                    requirements['cofactors'].append('ATP')
                if 'DNA' in term['name']:
                    requirements['cofactors'].append('DNA')
        
        return requirements

# Usage
pipeline = FunctionalAnnotationPipeline(gogpt_model, go_dag)
annotation = pipeline.annotate_protein(sequence, protein_id="PROT001")

print(f"Primary activity: {annotation['key_functions']['primary_activity']['name']}")
print(f"Simulation environment: {annotation['simulation_requirements']['environment']}")
```

## GO Annotation Best Practices

### 1. Use Multiple Evidence Sources

Combine GogPT predictions with:
- Sequence homology (BLAST)
- Domain annotations (InterProScan)
- Literature curation
- Experimental data

### 2. Validate Critical Predictions

For important decisions:
- Check multiple prediction tools
- Verify with literature
- Consider experimental validation

### 3. Respect GO Hierarchy

- Specific terms are more informative
- General terms are more reliable
- Use appropriate level for your application

### 4. Consider Confidence Scores

- Set appropriate thresholds for your use case
- Higher thresholds for critical applications
- Lower thresholds for exploratory analysis

### 5. Update Regularly

- GO is continuously updated
- New terms added regularly
- Annotations refined over time

## Resources

- **GO Consortium**: http://geneontology.org
- **GO Browser**: https://amigo.geneontology.org
- **QuickGO**: https://www.ebi.ac.uk/QuickGO/
- **GOtools Python package**: https://github.com/tanghaibao/goatools
- **GO Documentation**: http://geneontology.org/docs/
