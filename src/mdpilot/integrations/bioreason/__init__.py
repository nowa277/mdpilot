"""BioReason-Pro integration via SSH + Celery"""

from .celery_client import BioreasonCeleryClient

__all__ = ["BioreasonCeleryClient"]
