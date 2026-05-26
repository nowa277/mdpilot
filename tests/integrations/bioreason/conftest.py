"""Shared fixtures for BioReason integration tests with mocked SSH."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_ssh_conn():
    """Mock asyncssh connection that simulates remote Celery commands."""
    conn = AsyncMock()
    conn.is_closed = MagicMock(return_value=False)
    conn.close = MagicMock(return_value=None)
    conn.wait_closed.return_value = None

    task_id = "abc123-task-id"
    call_count = {"n": 0}

    async def fake_run(cmd, check=False):
        result = AsyncMock()
        call_count["n"] += 1

        if "annotate_protein.delay" in cmd:
            result.stdout = task_id + "\n"
        elif "AsyncResult" in cmd:
            n = call_count["n"]
            if n <= 2:
                result.stdout = json.dumps({"state": "PENDING", "result": None})
            elif n <= 3:
                result.stdout = json.dumps({"state": "STARTED", "result": None})
            elif n <= 4:
                result.stdout = json.dumps({"state": "PARSING", "result": None})
            else:
                result.stdout = json.dumps({
                    "state": "SUCCESS",
                    "result": {
                        "success": True,
                        "go_terms": {
                            "MF": ["molecular_function"],
                            "BP": ["biological_process"],
                            "CC": ["cellular_component"],
                        },
                    },
                })
        elif "LLEN celery" in cmd:
            result.stdout = "3\n"
        else:
            result.stdout = ""

        return result

    conn.run = fake_run
    return conn


@pytest.fixture
def mock_asyncssh(mock_ssh_conn):
    """Patch asyncssh.connect to return the mock connection."""
    with patch("asyncssh.connect", new_callable=AsyncMock, return_value=mock_ssh_conn) as mock_connect:
        yield mock_connect
