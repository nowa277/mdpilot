"""Unified configuration management using pydantic-settings."""

from __future__ import annotations

from typing import Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file.
    
    All settings can be overridden via environment variables.
    Example: DATABASE_URL, LLM_MODEL, AGENT_MAX_ITERATIONS
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database settings
    database_url: str = Field(
        default="sqlite+aiosqlite:///./mdpilot.db",
        description="Database connection URL",
    )
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=10, ge=0, le=50)
    db_pool_timeout: int = Field(default=30, ge=1)
    db_pool_recycle: int = Field(default=3600, ge=0)
    db_echo: bool = Field(default=False)

    # LLM Provider settings
    llm_model: str = Field(default="claude-sonnet-4-20250514")
    llm_api_key: Optional[SecretStr] = None
    llm_base_url: Optional[str] = None
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=4096, ge=1)
    llm_timeout: int = Field(default=120, ge=1)
    llm_max_retries: int = Field(default=3, ge=0)

    # Agent settings
    agent_max_iterations: int = Field(default=90, ge=1, le=200)
    agent_max_context_tokens: int = Field(default=100000, ge=1000)
    agent_max_concurrent_tasks: int = Field(default=5, ge=1, le=20)

    # API settings
    api_token: Optional[SecretStr] = None
    api_cors_origins: list[str] = Field(default=["*"])

    # AMBER settings
    amber_ssh_host: str = Field(default="localhost")
    amber_ssh_port: int = Field(default=22, ge=1, le=65535)
    amber_ssh_user: str = Field(default="user")
    amber_home: Optional[str] = None


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance (singleton pattern).
    
    Returns:
        Settings: The application settings instance.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Convenience alias for direct import
settings = get_settings()
