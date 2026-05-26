"""Database seeding utilities for development and testing.

Provides functions to populate the database with sample data.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from rich.console import Console

from mdpilot.database import get_session_factory
from mdpilot.database.models import Chat, Message, Task

console = Console()


async def seed_data(clear: bool = False) -> None:
    """Seed the database with sample data.

    Args:
        clear: If True, delete all existing data before seeding.
    """
    session_factory = get_session_factory()

    async with session_factory() as session:
        if clear:
            console.print("[yellow]Clearing existing data...[/yellow]")
            # Delete in correct order (respecting foreign keys)
            await session.execute(Message.__table__.delete())
            await session.execute(Chat.__table__.delete())
            await session.execute(Task.__table__.delete())
            await session.commit()
            console.print("[dim]✓ Existing data cleared[/dim]")

        # Create sample chats
        console.print("[cyan]Creating sample chats...[/cyan]")

        chat1 = Chat(
            id=str(uuid4()),
            title="Protein Structure Analysis",
            created_at=datetime.utcnow() - timedelta(days=2),
            updated_at=datetime.utcnow() - timedelta(hours=3),
        )

        chat2 = Chat(
            id=str(uuid4()),
            title="MD Simulation Setup",
            created_at=datetime.utcnow() - timedelta(days=1),
            updated_at=datetime.utcnow() - timedelta(minutes=30),
        )

        chat3 = Chat(
            id=str(uuid4()),
            title="Force Field Selection",
            created_at=datetime.utcnow() - timedelta(hours=5),
            updated_at=datetime.utcnow() - timedelta(minutes=10),
        )

        session.add_all([chat1, chat2, chat3])
        await session.flush()

        # Create sample messages for chat1
        console.print("[cyan]Creating sample messages...[/cyan]")

        messages_chat1 = [
            Message(
                id=str(uuid4()),
                chat_id=chat1.id,
                role="user",
                content="Can you help me analyze the structure of protein 1ABC?",
                created_at=datetime.utcnow() - timedelta(days=2),
            ),
            Message(
                id=str(uuid4()),
                chat_id=chat1.id,
                role="assistant",
                content="I'll help you analyze protein 1ABC. Let me fetch the structure from the PDB database and examine its key features.",
                created_at=datetime.utcnow() - timedelta(days=2, minutes=-2),
            ),
            Message(
                id=str(uuid4()),
                chat_id=chat1.id,
                role="user",
                content="What force field would you recommend for this protein?",
                created_at=datetime.utcnow() - timedelta(hours=3, minutes=5),
            ),
            Message(
                id=str(uuid4()),
                chat_id=chat1.id,
                role="assistant",
                content="For this protein, I recommend using the ff19SB force field with the OPC water model. This combination provides excellent accuracy for protein simulations.",
                created_at=datetime.utcnow() - timedelta(hours=3),
            ),
        ]

        # Create sample messages for chat2
        messages_chat2 = [
            Message(
                id=str(uuid4()),
                chat_id=chat2.id,
                role="user",
                content="I need to set up an MD simulation for a membrane protein. Where should I start?",
                created_at=datetime.utcnow() - timedelta(days=1),
            ),
            Message(
                id=str(uuid4()),
                chat_id=chat2.id,
                role="assistant",
                content="Setting up a membrane protein simulation requires several steps:\n\n1. Prepare the protein structure\n2. Build the membrane bilayer\n3. Solvate the system\n4. Add ions for neutralization\n5. Energy minimization\n6. Equilibration\n\nLet's start with step 1. Do you have the PDB file ready?",
                created_at=datetime.utcnow() - timedelta(days=1, minutes=-3),
            ),
            Message(
                id=str(uuid4()),
                chat_id=chat2.id,
                role="user",
                content="Yes, I have the PDB file. What's the best way to prepare it?",
                created_at=datetime.utcnow() - timedelta(minutes=30),
            ),
        ]

        # Create sample messages for chat3
        messages_chat3 = [
            Message(
                id=str(uuid4()),
                chat_id=chat3.id,
                role="user",
                content="What are the differences between ff14SB and ff19SB force fields?",
                created_at=datetime.utcnow() - timedelta(hours=5),
            ),
            Message(
                id=str(uuid4()),
                chat_id=chat3.id,
                role="assistant",
                content="The main differences between ff14SB and ff19SB are:\n\n**ff14SB:**\n- Released in 2014\n- Improved backbone parameters\n- Good for most protein simulations\n\n**ff19SB:**\n- Released in 2019\n- Further refined backbone and sidechain parameters\n- Better agreement with NMR data\n- Recommended for new simulations\n\nFor most modern simulations, ff19SB is the preferred choice.",
                created_at=datetime.utcnow() - timedelta(hours=5, minutes=-2),
            ),
            Message(
                id=str(uuid4()),
                chat_id=chat3.id,
                role="user",
                content="Thanks! And what about water models?",
                created_at=datetime.utcnow() - timedelta(minutes=10),
            ),
        ]

        session.add_all(messages_chat1 + messages_chat2 + messages_chat3)

        # Create sample tasks
        console.print("[cyan]Creating sample tasks...[/cyan]")

        tasks = [
            Task(
                id=str(uuid4()),
                title="Prepare protein structure for simulation",
                description="Clean PDB file, add missing atoms, and prepare topology",
                status="completed",
                priority="high",
                created_at=datetime.utcnow() - timedelta(days=3),
                updated_at=datetime.utcnow() - timedelta(days=2),
                completed_at=datetime.utcnow() - timedelta(days=2),
            ),
            Task(
                id=str(uuid4()),
                title="Run energy minimization",
                description="Minimize the system energy to remove bad contacts",
                status="in_progress",
                priority="high",
                created_at=datetime.utcnow() - timedelta(days=1),
                updated_at=datetime.utcnow() - timedelta(minutes=15),
            ),
            Task(
                id=str(uuid4()),
                title="Equilibration phase 1 (NVT)",
                description="Run NVT equilibration at 300K for 100ps",
                status="pending",
                priority="medium",
                created_at=datetime.utcnow() - timedelta(hours=12),
                updated_at=datetime.utcnow() - timedelta(hours=12),
            ),
            Task(
                id=str(uuid4()),
                title="Equilibration phase 2 (NPT)",
                description="Run NPT equilibration at 300K and 1 bar for 500ps",
                status="pending",
                priority="medium",
                created_at=datetime.utcnow() - timedelta(hours=12),
                updated_at=datetime.utcnow() - timedelta(hours=12),
            ),
            Task(
                id=str(uuid4()),
                title="Production MD simulation",
                description="Run 100ns production simulation",
                status="pending",
                priority="low",
                created_at=datetime.utcnow() - timedelta(hours=12),
                updated_at=datetime.utcnow() - timedelta(hours=12),
            ),
            Task(
                id=str(uuid4()),
                title="Analyze trajectory",
                description="Calculate RMSD, RMSF, and generate visualization",
                status="pending",
                priority="low",
                created_at=datetime.utcnow() - timedelta(hours=12),
                updated_at=datetime.utcnow() - timedelta(hours=12),
            ),
            Task(
                id=str(uuid4()),
                title="Review force field parameters",
                description="Compare ff14SB vs ff19SB for this system",
                status="completed",
                priority="medium",
                created_at=datetime.utcnow() - timedelta(days=5),
                updated_at=datetime.utcnow() - timedelta(days=4),
                completed_at=datetime.utcnow() - timedelta(days=4),
            ),
        ]

        session.add_all(tasks)

        # Commit all changes
        await session.commit()

        console.print(f"[green]✓ Created {len([chat1, chat2, chat3])} chats[/green]")
        console.print(f"[green]✓ Created {len(messages_chat1 + messages_chat2 + messages_chat3)} messages[/green]")
        console.print(f"[green]✓ Created {len(tasks)} tasks[/green]")
