"""Checkpoint management for workflow state persistence.

This module provides checkpoint functionality to save and restore workflow state,
enabling recovery from failures and resumption of interrupted workflows.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class WorkflowState:
    """Represents the complete state of a workflow at a point in time.

    This state can be serialized to disk and restored to resume workflow execution.
    """

    workflow_id: str
    timestamp: str
    current_phase: str
    current_step_index: int
    completed_phases: list[str] = field(default_factory=list)
    phase_results: dict[str, Any] = field(default_factory=dict)
    step_results: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize workflow state to dictionary.

        Returns:
            Dictionary representation of the workflow state.
        """
        return {
            "workflow_id": self.workflow_id,
            "timestamp": self.timestamp,
            "current_phase": self.current_phase,
            "current_step_index": self.current_step_index,
            "completed_phases": self.completed_phases,
            "phase_results": self.phase_results,
            "step_results": self.step_results,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowState":
        """Deserialize workflow state from dictionary.

        Args:
            data: Dictionary containing workflow state data.

        Returns:
            WorkflowState instance.

        Raises:
            KeyError: If required fields are missing.
            TypeError: If field types are invalid.
        """
        return cls(
            workflow_id=data["workflow_id"],
            timestamp=data["timestamp"],
            current_phase=data["current_phase"],
            current_step_index=data["current_step_index"],
            completed_phases=data.get("completed_phases", []),
            phase_results=data.get("phase_results", {}),
            step_results=data.get("step_results", []),
            context=data.get("context", {}),
        )


@dataclass
class CheckpointConfig:
    """Configuration for checkpoint behavior.

    Attributes:
        enabled: Whether checkpointing is enabled.
        checkpoint_interval: Save checkpoint every N steps.
        long_operation_threshold: Save checkpoint before operations exceeding N seconds.
        cleanup_on_success: Remove checkpoint file on successful workflow completion.
    """

    enabled: bool = True
    checkpoint_interval: int = 5
    long_operation_threshold: int = 60
    cleanup_on_success: bool = True


class CheckpointManager:
    """Manages workflow state checkpoints for recovery and resumption.

    Provides atomic checkpoint saves using temp file + rename pattern,
    and handles checkpoint loading with error recovery.
    """

    def __init__(self, checkpoint_dir: Path, config: CheckpointConfig):
        """Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory where checkpoint files are stored.
            config: Checkpoint configuration.
        """
        self.checkpoint_dir = checkpoint_dir
        self.config = config
        self.checkpoint_file = checkpoint_dir / ".workflow_checkpoint.json"

    def save_checkpoint(self, state: WorkflowState) -> None:
        """Save checkpoint atomically to disk.

        Uses temp file + rename pattern to ensure atomic writes and prevent
        corruption from interrupted saves.

        Args:
            state: Workflow state to save.

        Raises:
            OSError: If file write fails.
        """
        try:
            # Ensure checkpoint directory exists
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

            # Write to temp file first
            temp_file = self.checkpoint_dir / ".workflow_checkpoint.tmp"
            with open(temp_file, "w") as f:
                json.dump(state.to_dict(), f, indent=2)

            # Atomic rename (POSIX guarantees atomicity)
            temp_file.rename(self.checkpoint_file)

            logger.debug(
                f"Checkpoint saved: workflow_id={state.workflow_id}, "
                f"phase={state.current_phase}, step={state.current_step_index}"
            )

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            raise

    def load_checkpoint(self) -> Optional[WorkflowState]:
        """Load checkpoint from disk if it exists.

        Returns:
            WorkflowState if checkpoint exists and is valid, None otherwise.
        """
        if not self.checkpoint_file.exists():
            logger.debug("No checkpoint file found")
            return None

        try:
            with open(self.checkpoint_file) as f:
                data = json.load(f)

            state = WorkflowState.from_dict(data)
            logger.info(
                f"Checkpoint loaded: workflow_id={state.workflow_id}, "
                f"phase={state.current_phase}, step={state.current_step_index}"
            )
            return state

        except json.JSONDecodeError as e:
            logger.warning(f"Corrupted checkpoint file (invalid JSON): {e}")
            return None

        except (KeyError, TypeError) as e:
            logger.warning(f"Invalid checkpoint data (missing/invalid fields): {e}")
            return None

        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None

    def should_checkpoint(self, context: dict) -> bool:
        """Decide if checkpoint should be saved based on configuration and context.

        Checkpoint triggers:
        1. Phase transitions (always)
        2. Long operations (estimated_duration > threshold)
        3. Regular intervals (every N steps)

        Args:
            context: Execution context containing trigger information.

        Returns:
            True if checkpoint should be saved, False otherwise.
        """
        # Always checkpoint on phase transitions
        if context.get("phase_transition"):
            return True

        # Checkpoint before long operations
        estimated_duration = context.get("estimated_duration", 0)
        if estimated_duration > self.config.long_operation_threshold:
            return True

        # Checkpoint at regular intervals
        step_index = context.get("step_index", 0)
        if step_index % self.config.checkpoint_interval == 0:
            return True

        return False

    def cleanup_checkpoint(self) -> None:
        """Remove checkpoint file from disk.

        Called on successful workflow completion if cleanup_on_success is enabled.
        Does not raise error if file doesn't exist.
        """
        try:
            if self.checkpoint_file.exists():
                self.checkpoint_file.unlink()
                logger.debug("Checkpoint file cleaned up")
        except Exception as e:
            logger.warning(f"Failed to cleanup checkpoint: {e}")

    def exists(self) -> bool:
        """Check if checkpoint file exists.

        Returns:
            True if checkpoint file exists, False otherwise.
        """
        return self.checkpoint_file.exists()
