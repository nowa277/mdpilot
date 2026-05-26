"""RecoveryCoordinator — orchestrates error recovery for workflow execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from mdpilot.agent.checkpoint import CheckpointManager
from mdpilot.agent.error_classifier import ErrorCategory, ErrorClassifier
from mdpilot.agent.events import EventEmitter
from mdpilot.agent.retry_policy import RetryPolicy


class RecoveryActionType(Enum):
    """Types of recovery actions."""

    RETRY = "retry"  # Retry the operation
    SKIP = "skip"  # Skip and continue
    FAIL = "fail"  # Fail the workflow
    RECONFIGURE = "reconfigure"  # Return to CONFIGURE phase


@dataclass
class RecoveryAction:
    """Recovery action to take after error."""

    type: RecoveryActionType
    delay: float = 0.0  # Delay before retry (seconds)
    reason: str = ""  # Human-readable reason


class RecoveryCoordinator:
    """Coordinates error handling, retry, and recovery."""

    def __init__(
        self,
        checkpoint_mgr: CheckpointManager,
        retry_policy: RetryPolicy,
        error_classifier: ErrorClassifier,
        events: EventEmitter,
    ):
        """Initialize RecoveryCoordinator.

        Parameters
        ----------
        checkpoint_mgr : CheckpointManager
            Checkpoint manager for state persistence.
        retry_policy : RetryPolicy
            Retry policy for determining retry behavior.
        error_classifier : ErrorClassifier
            Error classifier for categorizing errors.
        events : EventEmitter
            Event emitter for recovery events.
        """
        self.checkpoint_mgr = checkpoint_mgr
        self.retry_policy = retry_policy
        self.error_classifier = error_classifier
        self.events = events

    def handle_error(self, error: Exception, context: dict) -> RecoveryAction:
        """Handle error and return recovery action.

        Parameters
        ----------
        error : Exception
            The exception that occurred.
        context : dict
            Execution context containing:
            - tool: str - Tool name (e.g., "pmemd")
            - attempt: int - Current attempt number (0-indexed)
            - phase: str - Current workflow phase
            - retry_count: int (optional) - Number of retries already attempted

        Returns
        -------
        RecoveryAction
            The recovery action to take.

        Recovery Logic
        --------------
        1. Classify error into category
        2. Get retry parameters for tool and error type
        3. Check if should retry based on attempt count
        4. Calculate delay if retrying
        5. Emit appropriate events
        6. Return RecoveryAction

        Recovery Strategy
        -----------------
        - TRANSIENT errors → RETRY with exponential backoff
        - RESOURCE errors → RETRY with longer backoff
        - CONFIGURATION errors → RECONFIGURE (return to CONFIGURE phase)
        - PERMANENT errors → FAIL immediately
        - Retry exhausted → FAIL
        """
        # Extract context values with defaults
        tool = context.get("tool", "unknown")
        attempt = context.get("attempt", 0)
        phase = context.get("phase", "UNKNOWN")

        # 1. Classify error
        category = self.error_classifier.classify(error, context)

        # Emit classification event
        self.events.emit(
            "error.classified",
            category=category,
            error_type=type(error).__name__,
            error_message=str(error),
            tool=tool,
            phase=phase,
        )

        # 2. Get retry parameters
        retry_params = self.retry_policy.get_retry_params(tool, category)

        # 3. Check if should retry
        should_retry = self.retry_policy.should_retry(attempt, category, retry_params)

        # Handle CONFIGURATION errors → RECONFIGURE
        if category == ErrorCategory.CONFIGURATION:
            self.events.emit(
                "recovery.reconfigure",
                phase=phase,
                error_type=type(error).__name__,
                error_message=str(error),
                tool=tool,
            )
            return RecoveryAction(
                type=RecoveryActionType.RECONFIGURE,
                delay=0.0,
                reason=f"Configuration error in {phase} phase, returning to CONFIGURE",
            )

        # Handle PERMANENT errors → FAIL
        if category == ErrorCategory.PERMANENT:
            self.events.emit(
                "recovery.failed",
                category=category,
                error_type=type(error).__name__,
                error_message=str(error),
                tool=tool,
                phase=phase,
                reason="Permanent error, cannot recover",
            )
            return RecoveryAction(
                type=RecoveryActionType.FAIL,
                delay=0.0,
                reason=f"Permanent error: {type(error).__name__}",
            )

        # Handle retry exhaustion → FAIL
        if not should_retry:
            self.events.emit(
                "recovery.retry_exhausted",
                attempt=attempt,
                max_attempts=retry_params.max_attempts,
                tool=tool,
                phase=phase,
                error_type=type(error).__name__,
            )
            self.events.emit(
                "recovery.failed",
                category=category,
                error_type=type(error).__name__,
                error_message=str(error),
                tool=tool,
                phase=phase,
                reason="Max retry attempts exhausted",
            )
            return RecoveryAction(
                type=RecoveryActionType.FAIL,
                delay=0.0,
                reason=f"Max retry attempts ({retry_params.max_attempts}) exhausted",
            )

        # 4. Calculate delay for retry
        delay = self.retry_policy.calculate_delay(attempt, retry_params)

        # 5. Emit retry scheduled event
        self.events.emit(
            "recovery.retry_scheduled",
            attempt=attempt,
            delay=delay,
            tool=tool,
            phase=phase,
            category=category,
            error_type=type(error).__name__,
        )

        # 6. Return RETRY action
        reason = f"Retrying {category.value} error (attempt {attempt + 1}/{retry_params.max_attempts})"
        return RecoveryAction(
            type=RecoveryActionType.RETRY,
            delay=delay,
            reason=reason,
        )
