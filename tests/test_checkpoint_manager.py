"""Tests for CheckpointManager - workflow state persistence."""

import json
import time
from pathlib import Path

import pytest

from mdpilot.agent.checkpoint import (
    CheckpointConfig,
    CheckpointManager,
    WorkflowState,
)


class TestWorkflowState:
    """Test WorkflowState dataclass serialization."""

    def test_to_dict(self):
        """Test WorkflowState serialization to dict."""
        state = WorkflowState(
            workflow_id="test-123",
            timestamp="2026-05-09T10:30:00Z",
            current_phase="RUN",
            current_step_index=2,
            completed_phases=["CONFIGURE", "PREPARE"],
            phase_results={"CONFIGURE": {"status": "success"}},
            step_results=[{"step": "minimize", "status": "success"}],
            context={"config": {"system": "protein.prmtop"}},
        )

        result = state.to_dict()

        assert result["workflow_id"] == "test-123"
        assert result["timestamp"] == "2026-05-09T10:30:00Z"
        assert result["current_phase"] == "RUN"
        assert result["current_step_index"] == 2
        assert result["completed_phases"] == ["CONFIGURE", "PREPARE"]
        assert result["phase_results"] == {"CONFIGURE": {"status": "success"}}
        assert result["step_results"] == [{"step": "minimize", "status": "success"}]
        assert result["context"] == {"config": {"system": "protein.prmtop"}}

    def test_from_dict(self):
        """Test WorkflowState deserialization from dict."""
        data = {
            "workflow_id": "test-456",
            "timestamp": "2026-05-09T11:00:00Z",
            "current_phase": "ANALYZE",
            "current_step_index": 5,
            "completed_phases": ["CONFIGURE", "PREPARE", "RUN"],
            "phase_results": {
                "CONFIGURE": {"status": "success"},
                "PREPARE": {"status": "success"},
            },
            "step_results": [
                {"step": "minimize", "status": "success"},
                {"step": "heat", "status": "success"},
            ],
            "context": {"retry_counts": {"pmemd": 1}},
        }

        state = WorkflowState.from_dict(data)

        assert state.workflow_id == "test-456"
        assert state.timestamp == "2026-05-09T11:00:00Z"
        assert state.current_phase == "ANALYZE"
        assert state.current_step_index == 5
        assert state.completed_phases == ["CONFIGURE", "PREPARE", "RUN"]
        assert state.phase_results == {
            "CONFIGURE": {"status": "success"},
            "PREPARE": {"status": "success"},
        }
        assert state.step_results == [
            {"step": "minimize", "status": "success"},
            {"step": "heat", "status": "success"},
        ]
        assert state.context == {"retry_counts": {"pmemd": 1}}

    def test_round_trip_serialization(self):
        """Test that to_dict/from_dict round-trip preserves data."""
        original = WorkflowState(
            workflow_id="test-789",
            timestamp="2026-05-09T12:00:00Z",
            current_phase="PREPARE",
            current_step_index=1,
            completed_phases=["CONFIGURE"],
            phase_results={"CONFIGURE": {"status": "success", "duration": 1.2}},
            step_results=[],
            context={"environment": {"AMBERHOME": "/opt/amber"}},
        )

        # Round-trip
        data = original.to_dict()
        restored = WorkflowState.from_dict(data)

        assert restored.workflow_id == original.workflow_id
        assert restored.timestamp == original.timestamp
        assert restored.current_phase == original.current_phase
        assert restored.current_step_index == original.current_step_index
        assert restored.completed_phases == original.completed_phases
        assert restored.phase_results == original.phase_results
        assert restored.step_results == original.step_results
        assert restored.context == original.context


class TestCheckpointConfig:
    """Test CheckpointConfig dataclass."""

    def test_default_values(self):
        """Test CheckpointConfig default values."""
        config = CheckpointConfig()

        assert config.enabled is True
        assert config.checkpoint_interval == 5
        assert config.long_operation_threshold == 60
        assert config.cleanup_on_success is True

    def test_custom_values(self):
        """Test CheckpointConfig with custom values."""
        config = CheckpointConfig(
            enabled=False,
            checkpoint_interval=10,
            long_operation_threshold=120,
            cleanup_on_success=False,
        )

        assert config.enabled is False
        assert config.checkpoint_interval == 10
        assert config.long_operation_threshold == 120
        assert config.cleanup_on_success is False


class TestCheckpointManager:
    """Test CheckpointManager functionality."""

    def test_init(self, tmp_path):
        """Test CheckpointManager initialization."""
        config = CheckpointConfig()
        manager = CheckpointManager(tmp_path, config)

        assert manager.checkpoint_dir == tmp_path
        assert manager.config == config
        assert manager.checkpoint_file == tmp_path / ".workflow_checkpoint.json"

    def test_save_checkpoint(self, tmp_path):
        """Test saving checkpoint to disk."""
        manager = CheckpointManager(tmp_path, CheckpointConfig())
        state = WorkflowState(
            workflow_id="test-save",
            timestamp="2026-05-09T10:00:00Z",
            current_phase="RUN",
            current_step_index=3,
            completed_phases=["CONFIGURE", "PREPARE"],
            phase_results={},
            step_results=[],
            context={},
        )

        manager.save_checkpoint(state)

        # Verify file exists
        assert manager.checkpoint_file.exists()

        # Verify content
        with open(manager.checkpoint_file) as f:
            data = json.load(f)
        assert data["workflow_id"] == "test-save"
        assert data["current_phase"] == "RUN"
        assert data["current_step_index"] == 3

    def test_save_checkpoint_atomic(self, tmp_path):
        """Test that checkpoint save is atomic (uses temp file + rename)."""
        manager = CheckpointManager(tmp_path, CheckpointConfig())
        state = WorkflowState(
            workflow_id="test-atomic",
            timestamp="2026-05-09T10:00:00Z",
            current_phase="RUN",
            current_step_index=1,
            completed_phases=[],
            phase_results={},
            step_results=[],
            context={},
        )

        manager.save_checkpoint(state)

        # Verify temp file doesn't exist after save
        temp_file = tmp_path / ".workflow_checkpoint.tmp"
        assert not temp_file.exists()

        # Verify final file exists
        assert manager.checkpoint_file.exists()

    def test_load_checkpoint(self, tmp_path):
        """Test loading checkpoint from disk."""
        manager = CheckpointManager(tmp_path, CheckpointConfig())
        original_state = WorkflowState(
            workflow_id="test-load",
            timestamp="2026-05-09T11:00:00Z",
            current_phase="ANALYZE",
            current_step_index=4,
            completed_phases=["CONFIGURE", "PREPARE", "RUN"],
            phase_results={"RUN": {"status": "success"}},
            step_results=[{"step": "production", "status": "success"}],
            context={"retry_counts": {"cpptraj": 2}},
        )

        # Save first
        manager.save_checkpoint(original_state)

        # Load
        loaded_state = manager.load_checkpoint()

        assert loaded_state is not None
        assert loaded_state.workflow_id == "test-load"
        assert loaded_state.current_phase == "ANALYZE"
        assert loaded_state.current_step_index == 4
        assert loaded_state.completed_phases == ["CONFIGURE", "PREPARE", "RUN"]
        assert loaded_state.phase_results == {"RUN": {"status": "success"}}
        assert loaded_state.step_results == [{"step": "production", "status": "success"}]
        assert loaded_state.context == {"retry_counts": {"cpptraj": 2}}

    def test_load_checkpoint_not_exists(self, tmp_path):
        """Test loading checkpoint when file doesn't exist."""
        manager = CheckpointManager(tmp_path, CheckpointConfig())

        result = manager.load_checkpoint()

        assert result is None

    def test_load_checkpoint_corrupted_json(self, tmp_path):
        """Test loading checkpoint with corrupted JSON."""
        manager = CheckpointManager(tmp_path, CheckpointConfig())

        # Write corrupted JSON
        with open(manager.checkpoint_file, "w") as f:
            f.write("{invalid json content")

        # Should return None on corrupted file
        result = manager.load_checkpoint()
        assert result is None

    def test_load_checkpoint_missing_fields(self, tmp_path):
        """Test loading checkpoint with missing required fields."""
        manager = CheckpointManager(tmp_path, CheckpointConfig())

        # Write incomplete data
        with open(manager.checkpoint_file, "w") as f:
            json.dump({"workflow_id": "test"}, f)

        # Should return None on invalid data
        result = manager.load_checkpoint()
        assert result is None

    def test_should_checkpoint_phase_transition(self, tmp_path):
        """Test should_checkpoint returns True on phase transitions."""
        config = CheckpointConfig()
        manager = CheckpointManager(tmp_path, config)

        context = {"phase_transition": True}

        assert manager.should_checkpoint(context) is True

    def test_should_checkpoint_long_operation(self, tmp_path):
        """Test should_checkpoint returns True for long operations."""
        config = CheckpointConfig(long_operation_threshold=60)
        manager = CheckpointManager(tmp_path, config)

        context = {"estimated_duration": 120}

        assert manager.should_checkpoint(context) is True

    def test_should_checkpoint_long_operation_below_threshold(self, tmp_path):
        """Test should_checkpoint returns False for short operations."""
        config = CheckpointConfig(long_operation_threshold=60)
        manager = CheckpointManager(tmp_path, config)

        context = {"estimated_duration": 30, "step_index": 1}

        assert manager.should_checkpoint(context) is False

    def test_should_checkpoint_interval(self, tmp_path):
        """Test should_checkpoint returns True at checkpoint intervals."""
        config = CheckpointConfig(checkpoint_interval=5)
        manager = CheckpointManager(tmp_path, config)

        # Should checkpoint at multiples of 5
        assert manager.should_checkpoint({"step_index": 0}) is True
        assert manager.should_checkpoint({"step_index": 5}) is True
        assert manager.should_checkpoint({"step_index": 10}) is True

        # Should not checkpoint at other steps
        assert manager.should_checkpoint({"step_index": 1}) is False
        assert manager.should_checkpoint({"step_index": 3}) is False
        assert manager.should_checkpoint({"step_index": 7}) is False

    def test_should_checkpoint_multiple_triggers(self, tmp_path):
        """Test should_checkpoint with multiple triggers."""
        config = CheckpointConfig(checkpoint_interval=5, long_operation_threshold=60)
        manager = CheckpointManager(tmp_path, config)

        # Phase transition takes precedence
        context = {
            "phase_transition": True,
            "estimated_duration": 30,
            "step_index": 3,
        }
        assert manager.should_checkpoint(context) is True

        # Long operation
        context = {"estimated_duration": 120, "step_index": 3}
        assert manager.should_checkpoint(context) is True

        # Interval
        context = {"step_index": 10}
        assert manager.should_checkpoint(context) is True

    def test_should_checkpoint_no_triggers(self, tmp_path):
        """Test should_checkpoint returns False when no triggers match."""
        config = CheckpointConfig(checkpoint_interval=5, long_operation_threshold=60)
        manager = CheckpointManager(tmp_path, config)

        context = {"step_index": 3, "estimated_duration": 30}

        assert manager.should_checkpoint(context) is False

    def test_cleanup_checkpoint(self, tmp_path):
        """Test cleanup_checkpoint removes checkpoint file."""
        manager = CheckpointManager(tmp_path, CheckpointConfig())
        state = WorkflowState(
            workflow_id="test-cleanup",
            timestamp="2026-05-09T10:00:00Z",
            current_phase="RUN",
            current_step_index=1,
            completed_phases=[],
            phase_results={},
            step_results=[],
            context={},
        )

        # Save checkpoint
        manager.save_checkpoint(state)
        assert manager.checkpoint_file.exists()

        # Cleanup
        manager.cleanup_checkpoint()
        assert not manager.checkpoint_file.exists()

    def test_cleanup_checkpoint_not_exists(self, tmp_path):
        """Test cleanup_checkpoint when file doesn't exist (should not error)."""
        manager = CheckpointManager(tmp_path, CheckpointConfig())

        # Should not raise error
        manager.cleanup_checkpoint()

    def test_exists(self, tmp_path):
        """Test exists() method."""
        manager = CheckpointManager(tmp_path, CheckpointConfig())

        # Initially doesn't exist
        assert manager.exists() is False

        # Save checkpoint
        state = WorkflowState(
            workflow_id="test-exists",
            timestamp="2026-05-09T10:00:00Z",
            current_phase="RUN",
            current_step_index=1,
            completed_phases=[],
            phase_results={},
            step_results=[],
            context={},
        )
        manager.save_checkpoint(state)

        # Now exists
        assert manager.exists() is True

        # Cleanup
        manager.cleanup_checkpoint()

        # Doesn't exist again
        assert manager.exists() is False

    def test_save_checkpoint_performance(self, tmp_path):
        """Test that checkpoint save completes in <100ms."""
        manager = CheckpointManager(tmp_path, CheckpointConfig())
        state = WorkflowState(
            workflow_id="test-perf",
            timestamp="2026-05-09T10:00:00Z",
            current_phase="RUN",
            current_step_index=1,
            completed_phases=["CONFIGURE", "PREPARE"],
            phase_results={
                "CONFIGURE": {"status": "success", "duration": 1.2},
                "PREPARE": {"status": "success", "duration": 45.3},
            },
            step_results=[
                {"step": "minimize", "status": "success", "duration": 120.5},
                {"step": "heat", "status": "success", "duration": 300.2},
            ],
            context={"config": {"system": "protein.prmtop"}, "retry_counts": {}},
        )

        start = time.time()
        manager.save_checkpoint(state)
        duration = time.time() - start

        assert duration < 0.1  # 100ms

    def test_load_checkpoint_performance(self, tmp_path):
        """Test that checkpoint load completes in <50ms."""
        manager = CheckpointManager(tmp_path, CheckpointConfig())
        state = WorkflowState(
            workflow_id="test-perf",
            timestamp="2026-05-09T10:00:00Z",
            current_phase="RUN",
            current_step_index=1,
            completed_phases=["CONFIGURE", "PREPARE"],
            phase_results={
                "CONFIGURE": {"status": "success", "duration": 1.2},
                "PREPARE": {"status": "success", "duration": 45.3},
            },
            step_results=[
                {"step": "minimize", "status": "success", "duration": 120.5},
                {"step": "heat", "status": "success", "duration": 300.2},
            ],
            context={"config": {"system": "protein.prmtop"}, "retry_counts": {}},
        )

        # Save first
        manager.save_checkpoint(state)

        # Measure load time
        start = time.time()
        manager.load_checkpoint()
        duration = time.time() - start

        assert duration < 0.05  # 50ms

    def test_save_checkpoint_with_complex_data(self, tmp_path):
        """Test saving checkpoint with complex nested data structures."""
        manager = CheckpointManager(tmp_path, CheckpointConfig())
        state = WorkflowState(
            workflow_id="test-complex",
            timestamp="2026-05-09T10:00:00Z",
            current_phase="RUN",
            current_step_index=5,
            completed_phases=["CONFIGURE", "PREPARE"],
            phase_results={
                "CONFIGURE": {
                    "status": "success",
                    "duration": 1.2,
                    "details": {"validated": True, "warnings": []},
                },
                "PREPARE": {
                    "status": "success",
                    "duration": 45.3,
                    "files": ["system.prmtop", "system.inpcrd"],
                },
            },
            step_results=[
                {
                    "step": "minimize",
                    "status": "success",
                    "duration": 120.5,
                    "metrics": {"energy": -12345.67, "rmsd": 0.123},
                },
                {
                    "step": "heat",
                    "status": "success",
                    "duration": 300.2,
                    "metrics": {"temperature": 300.0, "pressure": 1.0},
                },
            ],
            context={
                "config": {
                    "system": "protein.prmtop",
                    "parameters": {"temperature": 300, "steps": 50000},
                },
                "retry_counts": {"pmemd": 1, "cpptraj": 0},
                "environment": {"AMBERHOME": "/opt/amber", "CUDA_VISIBLE_DEVICES": "0"},
            },
        )

        # Save and load
        manager.save_checkpoint(state)
        loaded = manager.load_checkpoint()

        # Verify complex data preserved
        assert loaded.phase_results["CONFIGURE"]["details"]["validated"] is True
        assert loaded.step_results[0]["metrics"]["energy"] == -12345.67
        assert loaded.context["config"]["parameters"]["temperature"] == 300
        assert loaded.context["retry_counts"]["pmemd"] == 1

    def test_concurrent_save_safety(self, tmp_path):
        """Test that atomic save prevents corruption from concurrent writes."""
        manager = CheckpointManager(tmp_path, CheckpointConfig())
        state1 = WorkflowState(
            workflow_id="test-1",
            timestamp="2026-05-09T10:00:00Z",
            current_phase="RUN",
            current_step_index=1,
            completed_phases=[],
            phase_results={},
            step_results=[],
            context={},
        )
        state2 = WorkflowState(
            workflow_id="test-2",
            timestamp="2026-05-09T10:00:01Z",
            current_phase="ANALYZE",
            current_step_index=2,
            completed_phases=[],
            phase_results={},
            step_results=[],
            context={},
        )

        # Save twice
        manager.save_checkpoint(state1)
        manager.save_checkpoint(state2)

        # Load should get the last saved state
        loaded = manager.load_checkpoint()
        assert loaded.workflow_id == "test-2"
        assert loaded.current_phase == "ANALYZE"

        # Verify no temp files left behind
        temp_file = tmp_path / ".workflow_checkpoint.tmp"
        assert not temp_file.exists()
