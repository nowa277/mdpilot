"""Tests for ResourceGuard."""

import pytest

from mdpilot.coordination.config import ResourceLimits
from mdpilot.coordination.resource_guard import ResourceGuard
from mdpilot.coordination.types import ToolCall


class TestResourceGuard:
    """Test ResourceGuard functionality."""

    def test_init(self):
        """Test ResourceGuard initialization."""
        limits = ResourceLimits(max_cpu_hours=10.0, max_memory_gb=16.0, max_disk_gb=50.0)
        guard = ResourceGuard(limits)

        assert guard.limits == limits
        assert guard.current_usage["cpu_hours"] == 0.0
        assert guard.current_usage["memory_gb"] == 0.0
        assert guard.current_usage["disk_gb"] == 0.0

    def test_check_available_with_resources(self):
        """Test check_available when resources are available."""
        limits = ResourceLimits(max_cpu_hours=10.0, max_memory_gb=16.0, max_disk_gb=50.0)
        guard = ResourceGuard(limits)

        tool_call = ToolCall(tool_name="minimize", parameters={})
        assert guard.check_available(tool_call) is True

    def test_check_available_memory_exhausted(self):
        """Test check_available when memory is exhausted."""
        limits = ResourceLimits(max_cpu_hours=10.0, max_memory_gb=2.0, max_disk_gb=50.0)
        guard = ResourceGuard(limits)

        # Use up memory
        guard.current_usage["memory_gb"] = 1.5

        # Try to run tool that needs 2GB
        tool_call = ToolCall(tool_name="minimize", parameters={})
        assert guard.check_available(tool_call) is False

    def test_check_available_cpu_exhausted(self):
        """Test check_available when CPU is exhausted."""
        limits = ResourceLimits(max_cpu_hours=1.0, max_memory_gb=16.0, max_disk_gb=50.0)
        guard = ResourceGuard(limits)

        # Use up CPU
        guard.current_usage["cpu_hours"] = 0.8

        # Try to run tool that needs 0.5 CPU hours
        tool_call = ToolCall(tool_name="minimize", parameters={})
        assert guard.check_available(tool_call) is False

    def test_check_available_disk_exhausted(self):
        """Test check_available when disk is exhausted."""
        limits = ResourceLimits(max_cpu_hours=10.0, max_memory_gb=16.0, max_disk_gb=2.0)
        guard = ResourceGuard(limits)

        # Use up disk
        guard.current_usage["disk_gb"] = 1.5

        # Try to run tool that needs 1GB
        tool_call = ToolCall(tool_name="minimize", parameters={})
        assert guard.check_available(tool_call) is False

    def test_record_usage(self):
        """Test recording resource usage."""
        limits = ResourceLimits()
        guard = ResourceGuard(limits)

        tool_call = ToolCall(tool_name="minimize", parameters={})
        actual_usage = {"cpu_hours": 0.5, "memory_gb": 2.0, "disk_gb": 1.0}

        guard.record_usage(tool_call, actual_usage)

        assert guard.current_usage["cpu_hours"] == 0.5
        assert guard.current_usage["memory_gb"] == 2.0
        assert guard.current_usage["disk_gb"] == 1.0

    def test_record_usage_accumulates(self):
        """Test that record_usage accumulates over multiple calls."""
        limits = ResourceLimits()
        guard = ResourceGuard(limits)

        tool_call1 = ToolCall(tool_name="minimize", parameters={})
        tool_call2 = ToolCall(tool_name="equilibrate", parameters={})

        guard.record_usage(tool_call1, {"cpu_hours": 0.5, "memory_gb": 2.0, "disk_gb": 1.0})
        guard.record_usage(tool_call2, {"cpu_hours": 1.0, "memory_gb": 4.0, "disk_gb": 2.0})

        assert guard.current_usage["cpu_hours"] == 1.5
        assert guard.current_usage["memory_gb"] == 6.0
        assert guard.current_usage["disk_gb"] == 3.0

    def test_estimate_tool_resources_minimize(self):
        """Test resource estimation for minimize tool."""
        limits = ResourceLimits()
        guard = ResourceGuard(limits)

        tool_call = ToolCall(tool_name="minimize", parameters={})
        estimate = guard._estimate_tool_resources(tool_call)

        assert estimate["cpu_hours"] == 0.5
        assert estimate["memory_gb"] == 2.0
        assert estimate["disk_gb"] == 1.0

    def test_estimate_tool_resources_equilibrate(self):
        """Test resource estimation for equilibrate tool."""
        limits = ResourceLimits()
        guard = ResourceGuard(limits)

        tool_call = ToolCall(tool_name="equilibrate", parameters={})
        estimate = guard._estimate_tool_resources(tool_call)

        assert estimate["cpu_hours"] == 1.0
        assert estimate["memory_gb"] == 4.0
        assert estimate["disk_gb"] == 2.0

    def test_estimate_tool_resources_production(self):
        """Test resource estimation for production tool."""
        limits = ResourceLimits()
        guard = ResourceGuard(limits)

        tool_call = ToolCall(tool_name="production", parameters={})
        estimate = guard._estimate_tool_resources(tool_call)

        assert estimate["cpu_hours"] == 5.0
        assert estimate["memory_gb"] == 8.0
        assert estimate["disk_gb"] == 5.0

    def test_estimate_tool_resources_default(self):
        """Test resource estimation for unknown tool."""
        limits = ResourceLimits()
        guard = ResourceGuard(limits)

        tool_call = ToolCall(tool_name="unknown_tool", parameters={})
        estimate = guard._estimate_tool_resources(tool_call)

        assert estimate["cpu_hours"] == 0.1
        assert estimate["memory_gb"] == 1.0
        assert estimate["disk_gb"] == 0.5

    def test_get_current_usage(self):
        """Test getting current usage."""
        limits = ResourceLimits()
        guard = ResourceGuard(limits)

        guard.current_usage["cpu_hours"] = 1.5
        guard.current_usage["memory_gb"] = 4.0

        usage = guard.get_current_usage()

        assert usage["cpu_hours"] == 1.5
        assert usage["memory_gb"] == 4.0
        # Verify it's a copy
        usage["cpu_hours"] = 999
        assert guard.current_usage["cpu_hours"] == 1.5

    def test_reset_usage(self):
        """Test resetting usage counters."""
        limits = ResourceLimits()
        guard = ResourceGuard(limits)

        guard.current_usage["cpu_hours"] = 5.0
        guard.current_usage["memory_gb"] = 10.0
        guard.current_usage["disk_gb"] = 20.0

        guard.reset_usage()

        assert guard.current_usage["cpu_hours"] == 0.0
        assert guard.current_usage["memory_gb"] == 0.0
        assert guard.current_usage["disk_gb"] == 0.0

    def test_multiple_tool_calls_within_limits(self):
        """Test multiple tool calls within resource limits."""
        limits = ResourceLimits(max_cpu_hours=10.0, max_memory_gb=16.0, max_disk_gb=50.0)
        guard = ResourceGuard(limits)

        # First tool
        tool1 = ToolCall(tool_name="minimize", parameters={})
        assert guard.check_available(tool1) is True
        guard.record_usage(tool1, {"cpu_hours": 0.5, "memory_gb": 2.0, "disk_gb": 1.0})

        # Second tool
        tool2 = ToolCall(tool_name="equilibrate", parameters={})
        assert guard.check_available(tool2) is True
        guard.record_usage(tool2, {"cpu_hours": 1.0, "memory_gb": 4.0, "disk_gb": 2.0})

        # Third tool
        tool3 = ToolCall(tool_name="analyze", parameters={})
        assert guard.check_available(tool3) is True

    def test_multiple_tool_calls_exceeding_limits(self):
        """Test multiple tool calls exceeding resource limits."""
        limits = ResourceLimits(max_cpu_hours=2.0, max_memory_gb=8.0, max_disk_gb=5.0)
        guard = ResourceGuard(limits)

        # First tool
        tool1 = ToolCall(tool_name="minimize", parameters={})
        assert guard.check_available(tool1) is True
        guard.record_usage(tool1, {"cpu_hours": 0.5, "memory_gb": 2.0, "disk_gb": 1.0})

        # Second tool
        tool2 = ToolCall(tool_name="equilibrate", parameters={})
        assert guard.check_available(tool2) is True
        guard.record_usage(tool2, {"cpu_hours": 1.0, "memory_gb": 4.0, "disk_gb": 2.0})

        # Third tool - should fail due to memory
        tool3 = ToolCall(tool_name="equilibrate", parameters={})
        assert guard.check_available(tool3) is False
