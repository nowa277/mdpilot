"""AlphaFold2 API router."""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from mdpilot.api.auth import verify_token
from mdpilot.config.defaults import DEFAULT_ALPHAFOLD2_REMOTE
from mdpilot.config.loader import load_config
from mdpilot.integrations.alphafold2 import AlphaFold2CeleryClient

router = APIRouter(
    prefix="/api/v1/alphafold2",
    tags=["alphafold2"],
    dependencies=[Depends(verify_token)],
)


class AlphaFold2PredictRequest(BaseModel):
    sequence: str
    job_name: str = "prediction"
    output_dir: Optional[str] = None
    db_preset: str = "reduced_dbs"


@router.get("/health")
async def health_check() -> dict[str, Any]:
    remote_config = _alphafold2_remote_config()
    client = AlphaFold2CeleryClient(**remote_config)
    try:
        async with client:
            return {
                "status": "healthy",
                "mode": "remote",
                "host": client.ssh_config["host"],
                "work_dir": client.work_dir,
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "mode": "remote",
            "error": str(e),
        }


@router.post("/predict")
async def predict_structure(request: AlphaFold2PredictRequest) -> dict[str, Any]:
    if not request.sequence.strip():
        raise HTTPException(status_code=400, detail="sequence must not be empty")

    remote_config = _alphafold2_remote_config()
    client = AlphaFold2CeleryClient(**remote_config)
    try:
        async with client:
            return await client.predict(
                sequence=request.sequence,
                job_name=request.job_name,
                output_dir=request.output_dir,
                db_preset=request.db_preset,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


def _alphafold2_remote_config() -> dict[str, Any]:
    config = load_config()
    if config.alphafold2_remote is None:
        return DEFAULT_ALPHAFOLD2_REMOTE
    return config.alphafold2_remote.model_dump()
