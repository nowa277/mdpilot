"""AlphaFold2 protein structure prediction tool"""

from mdpilot.config import load_config
from mdpilot.config.defaults import DEFAULT_ALPHAFOLD2_REMOTE
from mdpilot.tools.decorator import tool
from mdpilot.integrations.alphafold2.celery_client import AlphaFold2CeleryClient


@tool(
    name="alphafold2_predict",
    description="Predict protein 3D structure using AlphaFold2. Returns PDB file path and confidence scores (pLDDT). Note: Prediction time varies with sequence length and db_preset (reduced_dbs: 5-10min for 100aa if small_bfd available, full_dbs: 30min-2hr for 100aa).",
    category="structure"
)
async def alphafold2_predict_tool(
    sequence: str, 
    job_name: str = "prediction",
    db_preset: str = "full_dbs"
) -> dict:
    """Predict protein structure with AlphaFold2
    
    Args:
        sequence: Protein amino acid sequence (single-letter code)
        job_name: Job name for output files (default: 'prediction')
        db_preset: Database preset for MSA search (default: 'full_dbs')
            - 'full_dbs': Full accuracy mode, 30min-2hr for 100aa (default, always available)
            - 'reduced_dbs': Fast mode, 5-10 min for 100aa (requires small_bfd database)
            - 'casp14': CASP14 competition mode, 30-40 min for 100aa
        
    Returns:
        Dictionary with prediction results:
            - success: bool
            - best_model: str (path to best PDB file)
            - avg_plddt: float (average confidence score)
            - output_dir: str (output directory)
            - sequence_length: int
            - num_models: int
            - db_preset: str (database preset used)
    """
    config = load_config()
    remote = config.alphafold2_remote.model_dump() if config.alphafold2_remote else DEFAULT_ALPHAFOLD2_REMOTE
    
    client = AlphaFold2CeleryClient(**remote)
    await client.connect()
    
    try:
        result = await client.predict(sequence, job_name, db_preset=db_preset)
        return result
    finally:
        await client.disconnect()
