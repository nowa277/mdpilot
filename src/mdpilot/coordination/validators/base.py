"""Base validator interface."""

from abc import ABC, abstractmethod

from mdpilot.coordination.types import ExecutionPlan, ValidationResult


class BaseValidator(ABC):
    """Base class for all validators."""

    @property
    @abstractmethod
    def level(self) -> str:
        """Validator level (E, D, C, B, or A)."""
        pass

    @abstractmethod
    def validate(self, plan: ExecutionPlan) -> ValidationResult:
        """Validate execution plan.

        Args:
            plan: Execution plan to validate

        Returns:
            ValidationResult with violations if any
        """
        pass
