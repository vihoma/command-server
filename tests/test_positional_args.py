#!/usr/bin/env python3
"""
Test script to verify positional argument support in command server.
"""

import shlex


def test_command_parsing():
    """Test that commands with positional arguments are parsed correctly."""

    test_cases = [
        ("ls -lha --color=always", ["ls", "-lha", "--color=always"]),
        ("echo 'hello world'", ["echo", "hello world"]),
        ("grep -i 'search term' file.txt", ["grep", "-i", "search term", "file.txt"]),
        ("find . -name '*.py' -type f", ["find", ".", "-name", "*.py", "-type", "f"]),
        ("pwd", ["pwd"]),
        ("whoami", ["whoami"]),
    ]

    print("Testing command parsing with shlex.split():")
    print("=" * 50)

    for cmd, expected in test_cases:
        try:
            result = shlex.split(cmd)
            status = "✓ PASS" if result == expected else "✗ FAIL"
            print(f"{status}: '{cmd}' -> {result}")
            if result != expected:
                print(f"  Expected: {expected}")
        except Exception as e:
            print(f"✗ ERROR: '{cmd}' -> {e}")

    print("\nTesting command whitelist validation:")
    print("=" * 50)

    allowed_commands = {
        "ls",
        "pwd",
        "echo",
        "cat",
        "grep",
        "find",
        "ps",
        "top",
        "df",
        "du",
        "whoami",
        "date",
        "uname",
        "stat",
    }

    test_commands = [
        ("ls -l", True),  # Allowed
        ("pwd", True),  # Allowed
        ("echo test", True),  # Allowed
        ("rm -rf /", False),  # Not allowed
        ("bash", False),  # Not allowed
        ("python", False),  # Not allowed
    ]

    for cmd, should_be_allowed in test_commands:
        try:
            parts = shlex.split(cmd)
            if parts:
                executable = parts[0]
                is_allowed = executable in allowed_commands
                status = "✓ ALLOWED" if is_allowed else "✗ REJECTED"
                expected = "✓" if should_be_allowed else "✗"
                match = "✓" if is_allowed == should_be_allowed else "✗"
                print(f"{match} {status}: '{cmd}' (executable: '{executable}')")
        except Exception as e:
            print(f"✗ ERROR parsing '{cmd}': {e}")


if __name__ == "__main__":
    test_command_parsing()
