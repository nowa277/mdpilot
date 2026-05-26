"""Tests for RecoveryCoordinator — error recovery orchestration."""

from unittest.mock import Mock, call

import pytest

from mdpilot.agent.checkpoint import CheckpointConfig, CheckpointManager, WorkflowState
from mdpilot.agent.error_classifier import ErrorCategory, ErrorClassifier
from mdpilot.agent.events import Event, EventEmitter
from mdpilot.agent.recovery_coordinator import (
    RecoveryAction,
    RecoveryActionType,
    RecoveryCoordinator,
)
from mdpilot.agent.retry_policy import RetryConfig, RetryPolicy


@pytest.fixture
def checkpoint_manager(tmp_path):
    """Create CheckpointManager for testing."""
    config = CheckpointConfig(enabled=True)
    return CheckpointManager(tmp_path / "checkpoints", config)


@pytest.fixture
def retry_policy():
    """Create RetryPolicy with default config."""
    config = RetryConfig(
        default_max_attempts=3,
        default_backoff_base=2.0,
        max_backoff=60.0,
    )
    return RetryPolicy(config)


@pytest.fixture
def error_classifier():
    """Create ErrorClassifier."""
    return ErrorClassifier()


@pytest.fixture
def event_emitter():
    """Create EventEmitter."""
    return EventEmitter()


@pytest.fixture
def coordinator(checkpoint_manager, retry_policy, error_classifier, event_emitter):
    """Create RecoveryCoordinator with all dependencies."""
    return RecoveryCoordinator(
        checkpoint_mgr=checkpoint_manager,
        retry_policy=retry_policy,
        error_classifier=error_classifier,
        events=event_emitter,
    )


# ----------------------------------------------------------------------------------
# RecoveryActionType Tests
# ----------------------------------------------------------------------------------


def test_recovery_action_type_enum():
    """Test RecoveryActionType enum values."""
    assert RecoveryActionType.RETRY.value == "retry"
    assert RecoveryActionType.SKIP.value == "skip"
    assert RecoveryActionType.FAIL.value == "fail"
    assert RecoveryActionType.RECONFIGURE.value == "reconfigure"


# ----------------------------------------------------------------------------------
# RecoveryAction Tests
# ----------------------------------------------------------------------------------


def test_recovery_action_defaults():
    """Test RecoveryAction default values."""
    action = RecoveryAction(type=RecoveryActionType.RETRY)
    assert action.type == RecoveryActionType.RETRY
    assert action.delay == 0.0
    assert action.reason == ""


def test_recovery_action_with_values():
    """Test RecoveryAction with custom values."""
    action = RecoveryAction(
        type=RecoveryActionType.RETRY,
        delay=2.5,
        reason="Network timeout, retrying",
    )
    assert action.type == RecoveryActionType.RETRY
    assert action.delay == 2.5
    assert action.reason == "Network timeout, retrying"


# ----------------------------------------------------------------------------------
# RecoveryCoordinator Initialization Tests
# ----------------------------------------------------------------------------------


def test_coordinator_initialization(coordinator, checkpoint_manager, retry_policy, error_classifier, event_emitter):
    """Test RecoveryCoordinator initialization."""
    assert coordinator.checkpoint_mgr is checkpoint_manager
    assert coordinator.retry_policy is retry_policy
    assert coordinator.error_classifier is error_classifier
    assert coordinator.events is event_emitter


# ----------------------------------------------------------------------------------
# TRANSIENT Error Recovery Tests
# ----------------------------------------------------------------------------------


def test_transient_error_retry_first_attempt(coordinator):
    """Test TRANSIENT error → RETRY on first attempt."""
    error = ConnectionError("Network timeout")
    context = {
        "tool": "pmemd",
        "attempt": 0,
        "phase": "RUN",
    }

    action = coordinator.handle_error(error, context)

    assert action.type == RecoveryActionType.RETRY
    assert action.delay > 0  # Should have exponential backoff delay
    assert "transient" in action.reason.lower() or "retry" in action.reason.lower()


def test_transient_error_retry_with_backoff(coordinator):
    """Test TRANSIENT error retry delay increases with attempts."""
    error = TimeoutError("Request timeout")

    # First attempt
    context1 = {"tool": "pmemd", "attempt": 0, "phase": "RUN"}
    action1 = coordinator.handle_error(error, context1)

    # Second attempt
    context2 = {"tool": "pmemd", "attempt": 1, "phase": "RUN"}
    action2 = coordinator.handle_error(error, context2)

    assert action1.type == RecoveryActionType.RETRY
    assert action2.type == RecoveryActionType.RETRY
    # Delay should increase (accounting for jitter, check base relationship)
    # With backoff_multiplier=2.0, base_delay=1.0: attempt 0 → ~1s, attempt 1 → ~2s
    assert action2.delay > action1.delay * 0.5  # Allow for jitter variance


# ----------------------------------------------------------------------------------
# RESOURCE Error Recovery Tests
# ----------------------------------------------------------------------------------


def test_resource_error_retry(coordinator):
    """Test RESOURCE error → RETRY with longer backoff."""
    error = MemoryError("Out of memory")
    context = {
        "tool": "pmemd",
        "attempt": 0,
        "phase": "RUN",
    }

    action = coordinator.handle_error(error, context)

    assert action.type == RecoveryActionType.RETRY
    assert action.delay > 0
    assert "resource" in action.reason.lower() or "memory" in action.reason.lower()


def test_resource_error_disk_space(coordinator):
    """Test RESOURCE error for disk space → RETRY."""
    error = OSError("No space left on device")
    context = {
        "tool": "pmemd",
        "attempt": 0,
        "phase": "RUN",
    }

    action = coordinator.handle_error(error, context)

    assert action.type == RecoveryActionType.RETRY
    assert action.delay > 0


# ----------------------------------------------------------------------------------
# CONFIGURATION Error Recovery Tests
# ----------------------------------------------------------------------------------


def test_configuration_error_reconfigure(coordinator):
    """Test CONFIGURATION error → RECONFIGURE."""
    error = ValueError("Invalid parameter: temperature must be positive")
    context = {
        "tool": "pmemd",
        "attempt": 0,
        "phase": "CONFIGURE",
    }

    action = coordinator.handle_error(error, context)

    assert action.type == RecoveryActionType.RECONFIGURE
    assert action.delay == 0.0  # No delay for reconfigure
    assert "configuration" in action.reason.lower() or "reconfigure" in action.reason.lower()


def test_configuration_error_keyerror(coordinator):
    """Test CONFIGURATION error with KeyError → RECONFIGURE."""
    error = KeyError("missing_parameter")
    context = {
        "tool": "pmemd",
        "attempt": 0,
        "phase": "CONFIGURE",
    }

    action = coordinator.handle_error(error, context)

    assert action.type == RecoveryActionType.RECONFIGURE
    assert action.delay == 0.0


# ----------------------------------------------------------------------------------
# PERMANENT Error Recovery Tests
# ----------------------------------------------------------------------------------


def test_permanent_error_fail(coordinator):
    """Test PERMANENT error → FAIL immediately."""
    error = FileNotFoundError("prmtop file not found")
    context = {
        "tool": "pmemd",
        "attempt": 0,
        "phase": "RUN",
        "retry_count": 3,  # Already retried 3 times
    }

    action = coordinator.handle_error(error, context)

    assert action.type == RecoveryActionType.FAIL
    assert action.delay == 0.0
    assert "permanent" in action.reason.lower() or "fail" in action.reason.lower()


# ----------------------------------------------------------------------------------
# Retry Exhaustion Tests
# ----------------------------------------------------------------------------------


def test_retry_exhausted_fail(coordinator):
    """Test retry exhaustion → FAIL."""
    error = ConnectionError("Network timeout")
    context = {
        "tool": "pmemd",
        "attempt": 3,  # Max attempts reached (0, 1, 2 = 3 attempts)
        "phase": "RUN",
    }

    action = coordinator.handle_error(error, context)

    assert action.type == RecoveryActionType.FAIL
    assert "exhausted" in action.reason.lower() or "max" in action.reason.lower()


def test_retry_exhausted_resource_error(coordinator):
    """Test retry exhaustion for RESOURCE error → FAIL."""
    error = MemoryError("Out of memory")
    context = {
        "tool": "pmemd",
        "attempt": 3,  # Max attempts reached
        "phase": "RUN",
    }

    action = coordinator.handle_error(error, context)

    assert action.type == RecoveryActionType.FAIL


# ----------------------------------------------------------------------------------
# Event Emission Tests
# ----------------------------------------------------------------------------------


def test_event_error_classified(coordinator):
    """Test 'error.classified' event emission."""
    events_received = []
    coordinator.events.on("error.classified", lambda e: events_received.append(e))

    error = ConnectionError("Network timeout")
    context = {"tool": "pmemd", "attempt": 0, "phase": "RUN"}

    coordinator.handle_error(error, context)

    assert len(events_received) == 1
    event = events_received[0]
    assert event.type == "error.classified"
    assert event.data["category"] == ErrorCategory.TRANSIENT
    assert event.data["error_type"] == "ConnectionError"


def test_event_retry_scheduled(coordinator):
    """Test 'recovery.retry_scheduled' event emission."""
    events_received = []
    coordinator.events.on("recovery.retry_scheduled", lambda e: events_received.append(e))

    error = ConnectionError("Network timeout")
    context = {"tool": "pmemd", "attempt": 0, "phase": "RUN"}

    coordinator.handle_error(error, context)

    assert len(events_received) == 1
    event = events_received[0]
    assert event.type == "recovery.retry_scheduled"
    assert event.data["attempt"] == 0
    assert event.data["delay"] > 0
    assert event.data["tool"] == "pmemd"


def test_event_retry_exhausted(coordinator):
    """Test 'recovery.retry_exhausted' event emission."""
    events_received = []
    coordinator.events.on("recovery.retry_exhausted", lambda e: events_received.append(e))

    error = ConnectionError("Network timeout")
    context = {"tool": "pmemd", "attempt": 3, "phase": "RUN"}

    coordinator.handle_error(error, context)

    assert len(events_received) == 1
    event = events_received[0]
    assert event.type == "recovery.retry_exhausted"
    assert event.data["attempt"] == 3
    assert event.data["tool"] == "pmemd"


def test_event_reconfigure(coordinator):
    """Test 'recovery.reconfigure' event emission."""
    events_received = []
    coordinator.events.on("recovery.reconfigure", lambda e: events_received.append(e))

    error = ValueError("Invalid parameter")
    context = {"tool": "pmemd", "attempt": 0, "phase": "CONFIGURE"}

    coordinator.handle_error(error, context)

    assert len(events_received) == 1
    event = events_received[0]
    assert event.type == "recovery.reconfigure"
    assert event.data["phase"] == "CONFIGURE"
    assert event.data["error_type"] == "ValueError"


def test_event_failed(coordinator):
    """Test 'recovery.failed' event emission."""
    events_received = []
    coordinator.events.on("recovery.failed", lambda e: events_received.append(e))

    error = FileNotFoundError("File not found")
    context = {"tool": "pmemd", "attempt": 0, "phase": "RUN", "retry_count": 3}

    coordinator.handle_error(error, context)

    assert len(events_received) == 1
    event = events_received[0]
    assert event.type == "recovery.failed"
    assert event.data["category"] == ErrorCategory.PERMANENT
    assert event.data["tool"] == "pmemd"


def test_multiple_event_emissions(coordinator):
    """Test that multiple events are emitted in correct order."""
    all_events = []
    coordinator.events.on("error.classified", lambda e: all_events.append(e.type))
    coordinator.events.on("recovery.retry_scheduled", lambda e: all_events.append(e.type))

    error = ConnectionError("Network timeout")
    context = {"tool": "pmemd", "attempt": 0, "phase": "RUN"}

    coordinator.handle_error(error, context)

    assert all_events == ["error.classified", "recovery.retry_scheduled"]


# ----------------------------------------------------------------------------------
# Context Passing Tests
# ----------------------------------------------------------------------------------


def test_context_passed_to_classifier(coordinator):
    """Test that context is passed to error classifier."""
    # ValueError in CONFIGURE phase → CONFIGURATION
    error = ValueError("Invalid parameter")
    context = {"tool": "pmemd", "attempt": 0, "phase": "CONFIGURE"}

    action = coordinator.handle_error(error, context)
    assert action.type == RecoveryActionType.RECONFIGURE

    # Same error in RUN phase → TRANSIENT (default)
    context_run = {"tool": "pmemd", "attempt": 0, "phase": "RUN"}
    action_run = coordinator.handle_error(error, context_run)
    assert action_run.type == RecoveryActionType.RETRY


def test_context_tool_name_in_events(coordinator):
    """Test that tool name from context appears in events."""
    events_received = []
    coordinator.events.on("recovery.retry_scheduled", lambda e: events_received.append(e))

    error = ConnectionError("Network timeout")
    context = {"tool": "cpptraj", "attempt": 0, "phase": "ANALYZE"}

    coordinator.handle_error(error, context)

    assert len(events_received) == 1
    assert events_received[0].data["tool"] == "cpptraj"


def test_context_phase_in_events(coordinator):
    """Test that phase from context appears in events."""
    events_received = []
    coordinator.events.on("recovery.reconfigure", lambda e: events_received.append(e))

    error = ValueError("Invalid parameter")
    context = {"tool": "pmemd", "attempt": 0, "phase": "CONFIGURE"}

    coordinator.handle_error(error, context)

    assert len(events_received) == 1
    assert events_received[0].data["phase"] == "CONFIGURE"


# ----------------------------------------------------------------------------------
# Edge Cases Tests
# ----------------------------------------------------------------------------------


def test_empty_context(coordinator):
    """Test handling error with empty context."""
    error = ConnectionError("Network timeout")
    context = {}

    action = coordinator.handle_error(error, context)

    # Should still classify and return action
    assert action.type == RecoveryActionType.RETRY
    assert action.delay > 0


def test_none_context_values(coordinator):
    """Test handling context with None values."""
    error = ConnectionError("Network timeout")
    context = {
        "tool": None,
        "attempt": 0,
        "phase": None,
    }

    action = coordinator.handle_error(error, context)

    # Should handle gracefully
    assert action.type == RecoveryActionType.RETRY


def test_missing_attempt_in_context(coordinator):
    """Test handling missing attempt in context."""
    error = ConnectionError("Network timeout")
    context = {
        "tool": "pmemd",
        "phase": "RUN",
        # Missing 'attempt'
    }

    action = coordinator.handle_error(error, context)

    # Should default to attempt 0 and retry
    assert action.type == RecoveryActionType.RETRY


# ----------------------------------------------------------------------------------
# Integration Tests
# ----------------------------------------------------------------------------------


def test_full_retry_cycle(coordinator):
    """Test full retry cycle from first attempt to exhaustion."""
    error = ConnectionError("Network timeout")

    # Attempt 0 → RETRY
    action0 = coordinator.handle_error(error, {"tool": "pmemd", "attempt": 0, "phase": "RUN"})
    assert action0.type == RecoveryActionType.RETRY

    # Attempt 1 → RETRY
    action1 = coordinator.handle_error(error, {"tool": "pmemd", "attempt": 1, "phase": "RUN"})
    assert action1.type == RecoveryActionType.RETRY

    # Attempt 2 → RETRY
    action2 = coordinator.handle_error(error, {"tool": "pmemd", "attempt": 2, "phase": "RUN"})
    assert action2.type == RecoveryActionType.RETRY

    # Attempt 3 → FAIL (exhausted)
    action3 = coordinator.handle_error(error, {"tool": "pmemd", "attempt": 3, "phase": "RUN"})
    assert action3.type == RecoveryActionType.FAIL


def test_different_error_categories_different_actions(coordinator):
    """Test that different error categories produce different actions."""
    context = {"tool": "pmemd", "attempt": 0, "phase": "RUN"}

    # TRANSIENT → RETRY
    transient_action = coordinator.handle_error(ConnectionError("timeout"), context)
    assert transient_action.type == RecoveryActionType.RETRY

    # RESOURCE → RETRY
    resource_action = coordinator.handle_error(MemoryError("OOM"), context)
    assert resource_action.type == RecoveryActionType.RETRY

    # CONFIGURATION → RECONFIGURE (need CONFIGURE phase)
    config_context = {"tool": "pmemd", "attempt": 0, "phase": "CONFIGURE"}
    config_action = coordinator.handle_error(ValueError("invalid"), config_context)
    assert config_action.type == RecoveryActionType.RECONFIGURE

    # PERMANENT → FAIL
    perm_context = {"tool": "pmemd", "attempt": 0, "phase": "RUN", "retry_count": 3}
    perm_action = coordinator.handle_error(FileNotFoundError("missing"), perm_context)
    assert perm_action.type == RecoveryActionType.FAIL


def test_event_emission_for_all_action_types(coordinator):
    """Test that appropriate events are emitted for all action types."""
    all_events = []

    # Subscribe to all recovery events
    coordinator.events.on("error.classified", lambda e: all_events.append(e.type))
    coordinator.events.on("recovery.retry_scheduled", lambda e: all_events.append(e.type))
    coordinator.events.on("recovery.retry_exhausted", lambda e: all_events.append(e.type))
    coordinator.events.on("recovery.reconfigure", lambda e: all_events.append(e.type))
    coordinator.events.on("recovery.failed", lambda e: all_events.append(e.type))

    # RETRY action
    all_events.clear()
    coordinator.handle_error(ConnectionError("timeout"), {"tool": "pmemd", "attempt": 0, "phase": "RUN"})
    assert "error.classified" in all_events
    assert "recovery.retry_scheduled" in all_events

    # RECONFIGURE action
    all_events.clear()
    coordinator.handle_error(ValueError("invalid"), {"tool": "pmemd", "attempt": 0, "phase": "CONFIGURE"})
    assert "error.classified" in all_events
    assert "recovery.reconfigure" in all_events

    # FAIL action (exhausted)
    all_events.clear()
    coordinator.handle_error(ConnectionError("timeout"), {"tool": "pmemd", "attempt": 3, "phase": "RUN"})
    assert "error.classified" in all_events
    assert "recovery.retry_exhausted" in all_events
    assert "recovery.failed" in all_events

    # FAIL action (permanent)
    all_events.clear()
    coordinator.handle_error(FileNotFoundError("missing"), {"tool": "pmemd", "attempt": 0, "phase": "RUN", "retry_count": 3})
    assert "error.classified" in all_events
    assert "recovery.failed" in all_events
