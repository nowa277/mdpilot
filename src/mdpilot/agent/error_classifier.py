"""ErrorClassifier — classify exceptions into recovery categories for workflow error recovery."""

from __future__ import annotations

from enum import Enum


class ErrorCategory(Enum):
    """Error categories for recovery strategy selection."""

    TRANSIENT = "transient"  # Network timeout, temporary issues
    RESOURCE = "resource"  # Memory/disk/GPU unavailable
    CONFIGURATION = "configuration"  # Invalid parameters
    PERMANENT = "permanent"  # Unrecoverable errors


class ErrorClassifier:
    """Classify errors into recovery categories."""

    def classify(self, error: Exception, context: dict | None) -> ErrorCategory:
        """Classify error into recovery category.

        Parameters
        ----------
        error : Exception
            The exception to classify.
        context : dict | None
            Context information including phase, retry_count, tool, etc.

        Returns
        -------
        ErrorCategory
            The recovery category for this error.

        Classification Logic
        --------------------
        1. Network errors (ConnectionError, TimeoutError) → TRANSIENT
        2. Resource errors (MemoryError, OSError with "space") → RESOURCE
        3. Configuration errors (ValueError, KeyError in CONFIGURE phase) → CONFIGURATION
        4. Permanent errors (FileNotFoundError after retries) → PERMANENT
        5. Unknown errors → TRANSIENT (safe fallback)
        """
        # Handle None context
        if context is None:
            context = {}

        # Network errors → TRANSIENT
        if isinstance(error, (ConnectionError, TimeoutError)):
            return ErrorCategory.TRANSIENT

        # Resource errors → RESOURCE
        if isinstance(error, MemoryError):
            return ErrorCategory.RESOURCE

        if isinstance(error, OSError) and "space" in str(error).lower():
            return ErrorCategory.RESOURCE

        # Configuration errors → CONFIGURATION (only in CONFIGURE phase)
        if isinstance(error, (ValueError, KeyError)):
            if context.get("phase") == "CONFIGURE":
                return ErrorCategory.CONFIGURATION

        # Permanent errors → PERMANENT (FileNotFoundError after retries)
        if isinstance(error, FileNotFoundError):
            retry_count = context.get("retry_count", 0)
            if retry_count >= 3:
                return ErrorCategory.PERMANENT

        # Default: treat as transient for safety
        return ErrorCategory.TRANSIENT
