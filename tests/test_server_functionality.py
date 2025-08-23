#!/usr/bin/env python3
"""
Test script to verify server functionality with positional arguments.
"""

import sys
import os

# Add the src directory to the Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Import the modules directly
import command_server.command_server as cmd_server
from command_server.command_server import CommandHandler, ServerStats
import threading


def test_command_execution():
    """Test that commands with positional arguments execute correctly."""

    # Create a mock server stats object
    stats = ServerStats()
    shutdown_event = threading.Event()

    # Create a handler instance (we won't use the socket connection)
    # We'll directly test the _exec_shell method
    handler = CommandHandler(None, ("127.0.0.1", 12345), stats, shutdown_event)

    test_cases = [
        ("echo hello", "hello"),
        ("echo 'hello world'", "hello world"),
        ("pwd", lambda x: len(x) > 0),  # pwd should return current directory
        ("whoami", lambda x: len(x) > 0),  # whoami should return username
    ]

    print("Testing command execution with positional arguments:")
    print("=" * 60)

    for cmd, expected in test_cases:
        try:
            stdout, stderr = handler._exec_shell(cmd)

            if stderr:
                print(f"✗ ERROR: '{cmd}' -> {stderr}")
                continue

            # Handle different expected types
            if callable(expected):
                # Use the validation function
                success = expected(stdout.strip())
                status = "✓ PASS" if success else "✗ FAIL"
                print(f"{status}: '{cmd}' -> '{stdout.strip()}'")
            else:
                # Compare directly
                success = stdout.strip() == expected
                status = "✓ PASS" if success else "✗ FAIL"
                print(
                    f"{status}: '{cmd}' -> '{stdout.strip()}' (expected: '{expected}')"
                )

        except Exception as e:
            print(f"✗ EXCEPTION: '{cmd}' -> {e}")

    # Test disallowed commands
    print("\nTesting command rejection (security):")
    print("=" * 60)

    disallowed_commands = [
        "rm -rf /",
        "bash -c 'echo dangerous'",
        "python -c 'print(\"dangerous\")'",
    ]

    for cmd in disallowed_commands:
        try:
            stdout, stderr = handler._exec_shell(cmd)
            if "not allowed" in stderr or "ERROR" in stderr:
                print(f"✓ REJECTED: '{cmd}' -> {stderr.strip()}")
            else:
                print(
                    f"✗ ALLOWED (UNEXPECTED): '{cmd}' -> stdout: '{stdout}', stderr: '{stderr}'"
                )
        except Exception as e:
            print(f"✗ EXCEPTION: '{cmd}' -> {e}")


if __name__ == "__main__":
    test_command_execution()
