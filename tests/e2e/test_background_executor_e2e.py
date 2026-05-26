"""End-to-end test for BackgroundExecutor integration."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mdpilot.api.services.task_service import TaskService
from mdpilot.api.services.agent_service import AgentService
from mdpilot.api.services.background_executor import BackgroundExecutor


@pytest.fixture
def mock_llm_provider():
    """Mock LLM provider that returns simple responses."""
    mock = MagicMock()
    
    async def mock_chat(*args, **kwargs):
        msg = MagicMock()
        msg.content = "Task completed successfully"
        msg.tool_calls = None
        
        choice = MagicMock()
        choice.message = msg
        choice.finish_reason = "stop"
        
        usage = MagicMock()
        usage.prompt_tokens = 10
        usage.completion_tokens = 20
        
        response = MagicMock()
        response.choices = [choice]
        response.usage = usage
        
        return response
    
    mock.chat = AsyncMock(side_effect=mock_chat)
    return mock


@pytest.mark.asyncio
async def test_background_executor_integration(db_session, mock_llm_provider):
    """Test BackgroundExecutor can submit and execute tasks."""
    
    with patch('mdpilot.agent.react.LLMProvider', return_value=mock_llm_provider):
        task_service = TaskService(db_session)
        agent_service = AgentService(max_concurrent=5)
        
        executor = BackgroundExecutor(task_service, agent_service)
        
        task_id = await executor.submit_agent_task(
            session_id="test-session-001",
            prompt="Test prompt",
            user_id="test-user"
        )
        
        assert task_id is not None
        assert isinstance(task_id, str)
        
        await asyncio.sleep(0.5)
        
        status = await executor.get_task_status(task_id)
        assert status is not None
        assert status["task_id"] == task_id


@pytest.mark.asyncio
async def test_background_executor_progress_tracking(db_session, mock_llm_provider):
    """Test BackgroundExecutor tracks progress correctly."""
    
    with patch('mdpilot.agent.react.LLMProvider', return_value=mock_llm_provider):
        task_service = TaskService(db_session)
        agent_service = AgentService()
        
        executor = BackgroundExecutor(task_service, agent_service)
        
        task_id = await executor.submit_agent_task(
            session_id="test-session-002",
            prompt="Test progress tracking",
            user_id="test-user"
        )
        
        await asyncio.sleep(0.2)
        
        status = await executor.get_task_status(task_id)
        assert status is not None
        assert "progress_percentage" in status
        assert "current_stage" in status
