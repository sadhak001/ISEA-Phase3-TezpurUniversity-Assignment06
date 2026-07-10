# Assignment 6: GUI-Based Multi-Client Chat Application Using TCP

## Objective

Convert the terminal-based TCP chat application developed in Assignment 5 into a graphical desktop application using Python's `tkinter` library, while reusing the existing server implementation. This assignment introduces GUI programming, event-driven programming, multithreading, and user-friendly network application development.

## Software Requirements

- Python 3.x
- Mininet
- Wireshark
- Tkinter (included with Python)

## Network Topology

```
Mininet: sudo mn --topo single,5

         +----------+
         |  Switch  |
         +----+-----+
              |
   +----+----+----+----+
   |    |    |    |    |
  h1   h2   h3   h4   h5
Server  A    B    C    D
```

| Host | Role     | IP Address |
|------|----------|------------|
| h1   | Server   | 10.0.0.1   |
| h2   | Client A | 10.0.0.2   |
| h3   | Client B | 10.0.0.3   |
| h4   | Client C | 10.0.0.4   |
| h5   | Client D | 10.0.0.5   |

## Execution Steps

### 1. Start Mininet

```bash
sudo mn --topo single,5
```

### 2. Verify Connectivity

```bash
mininet> nodes
mininet> net
mininet> pingall
```

### 3. Start the Server (on h1)

```bash
mininet> xterm h1
# In the h1 terminal:
python3 server.py
```

### 4. Start GUI Clients (on h2, h3, h4, h5)

```bash
mininet> xterm h2 h3 h4 h5
# In each terminal:
python3 client_gui.py
```

### 5. Using the Application

1. Enter the server IP (`10.0.0.1`), your username, and click **Connect**
2. Type messages in the input box and click **Send** or press Enter
3. For private messages, type `/msg <username> <message>` or double-click a user in the Online Users list
4. Click **Disconnect** to leave the chat

## Features

- **GUI Login Window**: Username/password entry with input validation
- **Chat Interface**: Scrollable message area with auto-scroll
- **Online Users Panel**: Auto-updating list of connected users
- **Broadcast Messaging**: Send messages to all connected users
- **Private Messaging**: Send direct messages using `/msg` command
- **Join/Leave Notifications**: Automatic system messages
- **Background Threading**: Non-blocking message reception keeps GUI responsive
- **Connection Status**: Visual indicator showing connection state

## Implementation Description

The application reuses the TCP server from Assignment 5 with minimal modifications:
- Server now accepts clients continuously (no fixed count)
- Added `USERLIST:` protocol message for GUI user list updates
- All original features preserved (broadcast, private messaging, chat history, CSV logging)

The GUI client (`client_gui.py`) separates networking logic (`ChatClient` class) from GUI code (`LoginWindow` and `ChatWindow` classes). A background thread handles `socket.recv()` and uses `root.after()` for thread-safe GUI updates.

## File Structure

```
Assignment06/
├── server.py          # Chat server (modified from Assignment 5)
├── client_gui.py      # GUI chat client
├── screenshots/       # Testing screenshots
└── README.md          # This file
```
