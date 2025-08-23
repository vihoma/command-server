#!/usr/bin/env python3
"""Test script to verify FileNotFoundError handling."""

import sys
import os

# Add the src directory to the Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from command_server.command_server import CommandHandler, ServerStats
import threading


def test_filenotfound_error():
    """Test that FileNotFoundError is properly handled."""

    # Create a mock server stats object
    stats = ServerStats()
    shutdown_event = threading.Event()

    # Create a handler instance
    handler = CommandHandler(None, ("127.0.0.1", 12345), stats, shutdown_event)

    # Test with a whitelisted but non-existent command
    stdout, stderr = handler._exec_shell("nonexistentls")

    # Check if the error message is correct
    expected_error = "ERROR: Command 'nonexistentls' not found"

    assert stderr == expected_error, f"Expected: {expected_error}, Got: {stderr}"
    assert stdout == "", f"Expected empty stdout, Got: {stdout}"

    print("✅ FileNotFoundError handling works correctly!")
    return True


def test_existing_command_still_works():
    """Test that existing commands still work after FileNotFoundError implementation."""

    # Create a mock server stats object
    stats = ServerStats()
    shutdown_event = threading.Event()

    # Create a handler instance
    handler = CommandHandler(None, ("127.0.0.1", 12345), stats, shutdown_event)

    # Test with an existing command
    stdout, stderr = handler._exec_shell("echo hello")

    assert "hello" in stdout, f"Expected 'hello' in stdout, Got: {stdout}"
    assert stderr == "", f"Expected empty stderr, Got: {stderr}"

    print("✅ Existing command still works correctly!")
    return True


if __name__ == "__main__":
    try:
        success1 = test_filenotfound_error()
        success2 = test_existing_command_still_works()

        if success1 and success2:
            print("\n🎉 All FileNotFoundError tests passed!")
            sys.exit(0)
        else:
            print("\n💥 Some tests failed!")
            sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        sys.exit(1)
