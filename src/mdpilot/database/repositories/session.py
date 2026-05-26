"""Repository for agent session persistence."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdpilot.database.models.session import AgentSession
from mdpilot.database.repositories.base import BaseRepository


class SessionRepository(BaseRepository[AgentSession]):
    """Repository for managing agent session persistence."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize session repository.
        
        Args:
            session: SQLAlchemy async session
        """
        super().__init__(session, AgentSession)

    async def save_session(
        self,
        session_id: str,
        context_messages: list[dict[str, Any]],
        system_prompt: str,
        iteration_count: int,
        max_iterations: int,
    ) -> AgentSession:
        """Save or update agent session state.
        
        Uses upsert pattern: updates if exists, creates if new.
        
        Args:
            session_id: Unique session identifier
            context_messages: Conversation message history
            system_prompt: Current system prompt
            iteration_count: Current iteration number
            max_iterations: Maximum allowed iterations
            
        Returns:
            Saved agent session
        """
        existing = await self.get_by_id(session_id)
        
        if existing:
            existing.context_messages = context_messages
            existing.system_prompt = system_prompt
            existing.iteration_count = iteration_count
            existing.max_iterations = max_iterations
            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        else:
            new_session = AgentSession(
                id=session_id,
                context_messages=context_messages,
                system_prompt=system_prompt,
                iteration_count=iteration_count,
                max_iterations=max_iterations,
            )
            self.session.add(new_session)
            await self.session.commit()
            await self.session.refresh(new_session)
            return new_session

    async def load_session(self, session_id: str) -> Optional[AgentSession]:
        """Load agent session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Agent session if found, None otherwise
        """
        return await self.get_by_id(session_id)
