"""BioReason-Pro CLI commands"""

import asyncio
from datetime import datetime

import typer
from rich.console import Console

from mdpilot.config import load_config
from mdpilot.config.defaults import DEFAULT_BIOREASON_REMOTE
from mdpilot.integrations.bioreason.celery_client import BioreasonCeleryClient
from mdpilot.ui.progress_tracker import TaskProgressTracker
from mdpilot.ui.result_panel import ResultPanel
from mdpilot.ui.rich_progress import RichProgressManager

app = typer.Typer(name="bioreason", help="BioReason-Pro protein function annotation")
console = Console()
result_panel = ResultPanel()


@app.command("annotate")
def annotate(
    sequence: str = typer.Argument(..., help="Protein amino acid sequence"),
    organism: str = typer.Option(
        "Homo sapiens (Human)",
        "--organism", "-o",
        help="Organism name (e.g., 'Homo sapiens (Human)')"
    ),
):
    """Annotate protein function with BioReason-Pro"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_output_dir = "/home/6-FF/changshengjie/project/mdpilot/output"
    timestamped_output_dir = f"{base_output_dir}/bioreason_{timestamp}"
    
    cfg = load_config()
    remote = cfg.bioreason_remote.model_dump() if cfg.bioreason_remote else DEFAULT_BIOREASON_REMOTE

    client = BioreasonCeleryClient(**remote)
    tracker = TaskProgressTracker()
    
    async def run_annotation():
        await client.connect()
        try:
            task_id = f"bioreason_{sequence[:10]}"
            tracker.add_task(task_id, f"Annotating {len(sequence)} aa sequence", total_steps=4)
            
            with RichProgressManager(tracker) as progress_mgr:
                async def progress_callback(progress):
                    tracker.update_progress(task_id, progress)
                    progress_mgr.refresh()
                
                result = await client.annotate(
                    sequence, organism, 
                    output_dir=timestamped_output_dir,
                    progress_callback=progress_callback
                )
            
            return result
        finally:
            await client.disconnect()
    
    result = asyncio.run(run_annotation())
    
    console.print("\n[bold cyan]BioReason Annotation Results[/bold cyan]")
    console.print(f"Sequence length: {len(sequence)} aa")
    console.print(f"Organism: {organism}\n")
    
    go_terms = result.get("go_terms", {})
    table_data = [
        {
            "Aspect": "MF (Molecular Function)",
            "Terms": ", ".join(go_terms.get("MF", [])),
        },
        {
            "Aspect": "BP (Biological Process)",
            "Terms": ", ".join(go_terms.get("BP", [])),
        },
        {
            "Aspect": "CC (Cellular Component)",
            "Terms": ", ".join(go_terms.get("CC", [])),
        },
    ]
    
    result_panel.display_table(table_data, "GO Terms")
    result_panel.display_success("Annotation completed successfully")


@app.command("test")
def test():
    """Test BioReason connection and worker status"""
    
    config = {
        "ssh": {"host": "lab06", "username": "zhao", "key_path": "~/.ssh/id_rsa"},
        "celery": {
            "broker_url": "redis://localhost:6379/0",
            "backend_url": "redis://localhost:6379/1",
            "task_timeout": 300,
            "poll_interval": 2
        },
        "work_dir": "/home/6-FF/luo/BioReason-Pro",
        "conda_env": "bioreason"
    }
    
    client = BioreasonCeleryClient(**config)
    
    async def test_connection():
        console.print("[yellow]Testing BioReason connection...[/yellow]")
        await client.connect()
        try:
            # Test with short sequence
            test_seq = "MVLSPADKTN"
            console.print(f"Submitting test task (sequence: {test_seq})...")
            result = await client.annotate(test_seq, "Homo sapiens (Human)")
            console.print("[green]✓ Connection successful[/green]")
            bp_terms = result.get('go_terms', {}).get('BP', [])
            console.print(f"Test result: {len(bp_terms)} BP terms found")
        finally:
            await client.disconnect()
    
    asyncio.run(test_connection())
