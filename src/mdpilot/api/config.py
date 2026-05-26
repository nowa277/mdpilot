"""API configuration using Pydantic settings."""
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """API configuration settings."""

    model_config = ConfigDict(env_prefix="MDPILOT_")

    app_name: str = "MDPilot API"
    api_version: str = "v1"
    debug: bool = False
    cors_origins: list[str] = ["*"]
    host: str = "0.0.0.0"
    port: int = 8000
