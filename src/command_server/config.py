"""
Configuration module for Command Server.

This module handles configuration loading from environment variables,
configuration files, and provides default values.
"""

import os
from typing import Dict, Any


def load_config() -> Dict[str, Any]:
    """
    Load configuration from environment variables with fallback to defaults.

    Returns:
        Dictionary containing configuration values
    """
    config = {
        "host": os.environ.get("COMMAND_SERVER_HOST", "127.0.0.1"),
        "port": int(os.environ.get("COMMAND_SERVER_PORT", "666")),
        "max_command_length": int(os.environ.get("MAX_COMMAND_LENGTH", "2048")),
        "max_recv_buffer": int(os.environ.get("MAX_RECV_BUFFER", "4096")),
        "command_timeout": int(os.environ.get("COMMAND_TIMEOUT", "30")),
        "socket_timeout": float(os.environ.get("SOCKET_TIMEOUT", "1.0")),
        "log_file": os.environ.get("LOG_FILE", "server.log"),
        "command_log_file": os.environ.get("COMMAND_LOG_FILE", "commands.log"),
    }

    return config


# Default configuration for easy import
DEFAULT_CONFIG = load_config()
