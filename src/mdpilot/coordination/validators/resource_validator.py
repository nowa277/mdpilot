"""E-level: Resource allocation validator (most strict)."""

from mdpilot.coordination.config import ResourceLimits
from mdpilot.coordination.types import ExecutionPlan, Severity, ValidationResult, Violation
from mdpilot.coordination.validators.base import BaseValidator


class ResourceValidator(BaseValidator):
    """Validates resource allocation constraints.

    E-level validator enforces hard resource limits:
    - CPU hours
    - Memory (GB)
    - Disk usage (GB)

    All violations are CRITICAL severity and non-fixable.
    """

    def __init__(self, limits: ResourceLimits):
        """Initialize validator.

        Args:
            limits: Resource limits configuration
        """
        self.limits = limits

    @property
    def level(self) -> str:
        return "E"

    def validate(self, plan: ExecutionPlan) -> ValidationResult:
        """Validate resource requirements.

        Args:
            plan: Execution plan to validate

        Returns:
            ValidationResult with CRITICAL violations if limits exceeded
        """
        violations = []

        # Check CPU hours
        if plan.estimated_resources.cpu_hours > self.limits.max_cpu_hours:
            violations.append(Violation(
                level="E",
                severity=Severity.CRITICAL,
                message=(
                    f"CPU hours {plan.estimated_resources.cpu_hours:.2f} "
                    f"exceeds limit {self.limits.max_cpu_hours:.2f}"
                ),
                step_id="",
                fixable=False
            ))

        # Check memory
        if plan.estimated_resources.memory_gb > self.limits.max_memory_gb:
            violations.append(Violation(
                level="E",
                severity=Severity.CRITICAL,
                message=(
                    f"Memory {plan.estimated_resources.memory_gb:.2f}GB "
                    f"exceeds limit {self.limits.max_memory_gb:.2f}GB"
                ),
                step_id="",
                fixable=False
            ))

        # Check disk usage
        if plan.estimated_resources.disk_gb > self.limits.max_disk_gb:
            violations.append(Violation(
                level="E",
                severity=Severity.CRITICAL,
                message=(
                    f"Disk usage {plan.estimated_resources.disk_gb:.2f}GB "
                    f"exceeds limit {self.limits.max_disk_gb:.2f}GB"
                ),
                step_id="",
                fixable=False
            ))

        return ValidationResult(
            valid=len(violations) == 0,
            violations=violations
        )
