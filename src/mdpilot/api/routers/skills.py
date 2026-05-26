"""Skills discovery API."""
from fastapi import APIRouter, Depends, Query
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
    category: str = ""
    command: str = ""
    tools: list[dict] = []


@router.get("", response_model=list[SkillInfo])
async def list_skills(category: str | None = Query(None)) -> list[SkillInfo]:
    """Return all registered skills (L1 metadata only)."""
    from mdpilot.agent.skills import UnifiedSkillRegistry

    reg = UnifiedSkillRegistry()
    reg.discover_all()
    skills = reg.list_skills()

    if category:
        skills = [s for s in skills if s.category == category]

    return [
        SkillInfo(
            name=s.name,
            title=s.title,
            description=s.description,
            tags=s.tags,
            source=s.source,
            category=s.category,
            command=s.command,
            tools=s.tools,
        )
        for s in skills
    ]
