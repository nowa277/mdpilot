"""BioReason-Pro protein function annotation tool"""

from mdpilot.config import load_config
from mdpilot.config.defaults import DEFAULT_BIOREASON_REMOTE
from mdpilot.tools.decorator import tool
from mdpilot.integrations.bioreason.celery_client import BioreasonCeleryClient


@tool(
    name="bioreason_annotate",
    description="Annotate protein function using BioReason-Pro. Returns GO terms (Molecular Function, Biological Process, Cellular Component) for the given protein sequence.",
    category="analysis"
)
async def bioreason_annotate_tool(sequence: str, organism: str = "Homo sapiens (Human)") -> dict:
    """Annotate protein function with BioReason-Pro
    
    Args:
        sequence: Protein amino acid sequence (single-letter code)
        organism: Organism name in format 'Species name (Common name)', e.g., 'Homo sapiens (Human)'
        
    Returns:
        Dictionary with GO terms:
            - go_terms: dict with MF, BP, CC lists
            - metadata: dict with organism and sequence_length
    """
    config = load_config()
    remote = config.bioreason_remote.model_dump() if config.bioreason_remote else DEFAULT_BIOREASON_REMOTE
    
    client = BioreasonCeleryClient(**remote)
    await client.connect()
    
    try:
        result = await client.annotate(sequence, organism)
        return result
    finally:
        await client.disconnect()
