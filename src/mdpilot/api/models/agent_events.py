"""Agent event models for WebSocket streaming"""
from enum import Enum
from typing import Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field


class AgentEventType(str, Enum):
    ITERATION_START = "iteration_start"
    LLM_RESPONSE = "llm_response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    LOOP_END = "loop_end"
    ERROR = "error"
    COMPLETE = "complete"


class AgentEvent(BaseModel):
    type: AgentEventType
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
