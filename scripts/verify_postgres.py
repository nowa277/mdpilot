#!/usr/bin/env python3
"""PostgreSQL verification script for MDPilot database layer.

Tests:
1. Basic connection (SELECT 1)
2. Alembic migration (upgrade head)
3. All 4 tables exist (chats, messages, tasks, agent_sessions)
4. CRUD operations on Chat model
5. Summary report

Usage:
    # Default PostgreSQL URL
    python scripts/verify_postgres.py

    # Custom URL (e.g. SQLite for baseline testing)
    python scripts/verify_postgres.py --url "sqlite+aiosqlite:///./test_verify.db"
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
import uuid

# Ensure project root is on sys.path so `mdpilot` is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mdpilot.database.base import Base
from mdpilot.database.models import Chat, Message, Task
from mdpilot.database.models.session import AgentSession

# ── helpers ──────────────────────────────────────────────────────────────────

EXPECTED_TABLES = {"chats", "messages", "tasks", "agent_sessions"}


class Reporter:
    """Collect pass/fail results and print a summary."""

    def __init__(self) -> None:
        self.results: list[tuple[str, bool, str]] = []

    def ok(self, name: str, detail: str = "") -> None:
        self.results.append((name, True, detail))

    def fail(self, name: str, detail: str = "") -> None:
        self.results.append((name, False, detail))

    def print_summary(self) -> int:
        print("\n" + "=" * 60)
        print("VERIFICATION SUMMARY")
        print("=" * 60)
        all_pass = True
        for name, passed, detail in self.results:
            status = "PASS" if passed else "FAIL"
            line = f"  [{status}] {name}"
            if detail:
                line += f" -- {detail}"
            print(line)
            if not passed:
                all_pass = False
        print("=" * 60)
        if all_pass:
            print("All checks passed.")
            return 0
        else:
            print("Some checks FAILED.")
            return 1


# ── check functions ──────────────────────────────────────────────────────────

async def check_connection(engine, report: Reporter) -> bool:
    """Test 1: basic connectivity via SELECT 1."""
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            row = result.scalar()
            if row == 1:
                report.ok("Connection", "SELECT 1 returned 1")
                return True
            else:
                report.fail("Connection", f"SELECT 1 returned {row!r}")
                return False
    except Exception as exc:
        report.fail("Connection", str(exc))
        return False


def run_alembic_upgrade(url: str, report: Reporter) -> bool:
    """Test 2: run alembic upgrade head via subprocess."""
    try:
        env = os.environ.copy()
        env["MDPILOT_DATABASE_URL"] = url
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
        if result.returncode == 0:
            report.ok("Alembic upgrade head", "migrations applied")
            return True
        else:
            detail = result.stderr.strip() or result.stdout.strip()
            report.fail("Alembic upgrade head", detail[:200])
            return False
    except Exception as exc:
        report.fail("Alembic upgrade head", str(exc))
        return False


async def check_tables(engine, report: Reporter) -> bool:
    """Test 3: verify all expected tables exist."""
    try:
        async with engine.connect() as conn:
            if engine.dialect.name == "sqlite":
                result = await conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )
            else:
                result = await conn.execute(
                    text(
                        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                    )
                )
            tables = {row[0] for row in result.fetchall()}

        missing = EXPECTED_TABLES - tables
        extra = tables - EXPECTED_TABLES - {"alembic_version"}
        if not missing:
            report.ok(
                "Tables exist",
                f"found {sorted(EXPECTED_TABLES)}"
                + (f", extra: {sorted(extra)}" if extra else ""),
            )
            return True
        else:
            report.fail("Tables exist", f"missing: {sorted(missing)}")
            return False
    except Exception as exc:
        report.fail("Tables exist", str(exc))
        return False


async def check_crud(engine, report: Reporter) -> bool:
    """Test 4: CRUD operations on Chat model."""
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    test_id: uuid.UUID | None = None
    try:
        # CREATE
        async with session_factory() as session:
            chat = Chat(title="verify-test-chat", extra_data={"test": True})
            session.add(chat)
            await session.commit()
            test_id = chat.id
            if test_id is None:
                report.fail("CRUD Create", "got None id after commit")
                return False

        # READ
        async with session_factory() as session:
            chat = await session.get(Chat, test_id)
            if chat is None:
                report.fail("CRUD Read", "chat not found by id")
                return False
            if chat.title != "verify-test-chat":
                report.fail("CRUD Read", f"title mismatch: {chat.title!r}")
                return False

        # UPDATE
        async with session_factory() as session:
            chat = await session.get(Chat, test_id)
            chat.title = "verify-test-updated"
            await session.commit()
        async with session_factory() as session:
            chat = await session.get(Chat, test_id)
            if chat.title != "verify-test-updated":
                report.fail("CRUD Update", f"title mismatch: {chat.title!r}")
                return False

        # DELETE
        async with session_factory() as session:
            chat = await session.get(Chat, test_id)
            await session.delete(chat)
            await session.commit()
        async with session_factory() as session:
            chat = await session.get(Chat, test_id)
            if chat is not None:
                report.fail("CRUD Delete", "chat still exists after delete")
                return False

        report.ok("CRUD (Chat)", "create/read/update/delete all passed")
        return True
    except Exception as exc:
        report.fail("CRUD (Chat)", str(exc))
        # Attempt cleanup
        if test_id is not None:
            try:
                async with session_factory() as session:
                    chat = await session.get(Chat, test_id)
                    if chat:
                        await session.delete(chat)
                        await session.commit()
            except Exception:
                pass
        return False


# ── main ─────────────────────────────────────────────────────────────────────

async def main(url: str) -> int:
    report = Reporter()

    print(f"Database URL: {url.split('@')[-1] if '@' in url else url}")
    print()

    # Create engine
    engine_kwargs: dict = {}
    if url.startswith("sqlite"):
        engine_kwargs["echo"] = False
    else:
        engine_kwargs.update({"echo": False, "pool_pre_ping": True})
    engine = create_async_engine(url, **engine_kwargs)

    # 1. Connection test
    await check_connection(engine, report)

    # 2. Alembic migrations
    run_alembic_upgrade(url, report)

    # 3. Table existence (after migrations)
    await check_tables(engine, report)

    # 4. CRUD
    await check_crud(engine, report)

    # Cleanup
    await engine.dispose()

    # If we used a file-based SQLite, clean up the file
    if url.startswith("sqlite") and "///" in url:
        db_path = url.split("///")[-1]
        if db_path and os.path.isfile(db_path):
            os.remove(db_path)

    return report.print_summary()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Verify MDPilot database layer against PostgreSQL or SQLite"
    )
    parser.add_argument(
        "--url",
        default="postgresql+asyncpg://mdpilot:mdpilot@lab03:5432/mdpilot",
        help="Database URL (default: PostgreSQL on lab03)",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.url)))
