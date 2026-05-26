"""Database CLI commands for MDPilot.

Provides commands for database initialization, migrations, seeding, and management.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import typer
from alembic import command
from alembic.config import Config
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlalchemy import text

from mdpilot.config import load_config
from mdpilot.database import init_db, get_engine, dispose_engine

console = Console()

# Create a Typer app for database commands
db_app = typer.Typer(
    name="db",
    help="Database management commands",
    add_completion=False,
    no_args_is_help=True,
)


def get_alembic_config() -> Config:
    """Get Alembic configuration object.

    Returns:
        Configured Alembic Config object.
    """
    # Find alembic.ini in project root
    project_root = Path(__file__).parent.parent.parent.parent
    alembic_ini = project_root / "alembic.ini"

    if not alembic_ini.exists():
        console.print(f"[red]Error: alembic.ini not found at {alembic_ini}[/red]")
        raise typer.Exit(1)

    config = Config(str(alembic_ini))

    # Set database URL from application config
    app_config = load_config()
    config.set_main_option("sqlalchemy.url", app_config.database.url)

    return config


@db_app.command("init")
def init_database() -> None:
    """Initialize the database (create tables without migrations).

    This creates all tables defined in the models. Use this for initial setup
    or testing. For production, use 'db upgrade' instead.
    """
    console.print("[cyan]Initializing database...[/cyan]")

    try:
        app_config = load_config()
        init_db(app_config.database)

        async def create_tables():
            from mdpilot.database.base import Base
            from mdpilot.database.models import Chat, Message, Task  # noqa: F401

            engine = get_engine()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            await dispose_engine()

        asyncio.run(create_tables())
        console.print("[green]✓ Database initialized successfully[/green]")

    except Exception as e:
        console.print(f"[red]✗ Failed to initialize database: {e}[/red]")
        raise typer.Exit(1)


@db_app.command("migrate")
def create_migration(
    message: str = typer.Argument(..., help="Migration message"),
    autogenerate: bool = typer.Option(True, "--autogenerate/--no-autogenerate", help="Auto-generate migration from models"),
) -> None:
    """Create a new migration script.

    Example:
        mdpilot db migrate "add user table"
    """
    console.print(f"[cyan]Creating migration: {message}[/cyan]")

    try:
        config = get_alembic_config()
        command.revision(config, message=message, autogenerate=autogenerate)
        console.print("[green]✓ Migration created successfully[/green]")

    except Exception as e:
        console.print(f"[red]✗ Failed to create migration: {e}[/red]")
        raise typer.Exit(1)


@db_app.command("upgrade")
def upgrade_database(
    revision: str = typer.Argument("head", help="Target revision (default: head)"),
) -> None:
    """Upgrade database to a specific revision.

    Example:
        mdpilot db upgrade          # Upgrade to latest
        mdpilot db upgrade +1       # Upgrade one version
        mdpilot db upgrade abc123   # Upgrade to specific revision
    """
    console.print(f"[cyan]Upgrading database to {revision}...[/cyan]")

    try:
        config = get_alembic_config()
        command.upgrade(config, revision)
        console.print("[green]✓ Database upgraded successfully[/green]")

    except Exception as e:
        console.print(f"[red]✗ Failed to upgrade database: {e}[/red]")
        raise typer.Exit(1)


@db_app.command("downgrade")
def downgrade_database(
    revision: str = typer.Argument("-1", help="Target revision (default: -1)"),
) -> None:
    """Downgrade database to a specific revision.

    Example:
        mdpilot db downgrade        # Downgrade one version
        mdpilot db downgrade -2     # Downgrade two versions
        mdpilot db downgrade abc123 # Downgrade to specific revision
    """
    console.print(f"[yellow]⚠ Downgrading database to {revision}...[/yellow]")

    confirm = typer.confirm("Are you sure you want to downgrade the database?")
    if not confirm:
        console.print("[dim]Cancelled[/dim]")
        raise typer.Exit(0)

    try:
        config = get_alembic_config()
        command.downgrade(config, revision)
        console.print("[green]✓ Database downgraded successfully[/green]")

    except Exception as e:
        console.print(f"[red]✗ Failed to downgrade database: {e}[/red]")
        raise typer.Exit(1)


@db_app.command("current")
def show_current_revision() -> None:
    """Show current database revision."""
    try:
        config = get_alembic_config()
        command.current(config, verbose=True)

    except Exception as e:
        console.print(f"[red]✗ Failed to get current revision: {e}[/red]")
        raise typer.Exit(1)


@db_app.command("history")
def show_migration_history(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed history"),
) -> None:
    """Show migration history."""
    try:
        config = get_alembic_config()
        command.history(config, verbose=verbose)

    except Exception as e:
        console.print(f"[red]✗ Failed to get migration history: {e}[/red]")
        raise typer.Exit(1)


@db_app.command("seed")
def seed_database(
    clear: bool = typer.Option(False, "--clear", help="Clear existing data before seeding"),
) -> None:
    """Seed the database with development data.

    Creates sample chats, messages, and tasks for testing and development.
    """
    console.print("[cyan]Seeding database...[/cyan]")

    if clear:
        confirm = typer.confirm("⚠ This will delete all existing data. Continue?")
        if not confirm:
            console.print("[dim]Cancelled[/dim]")
            raise typer.Exit(0)

    try:
        from mdpilot.database.seed import seed_data

        app_config = load_config()
        init_db(app_config.database)

        asyncio.run(seed_data(clear=clear))

        console.print("[green]✓ Database seeded successfully[/green]")

    except Exception as e:
        console.print(f"[red]✗ Failed to seed database: {e}[/red]")
        raise typer.Exit(1)


@db_app.command("reset")
def reset_database() -> None:
    """Drop all tables and recreate them (DEVELOPMENT ONLY).

    ⚠ WARNING: This will delete ALL data in the database!
    """
    console.print(Panel(
        "[bold red]⚠ WARNING ⚠[/bold red]\n\n"
        "This will DROP ALL TABLES and DELETE ALL DATA!\n"
        "This command should only be used in development.",
        title="Destructive Operation",
        border_style="red"
    ))

    confirm = typer.confirm("Are you absolutely sure you want to reset the database?")
    if not confirm:
        console.print("[dim]Cancelled[/dim]")
        raise typer.Exit(0)

    # Double confirmation
    confirm2 = typer.confirm("Type 'yes' to confirm", default=False)
    if not confirm2:
        console.print("[dim]Cancelled[/dim]")
        raise typer.Exit(0)

    try:
        app_config = load_config()
        init_db(app_config.database)

        async def drop_and_create():
            from mdpilot.database.base import Base
            from mdpilot.database.models import Chat, Message, Task  # noqa: F401

            engine = get_engine()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                console.print("[yellow]✓ All tables dropped[/yellow]")
                await conn.run_sync(Base.metadata.create_all)
                console.print("[green]✓ All tables recreated[/green]")
            await dispose_engine()

        asyncio.run(drop_and_create())

        # Reset Alembic version table
        console.print("[cyan]Resetting migration history...[/cyan]")
        config = get_alembic_config()
        command.stamp(config, "head")

        console.print("[green]✓ Database reset successfully[/green]")

    except Exception as e:
        console.print(f"[red]✗ Failed to reset database: {e}[/red]")
        raise typer.Exit(1)


@db_app.command("check")
def check_database() -> None:
    """Check database connectivity and status.

    Verifies connection, shows pool statistics, and current migration version.
    """
    console.print("[cyan]Checking database...[/cyan]\n")

    try:
        app_config = load_config()
        init_db(app_config.database)

        async def check():
            engine = get_engine()

            # Test connection
            try:
                async with engine.connect() as conn:
                    result = await conn.execute(text("SELECT 1"))
                    await result.fetchone()
                connection_status = "[green]✓ Connected[/green]"
            except Exception as e:
                connection_status = f"[red]✗ Failed: {e}[/red]"

            # Get pool stats
            pool = engine.pool
            pool_size = pool.size()
            checked_in = pool.checkedin()
            checked_out = pool.checkedout()
            overflow = pool.overflow()

            await dispose_engine()

            return {
                "connection": connection_status,
                "pool_size": pool_size,
                "checked_in": checked_in,
                "checked_out": checked_out,
                "overflow": overflow,
            }

        stats = asyncio.run(check())

        # Display results
        table = Table(title="Database Status", show_header=True, header_style="bold cyan")
        table.add_column("Property", style="cyan")
        table.add_column("Value")

        table.add_row("Connection", stats["connection"])
        table.add_row("Database URL", app_config.database.url.split("@")[-1])  # Hide credentials
        table.add_row("Pool Size", str(stats["pool_size"]))
        table.add_row("Connections (In)", str(stats["checked_in"]))
        table.add_row("Connections (Out)", str(stats["checked_out"]))
        table.add_row("Overflow", str(stats["overflow"]))

        console.print(table)

        # Show current migration
        console.print("\n[bold]Current Migration:[/bold]")
        config = get_alembic_config()
        command.current(config)

    except Exception as e:
        console.print(f"[red]✗ Database check failed: {e}[/red]")
        raise typer.Exit(1)
