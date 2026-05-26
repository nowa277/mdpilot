"""Integration tests for WorkflowEngine with recovery system."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import tempfile
import shutil

from mdpilot.agent.legacy_workflow_engine import WorkflowEngine, Phase
from mdpilot.agent.events import EventEmitter
from mdpilot.config.schema import AppConfig, AgentConfig, RecoveryConfig, CheckpointConfig, RetryConfig
from mdpilot.types import ToolOutput

# Use anyio for async tests
pytestmark = pytest.mark.anyio


@pytest.fixture
def temp_checkpoint_dir():
    """Create temporary directory for checkpoints."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def config_with_recovery():
    """Configuration with recovery enabled."""
    config = MagicMock(spec=AppConfig)
    config.agent = MagicMock(spec=AgentConfig)
    config.agent.recovery = RecoveryConfig(
        checkpoint=CheckpointConfig(
            enabled=True,
            checkpoint_interval=5,
            long_operation_threshold=60,
            cleanup_on_success=True
        ),
        retry=RetryConfig(
            default_max_attempts=3,
            default_backoff_base=2.0,
            max_backoff=300.0
        )
    )
    return config


@pytest.fixture
def config_without_recovery():
    """Configuration without recovery (backward compatibility)."""
    config = MagicMock()
    # Simulate old config without agent.recovery attribute
    config.agent = MagicMock()
    delattr(config.agent, 'recovery')
    return config


@pytest.fixture
def mock_dispatcher():
    """Mock tool dispatcher."""
    dispatcher = MagicMock()
    dispatcher.execute = AsyncMock()
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


class TestBackwardCompatibility:
    """Test that WorkflowEngine works without recovery config."""

    def test_engine_without_recovery_config(self, config_without_recovery, mock_dispatcher, mock_llm, mock_error_classifier, events):
        """Engine initializes without recovery when config lacks recovery section."""
        engine = WorkflowEngine(
            config=config_without_recovery,
            dispatcher=mock_dispatcher,
            llm=mock_llm,
            error_classifier=mock_error_classifier,
            events=events
        )

        assert engine.checkpoint_mgr is None
        assert engine.retry_policy is None
        assert engine.recovery is None

    async def test_workflow_runs_without_recovery(self, config_without_recovery, mock_dispatcher, mock_llm, mock_error_classifier, events, tmp_path):
        """Workflow executes normally without recovery components."""
        engine = WorkflowEngine(
            config=config_without_recovery,
            dispatcher=mock_dispatcher,
            llm=mock_llm,
            error_classifier=mock_error_classifier,
            events=events
        )

        # Mock successful tool execution
        mock_dispatcher.execute.return_value = ToolOutput(
            success=True,
            output="success",
            error=None,
            error_code=None,
            error_category=None,
            error_suggestion=None
        )

        # Create a test PDB file
        test_pdb = tmp_path / "test.pdb"
        test_pdb.write_text("ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N\n")

        # Mock mode selection
        async def set_mode():
            await asyncio.sleep(0.1)
            engine.set_workflow_mode("auto")

        # Mock parameter confirmation (not needed in auto mode)
        asyncio.create_task(set_mode())

        # Run workflow
        with patch.object(Path, 'cwd', return_value=tmp_path):
            result = await engine.run(str(test_pdb))

        assert result == "Workflow complete"
        assert engine._phase == Phase.COMPLETE


class TestRecoveryIntegration:
    """Test WorkflowEngine with recovery enabled."""

    def test_engine_with_recovery_config(self, config_with_recovery, mock_dispatcher, mock_llm, mock_error_classifier, events):
        """Engine initializes recovery components when config has recovery section."""
        engine = WorkflowEngine(
            config=config_with_recovery,
            dispatcher=mock_dispatcher,
            llm=mock_llm,
            error_classifier=mock_error_classifier,
            events=events
        )

        assert engine.checkpoint_mgr is not None
        assert engine.retry_policy is not None
        assert engine.recovery is not None

    
    async def test_checkpoint_saved_after_analyze(self, config_with_recovery, mock_dispatcher, mock_llm, mock_error_classifier, events, tmp_path):
        """Checkpoint is saved after ANALYZE phase."""
        engine = WorkflowEngine(
            config=config_with_recovery,
            dispatcher=mock_dispatcher,
            llm=mock_llm,
            error_classifier=mock_error_classifier,
            events=events
        )

        # Track checkpoint events
        checkpoint_events = []
        events.on("checkpoint.saved", lambda event: checkpoint_events.append(event.data))

        # Create test PDB
        test_pdb = tmp_path / "test.pdb"
        test_pdb.write_text("ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N\n")

        # Mock mode selection
        async def set_mode():
            await asyncio.sleep(0.1)
            engine.set_workflow_mode("auto")

        asyncio.create_task(set_mode())

        # Patch checkpoint directory to use tmp_path
        with patch.object(Path, 'cwd', return_value=tmp_path):
            # Re-initialize checkpoint manager with correct path
            engine.checkpoint_mgr.checkpoint_dir = tmp_path
            engine.checkpoint_mgr.checkpoint_file = tmp_path / ".workflow_checkpoint.json"

            # Run only analyze phase
            await engine._run_analyze(str(test_pdb))

        # Verify checkpoint was saved
        assert len(checkpoint_events) > 0
        assert checkpoint_events[0]["data"]["phase"] == "ANALYZE"
        assert (tmp_path / ".workflow_checkpoint.json").exists()

    
    async def test_checkpoint_loaded_on_restart(self, config_with_recovery, mock_dispatcher, mock_llm, mock_error_classifier, events, tmp_path):
        """Checkpoint is loaded when workflow restarts."""
        # Create a checkpoint file
        checkpoint_file = tmp_path / ".workflow_checkpoint.json"
        checkpoint_data = {
            "workflow_id": "test_workflow",
            "timestamp": "2024-01-01T00:00:00",
            "current_phase": "CONFIGURE",
            "current_step_index": 0,
            "completed_phases": ["ANALYZE"],
            "phase_results": {},
            "step_results": [],
            "context": {"params": {}}
        }
        import json
        checkpoint_file.write_text(json.dumps(checkpoint_data))

        engine = WorkflowEngine(
            config=config_with_recovery,
            dispatcher=mock_dispatcher,
            llm=mock_llm,
            error_classifier=mock_error_classifier,
            events=events
        )

        # Track checkpoint loaded events
        loaded_events = []
        events.on("checkpoint.loaded", lambda event: loaded_events.append(event.data))

        # Patch checkpoint directory
        with patch.object(Path, 'cwd', return_value=tmp_path):
            engine.checkpoint_mgr.checkpoint_dir = tmp_path
            engine.checkpoint_mgr.checkpoint_file = checkpoint_file

            # Mock successful execution
            mock_dispatcher.execute.return_value = ToolOutput(
                success=True,
                output="success",
                error=None,
                error_code=None,
                error_category=None,
                error_suggestion=None
            )

            # Create test PDB
            test_pdb = tmp_path / "test.pdb"
            test_pdb.write_text("ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N\n")

            # Mock mode selection
            async def set_mode():
                await asyncio.sleep(0.1)
                engine.set_workflow_mode("auto")

            asyncio.create_task(set_mode())

            # Run workflow
            result = await engine.run(str(test_pdb))

        # Verify checkpoint was loaded
        assert len(loaded_events) > 0
        assert loaded_events[0]["data"]["phase"] == "CONFIGURE"

    
    async def test_checkpoint_cleanup_on_success(self, config_with_recovery, mock_dispatcher, mock_llm, mock_error_classifier, events, tmp_path):
        """Checkpoint is cleaned up on successful completion."""
        engine = WorkflowEngine(
            config=config_with_recovery,
            dispatcher=mock_dispatcher,
            llm=mock_llm,
            error_classifier=mock_error_classifier,
            events=events
        )

        # Track cleanup events
        cleanup_events = []
        events.on("checkpoint.cleaned", lambda event: cleanup_events.append(event.data))

        # Patch checkpoint directory
        with patch.object(Path, 'cwd', return_value=tmp_path):
            engine.checkpoint_mgr.checkpoint_dir = tmp_path
            engine.checkpoint_mgr.checkpoint_file = tmp_path / ".workflow_checkpoint.json"

            # Create a checkpoint file
            engine.checkpoint_mgr.checkpoint_file.write_text('{"test": "data"}')

            # Run complete phase
            result = await engine._run_complete()

        # Verify checkpoint was cleaned up
        assert len(cleanup_events) > 0
        assert not (tmp_path / ".workflow_checkpoint.json").exists()


class TestErrorRecovery:
    """Test error recovery with retry logic."""

    
    async def test_error_recovery_with_retry(self, config_with_recovery, mock_dispatcher, mock_llm, mock_error_classifier, events, tmp_path):
        """Recovery coordinator handles errors and schedules retries."""
        engine = WorkflowEngine(
            config=config_with_recovery,
            dispatcher=mock_dispatcher,
            llm=mock_llm,
            error_classifier=mock_error_classifier,
            events=events
        )

        # Track recovery events
        recovery_events = []
        events.on("recovery.retry_scheduled", lambda event: recovery_events.append(event.data))

        # Mock tool failure
        mock_dispatcher.execute.return_value = ToolOutput(
            success=False,
            output="",
            error="Connection timeout",
            error_code="TIMEOUT",
            error_category="transient",
            error_suggestion="Retry the operation"
        )

        # Patch checkpoint directory
        with patch.object(Path, 'cwd', return_value=tmp_path):
            engine.checkpoint_mgr.checkpoint_dir = tmp_path
            engine.checkpoint_mgr.checkpoint_file = tmp_path / ".workflow_checkpoint.json"

            # Set phase to EXECUTE
            engine._phase = Phase.EXECUTE
            engine._params = {"pdb_file": "test.pdb"}

            # Run execute phase (will fail and trigger recovery)
            try:
                await engine._run_execute()
            except RuntimeError:
                pass  # Expected to fail eventually

        # Verify recovery was triggered
        assert len(recovery_events) > 0

    
    async def test_legacy_error_handling_without_recovery(self, config_without_recovery, mock_dispatcher, mock_llm, mock_error_classifier, events, tmp_path):
        """Legacy error handling works when recovery is disabled."""
        engine = WorkflowEngine(
            config=config_without_recovery,
            dispatcher=mock_dispatcher,
            llm=mock_llm,
            error_classifier=mock_error_classifier,
            events=events
        )

        # Track retry events
        retry_events = []
        events.on("retry_attempt", lambda event: retry_events.append(event.data))

        # Mock tool failure
        mock_dispatcher.execute.return_value = ToolOutput(
            success=False,
            output="",
            error="Test error",
            error_code="TEST",
            error_category="test",
            error_suggestion="Test suggestion"
        )

        # Set phase to EXECUTE
        engine._phase = Phase.EXECUTE
        engine._params = {"pdb_file": "test.pdb"}

        # Run execute phase (will fail and use legacy retry)
        try:
            await engine._run_execute()
        except RuntimeError:
            pass  # Expected to fail eventually

        # Verify legacy retry was used
        assert len(retry_events) > 0


class TestCheckpointStateCreation:
    """Test checkpoint state creation."""

    def test_create_checkpoint_state(self, config_with_recovery, mock_dispatcher, mock_llm, mock_error_classifier, events):
        """Checkpoint state is created correctly from engine state."""
        engine = WorkflowEngine(
            config=config_with_recovery,
            dispatcher=mock_dispatcher,
            llm=mock_llm,
            error_classifier=mock_error_classifier,
            events=events
        )

        # Set some state
        engine._phase = Phase.CONFIGURE
        engine._params = {"forcefield": "ff19SB", "water_model": "OPC3"}

        # Create checkpoint state
        state = engine._create_checkpoint_state()

        assert state.current_phase == "configure"
        assert state.context["params"] == engine._params
        assert state.workflow_id.startswith("workflow_")
        assert state.timestamp is not None
