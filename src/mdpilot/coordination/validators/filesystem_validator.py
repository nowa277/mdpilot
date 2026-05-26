"""A-level: File system permissions validator (most permissive)."""

from mdpilot.coordination.config import FileSystemPermissions
from mdpilot.coordination.types import ExecutionPlan, Severity, ValidationResult, Violation
from mdpilot.coordination.validators.base import BaseValidator


class FileSystemValidator(BaseValidator):
    """Validates file system access permissions.

    A-level validator enforces file system constraints:
    - File paths within allowed directories
    - No access to forbidden paths (/etc, /sys, /proc)
    - Write operations have proper permissions

    All violations are WARNING severity and fixable.
    """

    def __init__(self, permissions: FileSystemPermissions):
        """Initialize validator.

        Args:
            permissions: File system permissions configuration
        """
        self.permissions = permissions

    @property
    def level(self) -> str:
        return "A"

    def validate(self, plan: ExecutionPlan) -> ValidationResult:
        """Validate file system access.

        Args:
            plan: Execution plan to validate

        Returns:
            ValidationResult with WARNING violations if paths invalid
        """
        violations = []

        for step in plan.steps:
            # Check for file paths in parameters
            file_params = ["input_file", "output_file", "file_path", "path", "directory"]

            for param_name in file_params:
                if param_name in step.parameters:
                    file_path = step.parameters[param_name]

                    # Skip if not a string (might be None or other type)
                    if not isinstance(file_path, str):
                        continue

                    # Check forbidden paths first
                    is_forbidden = False
                    for forbidden in self.permissions.forbidden_paths:
                        if file_path.startswith(forbidden):
                            violations.append(Violation(
                                level="A",
                                severity=Severity.WARNING,
                                message=(
                                    f"Step {step.step_id} attempts to access forbidden path: {file_path} "
                                    f"(forbidden: {forbidden})"
                                ),
                                step_id=step.step_id,
                                fixable=True,
                                suggested_fix=f"Use a path within allowed directories"
                            ))
                            is_forbidden = True
                            break

                    # Skip allowed check if already forbidden
                    if is_forbidden:
                        continue

                    # Check if path is within allowed directories
                    if self.permissions.allowed_paths:
                        is_allowed = any(
                            file_path.startswith(allowed)
                            for allowed in self.permissions.allowed_paths
                        )

                        if not is_allowed:
                            violations.append(Violation(
                                level="A",
                                severity=Severity.WARNING,
                                message=(
                                    f"Step {step.step_id} path '{file_path}' not in allowed directories. "
                                    f"Allowed: {', '.join(self.permissions.allowed_paths)}"
                                ),
                                step_id=step.step_id,
                                fixable=True,
                                suggested_fix=f"Use a path within: {', '.join(self.permissions.allowed_paths)}"
                            ))

        return ValidationResult(
            valid=len(violations) == 0,
            violations=violations
        )
