"""
Secure Multi-Client Chat Server
Assignment 8 - Optimization, Scalability and Reliability

Enhancements over Assignment 7:
- Configuration loaded from config.json
- ThreadPoolExecutor for scalable thread management
- Heartbeat-based dead client detection
- Graceful server shutdown via signal handling
- Improved exception handling with specific catches
- Idempotent disconnect with proper resource cleanup
"""

import socket
import threading
import time
import csv
import os
import json
import signal
import sys
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# ---------------------------------------------------------------- config

def load_config():
    """Load configuration from config.json with sensible defaults."""
    defaults = {
        "host": "10.0.0.1",
        "port": 5000,
        "recv_buffer": 4096,
        "max_message_length": 1000,
        "session_timeout": 180,
        "max_failed_attempts": 5,
        "lockout_duration": 60,
        "max_workers": 20,
        "listen_backlog": 20,
        "heartbeat_interval": 15,
        "chat_log": "chat_log.csv",
        "connection_log": "connection_log.csv",
        "users_file": "users.csv",
        "security_log": "security_log.txt",
    }
    try:
        with open("config.json", "r") as f:
            cfg = json.load(f)
        server_cfg = cfg.get("server", {})
        file_cfg = cfg.get("files", {})
        defaults.update({
            "host": server_cfg.get("host", defaults["host"]),
            "port": server_cfg.get("port", defaults["port"]),
            "recv_buffer": server_cfg.get("recv_buffer", defaults["recv_buffer"]),
            "max_message_length": server_cfg.get("max_message_length", defaults["max_message_length"]),
            "session_timeout": server_cfg.get("session_timeout", defaults["session_timeout"]),
            "max_failed_attempts": server_cfg.get("max_failed_attempts", defaults["max_failed_attempts"]),
            "lockout_duration": server_cfg.get("lockout_duration", defaults["lockout_duration"]),
            "max_workers": server_cfg.get("max_workers", defaults["max_workers"]),
            "listen_backlog": server_cfg.get("listen_backlog", defaults["listen_backlog"]),
            "heartbeat_interval": server_cfg.get("heartbeat_interval", defaults["heartbeat_interval"]),
            "chat_log": file_cfg.get("chat_log", defaults["chat_log"]),
            "connection_log": file_cfg.get("connection_log", defaults["connection_log"]),
            "users_file": file_cfg.get("users_file", defaults["users_file"]),
            "security_log": file_cfg.get("security_log", defaults["security_log"]),
        })
    except FileNotFoundError:
        print("[config] config.json not found, using defaults.")
    except json.JSONDecodeError as e:
        print(f"[config] config.json parse error: {e}, using defaults.")
    return defaults


CONFIG = load_config()


class ChatServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.clients = {}          # socket -> {username, ip, port, login_time, status, last_activity}
        self.lock = threading.Lock()
        self.chat_history = []     # recent messages, shown to newly joined clients
        self.running = True        # flag for graceful shutdown

        self.user_db = {}          # username -> password_hash
        self.failed_attempts = {}  # username -> {"count": int, "timestamp": float}

        self.message_count = 0
        self.broadcast_count = 0
        self.private_count = 0

        self.load_users()

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((host, port))
        self.socket.listen(CONFIG["listen_backlog"])

        # Thread pool for scalable client handling
        self.executor = ThreadPoolExecutor(max_workers=CONFIG["max_workers"])

        # Start session & heartbeat monitor thread
        threading.Thread(target=self._monitor_loop, daemon=True).start()

    # ---------------------------------------------------------- utilities

    @staticmethod
    def hash_password(password):
        """Hash a password using SHA-256."""
        return hashlib.sha256(password.encode()).hexdigest()

    def load_users(self):
        """Load user database from CSV file."""
        users_file = CONFIG["users_file"]
        if not os.path.exists(users_file):
            return
        try:
            with open(users_file, "r") as f:
                reader = csv.reader(f)
                next(reader, None)  # skip header
                for row in reader:
                    if len(row) == 2:
                        self.user_db[row[0]] = row[1]
        except (IOError, csv.Error) as e:
            print(f"[error] Failed to load users file: {e}")

    def save_user(self, username, password_hash):
        """Persist a new user to the CSV database."""
        users_file = CONFIG["users_file"]
        file_exists = os.path.exists(users_file)
        try:
            with open(users_file, "a", newline="") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["username", "password_hash"])
                writer.writerow([username, password_hash])
            self.user_db[username] = password_hash
        except IOError as e:
            print(f"[error] Failed to save user: {e}")

    @staticmethod
    def timestamp():
        """Return a formatted timestamp string."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def log_security(self, event, details):
        """Append a security event to the security log file."""
        try:
            with open(CONFIG["security_log"], "a") as f:
                f.write(f"[{self.timestamp()}] {event}: {details}\n")
        except IOError:
            pass

    @staticmethod
    def _append_csv(path, header, row):
        """Append a row to a CSV file, creating header if needed."""
        file_exists = os.path.exists(path)
        try:
            with open(path, "a", newline="") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(header)
                writer.writerow(row)
        except IOError:
            pass

    def log_connection(self, event, username, ip):
        """Log a connection event."""
        self._append_csv(CONFIG["connection_log"],
                         ["timestamp", "event", "username", "ip"],
                         [self.timestamp(), event, username, ip])

    def save_chat(self, sender, receiver, msg_type, message):
        """Save a chat message to history and CSV."""
        row = [self.timestamp(), sender, receiver, msg_type, message]
        self.chat_history.append(row)
        self._append_csv(CONFIG["chat_log"],
                         ["timestamp", "sender", "receiver", "type", "message"], row)

    def show_statistics(self):
        """Print current server statistics."""
        with self.lock:
            online = sum(1 for c in self.clients.values() if c["status"] == "Online")
        print(f"[stats] messages={self.message_count} broadcast={self.broadcast_count} "
              f"private={self.private_count} online={online}")

    # ------------------------------------------------- monitor (session + heartbeat)

    def _monitor_loop(self):
        """Periodically check for inactive sessions and dead connections."""
        while self.running:
            time.sleep(CONFIG["heartbeat_interval"])
            now = time.time()
            to_disconnect = []

            with self.lock:
                for client, info in list(self.clients.items()):
                    if info["status"] != "Online":
                        continue

                    # Session timeout check
                    if (now - info["last_activity"]) > CONFIG["session_timeout"]:
                        to_disconnect.append((client, info["username"], "SESSION_TIMEOUT"))
                        continue

                    # Heartbeat: try sending PING
                    try:
                        client.send("PING\n".encode())
                    except (OSError, BrokenPipeError, ConnectionResetError):
                        to_disconnect.append((client, info["username"], "DEAD_CONNECTION"))

            for client, username, reason in to_disconnect:
                if reason == "SESSION_TIMEOUT":
                    self.log_security("SESSION_TIMEOUT",
                                      f"User '{username}' disconnected due to inactivity.")
                    try:
                        client.send("TIMEOUT\n".encode())
                    except (OSError, BrokenPipeError, ConnectionResetError):
                        pass
                else:
                    self.log_security("DEAD_CONNECTION",
                                      f"User '{username}' removed (connection dead).")
                    print(f"[heartbeat] {username} connection dead, cleaning up.")
                self._disconnect(client, username)

    # ---------------------------------------------------------- user list

    def get_online_usernames(self):
        """Return a list of online usernames."""
        with self.lock:
            return [info["username"] for info in self.clients.values()
                    if info["status"] == "Online"]

    def broadcast_userlist(self):
        """Send USERLIST:<comma-separated names> to every connected client."""
        names = self.get_online_usernames()
        payload = "USERLIST:" + ",".join(names) + "\n"
        with self.lock:
            for client in list(self.clients):
                try:
                    client.send(payload.encode())
                except (OSError, BrokenPipeError, ConnectionResetError):
                    pass

    # ---------------------------------------------------------- messaging

    def broadcast_system(self, text):
        """Send a system message to all connected clients."""
        with self.lock:
            for client in list(self.clients):
                try:
                    client.send(text.encode())
                except (OSError, BrokenPipeError, ConnectionResetError):
                    pass

    def broadcast_message(self, sender_socket, sender_name, message):
        """Broadcast a chat message to all clients except the sender."""
        with self.lock:
            for client in list(self.clients):
                if client != sender_socket:
                    try:
                        client.send(f"[{sender_name}] {message}\n".encode())
                    except (OSError, BrokenPipeError, ConnectionResetError):
                        pass
        self.broadcast_count += 1
        self.save_chat(sender_name, "ALL", "Broadcast", message)

    def private_message(self, sender_socket, sender_name, receiver_name, message):
        """Send a private message from one user to another."""
        with self.lock:
            target = next(
                (c for c, info in self.clients.items() if info["username"] == receiver_name),
                None,
            )

        if target is None:
            try:
                sender_socket.send(f"User '{receiver_name}' not found.\n".encode())
            except (OSError, BrokenPipeError, ConnectionResetError):
                pass
            return

        try:
            target.send(f"[Private from {sender_name}] {message}\n".encode())
            sender_socket.send(f"[Private to {receiver_name}] {message}\n".encode())
            self.private_count += 1
            self.save_chat(sender_name, receiver_name, "Private", message)
        except (OSError, BrokenPipeError, ConnectionResetError):
            pass

    def send_online_users(self, client):
        """Send a formatted list of online users to a client."""
        with self.lock:
            names = [info["username"] for info in self.clients.values()
                     if info["status"] == "Online"]
        body = "\n===== ONLINE USERS =====\n" + "\n".join(names) + "\n========================\n"
        try:
            client.send(body.encode())
        except (OSError, BrokenPipeError, ConnectionResetError):
            pass

    def send_last_messages(self, client, limit=10):
        """Send recent chat history to a newly connected client."""
        if not self.chat_history:
            return
        lines = ["\n===== RECENT CHAT HISTORY =====\n"]
        lines += [f"[{t}] {s} -> {r}: {m}\n" for t, s, r, _, m in self.chat_history[-limit:]]
        lines.append("================================\n")
        try:
            client.send("".join(lines).encode())
        except (OSError, BrokenPipeError, ConnectionResetError):
            pass

    # ------------------------------------------------------ client loop

    def handle_client(self, client):
        """Main receive loop for a single authenticated client."""
        with self.lock:
            info = self.clients.get(client)
        if not info:
            return
        username = info["username"]

        while self.running:
            try:
                data = client.recv(CONFIG["recv_buffer"])
                if not data:
                    break

                with self.lock:
                    if client in self.clients:
                        self.clients[client]["last_activity"] = time.time()

                message = data.decode().strip()

                # Heartbeat response from client — just ignore it
                if message == "PONG":
                    continue

                # Check message length
                if len(message) > CONFIG["max_message_length"]:
                    client.send("ERROR: Message exceeds maximum allowed length.\n".encode())
                    self.log_security("INPUT_VALIDATION",
                                      f"User '{username}' sent oversized message ({len(message)} chars).")
                    continue

                if message == "/logout":
                    break

                if message == "/list":
                    self.send_online_users(client)
                    continue

                if message == "/users":
                    names = self.get_online_usernames()
                    client.send(("USERLIST:" + ",".join(names) + "\n").encode())
                    continue

                if message.startswith("/msg "):
                    parts = message.split(" ", 2)
                    if len(parts) < 3:
                        client.send("Usage: /msg <username> <message>\n".encode())
                        continue
                    self.private_message(client, username, parts[1], parts[2])
                    self.message_count += 1
                    self.show_statistics()
                    continue

                if message.startswith("/") and message not in ["/list", "/users", "/logout"]:
                    client.send("ERROR: Unsupported command.\n".encode())
                    self.log_security("INPUT_VALIDATION",
                                      f"User '{username}' sent unsupported command '{message}'.")
                    continue

                print(f"[{username}] {message}")
                self.broadcast_message(client, username, message)
                self.message_count += 1
                self.show_statistics()

            except ConnectionResetError:
                print(f"[error] {username}: connection reset by peer.")
                break
            except BrokenPipeError:
                print(f"[error] {username}: broken pipe.")
                break
            except OSError as e:
                print(f"[error] {username}: OS error — {e}")
                break
            except Exception as e:
                print(f"[error] {username}: unexpected error — {e}")
                break

        self._disconnect(client, username)

    def _disconnect(self, client, username):
        """Idempotent disconnect: safe to call multiple times for the same client."""
        with self.lock:
            info = self.clients.get(client)
            if info is None:
                return  # already cleaned up
            info["status"] = "Offline"
            ip = info.get("ip", "unknown")
            self.clients.pop(client, None)

        print(f"{username} disconnected")

        self.broadcast_system(f"\n*** {username} left the chat ***\n")
        self.broadcast_userlist()
        self.show_statistics()
        self.log_connection("DISCONNECTED", username, ip)
        self.log_security("LOGOUT", f"User '{username}' logged out securely.")

        try:
            client.close()
        except OSError:
            pass

    # ------------------------------------------------------------ accept

    def accept_clients(self):
        """Continuously accept new client connections."""
        print(f"\nServer listening on {self.host}:{self.port}")
        print(f"Thread pool: max_workers={CONFIG['max_workers']}")
        print("Waiting for clients...\n")

        while self.running:
            try:
                self.socket.settimeout(1.0)  # allow periodic check of self.running
                try:
                    client, address = self.socket.accept()
                except socket.timeout:
                    continue

                # Receive credentials
                try:
                    client.settimeout(10.0)  # 10s to send credentials
                    credentials = client.recv(CONFIG["recv_buffer"]).decode().strip()
                    client.settimeout(None)
                except (OSError, UnicodeDecodeError, socket.timeout) as e:
                    print(f"[error] Failed to receive credentials from {address}: {e}")
                    try:
                        client.close()
                    except OSError:
                        pass
                    continue

                if not credentials or "\n" not in credentials:
                    try:
                        client.send("AUTH_FAIL: Invalid credentials format.\n".encode())
                    except OSError:
                        pass
                    try:
                        client.close()
                    except OSError:
                        pass
                    continue

                parts = credentials.split("\n", 1)

                if len(parts) != 2:
                    try:
                        client.send("AUTH_FAIL: Username and password required.\n".encode())
                    except OSError:
                        pass
                    try:
                        client.close()
                    except OSError:
                        pass
                    continue

                username, password = parts[0].strip(), parts[1].strip()

                # Input validation
                if not username or " " in username or not password:
                    try:
                        client.send("AUTH_FAIL: Invalid username or empty password.\n".encode())
                    except OSError:
                        pass
                    try:
                        client.close()
                    except OSError:
                        pass
                    continue

                # Check failed login protection
                if username in self.failed_attempts:
                    fa = self.failed_attempts[username]
                    if fa["count"] >= CONFIG["max_failed_attempts"]:
                        if time.time() - fa["timestamp"] < CONFIG["lockout_duration"]:
                            try:
                                client.send("AUTH_FAIL: Account temporarily locked out. Try again later.\n".encode())
                            except OSError:
                                pass
                            self.log_security("LOGIN_REJECTED",
                                              f"User '{username}' blocked (too many failed attempts, IP: {address[0]}).")
                            try:
                                client.close()
                            except OSError:
                                pass
                            continue
                        else:
                            self.failed_attempts[username] = {"count": 0, "timestamp": 0}

                # Authentication
                hashed_pw = self.hash_password(password)
                with self.lock:
                    if username in self.user_db:
                        if self.user_db[username] != hashed_pw:
                            if username not in self.failed_attempts:
                                self.failed_attempts[username] = {"count": 0, "timestamp": 0}
                            self.failed_attempts[username]["count"] += 1
                            self.failed_attempts[username]["timestamp"] = time.time()

                            try:
                                client.send("AUTH_FAIL: Incorrect password.\n".encode())
                            except OSError:
                                pass
                            self.log_security("LOGIN_FAILED",
                                              f"Failed login for '{username}' from IP {address[0]}.")
                            try:
                                client.close()
                            except OSError:
                                pass
                            continue
                    else:
                        # Auto-register new user
                        self.save_user(username, hashed_pw)
                        self.log_security("USER_REGISTERED", f"New user '{username}' registered.")

                # Check for duplicate login
                duplicate = False
                with self.lock:
                    for existing_client, einfo in self.clients.items():
                        if einfo["username"] == username and einfo["status"] == "Online":
                            duplicate = True
                            break

                if duplicate:
                    try:
                        client.send("AUTH_FAIL: User already logged in from another location.\n".encode())
                    except OSError:
                        pass
                    self.log_security("LOGIN_REJECTED",
                                      f"Duplicate login attempt for '{username}' from IP {address[0]}.")
                    try:
                        client.close()
                    except OSError:
                        pass
                    continue

                # Login Success
                with self.lock:
                    if username in self.failed_attempts:
                        self.failed_attempts[username] = {"count": 0, "timestamp": 0}

                    self.clients[client] = {
                        "username": username,
                        "ip": address[0],
                        "port": address[1],
                        "login_time": self.timestamp(),
                        "status": "Online",
                        "last_activity": time.time(),
                    }

                try:
                    client.send("AUTH_SUCCESS\n".encode())
                except OSError:
                    with self.lock:
                        self.clients.pop(client, None)
                    try:
                        client.close()
                    except OSError:
                        pass
                    continue

                online_count = len([c for c in self.clients.values() if c["status"] == "Online"])
                print(f"{username} connected from {address[0]} (Online: {online_count})")
                self.log_connection("CONNECTED", username, address[0])
                self.log_security("LOGIN_SUCCESS",
                                  f"User '{username}' logged in successfully from IP {address[0]}.")

                self.send_last_messages(client)
                self.broadcast_system(f"\n*** {username} joined the chat ***\n")
                self.broadcast_userlist()
                self.show_statistics()

                # Submit to thread pool instead of spawning unbounded threads
                self.executor.submit(self.handle_client, client)

            except OSError as e:
                if self.running:
                    print(f"[error] accept_clients OS error: {e}")
                break
            except Exception as e:
                if self.running:
                    print(f"[error] accept_clients unexpected error: {e}")

    # --------------------------------------------------------- shutdown

    def graceful_shutdown(self, signum=None, frame=None):
        """Handle SIGINT/SIGTERM for graceful server shutdown."""
        print("\n[shutdown] Shutting down server...")
        self.running = False

        # Notify all clients
        with self.lock:
            for client in list(self.clients):
                try:
                    client.send("SERVER_SHUTDOWN\n".encode())
                except (OSError, BrokenPipeError, ConnectionResetError):
                    pass
                try:
                    client.close()
                except OSError:
                    pass
            self.clients.clear()

        # Close server socket
        try:
            self.socket.close()
        except OSError:
            pass

        # Shutdown thread pool
        self.executor.shutdown(wait=False)
        self.log_security("SERVER_SHUTDOWN", "Server shut down gracefully.")
        print("[shutdown] Server stopped.")
        sys.exit(0)

    # ------------------------------------------------------------ run

    def run(self):
        """Start the server."""
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.graceful_shutdown)
        signal.signal(signal.SIGTERM, self.graceful_shutdown)

        print("=" * 50)
        print("   Optimized Chat Server (Assignment 8)")
        print("=" * 50)
        self.accept_clients()


if __name__ == "__main__":
    config = load_config()
    server = ChatServer(config["host"], config["port"])
    server.run()
