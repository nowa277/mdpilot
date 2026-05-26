"""AlphaFold2 integration via SSH + Celery"""

from .celery_client import AlphaFold2CeleryClient

__all__ = ["AlphaFold2CeleryClient"]
