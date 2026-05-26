"""Pydantic v2 configuration schema for mdpilot."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class ProviderConfig(BaseModel):
    """LLM provider settings.

    Controls which model is used, API credentials, and generation parameters.
    """

    model: str = "claude-sonnet-4-20250514"
    api_key: SecretStr | None = None
    base_url: str | None = None
    fallback_models: list[str] = Field(default_factory=list)
    max_retries: int = 3
    timeout: int = 120
    temperature: float = 0.0
    max_tokens: int = 8192
    custom_llm_provider: str | None = None


class AmberConfig(BaseModel):
    """AMBER-specific simulation settings."""

    model_config = ConfigDict(strict=True)

    amber_home: str | None = "/home/software/Amber24/amber24"
    tools_version: str = "24"
    gpu_enabled: bool = True


class CheckpointConfig(BaseModel):
    """Workflow checkpoint settings for recovery."""

    enabled: bool = True
    checkpoint_interval: int = Field(default=5, ge=0)
    long_operation_threshold: int = Field(default=60, ge=0)
    cleanup_on_success: bool = True


class RetryConfig(BaseModel):
    """Retry policy settings for error recovery."""

    default_max_attempts: int = Field(default=3, ge=0)
    default_backoff_base: float = Field(default=2.0, gt=0.0)
    max_backoff: float = Field(default=300.0, gt=0.0)
    by_tool: dict[str, dict[str, Any]] = Field(default_factory=dict)
    by_error_type: dict[str, dict[str, Any]] = Field(default_factory=dict)


class RecoveryConfig(BaseModel):
    """Workflow recovery configuration combining checkpoint and retry settings."""

    checkpoint: CheckpointConfig = Field(default_factory=CheckpointConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)


class ParallelConfig(BaseModel):
    """Configuration for parallel tool execution."""

    enable_parallel: bool = Field(
        default=False,
        description="Enable parallel tool execution"
    )
    max_concurrent_tools: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Maximum number of tools to run concurrently"
    )
    max_memory_mb: int = Field(
        default=8192,
        ge=512,
        description="Maximum total memory for concurrent tools (MB)"
    )
    max_gpu_tools: int = Field(
        default=1,
        ge=1,
        description="Maximum number of GPU tools to run concurrently"
    )


class TimeoutConfig(BaseModel):
    """Timeout configuration for tool execution."""

    default_timeout_sec: int | None = Field(
        default=None,
        ge=1,
        description="Global default timeout in seconds (None = no timeout)"
    )

    by_category: dict[str, int] = Field(
        default_factory=dict,
        description="Timeout overrides by tool category"
    )

    by_tool: dict[str, int] = Field(
        default_factory=dict,
        description="Timeout overrides by specific tool name"
    )

    warning_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Emit warning when execution reaches this fraction of timeout"
    )


class AgentConfig(BaseModel):
    """Agent runtime behaviour settings."""

    use_coordination: bool = False
    max_iterations: int = 90
    max_context_tokens: int = 100_000
    max_concurrent_tasks: int = Field(default=5, ge=1, le=20, description="Maximum concurrent agent tasks")
    default_mode: Literal["react", "plan"] = "react"
    auto_confirm_steps: int = 3
    recovery: RecoveryConfig = Field(default_factory=RecoveryConfig)
    parallel: ParallelConfig = Field(default_factory=ParallelConfig)
    timeout: TimeoutConfig = Field(default_factory=TimeoutConfig)


class DatabaseConfig(BaseModel):
    """Database connection and pool settings."""

    url: str = "postgresql+asyncpg://mdpilot:mdpilot@localhost:5432/mdpilot"
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600


class SSHConfig(BaseModel):
    """SSH 连接配置"""
    host: str = Field(..., description="SSH 主机名")
    port: int = Field(22, description="SSH 端口")
    username: str = Field(..., description="SSH 用户名")
    key_path: str = Field(..., description="SSH 私钥路径")
    timeout: int = Field(30, description="连接超时（秒）")


class CeleryConfig(BaseModel):
    """Celery 配置"""
    broker_url: str = Field(..., description="Broker URL")
    backend_url: str = Field(..., description="Backend URL")
    task_timeout: int = Field(300, description="任务超时（秒）")
    poll_interval: float = Field(2.0, description="轮询间隔（秒）")


class BioreasonRemoteConfig(BaseModel):
    """BioReason 远程配置"""
    ssh: SSHConfig
    celery: CeleryConfig
    work_dir: str = Field("/home/6-FF/luo/BioReason-Pro", description="工作目录")
    conda_env: str = Field("bioreason", description="Conda 环境")


class AlphaFold2RemoteConfig(BaseModel):
    """AlphaFold2 远程配置"""
    ssh: SSHConfig
    celery: CeleryConfig
    work_dir: str = Field("/home/2-BB/changshengjie/project/mdpilot", description="工作目录")
    conda_env: str = Field("af2_py310", description="Conda 环境")


class Lab03AmberToolsConfig(BaseModel):
    """lab03 AMBER 工具路径配置"""
    cpptraj: str = Field("/home/software/Amber24/amber24/bin/cpptraj", description="cpptraj 路径")
    pmemd: str = Field("/home/software/Amber24/amber24/bin/pmemd", description="pmemd 路径")
    pmemd_cuda: str = Field("/home/software/Amber24/amber24/bin/pmemd.cuda", description="pmemd.cuda 路径")


class Lab03RemoteConfig(BaseModel):
    """lab03 远程 AMBER 节点配置"""
    ssh: SSHConfig
    work_dir: str = Field("/home/3-FF/changshengjie/project/mdpilot", description="工作目录")
    amber_home: str = Field("/home/software/Amber24/amber24", description="AMBERHOME")
    tools: Lab03AmberToolsConfig = Field(default_factory=Lab03AmberToolsConfig)


class AppConfig(BaseModel):
    """Top-level configuration combining all subsystem settings."""

    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    amber: AmberConfig = Field(default_factory=AmberConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    bioreason_remote: Optional[BioreasonRemoteConfig] = None
    alphafold2_remote: Optional[AlphaFold2RemoteConfig] = None
    lab03_remote: Optional[Lab03RemoteConfig] = None
