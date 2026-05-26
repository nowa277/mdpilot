"""Tests for WorkflowEngine parallel execution integration."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from mdpilot.agent.legacy_workflow_engine import WorkflowEngine, STEP_RESULT
from mdpilot.agent.events import EventEmitter
from mdpilot.agent.parallel_executor import ExecutionResult
from mdpilot.types import ToolCall, ToolOutput


@pytest.fixture
def mock_config_parallel_enabled():
    """Mock configuration with parallel execution enabled."""
    config = MagicMock()
    config.agent.default_mode = "react"
    config.agent.parallel.enable_parallel = True
    config.agent.parallel.max_concurrent_tools = 4
    config.agent.parallel.max_memory_mb = 8192
    config.agent.parallel.max_gpu_tools = 1
    return config


@pytest.fixture
def mock_config_parallel_disabled():
    """Mock configuration with parallel execution disabled."""
    config = MagicMock()
    config.agent.default_mode = "react"
    config.agent.parallel.enable_parallel = False
    return config


@pytest.fixture
def mock_dispatcher_with_registry():
    """Mock tool dispatcher with registry."""
    dispatcher = MagicMock()
    dispatcher.execute = AsyncMock()

    # Mock registry
    registry = MagicMock()
    registry.get = MagicMock(return_value=None)
    dispatcher._registry = registry

    return dispatcher


@pytest.fixture
def mock_llm():
    """Mock LLM provider."""
    llm = MagicMock()
    llm.complete = AsyncMock(return_value="mock response")
    return llm


@pytest.fixture
def mock_error_classifier():
    """Mock error classifier."""
    def classifier(error_msg: str):
        result = MagicMock()
        result.code = "TEST_ERROR"
        result.category = "test"
        result.suggestion = "test suggestion"
        return result
    return classifier


@pytest.fixture
def events():
    """Real event emitter."""
    return EventEmitter()


class TestParallelExecutionIntegration:
    """Test WorkflowEngine integration with ParallelExecutor."""

    @pytest.mark.asyncio
    async def test_parallel_execution_enabled(
        self, mock_config_parallel_enabled, mock_dispatcher_with_registry,
        mock_llm, mock_error_classifier, events
    ):
        """WorkflowEngine uses parallel execution when enabled."""
        engine = WorkflowEngine(
            config=mock_config_parallel_enabled,
            dispatcher=mock_dispatcher_with_registry,
            llm=mock_llm,
            error_classifier=mock_error_classifier,
            events=events,
        )

        # Mock successful execution results
        mock_results = [
            ExecutionResult(
                tool_id="step_1",
                tool_call=ToolCall(id="step_1", name="pdb4amber", arguments={}),
                output=ToolOutput(output="success", success=True),
                start_time=0.0,
                end_time=1.0,
                wave_id=0
            ),
            ExecutionResult(
                tool_id="step_2",
                tool_call=ToolCall(id="step_2", name="reduce", arguments={}),
                output=ToolOutput(output="success", success=True),
                start_time=1.0,
                end_time=2.0,
                wave_id=1
            ),
            ExecutionResult(
                tool_id="step_3",
                tool_call=ToolCall(id="step_3", name="tleap", arguments={}),
                output=ToolOutput(output="success", success=True),
                start_time=2.0,
                end_time=3.0,
                wave_id=2
            ),
            ExecutionResult(
                tool_id="step_4",
                tool_call=ToolCall(id="step_4", name="sander", arguments={}),
                output=ToolOutput(output="success", success=True),
                start_time=3.0,
                end_time=4.0,
                wave_id=3
            ),
        ]

        with patch('mdpilot.agent.parallel_executor.ParallelExecutor') as MockExecutor:
            mock_executor_instance = MagicMock()
            mock_executor_instance.execute_parallel = AsyncMock(return_value=mock_results)
            MockExecutor.return_value = mock_executor_instance

            # Set up engine state
            engine._phase = engine._phase.EXECUTE
            engine._params = {"pdb_file": "test.pdb"}

            # Track events
            events_received = []
            events.on(STEP_RESULT, lambda data: events_received.append(data))

            # Execute
            await engine._run_execute()

            # Verify ParallelExecutor was created and used
            MockExecutor.assert_called_once()
            mock_executor_instance.execute_parallel.assert_called_once()

            # Verify results were processed
            assert len(events_received) == 4
            for event in events_received:
                assert event.data["data"]["success"] is True

    @pytest.mark.asyncio
    async def test_parallel_execution_disabled(
        self, mock_config_parallel_disabled, mock_dispatcher_with_registry,
        mock_llm, mock_error_classifier, events
    ):
        """WorkflowEngine uses sequential execution when parallel is disabled."""
        engine = WorkflowEngine(
            config=mock_config_parallel_disabled,
            dispatcher=mock_dispatcher_with_registry,
            llm=mock_llm,
            error_classifier=mock_error_classifier,
            events=events,
        )

        # Mock successful tool execution
        mock_dispatcher_with_registry.execute.return_value = ToolOutput(
            output="success", success=True
        )

        # Set up engine state
        engine._phase = engine._phase.EXECUTE
        engine._params = {"pdb_file": "test.pdb"}

        # Track events
        events_received = []
        events.on(STEP_RESULT, lambda data: events_received.append(data))

        with patch('mdpilot.agent.parallel_executor.ParallelExecutor') as MockExecutor:
            # Execute
            await engine._run_execute()

            # Verify ParallelExecutor was NOT used
            MockExecutor.assert_not_called()

            # Verify sequential execution happened
            assert mock_dispatcher_with_registry.execute.call_count == 4
            assert len(events_received) == 4

    @pytest.mark.asyncio
    async def test_parallel_execution_fallback_on_error(
        self, mock_config_parallel_enabled, mock_dispatcher_with_registry,
        mock_llm, mock_error_classifier, events
    ):
        """WorkflowEngine falls back to sequential on parallel execution error."""
        engine = WorkflowEngine(
            config=mock_config_parallel_enabled,
            dispatcher=mock_dispatcher_with_registry,
            llm=mock_llm,
            error_classifier=mock_error_classifier,
            events=events,
        )

        # Mock successful sequential execution
        mock_dispatcher_with_registry.execute.return_value = ToolOutput(
            output="success", success=True
        )

        # Set up engine state
        engine._phase = engine._phase.EXECUTE
        engine._params = {"pdb_file": "test.pdb"}

        # Track fallback event
        fallback_events = []
        events.on("parallel.fallback", lambda data: fallback_events.append(data))

        with patch('mdpilot.agent.parallel_executor.ParallelExecutor') as MockExecutor:
            # Make parallel execution fail
            mock_executor_instance = MagicMock()
            mock_executor_instance.execute_parallel = AsyncMock(
                side_effect=RuntimeError("Parallel execution failed")
            )
            MockExecutor.return_value = mock_executor_instance

            # Execute
            await engine._run_execute()

            # Verify fallback event was emitted
            assert len(fallback_events) == 1
            assert "Parallel execution failed" in fallback_events[0].data["data"]["reason"]

            # Verify sequential execution was used as fallback
            assert mock_dispatcher_with_registry.execute.call_count == 4

    @pytest.mark.asyncio
    async def test_parallel_execution_error_handling(
        self, mock_config_parallel_enabled, mock_dispatcher_with_registry,
        mock_llm, mock_error_classifier, events
    ):
        """WorkflowEngine handles errors from parallel execution."""
        # Disable recovery to test legacy error handling
        config = MagicMock()
        config.agent.default_mode = "react"
        config.agent.parallel.enable_parallel = True
        config.agent.parallel.max_concurrent_tools = 4
        config.agent.parallel.max_memory_mb = 8192
        config.agent.parallel.max_gpu_tools = 1
        # No recovery config

        engine = WorkflowEngine(
            config=config,
            dispatcher=mock_dispatcher_with_registry,
            llm=mock_llm,
            error_classifier=mock_error_classifier,
            events=events,
        )

        # Mock execution with all successes (to avoid fallback)
        mock_results = [
            ExecutionResult(
                tool_id="step_1",
                tool_call=ToolCall(id="step_1", name="pdb4amber", arguments={}),
                output=ToolOutput(output="success", success=True),
                start_time=0.0,
                end_time=1.0,
                wave_id=0
            ),
            ExecutionResult(
                tool_id="step_2",
                tool_call=ToolCall(id="step_2", name="reduce", arguments={}),
                output=ToolOutput(output="success", success=True),
                start_time=1.0,
                end_time=2.0,
                wave_id=1
            ),
            ExecutionResult(
                tool_id="step_3",
                tool_call=ToolCall(id="step_3", name="tleap", arguments={}),
                output=ToolOutput(output="success", success=True),
                start_time=2.0,
                end_time=3.0,
                wave_id=2
            ),
            ExecutionResult(
                tool_id="step_4",
                tool_call=ToolCall(id="step_4", name="sander", arguments={}),
                output=ToolOutput(output="success", success=True),
                start_time=3.0,
                end_time=4.0,
                wave_id=3
            ),
        ]

        with patch('mdpilot.agent.parallel_executor.ParallelExecutor') as MockExecutor:
            mock_executor_instance = MagicMock()
            mock_executor_instance.execute_parallel = AsyncMock(return_value=mock_results)
            MockExecutor.return_value = mock_executor_instance

            # Set up engine state
            engine._phase = engine._phase.EXECUTE
            engine._params = {"pdb_file": "test.pdb"}

            # Track events
            events_received = []
            events.on(STEP_RESULT, lambda data: events_received.append(data))

            # Execute - all successes should complete without fallback
            await engine._run_execute()

            # Verify all results were processed via parallel execution only
            assert len(events_received) == 4
            for event in events_received:
                assert event.data["data"]["success"] is True

    @pytest.mark.asyncio
    async def test_parallel_execution_config_missing(
        self, mock_dispatcher_with_registry, mock_llm, mock_error_classifier, events
    ):
        """WorkflowEngine handles missing parallel config gracefully."""
        # Config without parallel settings
        config = MagicMock()
        config.agent.default_mode = "react"
        # No parallel attribute
        del config.agent.parallel

        engine = WorkflowEngine(
            config=config,
            dispatcher=mock_dispatcher_with_registry,
            llm=mock_llm,
            error_classifier=mock_error_classifier,
            events=events,
        )

        # Mock successful sequential execution
        mock_dispatcher_with_registry.execute.return_value = ToolOutput(
            output="success", success=True
        )

        # Set up engine state
        engine._phase = engine._phase.EXECUTE
        engine._params = {"pdb_file": "test.pdb"}

        with patch('mdpilot.agent.parallel_executor.ParallelExecutor') as MockExecutor:
            # Execute - should use sequential
            await engine._run_execute()

            # Verify ParallelExecutor was NOT used
            MockExecutor.assert_not_called()

            # Verify sequential execution happened
            assert mock_dispatcher_with_registry.execute.call_count == 4


class TestParallelExecutorCreation:
    """Test ParallelExecutor creation with correct parameters."""

    @pytest.mark.asyncio
    async def test_executor_created_with_correct_config(
        self, mock_config_parallel_enabled, mock_dispatcher_with_registry,
        mock_llm, mock_error_classifier, events
    ):
        """ParallelExecutor is created with correct configuration."""
        engine = WorkflowEngine(
            config=mock_config_parallel_enabled,
            dispatcher=mock_dispatcher_with_registry,
            llm=mock_llm,
            error_classifier=mock_error_classifier,
            events=events,
        )

        # Set up engine state
        engine._phase = engine._phase.EXECUTE
        engine._params = {"pdb_file": "test.pdb"}

        with patch('mdpilot.agent.parallel_executor.ParallelExecutor') as MockExecutor:
            with patch('mdpilot.agent.parallel_executor.ExecutionConfig') as MockConfig:
                mock_executor_instance = MagicMock()
                mock_executor_instance.execute_parallel = AsyncMock(return_value=[])
                MockExecutor.return_value = mock_executor_instance

                # Execute
                await engine._run_execute()

                # Verify ExecutionConfig was created with correct parameters
                MockConfig.assert_called_once_with(
                    max_concurrent_tools=4,
                    max_memory_mb=8192,
                    max_gpu_tools=1,
                    enable_parallel=True
                )

                # Verify ParallelExecutor was created with dispatcher, registry, config, events
                assert MockExecutor.call_count == 1
                call_args = MockExecutor.call_args
                assert call_args[0][0] == mock_dispatcher_with_registry  # dispatcher
                assert call_args[0][1] == mock_dispatcher_with_registry._registry  # registry
                # config is call_args[0][2]
                assert call_args[0][3] == events  # events
