# Assignment 8: Application Optimization, Scalability and Reliability

## Objective

Enhance the existing GUI-based multi-client secure chat application (from Assignment 7) by improving scalability, reliability, maintainability, and overall software quality. This assignment focuses on connection management, automatic reconnection, thread-pool based scalability, externalized configuration, and performance benchmarking.

## Software Requirements

- Python 3.x
- Mininet
- Wireshark
- Tkinter (included with Python)
- matplotlib (`pip3 install matplotlib`) — for graph generation
- psutil (`pip3 install psutil`) — optional, for CPU/memory metrics

## Network Topology

```
Mininet: sudo mn --topo single,11

         +----------+
         |  Switch  |
         +----+-----+
              |
   +----+----+----+----+----+----+----+----+----+----+
   |    |    |    |    |    |    |    |    |    |    |
  h1   h2   h3   h4   h5   h6   h7   h8   h9  h10  h11
Server  ---- Clients (up to 10 concurrent) ----
```

| Host | Role     | IP Address  |
|------|----------|-------------|
| h1   | Server   | 10.0.0.1    |
| h2–h11 | Clients | 10.0.0.2–11 |

## Execution Steps

### 1. Start Mininet

```bash
sudo mn --topo single,11
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

### 4. Start GUI Clients (on h2–h11)

```bash
mininet> xterm h2 h3 h4 h5 h6 h7 h8 h9 h10 h11
# In each terminal:
python3 client_gui.py
```

### 5. Run Performance Benchmark

```bash
# On any host that can reach the server:
python3 benchmark.py 10.0.0.1 benchpass
```

### 6. Generate Graphs

```bash
python3 generate_graphs.py
```

## Optimizations Implemented (Assignment 8)

### Connection Management
- **Heartbeat-based dead client detection**: Server periodically sends `PING` to every client; if the socket is broken, the client is automatically removed.
- **Proper resource cleanup**: Idempotent `_disconnect()` ensures sockets are always closed, even on unexpected errors.
- **Meaningful error messages**: Human-readable errors are sent/logged on every failure path.

### Reliability Enhancement
- **Automatic reconnection**: Client retries up to 3 times (configurable) with stored credentials on unexpected disconnect.
- **Graceful server shutdown**: `SIGINT`/`SIGTERM` handlers send `SERVER_SHUTDOWN` to all clients and close everything cleanly.
- **Improved exception handling**: Bare `except` clauses replaced with specific catches (`ConnectionResetError`, `BrokenPipeError`, `OSError`, `socket.timeout`).

### Scalability Enhancement
- **ThreadPoolExecutor**: Replaced unbounded `threading.Thread` creation with `concurrent.futures.ThreadPoolExecutor(max_workers=20)` to cap resource usage.
- **Increased listen backlog**: `socket.listen(20)` to handle burst connections.
- **Tested with 10 concurrent clients** without crashes.

### Configuration Management
- All hardcoded values (host, port, buffer sizes, timeouts, worker counts, reconnect params) externalized to `config.json`.
- Both server and client load from the same file with built-in defaults.

### Performance Evaluation
- `benchmark.py` measures delay, throughput, CPU, and memory for 5, 8, and 10 concurrent clients.
- `generate_graphs.py` creates comparison bar charts saved in `graphs/`.

## Security Features (from Assignment 7)

- **User Authentication**: Username/password login with SHA-256 hashing.
- **Secure Password Storage**: Hashed passwords stored in `users.csv`.
- **Duplicate Login Prevention**: Rejects simultaneous logins for the same account.
- **Failed Login Protection**: 60-second lockout after 5 consecutive failed attempts.
- **Input Validation**: Rejects empty credentials, oversized messages, and unsupported commands.
- **Session Management**: Inactivity timeout and explicit `/logout` support.
- **Secure Logging**: All events logged to `security_log.txt` without sensitive data.

## File Structure

```
Assignment06/
├── server.py               # Optimized chat server
├── client_gui.py            # Optimized GUI chat client
├── config.json              # Centralized configuration
├── benchmark.py             # Performance benchmark script
├── generate_graphs.py       # Graph generation script
├── users.csv                # Hashed user database (generated)
├── security_log.txt         # Security event logs (generated)
├── performance_results.csv  # Benchmark results (generated)
├── graphs/                  # Performance comparison graphs (generated)
├── screenshots/             # Testing screenshots
└── README.md                # This file
```
