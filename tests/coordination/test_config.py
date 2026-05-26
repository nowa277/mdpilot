"""Tests for coordination configuration."""

import pytest
from mdpilot.coordination.config import (
    ResourceLimits,
    RecoveryPolicies,
    WorkflowRules,
    ToolConstraints,
    FileSystemPermissions,
    GuardrailConfig,
)


class TestResourceLimits:
    """Test ResourceLimits configuration."""

    def test_default_values(self):
        limits = ResourceLimits()
        assert limits.max_cpu_hours == 10.0
        assert limits.max_memory_gb == 16.0
        assert limits.max_disk_gb == 50.0
        assert limits.max_cpu == 8.0
        assert limits.max_memory == 16.0
        assert limits.max_disk == 50.0

    def test_custom_values(self):
        limits = ResourceLimits(
            max_cpu_hours=5.0,
            max_memory_gb=8.0,
            max_disk_gb=25.0,
            max_cpu=4.0,
            max_memory=8.0,
            max_disk=25.0
        )
        assert limits.max_cpu_hours == 5.0
        assert limits.max_memory_gb == 8.0
        assert limits.max_disk_gb == 25.0
        assert limits.max_cpu == 4.0
        assert limits.max_memory == 8.0
        assert limits.max_disk == 25.0

    def test_zero_limits(self):
        limits = ResourceLimits(
            max_cpu_hours=0.0,
            max_memory_gb=0.0,
            max_disk_gb=0.0
        )
        assert limits.max_cpu_hours == 0.0
        assert limits.max_memory_gb == 0.0
        assert limits.max_disk_gb == 0.0


class TestRecoveryPolicies:
    """Test RecoveryPolicies configuration."""

    def test_default_values(self):
        policies = RecoveryPolicies()
        assert policies.max_retries == 3
        assert policies.retry_delay == 1.0
        assert len(policies.allowed_strategies) == 4
        assert "retry_with_backoff" in policies.allowed_strategies
        assert "fallback_tool" in policies.allowed_strategies
        assert "skip_step" in policies.allowed_strategies
        assert "abort_plan" in policies.allowed_strategies

    def test_custom_values(self):
        policies = RecoveryPolicies(
            max_retries=5,
            retry_delay=2.0,
            allowed_strategies=["retry_with_backoff", "abort_plan"]
        )
        assert policies.max_retries == 5
        assert policies.retry_delay == 2.0
        assert len(policies.allowed_strategies) == 2
        assert "retry_with_backoff" in policies.allowed_strategies
        assert "abort_plan" in policies.allowed_strategies

    def test_no_retries(self):
        policies = RecoveryPolicies(max_retries=0)
        assert policies.max_retries == 0

    def test_empty_strategies(self):
        policies = RecoveryPolicies(allowed_strategies=[])
        assert policies.allowed_strategies == []


class TestWorkflowRules:
    """Test WorkflowRules configuration."""

    def test_default_values(self):
        rules = WorkflowRules()
        assert len(rules.required_steps) == 3
        assert "prepare_system" in rules.required_steps
        assert "minimize" in rules.required_steps
        assert "equilibrate" in rules.required_steps
        assert rules.step_order_constraints == {}

    def test_custom_required_steps(self):
        rules = WorkflowRules(required_steps=["step1", "step2"])
        assert len(rules.required_steps) == 2
        assert "step1" in rules.required_steps
        assert "step2" in rules.required_steps

    def test_step_order_constraints(self):
        rules = WorkflowRules(
            step_order_constraints={
                "minimize": ["prepare_system"],
                "equilibrate": ["minimize"]
            }
        )
        assert "minimize" in rules.step_order_constraints
        assert "prepare_system" in rules.step_order_constraints["minimize"]
        assert "equilibrate" in rules.step_order_constraints
        assert "minimize" in rules.step_order_constraints["equilibrate"]

    def test_empty_rules(self):
        rules = WorkflowRules(required_steps=[], step_order_constraints={})
        assert rules.required_steps == []
        assert rules.step_order_constraints == {}


class TestToolConstraints:
    """Test ToolConstraints configuration."""

    def test_default_values(self):
        constraints = ToolConstraints()
        assert constraints.parameter_ranges == {}
        assert constraints.required_parameters == {}

    def test_parameter_ranges(self):
        constraints = ToolConstraints(
            parameter_ranges={
                "sander": {
                    "maxcyc": {"min": 1, "max": 10000},
                    "ntpr": {"min": 1, "max": 1000}
                }
            }
        )
        assert "sander" in constraints.parameter_ranges
        assert "maxcyc" in constraints.parameter_ranges["sander"]
        assert constraints.parameter_ranges["sander"]["maxcyc"]["min"] == 1
        assert constraints.parameter_ranges["sander"]["maxcyc"]["max"] == 10000

    def test_required_parameters(self):
        constraints = ToolConstraints(
            required_parameters={
                "sander": ["input", "output", "topology"],
                "tleap": ["input"]
            }
        )
        assert "sander" in constraints.required_parameters
        assert len(constraints.required_parameters["sander"]) == 3
        assert "input" in constraints.required_parameters["sander"]
        assert "tleap" in constraints.required_parameters
        assert len(constraints.required_parameters["tleap"]) == 1

    def test_combined_constraints(self):
        constraints = ToolConstraints(
            parameter_ranges={"tool1": {"param1": {"min": 0, "max": 100}}},
            required_parameters={"tool1": ["param1", "param2"]}
        )
        assert "tool1" in constraints.parameter_ranges
        assert "tool1" in constraints.required_parameters


class TestFileSystemPermissions:
    """Test FileSystemPermissions configuration."""

    def test_default_values(self):
        perms = FileSystemPermissions()
        assert len(perms.allowed_paths) == 2
        assert "/home/user/obsidian/project/MDPilot" in perms.allowed_paths
        assert "/tmp" in perms.allowed_paths
        assert len(perms.forbidden_paths) == 3
        assert "/etc" in perms.forbidden_paths
        assert "/sys" in perms.forbidden_paths
        assert "/proc" in perms.forbidden_paths

    def test_custom_allowed_paths(self):
        perms = FileSystemPermissions(
            allowed_paths=["/home/user/data", "/home/user/output"]
        )
        assert len(perms.allowed_paths) == 2
        assert "/home/user/data" in perms.allowed_paths
        assert "/home/user/output" in perms.allowed_paths

    def test_custom_forbidden_paths(self):
        perms = FileSystemPermissions(
            forbidden_paths=["/root", "/boot"]
        )
        assert len(perms.forbidden_paths) == 2
        assert "/root" in perms.forbidden_paths
        assert "/boot" in perms.forbidden_paths

    def test_empty_permissions(self):
        perms = FileSystemPermissions(allowed_paths=[], forbidden_paths=[])
        assert perms.allowed_paths == []
        assert perms.forbidden_paths == []

    def test_overlapping_paths(self):
        # Test that we can create config with overlapping paths (validation happens elsewhere)
        perms = FileSystemPermissions(
            allowed_paths=["/home/user"],
            forbidden_paths=["/home/user/private"]
        )
        assert "/home/user" in perms.allowed_paths
        assert "/home/user/private" in perms.forbidden_paths


class TestGuardrailConfig:
    """Test GuardrailConfig complete configuration."""

    def test_default_values(self):
        config = GuardrailConfig()
        assert isinstance(config.resource_limits, ResourceLimits)
        assert isinstance(config.recovery_policies, RecoveryPolicies)
        assert isinstance(config.workflow_rules, WorkflowRules)
        assert isinstance(config.tool_constraints, ToolConstraints)
        assert isinstance(config.fs_permissions, FileSystemPermissions)

    def test_default_resource_limits(self):
        config = GuardrailConfig()
        assert config.resource_limits.max_cpu_hours == 10.0
        assert config.resource_limits.max_memory_gb == 16.0

    def test_default_recovery_policies(self):
        config = GuardrailConfig()
        assert config.recovery_policies.max_retries == 3
        assert config.recovery_policies.retry_delay == 1.0

    def test_default_workflow_rules(self):
        config = GuardrailConfig()
        assert "prepare_system" in config.workflow_rules.required_steps
        assert "minimize" in config.workflow_rules.required_steps

    def test_default_tool_constraints(self):
        config = GuardrailConfig()
        assert config.tool_constraints.parameter_ranges == {}
        assert config.tool_constraints.required_parameters == {}

    def test_default_fs_permissions(self):
        config = GuardrailConfig()
        assert "/tmp" in config.fs_permissions.allowed_paths
        assert "/etc" in config.fs_permissions.forbidden_paths

    def test_custom_resource_limits(self):
        config = GuardrailConfig(
            resource_limits=ResourceLimits(max_cpu_hours=5.0, max_memory_gb=8.0)
        )
        assert config.resource_limits.max_cpu_hours == 5.0
        assert config.resource_limits.max_memory_gb == 8.0

    def test_custom_recovery_policies(self):
        config = GuardrailConfig(
            recovery_policies=RecoveryPolicies(max_retries=5, retry_delay=2.0)
        )
        assert config.recovery_policies.max_retries == 5
        assert config.recovery_policies.retry_delay == 2.0

    def test_custom_workflow_rules(self):
        config = GuardrailConfig(
            workflow_rules=WorkflowRules(required_steps=["step1", "step2"])
        )
        assert len(config.workflow_rules.required_steps) == 2
        assert "step1" in config.workflow_rules.required_steps

    def test_custom_tool_constraints(self):
        config = GuardrailConfig(
            tool_constraints=ToolConstraints(
                required_parameters={"tool1": ["param1"]}
            )
        )
        assert "tool1" in config.tool_constraints.required_parameters

    def test_custom_fs_permissions(self):
        config = GuardrailConfig(
            fs_permissions=FileSystemPermissions(
                allowed_paths=["/custom/path"]
            )
        )
        assert "/custom/path" in config.fs_permissions.allowed_paths

    def test_fully_custom_config(self):
        config = GuardrailConfig(
            resource_limits=ResourceLimits(max_cpu_hours=2.0),
            recovery_policies=RecoveryPolicies(max_retries=1),
            workflow_rules=WorkflowRules(required_steps=["custom_step"]),
            tool_constraints=ToolConstraints(required_parameters={"tool": ["p1"]}),
            fs_permissions=FileSystemPermissions(allowed_paths=["/custom"])
        )
        assert config.resource_limits.max_cpu_hours == 2.0
        assert config.recovery_policies.max_retries == 1
        assert "custom_step" in config.workflow_rules.required_steps
        assert "tool" in config.tool_constraints.required_parameters
        assert "/custom" in config.fs_permissions.allowed_paths

    def test_partial_custom_config(self):
        # Test that we can customize some parts while keeping defaults for others
        config = GuardrailConfig(
            resource_limits=ResourceLimits(max_cpu_hours=5.0)
        )
        assert config.resource_limits.max_cpu_hours == 5.0
        # Other fields should have defaults
        assert config.recovery_policies.max_retries == 3
        assert "prepare_system" in config.workflow_rules.required_steps
