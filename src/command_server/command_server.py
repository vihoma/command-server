#!/usr/bin/env python3
"""
Command Server

Listens on TCP port 666, executes received commands in the system default
shell and returns the command output.  The server prints a Rich based TUI,
collects statistics and can be stopped with Ctrl‑C, **ESC**, **Q** or
displays statistics with the **S** key.
"""

from __future__ import annotations

import socket
import threading
import subprocess
import signal
from typing import List, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pynput import keyboard

# --------------------------------------------------------------------------- #
# Global console used by both the server and the TUI
# --------------------------------------------------------------------------- #
console = Console()


class ServerStats:
    """Collect simple runtime statistics."""

    def __init__(self) -> None:
        self.total_connections: int = 0
        self.total_commands: int = 0
        self.total_errors: int = 0
        self._lock = threading.Lock()

    def incr_connections(self) -> None:
        with self._lock:
            self.total_connections += 1

    def incr_commands(self) -> None:
        with self._lock:
            self.total_commands += 1

    def incr_errors(self) -> None:
        with self._lock:
            self.total_errors += 1

    def snapshot(self) -> Tuple[int, int, int]:
        """Return a thread‑safe snapshot of the counters."""
        with self._lock:
            return self.total_connections, self.total_commands, self.total_errors


class CommandHandler(threading.Thread):
    """
    One thread per client connection.

    Reads lines terminated by ``\\n`` from the client socket, executes them,
    and sends back the output (or an error message).  The special command
    ``stats`` (case‑insensitive) returns the current server statistics.
    """

    def __init__(self, conn: socket.socket,
                 addr: Tuple[str, int],
                 stats: ServerStats,
                 shutdown_event: threading.Event) -> None:
        super().__init__(daemon=True)
        self.conn = conn
        self.addr = addr
        self.stats = stats
        self.shutdown_event = shutdown_event
        self._running = True

    def run(self) -> None:
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
                    if command.lower() == "stats":
                        self._send_stats()
                        continue
                    self.stats.incr_commands()
                    output, error = self._exec_shell(command)
                    self._send_output(output, error)
        except Exception as exc:  # pragma: no cover – unexpected errors
            console.log(f"[red]Handler error[/] {self.addr}: {exc}")
            self.stats.incr_errors()
        finally:
            console.log(f"[yellow]Client disconnected[/] {self.addr}")

    def _recv_line(self) -> str:
        """Read a line terminated by ``\\n`` from the socket."""
        chunks: List[bytes] = []
        while True:
            try:
                chunk = self.conn.recv(4096)
                if not chunk:
                    return ""
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

        Returns a tuple ``(stdout, stderr)``.
        """
        try:
            completed = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return completed.stdout, completed.stderr
        except subprocess.SubprocessError as exc:
            self.stats.incr_errors()
            return "", f"Subprocess error: {exc}"

    def _send_output(self, out: str, err: str) -> None:
        """Send command output (or error) back to the client."""
        if err:
            payload = f"STDERR:\\n{err}"
        else:
            payload = f"STDOUT:\\n{out}"
        try:
            self.conn.sendall(payload.encode() + b"\n")
        except OSError:
            self._running = False

    def _send_stats(self) -> None:
        """Send a nicely formatted statistics string to the client."""
        conns, cmds, errs = self.stats.snapshot()
        stats_msg = (
            f"Connections: {conns}\\n"
            f"Commands executed: {cmds}\\n"
            f"Errors: {errs}"
        )
        try:
            self.conn.sendall(b"STATS:\\n" + stats_msg.encode() + b"\n")
        except OSError:
            self._running = False


class ServerTUI:
    """Rich based textual UI for the server."""

    def __init__(self,
                 server: "CommandServer",
                 shutdown_event: threading.Event) -> None:
        self.server = server
        self.shutdown_event = shutdown_event
        self.listener = keyboard.Listener(on_press=self._on_key)
        self.listener.start()
        console.print(Panel("Command Server started on port 666", style="bold cyan"))

    def _on_key(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        """Handle non‑blocking key presses."""
        try:
            if isinstance(key, keyboard.Key):
                # Special keys
                if key == keyboard.Key.esc:
                    console.log("[red]ESC pressed – shutting down[/]")
                    self.shutdown_event.set()
            elif isinstance(key, keyboard.KeyCode):
                if key.char == "Q":
                    console.log("[red]Q pressed – shutting down[/]")
                    self.shutdown_event.set()
                elif key.char == "S":
                    self._print_stats()
        except AttributeError:
            pass  # Non‑character key, ignore

    def _print_stats(self) -> None:
        """Print the server statistics to the console."""
        conns, cmds, errs = self.server.stats.snapshot()
        table = Table(title="Server Statistics", show_header=False)
        table.add_row("Connections", str(conns))
        table.add_row("Commands executed", str(cmds))
        table.add_row("Errors", str(errs))
        console.print(table)


class CommandServer:
    """Main server object – accepts connections and spawns handlers."""

    def __init__(self, host: str = "0.0.0.0", port: int = 666) -> None:
        self.host = host
        self.port = port
        self.stats = ServerStats()
        self.shutdown_event = threading.Event()
        self._client_threads: List[CommandHandler] = []
        self._socket: socket.socket | None = None

    def start(self) -> None:
        """Create listening socket and run the accept loop."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self.host, self.port))
        self._socket.listen()
        self._socket.settimeout(1.0)  # allow periodic shutdown checks

        # Launch TUI (starts key listener)
        ServerTUI(self, self.shutdown_event)

        # Register signal handler for Ctrl‑C
        signal.signal(signal.SIGINT, self._handle_sigint)

        console.log(f"[cyan]Listening on {self.host}:{self.port}[/]")
        try:
            while not self.shutdown_event.is_set():
                try:
                    conn, addr = self._socket.accept()
                except socket.timeout:
                    continue
                conn.settimeout(0.5)
                handler = CommandHandler(conn, addr, self.stats,
                                         self.shutdown_event)
                handler.start()
                self._client_threads.append(handler)
        finally:
            self.stop()

    def _handle_sigint(self, signum: int, frame) -> None:  # pragma: no cover
        """Graceful shutdown on Ctrl‑C."""
        console.log("[red]KeyboardInterrupt – shutting down[/]")
        self.shutdown_event.set()

    def stop(self) -> None:
        """Close listening socket, wait for client threads and clean up."""
        console.log("[magenta]Shutting down server…[/]")
        self.shutdown_event.set()
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
        for th in self._client_threads:
            th.join(timeout=2.0)
        console.log("[green]Server stopped cleanly[/]")


def main() -> None:
    server = CommandServer()
    server.start()


if __name__ == "__main__":
    main()
