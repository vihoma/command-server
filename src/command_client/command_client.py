#!/usr/bin/env python3
"""
Command Client

Connects to the server on TCP port 666, sends commands entered by the user
and prints the server's response.  The client handles server downtime,
timeouts, graceful disconnects and presents a Rich based UI.
"""

from __future__ import annotations

import socket
import sys
import threading
import time
from typing import Callable, Optional

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from pynput import keyboard

# --------------------------------------------------------------------------- #
# Global console used by the client UI
# --------------------------------------------------------------------------- #
console = Console()


class ClientStats:
    """Collect simple client‑side counters."""

    def __init__(self) -> None:
        """Initialise all counters to zero."""
        self.sent_commands = 0
        self.received_responses = 0
        self.errors = 0

    def snapshot(self) -> tuple[int, int, int]:
        """
        Return a snapshot of the current counters.

        Returns
        -------
        tuple[int, int, int]
            ``(sent_commands, received_responses, errors)``
        """
        return self.sent_commands, self.received_responses, self.errors


class CommandClient:
    """Encapsulates the socket connection and command handling."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 666,
        timeout: float = 5.0,
    ) -> None:
        """
        Initialise a client ready to connect to the server.

        Parameters
        ----------
        host:
            IP address or hostname of the server (default ``127.0.0.1``).
        port:
            TCP port on which the server is listening (default ``666``).
        timeout:
            Connection timeout in seconds (default ``5.0``).
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None
        self.stats = ClientStats()
        self._recv_thread: Optional[threading.Thread] = None
        self._running_lock = threading.Lock()
        self._running = threading.Event()
        self._running.set()
        self._buffer_lock = threading.Lock()
        self._recv_buffer = ""
        self.output_handler: Optional[Callable[[str], None]] = None

    def connect(self) -> bool:
        """Attempt to connect to the server – returns True on success."""
        try:
            self.sock = socket.create_connection(
                (self.host, self.port), timeout=self.timeout
            )
            self.sock.settimeout(0.5)
            console.log("[green]Connected to server[/]")
            # Start background receiver
            self._recv_thread = threading.Thread(
                target=self._receive_loop, daemon=True
            )
            self._recv_thread.start()
            return True
        except (ConnectionRefusedError, socket.timeout) as exc:
            console.log(f"[red]Cannot connect to server: {exc}[/]")
            return False

    def close(self) -> None:
        """Close the connection and stop the receiver."""
        with self._running_lock:
            self._running.clear()
        if self.sock:
            try:
                with self.sock:
                    self.sock.shutdown(socket.SHUT_RDWR)
            except OSError as exc:
                console.log(f"[red]Error shutting down socket: {exc}[/]")
            finally:
                self.sock.close()  # Ensure the socket is closed
        if self._recv_thread:
            self._recv_thread.join(timeout=2.0)
        console.log("[magenta]Client disconnected[/]")

    def send_command(self, cmd: str) -> None:
        """Send a command line to the server."""
        if not self.sock:
            console.log("[red]Not connected – cannot send[/]")
            self.stats.errors += 1
            return
        try:
            self.sock.sendall(cmd.encode() + b"\n")
            self.stats.sent_commands += 1
        except OSError as exc:
            console.log(f"[red]Send failed: {exc}[/]")
            self.stats.errors += 1
            self.close()

    def _receive_loop(self) -> None:
        """Background thread – receives data from the server."""
        while True:
            with self._running_lock:
                if not (self._running.is_set() and self.sock):
                    break
            try:
                data = self.sock.recv(4096)
                if not data:
                    console.log("[yellow]Server closed connection[/]")
                    break
                with self._buffer_lock:
                    self._recv_buffer += data.decode(errors="replace")
                while "\n" in self._recv_buffer:
                    with self._buffer_lock:
                        line, self._recv_buffer = self._recv_buffer.split("\n", 1)
                    self._handle_line(line)
            except socket.timeout:
                continue
            except OSError as exc:
                console.log(f"[red]Receive error: {exc}[/]")
                self.stats.errors += 1
                break

    def _handle_line(self, line: str) -> None:
        """Process a single line received from the server."""
        with self._buffer_lock:
            if self.output_handler:
                self.output_handler(line + "\n")
            self.stats.received_responses += 1


class TerminalClient:
    """Rich based terminal UI for the client."""

    def __init__(self, client: CommandClient) -> None:
        """
        Initialise the terminal UI.

        Parameters
        ----------
        client:
            The :class:`CommandClient` instance used to communicate with the server.
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
                "Network Terminal Client - Type commands, ESC or Ctrl+C to exit",
                style="bold cyan",
            )
        )
        with Live(self.layout, refresh_per_second=10, screen=True):
            while self.running:
                # Update output panel
                self.layout["output"].update(
                    Panel(self.output_buffer, title="Server Output")
                )
                
                # Update input panel
                input_panel = Panel(
                    Text(f">>> {self.input_buffer}", style="bold green"),
                    title="Input",
                )
                self.layout["input"].update(input_panel)
                
                time.sleep(0.05)
        
        self.client.close()
        try:
            self.key_listener.stop()
        except Exception as exc:
            console.log(f"[red]Error stopping key listener: {exc}[/]")

    def _on_key(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        """Handle key presses for input and commands."""
        try:
            if key == keyboard.Key.enter:
                self._send_command()
            elif key == keyboard.Key.backspace:
                if len(self.input_buffer) > 0:
                    self.input_buffer = self.input_buffer[:-1]
            elif key == keyboard.Key.esc:
                self.running = False
            elif isinstance(key, keyboard.KeyCode):
                try:
                    char = key.char
                    if char:  # Only add printable characters
                        self.input_buffer += char
                except AttributeError:
                    pass  # Ignore non-character keys
            else:
                console.log(f"[yellow]Unsupported key: {key}[/]")
        except Exception as exc:
            console.log(f"[red]Error processing key: {exc}[/]")

    def _send_command(self) -> None:
        """Send the current input buffer to the server."""
        cmd = self.input_buffer.strip()
        if not cmd:
            console.log("[yellow]Command cannot be empty[/]")
            return

        if cmd.lower() in {"exit", "quit"}:
            self.running = False
            return

        if len(cmd) > 1024:  # Arbitrary limit to prevent too long commands
            console.log("[yellow]Command too long[/]")
            return

        self.client.send_command(cmd)
        self.input_buffer = ""


def main() -> None:
    """Entry point for the command-line client."""
    client = CommandClient()
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
