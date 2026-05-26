"""Tests for FileSystemValidator (A-level)."""

import pytest

from mdpilot.coordination.config import FileSystemPermissions
from mdpilot.coordination.types import (
    ExecutionPlan,
    PlanStep,
    ResourceEstimate,
    Severity,
)
from mdpilot.coordination.validators.filesystem_validator import FileSystemValidator


@pytest.fixture
def default_permissions():
    """Default file system permissions."""
    return FileSystemPermissions(
        allowed_paths=[
            "/home/user/obsidian/project/amber-agent",
            "/tmp"
        ],
        forbidden_paths=[
            "/etc",
            "/sys",
            "/proc"
        ]
    )


@pytest.fixture
def validator(default_permissions):
    """FileSystemValidator with default permissions."""
    return FileSystemValidator(default_permissions)


@pytest.fixture
def valid_plan():
    """Valid plan with proper file paths."""
    return ExecutionPlan(
        plan_id="test-plan",
        task_description="Valid filesystem plan",
        steps=[
            PlanStep(
                step_id="step1",
                action="prepare_system",
                intent="Prepare",
                parameters={
                    "input_file": "/home/user/obsidian/project/amber-agent/data/input.pdb",
                    "output_file": "/tmp/output.prmtop"
                }
            ),
            PlanStep(
                step_id="step2",
                action="minimize",
                intent="Minimize",
                parameters={
                    "file_path": "/home/user/obsidian/project/amber-agent/min.in"
                }
            )
        ],
        estimated_resources=ResourceEstimate()
    )


class TestFileSystemValidator:
    """Test FileSystemValidator functionality."""

    def test_validator_level(self, validator):
        """Test validator reports correct level."""
        assert validator.level == "A"

    def test_valid_plan_passes(self, validator, valid_plan):
        """Test valid plan passes validation."""
        result = validator.validate(valid_plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_forbidden_path_etc(self, validator):
        """Test access to /etc is forbidden."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Forbidden /etc",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="read_config",
                    intent="Read",
                    parameters={"input_file": "/etc/passwd"}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.level == "A"
        assert violation.severity == Severity.WARNING
        assert "forbidden path" in violation.message
        assert "/etc/passwd" in violation.message
        assert violation.step_id == "step1"
        assert violation.fixable is True

    def test_forbidden_path_sys(self, validator):
        """Test access to /sys is forbidden."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Forbidden /sys",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="read_system",
                    intent="Read",
                    parameters={"path": "/sys/class/net"}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.level == "A"
        assert violation.severity == Severity.WARNING
        assert "forbidden path" in violation.message
        assert "/sys" in violation.message

    def test_forbidden_path_proc(self, validator):
        """Test access to /proc is forbidden."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Forbidden /proc",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="read_process",
                    intent="Read",
                    parameters={"file_path": "/proc/cpuinfo"}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.level == "A"
        assert violation.severity == Severity.WARNING
        assert "forbidden path" in violation.message
        assert "/proc" in violation.message

    def test_path_not_in_allowed_directories(self, validator):
        """Test path outside allowed directories."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Outside allowed",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="write_file",
                    intent="Write",
                    parameters={"output_file": "/var/log/output.log"}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.level == "A"
        assert violation.severity == Severity.WARNING
        assert "not in allowed directories" in violation.message
        assert "/var/log/output.log" in violation.message
        assert violation.step_id == "step1"
        assert violation.fixable is True

    def test_multiple_file_parameters(self, validator):
        """Test step with multiple file parameters."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Multiple files",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="process",
                    intent="Process",
                    parameters={
                        "input_file": "/home/user/obsidian/project/amber-agent/input.pdb",
                        "output_file": "/tmp/output.prmtop",
                        "file_path": "/home/user/obsidian/project/amber-agent/config.in"
                    }
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_multiple_violations_in_step(self, validator):
        """Test step with multiple path violations."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Multiple violations",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="process",
                    intent="Process",
                    parameters={
                        "input_file": "/etc/config",
                        "output_file": "/var/log/output.log"
                    }
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        # Should have violation for /etc (forbidden) but not /var/log (just not allowed)
        # because forbidden check breaks early
        assert len(result.violations) >= 1

        # All violations should be WARNING and fixable
        for violation in result.violations:
            assert violation.level == "A"
            assert violation.severity == Severity.WARNING
            assert violation.fixable is True

    def test_step_without_file_parameters(self, validator):
        """Test step without file parameters passes."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="No files",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="calculate",
                    intent="Calculate",
                    parameters={
                        "value": 42,
                        "name": "test"
                    }
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_none_file_parameter(self, validator):
        """Test None file parameter is skipped."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="None file",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="process",
                    intent="Process",
                    parameters={
                        "input_file": None,
                        "output_file": "/tmp/output.txt"
                    }
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_non_string_file_parameter(self, validator):
        """Test non-string file parameter is skipped."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Non-string file",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="process",
                    intent="Process",
                    parameters={
                        "input_file": 123,
                        "output_file": "/tmp/output.txt"
                    }
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_tmp_directory_allowed(self, validator):
        """Test /tmp directory is allowed."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Tmp directory",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="write_temp",
                    intent="Write",
                    parameters={"output_file": "/tmp/temp_file.txt"}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_project_directory_allowed(self, validator):
        """Test project directory is allowed."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Project directory",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="write_output",
                    intent="Write",
                    parameters={
                        "output_file": "/home/user/obsidian/project/amber-agent/output/result.txt"
                    }
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_custom_permissions(self):
        """Test validator with custom permissions."""
        custom_permissions = FileSystemPermissions(
            allowed_paths=["/data", "/output"],
            forbidden_paths=["/secret"]
        )
        validator = FileSystemValidator(custom_permissions)

        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Custom permissions",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="process",
                    intent="Process",
                    parameters={
                        "input_file": "/data/input.txt",
                        "output_file": "/output/result.txt"
                    }
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_all_file_parameter_names(self, validator):
        """Test all recognized file parameter names."""
        param_names = ["input_file", "output_file", "file_path", "path", "directory"]

        for param_name in param_names:
            plan = ExecutionPlan(
                plan_id="test-plan",
                task_description=f"Test {param_name}",
                steps=[
                    PlanStep(
                        step_id="step1",
                        action="test",
                        intent="Test",
                        parameters={
                            param_name: "/home/user/obsidian/project/amber-agent/test.txt"
                        }
                    )
                ],
                estimated_resources=ResourceEstimate()
            )

            result = validator.validate(plan)
            assert result.valid is True, f"Parameter {param_name} should be valid"

    def test_forbidden_takes_precedence(self, validator):
        """Test forbidden path check happens before allowed check."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Forbidden precedence",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="read",
                    intent="Read",
                    parameters={"input_file": "/etc/config"}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1
        assert "forbidden" in result.violations[0].message

    def test_empty_allowed_paths(self):
        """Test validator with empty allowed_paths list."""
        permissions = FileSystemPermissions(
            allowed_paths=[],
            forbidden_paths=["/etc"]
        )
        validator = FileSystemValidator(permissions)

        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Empty allowed",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="process",
                    intent="Process",
                    parameters={"input_file": "/home/user/file.txt"}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        # With empty allowed_paths, all non-forbidden paths should pass
        assert result.valid is True

    def test_subdirectory_of_allowed_path(self, validator):
        """Test subdirectory of allowed path is allowed."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Subdirectory",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="write",
                    intent="Write",
                    parameters={
                        "output_file": "/home/user/obsidian/project/amber-agent/subdir/deep/file.txt"
                    }
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_subdirectory_of_forbidden_path(self, validator):
        """Test subdirectory of forbidden path is forbidden."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Forbidden subdirectory",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="read",
                    intent="Read",
                    parameters={"input_file": "/etc/systemd/system.conf"}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) == 1
        assert "forbidden" in result.violations[0].message

    def test_multiple_steps_with_violations(self, validator):
        """Test multiple steps with path violations."""
        plan = ExecutionPlan(
            plan_id="test-plan",
            task_description="Multiple step violations",
            steps=[
                PlanStep(
                    step_id="step1",
                    action="read",
                    intent="Read",
                    parameters={"input_file": "/etc/config"}
                ),
                PlanStep(
                    step_id="step2",
                    action="write",
                    intent="Write",
                    parameters={"output_file": "/var/log/output.log"}
                ),
                PlanStep(
                    step_id="step3",
                    action="process",
                    intent="Process",
                    parameters={"file_path": "/proc/meminfo"}
                )
            ],
            estimated_resources=ResourceEstimate()
        )

        result = validator.validate(plan)
        assert result.valid is False
        assert len(result.violations) >= 2

        # All violations should be WARNING and fixable
        for violation in result.violations:
            assert violation.level == "A"
            assert violation.severity == Severity.WARNING
            assert violation.fixable is True
