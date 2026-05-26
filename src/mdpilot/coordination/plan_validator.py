"""Plan validator coordinator - orchestrates all 5 validation layers."""

from typing import Dict, List

from mdpilot.coordination.config import GuardrailConfig
from mdpilot.coordination.types import ExecutionPlan, Severity, ValidationResult, Violation
from mdpilot.coordination.validators.base import BaseValidator
from mdpilot.coordination.validators.filesystem_validator import FileSystemValidator
from mdpilot.coordination.validators.recovery_validator import RecoveryValidator
from mdpilot.coordination.validators.resource_validator import ResourceValidator
from mdpilot.coordination.validators.tool_validator import ToolValidator
from mdpilot.coordination.validators.workflow_validator import WorkflowValidator


class PlanValidator:
    """Coordinates all 5 validation layers.

    Runs validators in order from strictest to most permissive:
    E (Resource) → D (Recovery) → C (Workflow) → B (Tool) → A (FileSystem)

    Stops early on CRITICAL violations (E-level).
    Aggregates all violations and generates fix suggestions.
    """

    def __init__(self, config: GuardrailConfig):
        """Initialize validator with configuration.

        Args:
            config: Complete guardrail configuration
        """
        self.config = config

        # Initialize validators in order: E → D → C → B → A
        self.validators: List[BaseValidator] = [
            ResourceValidator(config.resource_limits),      # E - strictest
            RecoveryValidator(config.recovery_policies),    # D
            WorkflowValidator(config),                      # C
            ToolValidator(config.tool_constraints),         # B
            FileSystemValidator(config.fs_permissions),     # A - most permissive
        ]

    def validate(self, plan: ExecutionPlan) -> ValidationResult:
        """Run all validators and aggregate results.

        Executes validators in order, stopping early if CRITICAL violations found.

        Args:
            plan: Execution plan to validate

        Returns:
            ValidationResult with aggregated violations from all validators
        """
        all_violations = []

        for validator in self.validators:
            result = validator.validate(plan)

            if not result.valid:
                all_violations.extend(result.violations)

                # Stop on CRITICAL violations (E-level only)
                if any(v.severity == Severity.CRITICAL for v in result.violations):
                    break

        return ValidationResult(
            valid=len(all_violations) == 0,
            violations=all_violations
        )

    def suggest_fixes(self, violations: List[Violation]) -> List[Dict]:
        """Generate fix suggestions for fixable violations.

        Args:
            violations: List of violations to generate fixes for

        Returns:
            List of fix suggestions with level, message, fix, and step_id
        """
        fixes = []

        for violation in violations:
            if violation.fixable and violation.suggested_fix:
                fixes.append({
                    "level": violation.level,
                    "message": violation.message,
                    "fix": violation.suggested_fix,
                    "step_id": violation.step_id
                })

        return fixes
