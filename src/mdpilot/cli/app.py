"""Typer-based CLI application for MDPilot.

Usage examples::

    md run "What is the pH of a 0.1M acetate buffer?"
    md config
    md config --json
    md tools list
    md version
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.spinner import Spinner
from rich.live import Live
from rich.panel import Panel
from rich.markdown import Markdown

import litellm

litellm.suppress_debug_info = True
import logging

logging.getLogger("litellm").setLevel(logging.ERROR)

from mdpilot import __version__
from mdpilot.config import load_config
from mdpilot.config.schema import AppConfig
from mdpilot.agent import ReActLoop, EventEmitter, Event
from mdpilot.tools.amber_detector import detect_amber_env
from mdpilot.agent.events import (
    ITERATION_START,
    TOOL_CALL,
    TOOL_RESULT,
    LLM_RESPONSE,
    LOOP_END,
    ERROR,
)
from mdpilot.database.cli import db_app

# Application-wide console for consistent output styling
app = typer.Typer(
    name="mdpilot",
    help="MDPilot — AMBER molecular dynamics simulation agent",
    add_completion=False,
    no_args_is_help=False,
    invoke_without_command=True,
)
console = Console(stderr=False)

# Auto-detected AMBER environment (populated once at startup)
_amber_env = None


def _init_amber_env() -> None:
    """Detect and apply the local AMBER environment on first call."""
    global _amber_env
    if _amber_env is not None:
        return
    _amber_env = detect_amber_env(apply=True)
    if _amber_env.available:
        console.print(
            f"[dim]AMBER {(_amber_env.tools_version or '')}: "
            f"{_amber_env.amber_home} "
            f"({'GPU' if _amber_env.gpu_enabled else 'CPU'}, "
            f"{sum(1 for e in _amber_env.executables if e.available)} tools)[/dim]"
        )


@app.callback()
def main_callback(
    ctx: typer.Context,
) -> None:
    """Main callback - shows help when no subcommand is specified.

    When a subcommand (version, config, tools, run) is given, this callback
    returns early and lets the subcommand handler take over.
    """
    # Typer invokes the app callback before dispatching to subcommands.
    # If a subcommand was invoked, do nothing — let it handle the request.
    invoked = ctx.invoked_subcommand
    if invoked is not None:
        return

    # No subcommand provided - show help
    console.print(ctx.get_help())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_cli_overrides(
    model: str | None,
    base_url: str | None,
    api_key: str | None,
    max_iterations: int | None,
) -> dict:
    """Build a CLI-override dict from raw CLI arguments.

    Only non-None values are included so that unspecified flags fall through
    to the normal config layers (defaults → env → YAML → CLI).
    """
    overrides: dict = {}
    provider: dict = {}
    agent: dict = {}

    if model is not None:
        provider["model"] = model
    if base_url is not None:
        provider["base_url"] = base_url
    if api_key is not None:
        provider["api_key"] = api_key
    if max_iterations is not None:
        agent["max_iterations"] = max_iterations

    if provider:
        overrides["provider"] = provider
    if agent:
        overrides["agent"] = agent

    return overrides


def _print_version() -> None:
    """Print version string and exit."""
    console.print(f"mdpilot [bold]{__version__}[/bold]")
    raise typer.Exit()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command()
def version() -> None:
    """Show the mdpilot version."""
    _print_version()


@app.command("config")
def show_config(
    json_output: bool = typer.Option(
        False, "--json", help="Emit config as JSON instead of a human-readable summary."
    ),
    model: str | None = typer.Option(
        None, "--model", help="Override the LLM model (CLI layer)."
    ),
    base_url: str | None = typer.Option(
        None, "--base-url", help="Override the API base URL (CLI layer)."
    ),
    api_key: str | None = typer.Option(
        None, "--api-key", help="Override the API key (CLI layer)."
    ),
    max_iterations: int | None = typer.Option(
        None, "--max-iterations", help="Override max ReAct iterations (CLI layer)."
    ),
) -> None:
    """Print the merged configuration.

    By default shows a human-readable summary of all config layers.
    With ``--json`` emits the full validated AppConfig as JSON.
    """
    cli_overrides = _build_cli_overrides(model, base_url, api_key, max_iterations)
    cfg: AppConfig = load_config(cli_overrides=cli_overrides or None)

    if json_output:
        console.print_json(data=cfg.model_dump(mode='json'))
        return

    # Human-readable summary
    console.print(Panel("[bold]mdpilot configuration[/bold]", expand=False))

    # Provider section
    prov = cfg.provider
    console.print(f"\n[bold cyan]provider[/bold cyan]")
    console.print(f"  model        : {prov.model}")
    console.print(f"  base_url     : {prov.base_url or '(default)'}")
    console.print(f"  api_key      : {'***' if prov.api_key else '(none)'}")
    console.print(f"  temperature  : {prov.temperature}")
    console.print(f"  max_tokens   : {prov.max_tokens}")
    console.print(f"  timeout      : {prov.timeout}s")
    console.print(f"  max_retries  : {prov.max_retries}")

    # Amber section
    amber = cfg.amber
    console.print(f"\n[bold cyan]amber[/bold cyan]")
    console.print(f"  amber_home   : {amber.amber_home or '(none)'}")
    console.print(f"  tools_version: {amber.tools_version}")
    console.print(f"  gpu_enabled  : {amber.gpu_enabled}")

    # Agent section
    agent = cfg.agent
    console.print(f"\n[bold cyan]agent[/bold cyan]")
    console.print(f"  max_iterations    : {agent.max_iterations}")
    console.print(f"  max_context_tokens: {agent.max_context_tokens:,}")
    console.print(f"  default_mode      : {agent.default_mode}")
    console.print(f"  auto_confirm_steps: {agent.auto_confirm_steps}")


@app.command("tools")
def list_tools(
    model: str | None = typer.Option(None, "--model", help="Override the LLM model."),
    base_url: str | None = typer.Option(None, "--base-url", help="Override the API base URL."),
    api_key: str | None = typer.Option(None, "--api-key", help="Override the API key."),
    max_iterations: int | None = typer.Option(
        None, "--max-iterations", help="Override max ReAct iterations."
    ),
) -> None:
    """List all registered tools and their descriptions."""
    cli_overrides = _build_cli_overrides(model, base_url, api_key, max_iterations)
    cfg: AppConfig = load_config(cli_overrides=cli_overrides or None)

    # Build a ReActLoop just to get the tool registry (no LLM call)
    from mdpilot.tools.registry import ToolRegistry
    from mdpilot.tools.dispatcher import ToolDispatcher

    registry = ToolRegistry()
    registry.auto_discover("mdpilot.tools.builtin")

    tools = [
        (meta, fn)
        for meta, fn in (
            registry.get(name) or (None, None)
            for name in registry.list_tools()
        )
        if meta is not None
    ]

    if not tools:
        console.print("[yellow]No tools registered.[/yellow]")
        return

    table = Table(title="Registered Tools", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Category", style="dim")
    table.add_column("Description")

    for meta, _ in tools:
        table.add_row(meta.name, meta.category, meta.description)

    console.print(table)
    console.print(f"\n[dim]{len(tools)} tool(s) registered[/dim]")


@app.command()
def run(
    prompt: str = typer.Argument(..., help="The user query or task description."),
    model: str | None = typer.Option(None, "--model", help="Override the LLM model."),
    base_url: str | None = typer.Option(None, "--base-url", help="Override the API base URL."),
    api_key: str | None = typer.Option(None, "--api-key", help="Override the API key."),
    max_iterations: int | None = typer.Option(
        None, "--max-iterations", help="Override max ReAct iterations."
    ),
    stream: bool = typer.Option(False, "--stream", help="Stream LLM output in real time."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Emit verbose event log to stderr."),
) -> None:
    """Run a query through the ReAct loop and print the result.

    The loop reads configuration from the environment, project YAML, and user
    YAML, then applies any CLI overrides passed via the options below.
    """
    cli_overrides = _build_cli_overrides(model, base_url, api_key, max_iterations)
    cfg: AppConfig = load_config(cli_overrides=cli_overrides or None)

    # Initialise the ReAct loop
    loop = ReActLoop(cfg)

    # Collect events for verbose output
    verbose_events: list[str] = []

    def on_event(event: Event) -> None:
        if verbose:
            verbose_events.append(
                f"[dim][{event.type}] {', '.join(f'{k}={v!r}' for k, v in event.data.items())}[/dim]"
            )

    # Subscribe to all event types
    for _event_type in (ITERATION_START, TOOL_CALL, TOOL_RESULT, LLM_RESPONSE, LOOP_END, ERROR):
        loop.events.on(_event_type, on_event)

    # Run the loop
    if stream:
        _run_stream(loop, prompt, verbose_events)
    else:
        _run_normal(loop, prompt, verbose_events, verbose=verbose)


def _run_normal(
    loop: ReActLoop,
    prompt: str,
    verbose_events: list[str],
    verbose: bool = False,
) -> None:
    """Run the loop non-streaming, print the final result."""
    try:
        result = asyncio.run(loop.run(prompt, stream=False))
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    if verbose_events and verbose:
        console.print("\n[bold]Event log:[/bold]")
        for ev in verbose_events:
            console.print(ev)

    console.print("\n[bold green]Result:[/bold green]")
    console.print(Markdown(result))


def _run_stream(
    loop: ReActLoop,
    prompt: str,
    verbose_events: list[str],
) -> None:
    """Run the loop with streaming, showing a spinner then the result."""
    spinner = Spinner("dots2", text="Running agent...")
    result_container: list[str] = []

    def collector(event: Event) -> None:
        if event.type == LLM_RESPONSE:
            content = event.data.get("content", "")
            if content:
                result_container.append(content)
        elif verbose and event.type != LLM_RESPONSE:
            verbose_events.append(
                f"[dim][{event.type}] {', '.join(f'{k}={v!r}' for k, v in event.data.items())}[/dim]"
            )

    for _event_type in (ITERATION_START, TOOL_CALL, TOOL_RESULT, LLM_RESPONSE, LOOP_END, ERROR):
        loop.events.on(_event_type, collector)

    with Live(spinner, console=console, refresh_per_second=10):
        try:
            asyncio.run(loop.run(prompt, stream=True))
        except Exception as exc:
            console.print(f"\n[bold red]Error:[/bold red] {exc}")
            raise typer.Exit(code=1) from exc

    full = "".join(result_container)
    if verbose_events and verbose:
        console.print("\n[bold]Event log:[/bold]")
        for ev in verbose_events:
            console.print(ev)

    console.print("\n[bold green]Result:[/bold green]")
    console.print(Markdown(full))




# --------------------------------------------
# Database and other commands
# --------------------------------------

# Add database management commands
app.add_typer(db_app, name="db")

# Add BioReason and AlphaFold2 commands
from mdpilot.cli import bioreason_commands, alphafold2_commands
app.add_typer(bioreason_commands.app, name="bioreason")
app.add_typer(alphafold2_commands.app, name="alphafold2")

# ---------------------------------------------------------------------------
# Workflow templates
# ---------------------------------------------------------------------------

@app.command("workflows")
def list_workflows(
    category: str | None = typer.Option(None, "--category", "-c", help="Filter by category."),
) -> None:
    """List available AMBER workflow templates."""
    from mdpilot.workflows import list_templates
    _init_amber_env()
    templates = list_templates(category=category)
    if not templates:
        console.print("[dim]No workflow templates found.[/dim]")
        return

    table = Table(title="AMBER Workflow Templates", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="cyan")
    table.add_column("Category")
    table.add_column("Description")
    table.add_column("Est. Time")

    for t in templates:
        table.add_row(t["name"], t["category"], t["description"][:60], t["estimated_time"])
    console.print(table)


@app.command("prepare")
def prepare_system(
    pdb_id: str = typer.Argument(..., help="PDB ID (e.g., 2CAB) or path to PDB file"),
    output_dir: Path = typer.Option(
        Path.cwd(), "--output", "-o", help="Output directory for generated files"
    ),
    force_field: str = typer.Option("ff19SB", "--ff", help="Force field to use"),
    water_model: str = typer.Option("OPC", "--water", help="Water model (OPC, OPC3, TIP3P, etc.)"),
    box_type: str = typer.Option("octahedron", "--box", help="Box type (octahedron or cubic)"),
    box_padding: float = typer.Option(10.0, "--padding", help="Box padding in Angstroms"),
    minimize_steps: int = typer.Option(1000, "--steps", help="Minimization steps"),
) -> None:
    """Prepare a standard protein system from PDB ID or file.

    This command runs the complete workflow:
    1. Download PDB (if PDB ID given) or use existing file
    2. Clean PDB structure
    3. Run pdb4amber (fix residues, add missing atoms)
    4. Run reduce (add hydrogens)
    5. Build topology with tleap
    6. Energy minimization
    7. Validate system

    Example:
        amber prepare 2CAB --output ./2cab_system
        amber prepare my_protein.pdb --ff ff19SB --water OPC
    """
    from mdpilot.workflows import StandardProteinWorkflow, WorkflowConfig

    _init_amber_env()

    # Check if input is PDB ID or file path
    input_path = Path(pdb_id)
    is_file = input_path.exists() and input_path.is_file()

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Configure workflow
    config = WorkflowConfig(
        force_field=force_field,
        water_model=water_model,
        box_type=box_type,
        box_padding=box_padding,
        minimize_steps=minimize_steps,
        work_dir=output_dir,
        keep_intermediates=True,
    )

    workflow = StandardProteinWorkflow(config)

    # Run workflow with progress indicator
    console.print(f"\n[bold cyan]Preparing system: {pdb_id}[/bold cyan]")
    console.print(f"Output directory: {output_dir}\n")

    with console.status("[bold green]Running workflow...") as status:
        try:
            if is_file:
                status.update(f"[bold green]Processing PDB file: {input_path}")
                result = asyncio.run(workflow.run_from_pdb_file(input_path))
            else:
                status.update(f"[bold green]Downloading PDB: {pdb_id}")
                result = asyncio.run(workflow.run_from_pdb_id(pdb_id))
        except Exception as e:
            console.print(f"\n[bold red]Error:[/bold red] {e}")
            raise typer.Exit(1)

    # Display results
    console.print("\n" + "="*70)
    if result.success:
        console.print("[bold green]✓ Workflow completed successfully[/bold green]\n")

        console.print(f"[bold]Output files:[/bold]")
        console.print(f"  Topology:    {result.prmtop}")
        console.print(f"  Coordinates: {result.inpcrd}")

        if result.intermediate_files:
            console.print(f"\n[bold]Intermediate files:[/bold]")
            for name, path in result.intermediate_files.items():
                console.print(f"  {name:15s}: {path}")

        # Validation report
        if result.validation:
            console.print(f"\n[bold]Validation:[/bold]")

            table = Table(show_header=True, header_style="bold cyan", box=None)
            table.add_column("Check", style="cyan")
            table.add_column("Status", justify="center")
            table.add_column("Details")

            for check in result.validation.checks:
                status_icon = "✓" if check.passed else "✗"
                status_color = "green" if check.passed else "red"
                table.add_row(
                    check.name,
                    f"[{status_color}]{status_icon}[/{status_color}]",
                    check.message or ""
                )

            console.print(table)

            if result.validation.passed:
                console.print("\n[bold green]All validation checks passed![/bold green]")
            else:
                console.print("\n[bold yellow]Some validation checks failed. Review the details above.[/bold yellow]")
    else:
        console.print(f"[bold red]✗ Workflow failed[/bold red]\n")
        console.print(f"[red]Error: {result.error}[/red]")
        raise typer.Exit(1)

    console.print("="*70 + "\n")


# ---------------------------------------------------------------------------
# Entry point wired by pyproject.toml
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point — detect AMBER env, then run CLI."""
    _init_amber_env()
    app()


if __name__ == "__main__":
    main()
