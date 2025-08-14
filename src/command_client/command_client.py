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
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

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
        self._running = threading.Event()
        self._running.set()
        self._recv_buffer = ""

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
        self._running.clear()
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self.sock.close()
            except OSError:
                pass
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
        while self._running.is_set() and self.sock:
            try:
                data = self.sock.recv(4096)
                if not data:
                    console.log("[yellow]Server closed connection[/]")
                    self._running.clear()
                    break
                self._recv_buffer += data.decode(errors="replace")
                while "\n" in self._recv_buffer:
                    line, self._recv_buffer = self._recv_buffer.split("\n", 1)
                    self._handle_line(line)
            except socket.timeout:
                continue
            except OSError as exc:
                console.log(f"[red]Receive error: {exc}[/]")
                self.stats.errors += 1
                self._running.clear()
                break

    def _handle_line(self, line: str) -> None:
        """Process a single line received from the server."""
        if line.startswith("STATS:"):
            console.print(Panel(line[6:], title="Server Statistics"))
        elif line.startswith("STDOUT:"):
            console.print(Panel(line[7:], title="STDOUT"))
        elif line.startswith("STDERR:"):
            console.print(Panel(line[7:], title="STDERR", style="red"))
        else:
            console.print(Panel(line, title="Message"))
        self.stats.received_responses += 1


class ClientTUI:
    """Rich based UI – reads user input and forwards to the server."""

    EXIT_CMDS = {"quit", "exit"}

    def __init__(self, client: CommandClient) -> None:
        """
        Initialise the TUI and start a key‑listener for future shortcuts.

        Parameters
        ----------
        client:
            The :class:`CommandClient` instance used to communicate with the server.
        """
        self.client = client
        self._key_listener = keyboard.Listener(on_press=self._on_key)
        self._key_listener.start()

    def run(self) -> None:
        """Main input loop."""
        console.print(
            Panel(
                "Command Client – type commands, 'quit' or 'exit' to exit",
                style="bold cyan",
            )
        )
        while True:
            try:
                cmd = Prompt.ask("[bold green]>>>[/]")
            except (KeyboardInterrupt, EOFError):
                console.log("[red]User interrupt – exiting[/]")
                break

            if cmd.strip().lower() in self.EXIT_CMDS:
                console.log("[magenta]Exiting client per user request[/]")
                break

            self.client.send_command(cmd)

        self.client.close()
        self._key_listener.stop()

    def _on_key(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        """Optional: future non‑blocking shortcuts can be added here."""
        pass  # currently no shortcuts required for the client


def main() -> None:
    """Entry point for the command‑line client."""
    client = CommandClient()
    if not client.connect():
        sys.exit(1)
    ui = ClientTUI(client)
    ui.run()


if __name__ == "__main__":
    main()
