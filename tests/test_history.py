#!/usr/bin/env python3
"""Test script for command history functionality."""

import json
import tempfile
from pathlib import Path
from src.command_client.command_client import TerminalClient


# Create a minimal mock client
class MockClient:
    def __init__(self):
        pass


def test_history_file_path():
    """Test that history file path is platform agnostic."""
    client = MockClient()
    terminal = TerminalClient(client)

    history_path = terminal._get_history_file_path()
    home_dir = Path.home()

    print(f"Home directory: {home_dir}")
    print(f"History file path: {history_path}")
    print(f"Parent directory matches home: {history_path.parent == home_dir}")
    print(f"Filename correct: {history_path.name == '.command_server_history'}")


def test_load_save_history():
    """Test loading and saving history."""
    # Create a temporary history file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        test_history = ["command1", "command2", "command3"]
        json.dump(test_history, tmp)
        tmp_path = Path(tmp.name)

    try:
        # Test loading
        client = MockClient()
        terminal = TerminalClient(client)

        # Override the history file path for testing
        terminal._get_history_file_path = lambda: tmp_path

        # Load history
        terminal._load_history()
        print(f"Loaded history: {terminal.command_history}")
        print(f"History matches test data: {terminal.command_history == test_history}")

        # Test saving
        terminal.command_history.append("command4")
        terminal._save_history()

        # Verify saved content
        with open(tmp_path, "r") as f:
            saved_history = json.load(f)
        print(f"Saved history: {saved_history}")
        print(f"Save successful: {saved_history == terminal.command_history}")

    finally:
        # Clean up
        if tmp_path.exists():
            tmp_path.unlink()


if __name__ == "__main__":
    print("Testing history file path...")
    test_history_file_path()
    print("\nTesting load/save functionality...")
    test_load_save_history()
