# Assignment 7: Secure Network Application Development Using TCP

## Objective

Enhance the GUI-based multi-client TCP application developed in Assignment 6 by implementing practical security mechanisms. This assignment introduces authentication, secure password storage using SHA-256 hashing, duplicate login prevention, input validation, failed login protection, and session management.

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

1. Enter the server IP (`10.0.0.1`), your username, and your password, then click **Connect / Register**
   - Note: If this is your first time logging in with a username, the server will securely auto-register you.
2. Type messages in the input box and click **Send** or press Enter
3. For private messages, type `/msg <username> <message>` or double-click a user in the Online Users list
4. Click **Disconnect / Logout** to cleanly leave the chat and terminate the session.

## Security Features (Assignment 7)

- **User Authentication**: Validates username and password credentials.
- **Secure Password Storage**: Passwords are hashed using `SHA-256` before being saved to `users.csv`. No plaintext passwords are stored.
- **Duplicate Login Prevention**: Rejects attempts to log into an account that is currently online elsewhere.
- **Failed Login Protection**: Temporarily locks out an account for 60 seconds after 5 consecutive failed login attempts.
- **Input Validation**: Rejects empty usernames/passwords, oversized messages (over 1000 characters), and unsupported commands.
- **Session Management**: Implements an inactivity timeout (disconnects idle users after 3 minutes) and explicit `/logout` support.
- **Secure Logging**: Persistent logging of authentication successes, failures, lockouts, and timeouts to `security_log.txt`.

## File Structure

```
Assignment06/
├── server.py          # Secure chat server
├── client_gui.py      # Secure GUI chat client
├── users.csv          # Hashed user database (generated)
├── security_log.txt   # Security event logs (generated)
├── screenshots/       # Testing screenshots
└── README.md          # This file
```
