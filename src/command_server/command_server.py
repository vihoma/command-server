#!/usr/bin/env python3
"""
Command Server

Listens on TCP port (configurable), executes received commands in the system default
shell and returns the command output.  The server prints a Rich based TUI,
collects statistics and can be stopped with Ctrl‑C, **ESC**, **Q** or
displays statistics with the **S** key.
"""

from __future__ import annotations

import logging
import os
import shlex
import socket
import subprocess
import threading
import time
from typing import Any, Dict, List, Tuple

from pynput import keyboard
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


# Default configuration
DEFAULT_CONFIG = {
    "host": "127.0.0.1",
    "port": 666,
    "max_command_length": 2048,
    "max_recv_buffer": 4096,
    "command_timeout": 30,
    "socket_timeout": 1.0,
    "log_file": "server.log",
    "command_log_file": "commands.log",
}

# Socket constants
SOCKET_RECV_CHUNK_SIZE = 4096
SOCKET_TIMEOUT = DEFAULT_CONFIG["socket_timeout"]
SOCKET_CONNECTION_TIMEOUT = 0.5

# Threading constants
THREAD_JOIN_TIMEOUT = 2.0

# Command execution constants
COMMAND_TIMEOUT = DEFAULT_CONFIG["command_timeout"]

# --------------------------------------------------------------------------- #
# Global console used by both the server and the TUI
# --------------------------------------------------------------------------- #
console = Console()

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
    handlers=[
        logging.FileHandler(DEFAULT_CONFIG["log_file"], encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Performance monitoring variables
start_time = time.time()
last_monitor_time = start_time

# Command log file
command_log_file = DEFAULT_CONFIG["command_log_file"]

# Configuration constants
MAX_COMMAND_LENGTH = DEFAULT_CONFIG["max_command_length"]
MAX_RECV_BUFFER = DEFAULT_CONFIG["max_recv_buffer"]


class ServerStats:
    """Collect simple runtime statistics."""

    def __init__(self) -> None:
        """Initialize all counters to zero and create a lock for thread safety."""
        self.total_connections: int = 0
        self.total_commands: int = 0
        self.total_errors: int = 0
        self._lock = threading.Lock()

    def incr_connections(self) -> None:
        """Increment the total number of client connections."""
        with self._lock:
            self.total_connections += 1

    def incr_commands(self) -> None:
        """Increment the total number of commands executed."""
        with self._lock:
            self.total_commands += 1

    def incr_errors(self) -> None:
        """Increment the total number of errors encountered."""
        with self._lock:
            self.total_errors += 1

    def snapshot(self) -> Tuple[int, int, int]:
        """Return a thread‑safe snapshot of the three counters."""
        with self._lock:
            return self.total_connections, self.total_commands, self.total_errors


class CommandHandler(threading.Thread):
    """
    One thread per client connection.

    Reads lines terminated by ``\n`` from the client socket, executes them,
    and sends back the output (or an error message).  The special command
    ``stats`` (case‑insensitive) returns the current server statistics.
    """

    def __init__(
        self,
        conn: socket.socket,
        addr: Tuple[str, int],
        stats: ServerStats,
        shutdown_event: threading.Event,
    ) -> None:
        """
        Initialise a handler for a single client connection.

        Parameters
        ----------
        conn:
            The socket belonging to the connected client.
        addr:
            A tuple ``(host, port)`` identifying the client.
        stats:
            Shared :class:`ServerStats` instance for recording statistics.
        shutdown_event:
            Event used to signal a server‑wide shutdown.
        """
        super().__init__(daemon=True)
        self.conn = conn
        self.addr = addr
        self.stats = stats
        self.shutdown_event = shutdown_event
        self._running = True

    def run(self) -> None:
        """Main loop for handling client requests until disconnection or shutdown."""
        console.log(f"[green]Client connected[/] {self.addr}")
        self.stats.incr_connections()
        try:
            with self.conn:
                while self._running and not self.shutdown_event.is_set():
                    data = self._recv_line()
                    if data == "":
                        # Empty line -> client closed connection
                        break
                    command = data.strip()
                    if not command:
                        continue

                    # Validate command length
                    if len(command) > MAX_COMMAND_LENGTH:
                        self.conn.sendall(
                            f"ERROR: Command too long (max {MAX_COMMAND_LENGTH} characters)\n".encode()
                        )
                        continue

                    if command.lower() == "stats":
                        self._send_stats()
                        continue

                    self.stats.incr_commands()
                    output, error = self._exec_shell(command)
                    self._send_output(output, error)
        except (socket.error, OSError, UnicodeDecodeError) as exc:
            console.log(f"[red]Handler error[/] {self.addr}: {exc}")
            self.stats.incr_errors()
        except Exception as exc:  # pragma: no cover – unexpected errors
            console.log(f"[red]Unexpected error[/] {self.addr}: {exc}")
            logger.exception("Unexpected error in command handler")
            self.stats.incr_errors()
        finally:
            console.log(f"[yellow]Client disconnected[/] {self.addr}")

    def _recv_line(self) -> str:
        """Read a line terminated by ``\n`` from the socket."""
        chunks: List[bytes] = []
        total_bytes = 0

        while True:
            try:
                chunk = self.conn.recv(SOCKET_RECV_CHUNK_SIZE)
                if not chunk:
                    return ""

                # Check buffer size limit
                total_bytes += len(chunk)
                if total_bytes > MAX_RECV_BUFFER:
                    return ""  # Close connection on buffer overflow

                chunks.append(chunk)
                if b"\n" in chunk:
                    break
            except socket.timeout:
                continue
        data = b"".join(chunks).decode(errors="replace")
        line, *_ = data.split("\n", 1)
        return line + "\n"

    def _exec_shell(self, cmd: str) -> Tuple[str, str]:
        """
        Execute *cmd* in the system default shell.

        Returns a tuple ``(stdout, stderr)``.  Errors from the subprocess
        are caught and reported as ``stderr`` while also updating the error
        counter.
        """
        # Parse command into executable and arguments
        try:
            parts = shlex.split(cmd)
        except ValueError:
            return "", "ERROR: Invalid command syntax"

        if not parts:
            return "", "ERROR: Empty command"

        executable = parts[0]
        args = parts[1:] if len(parts) > 1 else []

        # Validate executable against whitelist
        allowed_commands = {
            "ls",
            "lsd",
            "eza",
            "tree",
            "cd",
            "pwd",
            "echo",
            "cat",
            "grep",
            "rg",
            "ug",
            "find",
            "ps",
            "top",
            "df",
            "du",
            "dust",
            "free",
            "whoami",
            "date",
            "uname",
            "stat",
        }

        if executable not in allowed_commands:
            return "", f"ERROR: Command '{executable}' not allowed"

        try:
            # Execute safely without shell=True
            completed = subprocess.run(
                [executable] + args,
                shell=False,
                capture_output=True,
                text=True,
                check=True,
                timeout=COMMAND_TIMEOUT,
            )
            return completed.stdout, completed.stderr
        except subprocess.TimeoutExpired:
            self.stats.incr_errors()
            return "", "ERROR: Command execution timed out"
        except subprocess.CalledProcessError as exc:
            self.stats.incr_errors()
            return "", f"ERROR: Command failed with exit code {exc.returncode}"
        except FileNotFoundError:
            self.stats.incr_errors()
            return "", f"ERROR: Command '{executable}' not found"
        except subprocess.SubprocessError as exc:
            self.stats.incr_errors()
            logger.error(f"Subprocess error: {exc}")
            return "", "ERROR: Command execution failed"
        except Exception as exc:
            self.stats.incr_errors()
            logger.exception("Unexpected error during command execution")
            return "", "ERROR: Internal server error"

    def _send_output(self, out: str, err: str) -> None:
        """Send command output (or error) back to the client.

        This method sends the output or error of a command execution back
        to the client. It handles any errors that occur during transmission.
        """
        if err:
            payload = f"STDERR:\n{err}"
        else:
            payload = f"STDOUT:\n{out}"
        try:
            self.conn.sendall(payload.encode() + b"\n")
        except OSError as exc:
            logger.error(f"Error sending output to client {self.addr}: {exc}")
            self._running = False

    def _send_stats(self) -> None:
        """Send a nicely formatted statistics string to the client.

        This method sends server statistics to the client in response to
        the "stats" command. It handles any errors that occur during transmission.
        """
        conns, cmds, errs = self.stats.snapshot()
        stats_msg = f"Connections: {conns}\nCommands executed: {cmds}\nErrors: {errs}"
        try:
            self.conn.sendall(b"STATS:\n" + stats_msg.encode() + b"\n")
        except OSError as exc:
            logger.error(f"Error sending statistics to client {self.addr}: {exc}")
            self._running = False


class ServerTUI:
    """Rich based textual UI for the server."""

    def __init__(
        self, server: "CommandServer", shutdown_event: threading.Event
    ) -> None:
        """
        Initialise the TUI and start a non‑blocking key listener.

        Parameters
        ----------
        server:
            The :class:`CommandServer` instance to query for statistics.
        shutdown_event:
            Event used to signal a server‑wide shutdown when a quit key is pressed.
        """
        self.server = server
        self.shutdown_event = shutdown_event
        self.listener = keyboard.Listener(on_press=self._on_key)
        self.listener.start()
        console.print(
            Panel(
                f"Command Server started on port {self.server.port}", style="bold cyan"
            )
        )

    def _on_key(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        """Handle non‑blocking key presses for shutdown and statistics display.

        This method processes key presses from the user to trigger actions
        like shutting down the server or displaying statistics.
        """
        if key is None:
            return  # Ignore None keys

        try:
            if isinstance(key, keyboard.Key):
                # Special keys
                if key == keyboard.Key.esc:
                    logger.info("ESC pressed – shutting down")
                    self.shutdown_event.set()
            elif isinstance(key, keyboard.KeyCode):
                if key.char == "Q":
                    logger.info("Q pressed – shutting down")
                    self.shutdown_event.set()
                elif key.char == "S":
                    self._print_stats()
                # Add Ctrl+C handling for Windows
                elif key.char == "\x03":  # Ctrl+C character code
                    logger.info("Ctrl+C pressed – shutting down")
                    self.shutdown_event.set()
        except AttributeError:
            pass  # Non‑character key, ignore

    def _print_stats(self) -> None:
        """Print the server statistics to the console in a table format.

        This method displays the current server statistics in a nicely formatted
        table on the console.
        """
        conns, cmds, errs = self.server.stats.snapshot()
        table = Table(title="Server Statistics", show_header=False)
        table.add_row("Connections", str(conns))
        table.add_row("Commands executed", str(cmds))
        table.add_row("Errors", str(errs))
        console.print(table)


class CommandServer:
    """Main server object – accepts connections and spawns handlers."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        config: Dict[str, Any] | None = None,
    ) -> None:
        """
        Initialise the server with the given host and port.

        Parameters
        ----------
        host:
            Interface address to bind to. Defaults to config value.
        port:
            TCP port on which the server listens. Defaults to config value.
        config:
            Configuration dictionary. Uses default config if not provided.
        """
        # Use provided config or load from environment variables
        if config is not None:
            self.config = config
        else:
            # Load configuration from environment variables with fallback to defaults
            self.config = {
                "host": os.environ.get("COMMAND_SERVER_HOST", DEFAULT_CONFIG["host"]),
                "port": int(
                    os.environ.get("COMMAND_SERVER_PORT", str(DEFAULT_CONFIG["port"]))
                ),
                "max_command_length": int(
                    os.environ.get(
                        "MAX_COMMAND_LENGTH", str(DEFAULT_CONFIG["max_command_length"])
                    )
                ),
                "max_recv_buffer": int(
                    os.environ.get(
                        "MAX_RECV_BUFFER", str(DEFAULT_CONFIG["max_recv_buffer"])
                    )
                ),
                "command_timeout": int(
                    os.environ.get(
                        "COMMAND_TIMEOUT", str(DEFAULT_CONFIG["command_timeout"])
                    )
                ),
                "socket_timeout": float(
                    os.environ.get(
                        "SOCKET_TIMEOUT", str(DEFAULT_CONFIG["socket_timeout"])
                    )
                ),
                "log_file": os.environ.get("LOG_FILE", DEFAULT_CONFIG["log_file"]),
                "command_log_file": os.environ.get(
                    "COMMAND_LOG_FILE", DEFAULT_CONFIG["command_log_file"]
                ),
            }

        self.host = host or self.config["host"]
        self.port = port or self.config["port"]
        self.stats = ServerStats()
        self.shutdown_event = threading.Event()
        self._client_threads: List[CommandHandler] = []
        self._socket: socket.socket | None = None

    def start(self) -> None:
        """Create a listening socket, launch the TUI, and accept client connections."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self.host, self.port))
        self._socket.listen()
        self._socket.settimeout(SOCKET_TIMEOUT)  # allow periodic shutdown checks

        # Launch TUI (starts key listener)
        ServerTUI(self, self.shutdown_event)

        console.log(f"[cyan]Listening on {self.host}:{self.port}[/]")
        try:
            while not self.shutdown_event.is_set():
                try:
                    conn, addr = self._socket.accept()
                except socket.timeout:
                    continue
                conn.settimeout(SOCKET_CONNECTION_TIMEOUT)
                handler = CommandHandler(conn, addr, self.stats, self.shutdown_event)
                handler.start()
                self._client_threads.append(handler)
        except KeyboardInterrupt:
            console.log("[red]KeyboardInterrupt – shutting down[/]")
            self.shutdown_event.set()
        finally:
            self.stop()

    def stop(self) -> None:
        """Close listening socket, wait for client threads and clean up resources."""
        console.log("[magenta]Shutting down server…[/]")
        self.shutdown_event.set()
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
        # Clean up finished threads to prevent memory leaks
        active_threads = []
        for th in self._client_threads:
            if th.is_alive():
                th.join(timeout=THREAD_JOIN_TIMEOUT)
                if th.is_alive():
                    active_threads.append(th)
            # Threads that are no longer alive are automatically garbage collected

        self._client_threads = active_threads
        console.log("[green]Server stopped cleanly[/]")


def main() -> None:
    """Entry point for running the command server as a script."""
    server = CommandServer()
    server.start()


if __name__ == "__main__":
    main()
