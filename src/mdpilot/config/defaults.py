"""Embedded default configuration values for mdpilot.

These serve as the lowest-priority layer in the 5-layer config merge.
"""

from __future__ import annotations

DEFAULT_BIOREASON_REMOTE = {
    "ssh": {
        "host": "lab06",
        "port": 22,
        "username": "zhao",
        "key_path": "~/.ssh/id_ed25519",
        "timeout": 30
    },
    "celery": {
        "broker_url": "redis://localhost:6379/0",
        "backend_url": "redis://localhost:6379/1",
        "task_timeout": 300,
        "poll_interval": 2.0
    },
    "work_dir": "/home/6-FF/luo/BioReason-Pro",
    "conda_env": "bioreason"
}

DEFAULT_ALPHAFOLD2_REMOTE = {
    "ssh": {
        "host": "lab02",
        "port": 22,
        "username": "zhao",
        "key_path": "~/.ssh/id_ed25519",
        "timeout": 30
    },
    "celery": {
        "broker_url": "redis://localhost:6379/2",
        "backend_url": "redis://localhost:6379/3",
        "task_timeout": 14400,
        "poll_interval": 5.0
    },
    "work_dir": "/home/2-BB/changshengjie/project/mdpilot",
    "conda_env": "af2_py310"
}

DEFAULT_LAB03_REMOTE = {
    "ssh": {
        "host": "lab03",
        "port": 22,
        "username": "zhao",
        "key_path": "~/.ssh/id_ed25519",
        "timeout": 30,
    },
    "work_dir": "/home/3-FF/changshengjie/project/mdpilot",
    "amber_home": "/home/software/Amber24/amber24",
    "tools": {
        "cpptraj": "/home/software/Amber24/amber24/bin/cpptraj",
        "pmemd": "/home/software/Amber24/amber24/bin/pmemd",
        "pmemd_cuda": "/home/software/Amber24/amber24/bin/pmemd.cuda",
    },
}

DEFAULTS: dict = {
    "provider": {
        "model": "MiniMax-M2.7-highspeed",
        "api_key": "gw-2a2beea0-7fb3-4902-b986-c7c12a60ace9",
        "base_url": "https://minnimax.chat/v1",
        "custom_llm_provider": "openai",
        "fallback_models": [],
        "max_retries": 3,
        "timeout": 120,
        "temperature": 0.0,
        "max_tokens": 32768,
    },
    "amber": {
        "amber_home": "/home/software/Amber24/amber24",
        "tools_version": "24",
        "gpu_enabled": True,
    },
    "agent": {
        "use_coordination": False,
      "max_iterations": 90,
        "max_context_tokens": 100_000,
        "default_mode": "react",
        "auto_confirm_steps": 3,
    },
    "database": {
        "url": "postgresql+asyncpg://mdpilot:mdpilot@localhost:5432/mdpilot",
        "echo": False,
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 3600,
    },
    "bioreason_remote": DEFAULT_BIOREASON_REMOTE,
    "alphafold2_remote": DEFAULT_ALPHAFOLD2_REMOTE,
    "lab03_remote": DEFAULT_LAB03_REMOTE,
}
