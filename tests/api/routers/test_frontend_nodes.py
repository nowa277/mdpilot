from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mdpilot.api.routers.frontend import _collect_node_gpus, _parse_nvidia_smi_output, list_nodes


SAMPLE_NVIDIA_SMI = """
0, NVIDIA TITAN V, 512, 12288, 35, 0, 24, 250
1, NVIDIA RTX 3090, 2048, 24576, 42, 15, 120, 350
"""


def test_parse_nvidia_smi_output_returns_frontend_gpu_shape() -> None:
    gpus = _parse_nvidia_smi_output(SAMPLE_NVIDIA_SMI)

    assert gpus == [
        {"id": "0", "model": "NVIDIA TITAN V", "usedMB": 512, "totalMB": 12288, "tempC": 35, "utilization": 0, "powerDraw": 24.0, "powerLimit": 250.0},
        {"id": "1", "model": "NVIDIA RTX 3090", "usedMB": 2048, "totalMB": 24576, "tempC": 42, "utilization": 15, "powerDraw": 120.0, "powerLimit": 350.0},
    ]


@pytest.mark.asyncio
async def test_collect_node_gpus_runs_nvidia_smi_through_saved_ssh_alias() -> None:
    process = MagicMock(returncode=0, stdout=SAMPLE_NVIDIA_SMI, stderr="")

    with patch("mdpilot.api.routers.frontend.asyncio.create_subprocess_exec", new=AsyncMock(return_value=process)) as create:
        process.communicate = AsyncMock(return_value=(SAMPLE_NVIDIA_SMI.encode(), b""))
        gpus = await _collect_node_gpus("lab02", "lab02")

    create.assert_awaited_once_with(
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "lab02",
        "timeout 5 nvidia-smi --query-gpu=index,name,memory.used,memory.total,temperature.gpu,utilization.gpu,power.draw,power.limit --format=csv,noheader,nounits",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    process.communicate.assert_awaited_once_with()
    assert gpus[0]["usedMB"] == 512


@pytest.mark.asyncio
async def test_collect_lab03_gpus_runs_nvidia_smi_locally_on_lab03() -> None:
    process = MagicMock(returncode=0, stdout=SAMPLE_NVIDIA_SMI, stderr="")

    with (
        patch("socket.gethostname", return_value="lab-03"),
        patch("mdpilot.api.routers.frontend.asyncio.create_subprocess_exec", new=AsyncMock(return_value=process)) as create,
    ):
        process.communicate = AsyncMock(return_value=(SAMPLE_NVIDIA_SMI.encode(), b""))
        gpus = await _collect_node_gpus("lab03", "lab03")

    create.assert_awaited_once_with(
        "nvidia-smi",
        "--query-gpu=index,name,memory.used,memory.total,temperature.gpu,utilization.gpu,power.draw,power.limit",
        "--format=csv,noheader,nounits",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    process.communicate.assert_awaited_once_with()
    assert gpus[0]["usedMB"] == 512


@pytest.mark.asyncio
async def test_list_nodes_uses_remote_gpu_telemetry_and_first_gpu_contract() -> None:
    async def fake_collect(node_id: str, host: str):
        if node_id == "lab02":
            return [{"id": "0", "model": "NVIDIA TITAN V", "usedMB": 512, "totalMB": 12288}]
        if node_id == "lab06":
            return [
                {"id": "0", "model": "NVIDIA RTX 3090", "usedMB": 2048, "totalMB": 24576},
                {"id": "1", "model": "NVIDIA RTX 3090", "usedMB": 0, "totalMB": 24576},
            ]
        raise AssertionError(node_id)

    with patch("mdpilot.api.routers.frontend._collect_node_gpus", new=AsyncMock(side_effect=fake_collect)):
        nodes = await list_nodes()

    lab02 = next(node for node in nodes if node["id"] == "lab02")
    lab06 = next(node for node in nodes if node["id"] == "lab06")
    lab03 = next(node for node in nodes if node["id"] == "lab03")

    assert lab02["online"] is True
    assert lab02["gpu"] == lab02["gpus"][0]
    assert lab02["gpu"]["usedMB"] == 512
    assert lab06["online"] is True
    assert lab06["gpu"] == lab06["gpus"][0]
    assert len(lab06["gpus"]) == 2
    assert "gpu" not in lab03
    assert "gpus" not in lab03


@pytest.mark.asyncio
async def test_list_nodes_degrades_failed_gpu_node_without_breaking_other_nodes() -> None:
    async def fake_collect(node_id: str, host: str):
        if node_id == "lab02":
            raise RuntimeError("ssh failed")
        return [{"id": "0", "model": "NVIDIA RTX 3090", "usedMB": 2048, "totalMB": 24576}]

    with patch("mdpilot.api.routers.frontend._collect_node_gpus", new=AsyncMock(side_effect=fake_collect)):
        nodes = await list_nodes()

    lab02 = next(node for node in nodes if node["id"] == "lab02")
    lab06 = next(node for node in nodes if node["id"] == "lab06")

    assert lab02["online"] is False
    assert "gpu" not in lab02
    assert "gpus" not in lab02
    assert lab06["online"] is True
    assert lab06["gpu"] == lab06["gpus"][0]


@pytest.mark.asyncio
async def test_list_nodes_probes_lab03_instead_of_hardcoding_online_status() -> None:
    async def fake_collect(node_id: str, host: str):
        if node_id == "lab02":
            return [{"id": "0", "model": "NVIDIA TITAN V", "usedMB": 512, "totalMB": 12288}]
        if node_id == "lab06":
            return [{"id": "0", "model": "NVIDIA RTX 3090", "usedMB": 2048, "totalMB": 24576}]
        if node_id == "lab03":
            return [
                {"id": "0", "model": "NVIDIA GeForce GTX 1080 Ti", "usedMB": 3, "totalMB": 11264},
                {"id": "1", "model": "NVIDIA GeForce GTX 1080 Ti", "usedMB": 3, "totalMB": 11264},
                {"id": "2", "model": "NVIDIA GeForce GTX 1080 Ti", "usedMB": 3, "totalMB": 11264},
                {"id": "3", "model": "NVIDIA GeForce GTX 1080 Ti", "usedMB": 3, "totalMB": 11264},
            ]
        raise AssertionError(node_id)

    with patch("mdpilot.api.routers.frontend._collect_node_gpus", new=AsyncMock(side_effect=fake_collect)) as collect:
        nodes = await list_nodes()

    lab03 = next(node for node in nodes if node["id"] == "lab03")

    assert collect.await_args_list[-1].args == ("lab03", "lab03")
    assert lab03["online"] is True
    assert lab03["gpu"] == lab03["gpus"][0]
    assert len(lab03["gpus"]) == 4
