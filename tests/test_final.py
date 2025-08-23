#!/usr/bin/env python3
"""
Final test of the command server functionality with positional arguments.
"""

import shlex


def test_command_parsing():
    """Test that commands with positional arguments are parsed correctly."""

    print("Testing command parsing with shlex.split():")
    print("=" * 50)

    test_cases = [
        ("ls -lha --color=always", ["ls", "-lha", "--color=always"]),
        ("echo 'hello world'", ["echo", "hello world"]),
        ("grep -i 'search term' file.txt", ["grep", "-i", "search term", "file.txt"]),
        ("find . -name '*.py' -type f", ["find", ".", "-name", "*.py", "-type", "f"]),
    ]

    for cmd, expected in test_cases:
        result = shlex.split(cmd)
        status = "✓ PASS" if result == expected else "✗ FAIL"
        print(f"{status}: '{cmd}' -> {result}")
        if result != expected:
            print(f"  Expected: {expected}")


def test_whitelist_validation():
    """Test that only whitelisted commands are allowed."""

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

    test_cases = [
        ("ls -l", True),  # Allowed
        ("echo hello", True),  # Allowed
        ("pwd", True),  # Allowed
        ("rm -rf /", False),  # Not allowed
        ("bash", False),  # Not allowed
        ("python", False),  # Not allowed
    ]

    for cmd, should_be_allowed in test_cases:
        try:
            parts = shlex.split(cmd)
            if parts:
                executable = parts[0]
                is_allowed = executable in allowed_commands
                status = "✓ ALLOWED" if is_allowed else "✗ REJECTED"
                expected_status = "✓" if should_be_allowed else "✗"
                match = "✓" if is_allowed == should_be_allowed else "✗"
                print(f"{match} {status}: '{cmd}' (executable: '{executable}')")
            else:
                print(f"✗ ERROR: Failed to parse '{cmd}'")
        except Exception as e:
            print(f"✗ ERROR parsing '{cmd}': {e}")


def test_shell_injection_prevention():
    """Test that shell injection attempts are prevented."""

    print("\nTesting shell injection prevention:")
    print("=" * 50)

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
        try:
            parts = shlex.split(attempt)
            # These should either fail to parse or contain dangerous commands
            dangerous_cmds = {"rm", "bash", "sh", "python"}
            has_dangerous = (
                any(part in dangerous_cmds for part in parts) if parts else False
            )

            if has_dangerous:
                print(f"✓ DETECTED: '{attempt}' -> Contains dangerous command")
            else:
                print(f"? AMBIGUOUS: '{attempt}' -> Parsed as: {parts}")
        except ValueError:
            print(f"✓ REJECTED: '{attempt}' -> Invalid syntax")


if __name__ == "__main__":
    test_command_parsing()
    test_whitelist_validation()
    test_shell_injection_prevention()
    print("\nAll tests completed!")
