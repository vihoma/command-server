#!/usr/bin/env python3
"""Command client.

Provides a TCP client that talks to a command‑execution server and a
Rich‑based terminal UI for interactive use.
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
from typing import Callable, Optional

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from pynput import keyboard

# --------------------------------------------------------------------------- #
# Configuration constants
# --------------------------------------------------------------------------- #
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 666
DEFAULT_TIMEOUT = 5.0
MAX_CMD_LENGTH = 2048
UI_REFRESH_RATE = 10  # Hz

# --------------------------------------------------------------------------- #
# Global console used by the client UI
# --------------------------------------------------------------------------- #
console = Console()


class ClientStats:
    """Thread‑safe container for simple client counters.

    The counters are protected by a lock to make updates safe when accessed
    from multiple threads (the main UI thread and the receiver thread).
    """

    __slots__ = ("sent_commands", "received_responses", "errors", "_lock")

    def __init__(self) -> None:
        """Initialise all counters to zero."""
        self.sent_commands: int = 0
        self.received_responses: int = 0
        self.errors: int = 0
        self._lock = threading.Lock()

    def inc_sent(self) -> None:
        """Increment the sent‑command counter."""
        with self._lock:
            self.sent_commands += 1

    def inc_received(self) -> None:
        """Increment the received‑response counter."""
        with self._lock:
            self.received_responses += 1

    def inc_error(self) -> None:
        """Increment the error counter."""
        with self._lock:
            self.errors += 1

    def snapshot(self) -> tuple[int, int, int]:
        """Return a snapshot of the current counters."""
        with self._lock:
            return self.sent_commands, self.received_responses, self.errors


class CommandClient:
    """Encapsulates the socket connection and command handling.

    The client runs a background thread that reads from the socket and
    forwards complete lines to a user‑provided ``output_handler``.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Create a client ready to connect to the server.

        Parameters
        ----------
        host : str
            IP address or hostname of the server.
        port : int
            TCP port on which the server is listening.
        timeout : float
            Connection timeout in seconds.
        """
        self._host = host
        self._port = port
        self._timeout = timeout

        self.sock: Optional[socket.socket] = None
        self.stats = ClientStats()
        self._recv_thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._running.set()
        self._recv_lock = threading.Lock()
        self._recv_buffer = ""
        self.output_handler: Optional[Callable[[str], None]] = None

    def connect(self) -> bool:
        """Attempt to open a TCP connection to the server.

        Returns
        -------
        bool
            ``True`` if the connection was established, ``False`` otherwise.
        """
        try:
            self.sock = socket.create_connection(
                (self._host, self._port), timeout=self._timeout
            )
            # TODO: wrap with SSL/TLS for production use
            # import ssl
            # context = ssl.create_default_context()
            # self.sock = context.wrap_socket(self.sock, server_hostname=self._host)

            # Use a blocking socket; the receiver thread will block on ``recv``.
            self.sock.settimeout(None)

            console.log("[green]Connected to server[/]")
            # Start background receiver
            self._recv_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._recv_thread.start()
            return True
        except (ConnectionRefusedError, socket.timeout) as exc:
            console.log(f"[red]Cannot connect to server: {exc}[/]")
            return False
        except OSError as exc:
            console.log(f"[red]Socket error during connect: {exc}[/]")
            return False

    def close(self) -> None:
        """Close the connection and stop the receiver thread."""
        self._running.clear()
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()
            except OSError as exc:
                console.log(f"[red]Error shutting down socket: {exc}[/]")
        if self._recv_thread:
            self._recv_thread.join(timeout=2.0)
        console.log("[magenta]Client disconnected[/]")

    def send_command(self, cmd: str) -> None:
        """Send a command line to the server.

        Parameters
        ----------
        cmd : str
            Command string without a trailing newline.
        """
        if not self.sock:
            console.log("[red]Not connected – cannot send[/]")
            self.stats.inc_error()
            return
        try:
            self.sock.sendall(f"{cmd}\n".encode())
            self.stats.inc_sent()
        except OSError as exc:
            console.log(f"[red]Send failed: {exc}[/]")
            self.stats.inc_error()
            self.close()

    def _receive_loop(self) -> None:
        """Background thread – receives data from the server."""
        while self._running.is_set() and self.sock:
            try:
                data = self.sock.recv(4096)  # Blocking read
                if not data:
                    console.log("[yellow]Server closed connection[/]")
                    break
                with self._recv_lock:
                    self._recv_buffer += data.decode(errors="replace")
                while "\n" in self._recv_buffer:
                    with self._recv_lock:
                        line, self._recv_buffer = self._recv_buffer.split("\n", 1)
                    self._handle_line(line)
            except OSError as exc:
                console.log(f"[red]Receive error: {exc}[/]")
                self.stats.inc_error()
                break

    def _handle_line(self, line: str) -> None:
        """Process a single line received from the server.

        The line is treated as plain text to avoid Rich markup injection.
        """
        self.stats.inc_received()
        if self.output_handler:
            # Ensure Rich does not interpret markup
            self.output_handler(f"{line}\n")


class TerminalClient:
    """Rich‑based terminal UI for the client."""

    def __init__(self, client: CommandClient) -> None:
        """Create the UI wrapper.

        Parameters
        ----------
        client : CommandClient
            The networking client used to communicate with the server.
        """
        self.client = client
        self.input_buffer = ""
        self.output_buffer = Text()
        self.layout = Layout()
        self.layout.split(
            Layout(name="output", ratio=8),
            Layout(name="input", size=3),
        )
        self.key_listener = keyboard.Listener(on_press=self._on_key)
        self.key_listener.start()
        self.running = True

    def run(self) -> None:
        """Main terminal loop."""
        console.print(
            Panel(
                "Network Terminal Client – type commands, ESC or Ctrl‑C to exit",
                style="bold cyan",
            )
        )
        # Let Live manage the refresh rate; no explicit sleep required.
        with Live(self.layout, refresh_per_second=UI_REFRESH_RATE, screen=True):
            while self.running:
                # Update output panel
                self.layout["output"].update(
                    Panel(self.output_buffer, title="Server Output")
                )
                # Update input panel
                self.layout["input"].update(
                    Panel(
                        Text(f">>> {self.input_buffer}", style="bold green"),
                        title="Input",
                    )
                )
        # Cleanup after loop ends
        self.client.close()
        self.key_listener.stop()

    def _on_key(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        """Handle key presses for input and commands."""
        if key is None:
            return

        try:
            if key == keyboard.Key.enter:
                self._send_command()
            elif key == keyboard.Key.backspace:
                self.input_buffer = self.input_buffer[:-1]
            elif key == keyboard.Key.esc:
                self.running = False
            elif key == keyboard.Key.space:
                self.input_buffer += " "
            elif isinstance(key, keyboard.KeyCode):
                char = key.char
                if char and char.isprintable():
                    self.input_buffer += char
            else:
                console.log(f"[yellow]Unsupported key: {key}[/]")
        except Exception as exc:
            console.log(f"[red]Error processing key: {exc}[/]")
            raise

    def _send_command(self) -> None:
        """Send the current input buffer to the server."""
        cmd = self.input_buffer.strip()
        if not cmd:
            console.log("[yellow]Command cannot be empty[/]")
            return

        if cmd.lower() in {"exit", "quit"}:
            self.running = False
            return

        if len(cmd) > MAX_CMD_LENGTH:
            console.log("[yellow]Command too long[/]")
            return

        self.client.send_command(cmd)
        self.input_buffer = ""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rich terminal client for the command server."
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="Server hostname or IP")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="Server TCP port"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="Connection timeout in seconds",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for the command‑line client."""
    args = _parse_args()
    client = CommandClient(host=args.host, port=args.port, timeout=args.timeout)
    if not client.connect():
        sys.exit(1)

    terminal = TerminalClient(client)

    # Set up output handling
    def handle_output(line: str) -> None:
        terminal.output_buffer.append(line)

    client.output_handler = handle_output
    terminal.run()


if __name__ == "__main__":
    main()
