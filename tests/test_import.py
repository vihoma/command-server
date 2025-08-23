#!/usr/bin/env python3
"""Test script to verify imports work correctly."""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Try to import the module
try:
    from src.command_server.command_server import CommandHandler, ServerStats

    print("✅ Import successful!")

    # Test basic functionality
    import threading

    stats = ServerStats()
    shutdown_event = threading.Event()
    handler = CommandHandler(None, ("127.0.0.1", 12345), stats, shutdown_event)

    # Test FileNotFoundError
    stdout, stderr = handler._exec_shell("nonexistentls")
    print(f"FileNotFoundError test result: {stderr}")

    # Test existing command
    stdout2, stderr2 = handler._exec_shell("echo hello")
    print(f"Existing command test result: {stdout2.strip()}")

    print("✅ All tests completed successfully!")

except ImportError as e:
    print(f"❌ Import failed: {e}")
    print(f"Current Python path: {sys.path}")

except Exception as e:
    print(f"❌ Test failed: {e}")
    import traceback

    traceback.print_exc()
