"""B-level: Tool parameter validator."""

from mdpilot.coordination.config import ToolConstraints
from mdpilot.coordination.types import ExecutionPlan, Severity, ValidationResult, Violation
from mdpilot.coordination.validators.base import BaseValidator


class ToolValidator(BaseValidator):
    """Validates tool parameters and constraints.

    B-level validator enforces tool constraints:
    - Tool names are valid (exist in tool registry)
    - Required parameters present
    - Parameter values within allowed ranges
    - Parameter types correct

    All violations are WARNING severity and fixable.
    """

    def __init__(self, constraints: ToolConstraints):
        """Initialize validator.

        Args:
            constraints: Tool parameter constraints
        """
        self.constraints = constraints

    @property
    def level(self) -> str:
        return "B"

    def validate(self, plan: ExecutionPlan) -> ValidationResult:
        """Validate tool parameters.

        Args:
            plan: Execution plan to validate

        Returns:
            ValidationResult with WARNING violations if parameters invalid
        """
        violations = []

        for step in plan.steps:
            # Check each required tool
            for tool_name in step.required_tools:
                # Check if tool has required parameters defined
                if tool_name in self.constraints.required_parameters:
                    required_params = self.constraints.required_parameters[tool_name]
                    for param in required_params:
                        if param not in step.parameters:
                            violations.append(Violation(
                                level="B",
                                severity=Severity.WARNING,
                                message=(
                                    f"Step {step.step_id} missing required parameter '{param}' "
                                    f"for tool '{tool_name}'"
                                ),
                                step_id=step.step_id,
                                fixable=True,
                                suggested_fix=f"Add '{param}' parameter to step {step.step_id}"
                            ))

                # Check parameter ranges
                if tool_name in self.constraints.parameter_ranges:
                    ranges = self.constraints.parameter_ranges[tool_name]
                    for param_name, param_value in step.parameters.items():
                        if param_name in ranges:
                            range_spec = ranges[param_name]

                            # Check min value
                            if "min" in range_spec and param_value < range_spec["min"]:
                                violations.append(Violation(
                                    level="B",
                                    severity=Severity.WARNING,
                                    message=(
                                        f"Step {step.step_id} parameter '{param_name}' value {param_value} "
                                        f"below minimum {range_spec['min']}"
                                    ),
                                    step_id=step.step_id,
                                    fixable=True,
                                    suggested_fix=f"Set '{param_name}' >= {range_spec['min']}"
                                ))

                            # Check max value
                            if "max" in range_spec and param_value > range_spec["max"]:
                                violations.append(Violation(
                                    level="B",
                                    severity=Severity.WARNING,
                                    message=(
                                        f"Step {step.step_id} parameter '{param_name}' value {param_value} "
                                        f"exceeds maximum {range_spec['max']}"
                                    ),
                                    step_id=step.step_id,
                                    fixable=True,
                                    suggested_fix=f"Set '{param_name}' <= {range_spec['max']}"
                                ))

                            # Check allowed values
                            if "allowed" in range_spec and param_value not in range_spec["allowed"]:
                                violations.append(Violation(
                                    level="B",
                                    severity=Severity.WARNING,
                                    message=(
                                        f"Step {step.step_id} parameter '{param_name}' value '{param_value}' "
                                        f"not in allowed values: {range_spec['allowed']}"
                                    ),
                                    step_id=step.step_id,
                                    fixable=True,
                                    suggested_fix=f"Use one of: {', '.join(map(str, range_spec['allowed']))}"
                                ))

        return ValidationResult(
            valid=len(violations) == 0,
            violations=violations
        )
