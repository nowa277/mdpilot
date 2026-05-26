"""C-level: Workflow step order and completeness validator."""

from mdpilot.coordination.config import GuardrailConfig
from mdpilot.coordination.types import ExecutionPlan, Severity, ValidationResult, Violation
from mdpilot.coordination.validators.base import BaseValidator


class WorkflowValidator(BaseValidator):
    """Validates workflow step order and completeness.

    C-level validator enforces workflow constraints:
    - Required steps must be present
    - Step order constraints must be satisfied
    - No duplicate steps allowed

    All violations are ERROR severity and fixable.
    """

    def __init__(self, config: GuardrailConfig):
        """Initialize validator.

        Args:
            config: Guardrail configuration with workflow rules
        """
        self.config = config

    @property
    def level(self) -> str:
        return "C"

    def validate(self, plan: ExecutionPlan) -> ValidationResult:
        """Validate workflow structure.

        Args:
            plan: Execution plan to validate

        Returns:
            ValidationResult with ERROR violations if workflow invalid
        """
        violations = []
        plan_actions = [step.action for step in plan.steps]

        # Check for duplicate steps
        seen_actions = set()
        for step in plan.steps:
            if step.action in seen_actions:
                violations.append(Violation(
                    level="C",
                    severity=Severity.ERROR,
                    message=f"Duplicate step: {step.action}",
                    step_id=step.step_id,
                    fixable=True,
                    suggested_fix=f"Remove duplicate {step.action} step"
                ))
            seen_actions.add(step.action)

        # Check required steps
        for required in self.config.workflow_rules.required_steps:
            if required not in plan_actions:
                violations.append(Violation(
                    level="C",
                    severity=Severity.ERROR,
                    message=f"Missing required step: {required}",
                    step_id="",
                    fixable=True,
                    suggested_fix=f"Add {required} step to workflow"
                ))

        # Check step order constraints
        for step_action, prerequisites in self.config.workflow_rules.step_order_constraints.items():
            if step_action in plan_actions:
                step_index = plan_actions.index(step_action)
                for prereq in prerequisites:
                    if prereq in plan_actions:
                        prereq_index = plan_actions.index(prereq)
                        if prereq_index > step_index:
                            violations.append(Violation(
                                level="C",
                                severity=Severity.ERROR,
                                message=f"{step_action} must come after {prereq}",
                                step_id=step_action,
                                fixable=True,
                                suggested_fix=f"Reorder steps: {prereq} before {step_action}"
                            ))

        return ValidationResult(
            valid=len(violations) == 0,
            violations=violations
        )
