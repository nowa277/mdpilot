"""AlphaFold2 CLI commands"""

import asyncio
from datetime import datetime

import typer
from rich.console import Console

from mdpilot.config import load_config
from mdpilot.config.defaults import DEFAULT_ALPHAFOLD2_REMOTE
from mdpilot.integrations.alphafold2.celery_client import AlphaFold2CeleryClient
from mdpilot.ui.progress_tracker import TaskProgressTracker
from mdpilot.ui.result_panel import ResultPanel
from mdpilot.ui.rich_progress import RichProgressManager

app = typer.Typer(name="alphafold2", help="AlphaFold2 protein structure prediction")
console = Console()
result_panel = ResultPanel()


@app.command("predict")
def predict(
    sequence: str = typer.Argument(..., help="Protein amino acid sequence"),
    job_name: str = typer.Option(
        "prediction",
        "--name", "-n",
        help="Job name for output files"
    ),
):
    """Predict protein structure with AlphaFold2"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_output_dir = "/home/2-BB/changshengjie/predictions"
    timestamped_output_dir = f"{base_output_dir}/alphafold2_{job_name}_{timestamp}"
    
    cfg = load_config()
    remote = cfg.alphafold2_remote.model_dump() if cfg.alphafold2_remote else DEFAULT_ALPHAFOLD2_REMOTE
    
    client = AlphaFold2CeleryClient(**remote)
    tracker = TaskProgressTracker()
    
    async def run_prediction():
        await client.connect()
        try:
            console.print("\n[bold cyan]AlphaFold2 Structure Prediction[/bold cyan]")
            console.print(f"Sequence length: {len(sequence)} aa")
            console.print(f"Job name: {job_name}\n")
            
            task_id = f"alphafold2_{job_name}"
            tracker.add_task(task_id, f"Predicting structure for {job_name}", total_steps=5)
            
            with RichProgressManager(tracker) as progress_mgr:
                async def progress_callback(progress):
                    tracker.update_progress(task_id, progress)
                    progress_mgr.refresh()
                
                result = await client.predict(
                    sequence, job_name, output_dir=timestamped_output_dir, progress_callback=progress_callback
                )
            
            return result
        finally:
            await client.disconnect()
    
    result = asyncio.run(run_prediction())
    
    result_panel.display_success("Prediction completed successfully")
    console.print("\n[bold]Results:[/bold]")
    console.print(f"  Best Model: {result['best_model']}")
    console.print(f"  Avg pLDDT: {result['avg_plddt']:.2f}")
    console.print(f"  Output Dir: {result['output_dir']}")
    console.print(f"  Models Generated: {result['num_models']}\n")


@app.command("test")
def test():
    """Test AlphaFold2 connection and worker status"""
    
    config = {
        "ssh": {"host": "lab02", "username": "zhao", "key_path": "~/.ssh/id_rsa"},
        "celery": {
            "broker_url": "redis://localhost:6379/2",
            "backend_url": "redis://localhost:6379/3",
            "task_timeout": 14400,
            "poll_interval": 5
        },
        "work_dir": "/home/2-BB/changshengjie/project/mdpilot",
        "conda_env": "af2_py310"
    }

    client = AlphaFold2CeleryClient(**config)

    async def test_connection():
        console.print("[yellow]Testing AlphaFold2 connection...[/yellow]")
        await client.connect()
        try:
            console.print("[green]✓ SSH connection successful[/green]")
            console.print(f"Connected to: {config['ssh']['host']}")
            console.print(f"Work directory: {config['work_dir']}")
        finally:
            await client.disconnect()
    
    asyncio.run(test_connection())
