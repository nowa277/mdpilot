"""GPU selector module for AMBER simulations.

This module provides utilities to automatically select the optimal GPU
for molecular dynamics simulations based on current GPU utilization.
"""

import logging
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


def get_gpu_info() -> list[dict[str, Any]]:
    """Get information about all available GPUs.

    Returns:
        List of dictionaries containing GPU information with keys:
        - id: GPU index
        - memory_used: Used memory in MB
        - memory_total: Total memory in MB
        - utilization: GPU utilization percentage

    Example:
        >>> gpus = get_gpu_info()
        >>> print(gpus[0])
        {'id': 0, 'memory_used': 1024, 'memory_total': 8192, 'utilization': 30}
    """
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

        if result.returncode != 0:
            logger.warning(
                "nvidia-smi command failed with return code %d: %s",
                result.returncode,
                result.stderr,
            )
            return []

        gpus = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue

            try:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) != 4:
                    logger.debug("Skipping invalid line: %s", line)
                    continue

                gpu_info = {
                    "id": int(parts[0]),
                    "memory_used": int(parts[1]),
                    "memory_total": int(parts[2]),
                    "utilization": int(parts[3]),
                }
                gpus.append(gpu_info)
            except (ValueError, IndexError) as e:
                logger.debug("Failed to parse GPU info line '%s': %s", line, e)
                continue

        return gpus

    except FileNotFoundError:
        logger.warning("nvidia-smi not found. GPU detection unavailable.")
        return []
    except subprocess.TimeoutExpired:
        logger.warning("nvidia-smi command timed out.")
        return []
    except Exception as e:
        logger.warning("Unexpected error querying GPU info: %s", e)
        return []


def select_optimal_gpu() -> int:
    """Select the optimal GPU based on lowest memory usage.

    Selects the GPU with the lowest absolute memory usage. If multiple GPUs
    have the same memory usage, selects the one with the lowest ID.

    Returns:
        GPU ID (index) to use. Returns 0 if no GPUs are detected or if
        an error occurs.

    Example:
        >>> gpu_id = select_optimal_gpu()
        >>> print(f"Selected GPU: {gpu_id}")
        Selected GPU: 1
    """
    gpus = get_gpu_info()

    if not gpus:
        logger.warning("No GPUs detected, defaulting to GPU 0")
        return 0

    # Sort by memory_used (ascending), then by id (ascending)
    optimal_gpu = min(gpus, key=lambda g: (g["memory_used"], g["id"]))

    logger.debug(
        "Selected GPU %d (memory used: %d MB, utilization: %d%%)",
        optimal_gpu["id"],
        optimal_gpu["memory_used"],
        optimal_gpu["utilization"],
    )

    return optimal_gpu["id"]


def validate_gpu(gpu_id: int) -> bool:
    """Validate that a specific GPU ID is available.

    Args:
        gpu_id: GPU index to validate

    Returns:
        True if the GPU exists and is available, False otherwise

    Example:
        >>> if validate_gpu(1):
        ...     print("GPU 1 is available")
        ... else:
        ...     print("GPU 1 is not available")
    """
    if gpu_id < 0:
        return False

    gpus = get_gpu_info()
    return any(gpu["id"] == gpu_id for gpu in gpus)
