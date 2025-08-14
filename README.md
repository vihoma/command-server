# A threaded command server and client.
# A kind of a BACKDOOR, if You must...
 **NOTE!!!**: This is and **academic excersise**, not a real-world exploit!!!

## The client isn't that nice, just use nc/ncat to connect to the server...:p

## The server:
  * Listens on TCP port 666.
  * Uses threading to send/receive data and for the key event listener.
  * Accepts multiple connections.
  * Sends a welcome message upon connection.
  * Sends a command prompt.
  * Receives commands.
  * Handles command execution errors.
  * Executes received commands in the system default shell with output capture and error handling.
  * Uses subprocess for command execution.
  * Sends command output back to the client.
  * Sends error messages to the client upon command failure.
  * Implements a simple statistics system.
    * Collects statistics (connections, commands, errors).
    * Press “S” in the server console to dump current statistics.
  * Rich‑based TUI and non‑blocking key handling (pynput).
  * Clean shutdown on Ctrl‑C, ESC, or Q.

## The client:
  * Connects to the server via TCP.
  * Sends commands to the server.
  * Receives command output from the server.
  * Handles connection errors.
  * Clean shutdown on Ctrl‑C, 'exit' or 'quit'
  * Displays server output in a pretty way.
  * Uses rich for nice output.
  * Uses a custom prompt.
  * Uses threading to send/receive data and for the key event listener.
  * **You should use a command like nc/ncat as a client instead!**
