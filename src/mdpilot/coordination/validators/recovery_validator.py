"""D-level: Error recovery validator."""

from mdpilot.coordination.config import RecoveryPolicies
from mdpilot.coordination.types import ExecutionPlan, Severity, ValidationResult, Violation
from mdpilot.coordination.validators.base import BaseValidator


class RecoveryValidator(BaseValidator):
    """Validates error recovery strategies.

    D-level validator enforces recovery constraints:
    - Each step has error_handling defined
    - Retry policies are reasonable (max_retries within limits)
    - Recovery strategies are in allowed list
    - Fallback options exist when needed

    All violations are ERROR severity and fixable.
    """

    def __init__(self, policies: RecoveryPolicies):
        """Initialize validator.

        Args:
            policies: Recovery policies configuration
        """
        self.policies = policies

    @property
    def level(self) -> str:
        return "D"

    def validate(self, plan: ExecutionPlan) -> ValidationResult:
        """Validate error recovery strategies.

        Args:
            plan: Execution plan to validate

        Returns:
            ValidationResult with ERROR violations if recovery invalid
        """
        violations = []

        for step in plan.steps:
            # Check if error_handling is defined
            if step.error_handling is None:
                violations.append(Violation(
                    level="D",
                    severity=Severity.ERROR,
                    message=f"Step {step.step_id} missing error_handling strategy",
                    step_id=step.step_id,
                    fixable=True,
                    suggested_fix=f"Add error_handling to step {step.step_id}"
                ))
                continue

            # Check if strategy is in allowed list
            if step.error_handling not in self.policies.allowed_strategies:
                violations.append(Violation(
                    level="D",
                    severity=Severity.ERROR,
                    message=(
                        f"Invalid recovery strategy '{step.error_handling}' for step {step.step_id}. "
                        f"Allowed: {', '.join(self.policies.allowed_strategies)}"
                    ),
                    step_id=step.step_id,
                    fixable=True,
                    suggested_fix=f"Use one of: {', '.join(self.policies.allowed_strategies)}"
                ))

            # Check retry-specific constraints
            if "retry" in step.error_handling.lower():
                max_retries = step.parameters.get("max_retries")
                if max_retries is not None:
                    if max_retries > self.policies.max_retries:
                        violations.append(Violation(
                            level="D",
                            severity=Severity.ERROR,
                            message=(
                                f"Step {step.step_id} max_retries {max_retries} "
                                f"exceeds limit {self.policies.max_retries}"
                            ),
                            step_id=step.step_id,
                            fixable=True,
                            suggested_fix=f"Set max_retries <= {self.policies.max_retries}"
                        ))
                    elif max_retries < 0:
                        violations.append(Violation(
                            level="D",
                            severity=Severity.ERROR,
                            message=f"Step {step.step_id} has negative max_retries: {max_retries}",
                            step_id=step.step_id,
                            fixable=True,
                            suggested_fix="Set max_retries to a non-negative value"
                        ))

            # Check fallback-specific constraints
            if "fallback" in step.error_handling.lower():
                fallback_tool = step.parameters.get("fallback_tool")
                if not fallback_tool:
                    violations.append(Violation(
                        level="D",
                        severity=Severity.ERROR,
                        message=f"Step {step.step_id} uses fallback strategy but no fallback_tool specified",
                        step_id=step.step_id,
                        fixable=True,
                        suggested_fix="Add fallback_tool parameter"
                    ))

        return ValidationResult(
            valid=len(violations) == 0,
            violations=violations
        )
