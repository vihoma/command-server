- Create a Python 3 program using the object-oriented paradigm for a basic
command server which listens on TCP port 666, receives commands and executes
the commands in the systems default shell.
- Use docstrings and comments and do not explain basic concepts in your answer
but do comment the code as appropriate considering Python 3 best practices,
PEP 8 and PEP 257, use type hints and create a complete working program which
runs without modifications.
- Only output the working code, not any other output.
- Make the code so that the program exits cleanly when a keyboard interrupt
happens in the console where this program is run.
- Do not exit the server if a keyboard interrupt happens at the client side,
instead then exit the client.
- Also exit the server in the case that the keys ESC or Q (case sensitive) is
pressed in the console where this program is run but not when these keys are
pressed on the client side.
- When the client side inputs 'quit' or 'exit' and a carriage return, Ctrl+C
or Ctrl+D, the client side should gracefully close the client side connection,
but only gracefully exits the client and not the server.
- The client should be able to send commands to the server and receive the
output of the commands.
- Make the program collect useful statisctics of connections, command count
and errors count.
- Print these statistics to the client if the client inputs the command
'stats' (case insensitive) followed by a carriage return.
- Also print these statistics to the console where this server is started if
the key 'S' (case sensitive) is pressed on on the starting console.
- Separate the server logic, TUI and client handling to separate classes as
appropriate.
- Don't use asyncio for the implementation. Use subprocesses instead, if
needed.
- The client should be a separate set of files and classes which can be run
from the command line and connect to the server.
- The server should be able to handle multiple concurrent connections.
- Make sure the client can handle multiple commands in a row without
disconnecting.
- The server should be able to handle a client disconnecting gracefully.
- The server should be able to handle the server console being closed
gracefully.
- The server and client should be able to handle the server being closed
gracefully.
- The client should be able to handle the server disconnecting gracefully.
- Make sure the client can handle the server being down when it starts up.
- The client should be able to handle the server being up but not responding.
- The client should be able to handle the server being up and responding but
returning an error.
- The client should be able to handle the server returning a command that
is not a valid command.
- Make sure all client sockets are properly closed and cleaned up when
the client is closed.
- Make sure all client listeners are properly closed and cleaned up when the
client is closed.
- Make sure all sockets are properly closed and cleaned up when the server
is closed.
- Make sure all listeners are properly closed and cleaned up when the server
is closed.
- Make sure all network connections are properly closed and cleaned up when
the server is closed.
- Make sure all threads are properly closed and cleaned up when the server
is closed.
- Make sure all processes are properly closed and cleaned up when the server
is closed.
- Make sure all file handles are properly closed and cleaned up when the
server is closed.
- Create a nice looking and still mainly funtional TUI for the server and
the client using the Rich module/library.
- Use the pynput module for the key-press events on the server console and
the client, make sure the key press detection is non-blocking.
