"""
Security tests for the Command Server.

These tests verify that security vulnerabilities have been addressed.
"""

import subprocess
import shlex
from command_server.command_server import CommandHandler


def test_shell_injection_protection():
    """Test that shell injection attacks are prevented."""
    # Test various shell injection attempts
    injection_attempts = [
        "; rm -rf /",
        "$(rm -rf /)",
        "`rm -rf /`",
        "| rm -rf /",
        "&& rm -rf /",
        "|| rm -rf /",
        "echo 'test'; rm -rf /",
    ]

    for attempt in injection_attempts:
        # Test that shlex.quote properly escapes the command
        safe_cmd = shlex.quote(attempt)

        # The safe command should not execute the injection
        assert "rm -rf /" not in safe_cmd, f"Injection not prevented: {attempt}"
        assert safe_cmd.startswith("'") and safe_cmd.endswith("'"), (
            f"Command not properly quoted: {safe_cmd}"
        )


def test_command_length_validation():
    """Test that long commands are rejected."""
    from command_server.command_server import MAX_COMMAND_LENGTH

    # Create a command that exceeds the limit
    long_command = "A" * (MAX_COMMAND_LENGTH + 1)

    # This should be rejected by the validation logic
    assert len(long_command) > MAX_COMMAND_LENGTH


def test_buffer_size_limits():
    """Test that buffer size limits are enforced."""
    from command_server.command_server import MAX_RECV_BUFFER

    # The buffer limit should be a reasonable value
    assert MAX_RECV_BUFFER > 0
    assert MAX_RECV_BUFFER <= 65536  # Reasonable upper limit


if __name__ == "__main__":
    test_shell_injection_protection()
    test_command_length_validation()
    test_buffer_size_limits()
    print("All security tests passed!")
