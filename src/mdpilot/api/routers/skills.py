"""Skills discovery API."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from mdpilot.api.auth import verify_token

router = APIRouter(
    prefix="/api/v1/skills",
    tags=["skills"],
    dependencies=[Depends(verify_token)],
)


class SkillInfo(BaseModel):
    name: str
    title: str
    description: str
    tags: list[str]
    source: str


@router.get("", response_model=list[SkillInfo])
async def list_skills() -> list[SkillInfo]:
    """Return all registered skills (L1 metadata only)."""
    from mdpilot.agent.skills import UnifiedSkillRegistry

    reg = UnifiedSkillRegistry()
    reg.discover_all()
    return [
        SkillInfo(
            name=s.name,
            title=s.title,
            description=s.description,
            tags=s.tags,
            source=s.source,
        )
        for s in reg.list_skills()
    ]
