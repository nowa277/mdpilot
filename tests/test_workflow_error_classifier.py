"""Tests for ErrorClassifier."""
import pytest
from mdpilot.agent.error_classifier import ErrorCategory, ErrorClassifier


class TestErrorCategory:
    """Test ErrorCategory enum."""

    def test_error_category_values(self) -> None:
        """Test that ErrorCategory has correct values."""
        assert ErrorCategory.TRANSIENT.value == "transient"
        assert ErrorCategory.RESOURCE.value == "resource"
        assert ErrorCategory.CONFIGURATION.value == "configuration"
        assert ErrorCategory.PERMANENT.value == "permanent"

    def test_error_category_members(self) -> None:
        """Test that all expected categories exist."""
        categories = {e.value for e in ErrorCategory}
        assert categories == {"transient", "resource", "configuration", "permanent"}


class TestErrorClassifier:
    """Test ErrorClassifier classification logic."""

    @pytest.fixture
    def classifier(self) -> ErrorClassifier:
        """Create ErrorClassifier instance."""
        return ErrorClassifier()

    # TRANSIENT error tests
    @pytest.mark.parametrize("error", [
        ConnectionError("Connection refused"),
        ConnectionError("Network unreachable"),
        TimeoutError("Connection timeout"),
        TimeoutError("Read timeout"),
    ])
    def test_classify_network_errors_as_transient(
        self, classifier: ErrorClassifier, error: Exception
    ) -> None:
        """Test that network errors are classified as TRANSIENT."""
        result = classifier.classify(error, {})
        assert result == ErrorCategory.TRANSIENT

    # RESOURCE error tests
    def test_classify_memory_error_as_resource(self, classifier: ErrorClassifier) -> None:
        """Test that MemoryError is classified as RESOURCE."""
        error = MemoryError("Out of memory")
        result = classifier.classify(error, {})
        assert result == ErrorCategory.RESOURCE

    @pytest.mark.parametrize("error_msg", [
        "No space left on device",
        "Disk space exhausted",
        "not enough space",
        "insufficient space available",
    ])
    def test_classify_disk_space_errors_as_resource(
        self, classifier: ErrorClassifier, error_msg: str
    ) -> None:
        """Test that disk space OSErrors are classified as RESOURCE."""
        error = OSError(error_msg)
        result = classifier.classify(error, {})
        assert result == ErrorCategory.RESOURCE

    def test_classify_oserror_without_space_as_transient(
        self, classifier: ErrorClassifier
    ) -> None:
        """Test that OSError without 'space' keyword defaults to TRANSIENT."""
        error = OSError("Permission denied")
        result = classifier.classify(error, {})
        assert result == ErrorCategory.TRANSIENT

    # CONFIGURATION error tests
    @pytest.mark.parametrize("error", [
        ValueError("Invalid parameter value"),
        KeyError("missing_key"),
    ])
    def test_classify_config_errors_in_configure_phase(
        self, classifier: ErrorClassifier, error: Exception
    ) -> None:
        """Test that ValueError/KeyError in CONFIGURE phase are CONFIGURATION."""
        context = {"phase": "CONFIGURE"}
        result = classifier.classify(error, context)
        assert result == ErrorCategory.CONFIGURATION

    @pytest.mark.parametrize("error", [
        ValueError("Invalid parameter value"),
        KeyError("missing_key"),
    ])
    def test_classify_config_errors_outside_configure_phase_as_transient(
        self, classifier: ErrorClassifier, error: Exception
    ) -> None:
        """Test that ValueError/KeyError outside CONFIGURE phase are TRANSIENT."""
        context = {"phase": "RUN"}
        result = classifier.classify(error, context)
        assert result == ErrorCategory.TRANSIENT

    # PERMANENT error tests
    def test_classify_file_not_found_after_retries_as_permanent(
        self, classifier: ErrorClassifier
    ) -> None:
        """Test that FileNotFoundError after retries is PERMANENT."""
        error = FileNotFoundError("File not found")
        context = {"retry_count": 3}
        result = classifier.classify(error, context)
        assert result == ErrorCategory.PERMANENT

    def test_classify_file_not_found_before_max_retries_as_transient(
        self, classifier: ErrorClassifier
    ) -> None:
        """Test that FileNotFoundError before max retries is TRANSIENT."""
        error = FileNotFoundError("File not found")
        context = {"retry_count": 2}
        result = classifier.classify(error, context)
        assert result == ErrorCategory.TRANSIENT

    def test_classify_file_not_found_without_retry_count_as_transient(
        self, classifier: ErrorClassifier
    ) -> None:
        """Test that FileNotFoundError without retry_count is TRANSIENT."""
        error = FileNotFoundError("File not found")
        context = {}
        result = classifier.classify(error, context)
        assert result == ErrorCategory.TRANSIENT

    # Default fallback tests
    @pytest.mark.parametrize("error", [
        RuntimeError("Unknown error"),
        TypeError("Type mismatch"),
        AttributeError("Missing attribute"),
        IndexError("Index out of range"),
        ZeroDivisionError("Division by zero"),
    ])
    def test_classify_unknown_errors_as_transient(
        self, classifier: ErrorClassifier, error: Exception
    ) -> None:
        """Test that unknown errors default to TRANSIENT (safe fallback)."""
        result = classifier.classify(error, {})
        assert result == ErrorCategory.TRANSIENT

    # Context edge cases
    def test_classify_with_none_context(self, classifier: ErrorClassifier) -> None:
        """Test classification with None context."""
        error = ConnectionError("Network error")
        result = classifier.classify(error, None)
        assert result == ErrorCategory.TRANSIENT

    def test_classify_with_empty_context(self, classifier: ErrorClassifier) -> None:
        """Test classification with empty context."""
        error = TimeoutError("Timeout")
        result = classifier.classify(error, {})
        assert result == ErrorCategory.TRANSIENT

    def test_classify_with_missing_phase_key(self, classifier: ErrorClassifier) -> None:
        """Test classification when phase key is missing from context."""
        error = ValueError("Invalid value")
        context = {"tool": "pmemd", "step": "minimize"}
        result = classifier.classify(error, context)
        assert result == ErrorCategory.TRANSIENT

    def test_classify_with_missing_retry_count_key(
        self, classifier: ErrorClassifier
    ) -> None:
        """Test classification when retry_count key is missing from context."""
        error = FileNotFoundError("File not found")
        context = {"phase": "RUN"}
        result = classifier.classify(error, context)
        assert result == ErrorCategory.TRANSIENT

    # Complex scenarios
    def test_classify_memory_error_in_configure_phase(
        self, classifier: ErrorClassifier
    ) -> None:
        """Test that MemoryError is RESOURCE even in CONFIGURE phase."""
        error = MemoryError("Out of memory")
        context = {"phase": "CONFIGURE"}
        result = classifier.classify(error, context)
        assert result == ErrorCategory.RESOURCE

    def test_classify_connection_error_with_high_retry_count(
        self, classifier: ErrorClassifier
    ) -> None:
        """Test that ConnectionError remains TRANSIENT even with high retry count."""
        error = ConnectionError("Connection refused")
        context = {"retry_count": 5}
        result = classifier.classify(error, context)
        assert result == ErrorCategory.TRANSIENT

    def test_classify_preserves_case_insensitivity_for_space_keyword(
        self, classifier: ErrorClassifier
    ) -> None:
        """Test that 'space' keyword matching is case-insensitive."""
        error = OSError("No SPACE left on device")
        result = classifier.classify(error, {})
        assert result == ErrorCategory.RESOURCE

    # Integration-style tests
    def test_classify_typical_workflow_errors(self, classifier: ErrorClassifier) -> None:
        """Test classification of typical workflow errors."""
        # Network timeout during RUN phase
        assert classifier.classify(
            TimeoutError("Timeout"), {"phase": "RUN", "tool": "pmemd"}
        ) == ErrorCategory.TRANSIENT

        # Invalid parameter during CONFIGURE
        assert classifier.classify(
            ValueError("Invalid forcefield"), {"phase": "CONFIGURE"}
        ) == ErrorCategory.CONFIGURATION

        # Disk full during PREPARE
        assert classifier.classify(
            OSError("No space left"), {"phase": "PREPARE"}
        ) == ErrorCategory.RESOURCE

        # File not found after multiple retries
        assert classifier.classify(
            FileNotFoundError("Missing file"), {"retry_count": 3}
        ) == ErrorCategory.PERMANENT
