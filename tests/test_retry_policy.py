"""Tests for RetryPolicy — configurable retry behavior."""

from __future__ import annotations

import pytest

from mdpilot.agent.error_classifier import ErrorCategory
from mdpilot.agent.retry_policy import RetryConfig, RetryParams, RetryPolicy


class TestRetryParams:
    """Test RetryParams dataclass."""

    def test_default_values(self):
        """Test default parameter values."""
        params = RetryParams()
        assert params.max_attempts == 3
        assert params.base_delay == 1.0
        assert params.max_delay == 60.0
        assert params.backoff_multiplier == 2.0
        assert params.jitter is True

    def test_custom_values(self):
        """Test custom parameter values."""
        params = RetryParams(
            max_attempts=5,
            base_delay=2.0,
            max_delay=300.0,
            backoff_multiplier=3.0,
            jitter=False,
        )
        assert params.max_attempts == 5
        assert params.base_delay == 2.0
        assert params.max_delay == 300.0
        assert params.backoff_multiplier == 3.0
        assert params.jitter is False


class TestRetryConfig:
    """Test RetryConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = RetryConfig()
        assert config.default_max_attempts == 3
        assert config.default_backoff_base == 2.0
        assert config.max_backoff == 300.0
        assert config.by_tool == {}
        assert config.by_error_type == {}

    def test_custom_values(self):
        """Test custom configuration values."""
        config = RetryConfig(
            default_max_attempts=5,
            default_backoff_base=3.0,
            max_backoff=600.0,
            by_tool={"pmemd": {"max_attempts": 10}},
            by_error_type={"TRANSIENT": {"backoff_multiplier": 2.5}},
        )
        assert config.default_max_attempts == 5
        assert config.default_backoff_base == 3.0
        assert config.max_backoff == 600.0
        assert config.by_tool == {"pmemd": {"max_attempts": 10}}
        assert config.by_error_type == {"TRANSIENT": {"backoff_multiplier": 2.5}}


class TestRetryPolicy:
    """Test RetryPolicy class."""

    def test_init(self):
        """Test initialization."""
        config = RetryConfig()
        policy = RetryPolicy(config)
        assert policy.config == config

    def test_get_retry_params_defaults(self):
        """Test getting retry parameters with defaults only."""
        config = RetryConfig(
            default_max_attempts=3,
            default_backoff_base=2.0,
            max_backoff=60.0,
        )
        policy = RetryPolicy(config)

        params = policy.get_retry_params("pmemd", ErrorCategory.TRANSIENT)

        assert params.max_attempts == 3
        assert params.base_delay == 1.0
        assert params.backoff_multiplier == 2.0
        assert params.max_delay == 60.0
        assert params.jitter is True

    def test_get_retry_params_tool_override(self):
        """Test tool-specific overrides."""
        config = RetryConfig(
            default_max_attempts=3,
            by_tool={
                "pmemd": {
                    "max_attempts": 5,
                    "base_delay": 2.0,
                }
            },
        )
        policy = RetryPolicy(config)

        params = policy.get_retry_params("pmemd", ErrorCategory.TRANSIENT)

        assert params.max_attempts == 5
        assert params.base_delay == 2.0
        # Other params should use defaults
        assert params.backoff_multiplier == 2.0
        assert params.jitter is True

    def test_get_retry_params_error_type_override(self):
        """Test error-type specific overrides."""
        config = RetryConfig(
            default_max_attempts=3,
            by_error_type={
                "RESOURCE": {
                    "max_attempts": 5,
                    "backoff_multiplier": 3.0,
                    "max_delay": 300.0,
                }
            },
        )
        policy = RetryPolicy(config)

        params = policy.get_retry_params("pmemd", ErrorCategory.RESOURCE)

        assert params.max_attempts == 5
        assert params.backoff_multiplier == 3.0
        assert params.max_delay == 300.0
        # Other params should use defaults
        assert params.base_delay == 1.0
        assert params.jitter is True

    def test_get_retry_params_layered_overrides(self):
        """Test layered configuration: defaults → tool → error-type."""
        config = RetryConfig(
            default_max_attempts=3,
            by_tool={
                "pmemd": {
                    "max_attempts": 5,
                    "base_delay": 2.0,
                }
            },
            by_error_type={
                "RESOURCE": {
                    "max_attempts": 7,  # Should override tool override
                    "backoff_multiplier": 3.0,
                }
            },
        )
        policy = RetryPolicy(config)

        params = policy.get_retry_params("pmemd", ErrorCategory.RESOURCE)

        # Error-type override should win for max_attempts
        assert params.max_attempts == 7
        # Tool override should apply for base_delay
        assert params.base_delay == 2.0
        # Error-type override should apply for backoff_multiplier
        assert params.backoff_multiplier == 3.0

    def test_calculate_delay_exponential_backoff(self):
        """Test exponential backoff calculation."""
        config = RetryConfig()
        policy = RetryPolicy(config)
        params = RetryParams(
            base_delay=1.0,
            backoff_multiplier=2.0,
            max_delay=60.0,
            jitter=False,
        )

        # attempt 0: 1.0 * (2.0 ** 0) = 1.0
        assert policy.calculate_delay(0, params) == 1.0

        # attempt 1: 1.0 * (2.0 ** 1) = 2.0
        assert policy.calculate_delay(1, params) == 2.0

        # attempt 2: 1.0 * (2.0 ** 2) = 4.0
        assert policy.calculate_delay(2, params) == 4.0

        # attempt 3: 1.0 * (2.0 ** 3) = 8.0
        assert policy.calculate_delay(3, params) == 8.0

    def test_calculate_delay_max_cap(self):
        """Test max_delay cap."""
        config = RetryConfig()
        policy = RetryPolicy(config)
        params = RetryParams(
            base_delay=1.0,
            backoff_multiplier=2.0,
            max_delay=10.0,
            jitter=False,
        )

        # attempt 10: 1.0 * (2.0 ** 10) = 1024.0, but capped at 10.0
        assert policy.calculate_delay(10, params) == 10.0

    def test_calculate_delay_jitter(self):
        """Test jitter adds 0-50% randomness."""
        config = RetryConfig()
        policy = RetryPolicy(config)
        params = RetryParams(
            base_delay=10.0,
            backoff_multiplier=2.0,
            max_delay=60.0,
            jitter=True,
        )

        # Run multiple times to test jitter range
        delays = [policy.calculate_delay(0, params) for _ in range(100)]

        # Base delay is 10.0, jitter should make it 5.0-15.0
        # (10.0 * 0.5 to 10.0 * 1.5, but actually 10.0 * (0.5 + [0, 1)))
        assert all(5.0 <= d <= 15.0 for d in delays)
        # Should have some variation
        assert len(set(delays)) > 10

    def test_calculate_delay_no_jitter(self):
        """Test no jitter produces consistent delays."""
        config = RetryConfig()
        policy = RetryPolicy(config)
        params = RetryParams(
            base_delay=10.0,
            backoff_multiplier=2.0,
            max_delay=60.0,
            jitter=False,
        )

        # Run multiple times
        delays = [policy.calculate_delay(0, params) for _ in range(10)]

        # All should be exactly 10.0
        assert all(d == 10.0 for d in delays)

    def test_should_retry_within_max_attempts(self):
        """Test retry allowed within max_attempts."""
        config = RetryConfig()
        policy = RetryPolicy(config)
        params = RetryParams(max_attempts=3)

        assert policy.should_retry(0, ErrorCategory.TRANSIENT, params) is True
        assert policy.should_retry(1, ErrorCategory.TRANSIENT, params) is True
        assert policy.should_retry(2, ErrorCategory.TRANSIENT, params) is True

    def test_should_retry_exceeds_max_attempts(self):
        """Test retry denied when exceeding max_attempts."""
        config = RetryConfig()
        policy = RetryPolicy(config)
        params = RetryParams(max_attempts=3)

        assert policy.should_retry(3, ErrorCategory.TRANSIENT, params) is False
        assert policy.should_retry(4, ErrorCategory.TRANSIENT, params) is False

    def test_should_retry_permanent_error(self):
        """Test PERMANENT errors never retry."""
        config = RetryConfig()
        policy = RetryPolicy(config)
        params = RetryParams(max_attempts=3)

        # Even at attempt 0, PERMANENT errors should not retry
        assert policy.should_retry(0, ErrorCategory.PERMANENT, params) is False
        assert policy.should_retry(1, ErrorCategory.PERMANENT, params) is False
        assert policy.should_retry(2, ErrorCategory.PERMANENT, params) is False

    def test_should_retry_all_error_categories(self):
        """Test retry behavior for all error categories."""
        config = RetryConfig()
        policy = RetryPolicy(config)
        params = RetryParams(max_attempts=3)

        # TRANSIENT, RESOURCE, CONFIGURATION should retry
        assert policy.should_retry(0, ErrorCategory.TRANSIENT, params) is True
        assert policy.should_retry(0, ErrorCategory.RESOURCE, params) is True
        assert policy.should_retry(0, ErrorCategory.CONFIGURATION, params) is True

        # PERMANENT should never retry
        assert policy.should_retry(0, ErrorCategory.PERMANENT, params) is False

    def test_retry_decision_performance(self):
        """Test retry decision completes in <10ms."""
        import time

        config = RetryConfig()
        policy = RetryPolicy(config)
        params = RetryParams(max_attempts=3)

        start = time.perf_counter()
        for _ in range(1000):
            policy.should_retry(1, ErrorCategory.TRANSIENT, params)
        elapsed = time.perf_counter() - start

        # 1000 decisions should complete in <10ms
        assert elapsed < 0.01

    def test_integration_full_retry_sequence(self):
        """Test full retry sequence with realistic configuration."""
        config = RetryConfig(
            default_max_attempts=3,
            by_tool={
                "pmemd": {
                    "max_attempts": 5,
                    "base_delay": 2.0,
                }
            },
            by_error_type={
                "RESOURCE": {
                    "backoff_multiplier": 3.0,
                    "max_delay": 300.0,
                }
            },
        )
        policy = RetryPolicy(config)

        # Get params for pmemd with RESOURCE error
        params = policy.get_retry_params("pmemd", ErrorCategory.RESOURCE)

        # Should have layered overrides
        assert params.max_attempts == 5  # from tool override
        assert params.base_delay == 2.0  # from tool override
        assert params.backoff_multiplier == 3.0  # from error-type override
        assert params.max_delay == 300.0  # from error-type override

        # Test retry sequence
        assert policy.should_retry(0, ErrorCategory.RESOURCE, params) is True
        delay_0 = policy.calculate_delay(0, params)

        assert policy.should_retry(1, ErrorCategory.RESOURCE, params) is True
        delay_1 = policy.calculate_delay(1, params)

        assert policy.should_retry(2, ErrorCategory.RESOURCE, params) is True
        delay_2 = policy.calculate_delay(2, params)

        assert policy.should_retry(3, ErrorCategory.RESOURCE, params) is True
        delay_3 = policy.calculate_delay(3, params)

        assert policy.should_retry(4, ErrorCategory.RESOURCE, params) is True
        delay_4 = policy.calculate_delay(4, params)

        # Attempt 5 should fail (max_attempts=5 means attempts 0-4)
        assert policy.should_retry(5, ErrorCategory.RESOURCE, params) is False

        # Delays should increase (with jitter, approximate check)
        # Base pattern: 2.0, 6.0, 18.0, 54.0, 162.0
        # With jitter disabled for predictable test
        params_no_jitter = RetryParams(
            max_attempts=5,
            base_delay=2.0,
            backoff_multiplier=3.0,
            max_delay=300.0,
            jitter=False,
        )
        assert policy.calculate_delay(0, params_no_jitter) == 2.0
        assert policy.calculate_delay(1, params_no_jitter) == 6.0
        assert policy.calculate_delay(2, params_no_jitter) == 18.0
        assert policy.calculate_delay(3, params_no_jitter) == 54.0
        assert policy.calculate_delay(4, params_no_jitter) == 162.0
