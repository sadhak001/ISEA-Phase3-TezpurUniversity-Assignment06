import socket
import threading
import time
import csv
import os
import hashlib
from datetime import datetime

HOST = "10.0.0.1"
PORT = 5000
RECV_BUFFER = 4096
MAX_MESSAGE_LENGTH = 1000
SESSION_TIMEOUT = 180  # 3 minutes inactivity timeout
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = 60  # seconds

CHAT_LOG = "chat_log.csv"
CONNECTION_LOG = "connection_log.csv"
USERS_FILE = "users.csv"
SECURITY_LOG = "security_log.txt"


class ChatServer:
    def __init__(self, host, port):
        self.clients = {}          # socket -> {username, ip, port, login_time, status, last_activity}
        self.lock = threading.Lock()
        self.chat_history = []     # recent messages, shown to newly joined clients

        self.user_db = {}          # username -> password_hash
        self.failed_attempts = {}  # username -> {"count": int, "timestamp": float}

        self.message_count = 0
        self.broadcast_count = 0
        self.private_count = 0

        self.load_users()

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((host, port))
        self.socket.listen()
        
        # Start session monitor thread
        threading.Thread(target=self.session_monitor, daemon=True).start()

    # ---------------------------------------------------------- utilities

    @staticmethod
    def hash_password(password):
        return hashlib.sha256(password.encode()).hexdigest()

    def load_users(self):
        if not os.path.exists(USERS_FILE):
            return
        with open(USERS_FILE, "r") as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                if len(row) == 2:
                    self.user_db[row[0]] = row[1]
                    
    def save_user(self, username, password_hash):
        file_exists = os.path.exists(USERS_FILE)
        with open(USERS_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["username", "password_hash"])
            writer.writerow([username, password_hash])
        self.user_db[username] = password_hash

    @staticmethod
    def timestamp():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def log_security(self, event, details):
        with open(SECURITY_LOG, "a") as f:
            f.write(f"[{self.timestamp()}] {event}: {details}\n")

    @staticmethod
    def _append_csv(path, header, row):
        file_exists = os.path.exists(path)
        with open(path, "a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(header)
            writer.writerow(row)

    def log_connection(self, event, username, ip):
        self._append_csv(CONNECTION_LOG, ["timestamp", "event", "username", "ip"],
                          [self.timestamp(), event, username, ip])

    def save_chat(self, sender, receiver, msg_type, message):
        row = [self.timestamp(), sender, receiver, msg_type, message]
        self.chat_history.append(row)
        self._append_csv(CHAT_LOG, ["timestamp", "sender", "receiver", "type", "message"], row)

    def show_statistics(self):
        with self.lock:
            online = sum(1 for c in self.clients.values() if c["status"] == "Online")
        print(f"[stats] messages={self.message_count} broadcast={self.broadcast_count} "
              f"private={self.private_count} online={online}")

    # ---------------------------------------------------------- session monitor
    
    def session_monitor(self):
        """Periodically check for inactive sessions and disconnect them."""
        while True:
            time.sleep(10)
            now = time.time()
            to_disconnect = []
            with self.lock:
                for client, info in self.clients.items():
                    if info["status"] == "Online" and (now - info["last_activity"]) > SESSION_TIMEOUT:
                        to_disconnect.append((client, info["username"]))
            
            for client, username in to_disconnect:
                self.log_security("SESSION_TIMEOUT", f"User '{username}' disconnected due to inactivity.")
                try:
                    client.send("TIMEOUT\n".encode())
                except:
                    pass
                self._disconnect(client, username)

    # ---------------------------------------------------------- user list

    def get_online_usernames(self):
        """Return a list of online usernames (called under lock)."""
        with self.lock:
            return [info["username"] for info in self.clients.values()
                    if info["status"] == "Online"]

    def broadcast_userlist(self):
        """Send USERLIST:<comma-separated names> to every connected client."""
        names = self.get_online_usernames()
        payload = "USERLIST:" + ",".join(names) + "\n"
        with self.lock:
            for client in self.clients:
                try:
                    client.send(payload.encode())
                except OSError:
                    pass

    # ---------------------------------------------------------- messaging

    def broadcast_system(self, text):
        with self.lock:
            for client in self.clients:
                try:
                    client.send(text.encode())
                except OSError:
                    pass

    def broadcast_message(self, sender_socket, sender_name, message):
        with self.lock:
            for client in self.clients:
                if client != sender_socket:
                    try:
                        client.send(f"[{sender_name}] {message}\n".encode())
                    except OSError:
                        pass
        self.broadcast_count += 1
        self.save_chat(sender_name, "ALL", "Broadcast", message)

    def private_message(self, sender_socket, sender_name, receiver_name, message):
        with self.lock:
            target = next(
                (c for c, info in self.clients.items() if info["username"] == receiver_name),
                None,
            )

        if target is None:
            sender_socket.send(f"User '{receiver_name}' not found.\n".encode())
            return

        try:
            target.send(f"[Private from {sender_name}] {message}\n".encode())
            sender_socket.send(f"[Private to {receiver_name}] {message}\n".encode())
            self.private_count += 1
            self.save_chat(sender_name, receiver_name, "Private", message)
        except OSError:
            pass

    def send_online_users(self, client):
        with self.lock:
            names = [info["username"] for info in self.clients.values() if info["status"] == "Online"]
        body = "\n===== ONLINE USERS =====\n" + "\n".join(names) + "\n========================\n"
        client.send(body.encode())

    def send_last_messages(self, client, limit=10):
        if not self.chat_history:
            return
        lines = ["\n===== RECENT CHAT HISTORY =====\n"]
        lines += [f"[{t}] {s} -> {r}: {m}\n" for t, s, r, _, m in self.chat_history[-limit:]]
        lines.append("================================\n")
        try:
            client.send("".join(lines).encode())
        except OSError:
            pass

    # ------------------------------------------------------ client loop

    def handle_client(self, client):
        username = self.clients[client]["username"]

        while True:
            try:
                data = client.recv(RECV_BUFFER)
                if not data:
                    break
                    
                with self.lock:
                    if client in self.clients:
                        self.clients[client]["last_activity"] = time.time()

                message = data.decode().strip()
                
                # Check message length
                if len(message) > MAX_MESSAGE_LENGTH:
                    client.send("ERROR: Message exceeds maximum allowed length.\n".encode())
                    self.log_security("INPUT_VALIDATION", f"User '{username}' sent oversized message ({len(message)} chars).")
                    continue

                if message == "/logout":
                    break

                if message == "/list":
                    self.send_online_users(client)
                    continue

                if message == "/users":
                    # Machine-parsable user list for GUI
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
                    
                if message.startswith("/") and not message.startswith("/msg ") and message not in ["/list", "/users", "/logout"]:
                    client.send("ERROR: Unsupported command.\n".encode())
                    self.log_security("INPUT_VALIDATION", f"User '{username}' sent unsupported command '{message}'.")
                    continue

                print(f"[{username}] {message}")
                self.broadcast_message(client, username, message)
                self.message_count += 1
                self.show_statistics()

            except Exception:
                break

        self._disconnect(client, username)

    def _disconnect(self, client, username):
        print(f"{username} disconnected")

        with self.lock:
            info = self.clients.get(client)
            if info:
                info["status"] = "Offline"
            ip = info["ip"] if info else "unknown"

        self.broadcast_system(f"\n*** {username} left the chat ***\n")
        self.broadcast_userlist()
        self.show_statistics()
        self.log_connection("DISCONNECTED", username, ip)
        self.log_security("LOGOUT", f"User '{username}' logged out securely.")

        with self.lock:
            self.clients.pop(client, None)

        try:
            client.close()
        except:
            pass

    # ------------------------------------------------------------ accept

    def accept_clients(self):
        """Continuously accept new client connections."""
        print(f"\nServer listening on {HOST}:{PORT}")
        print("Waiting for clients...\n")

        while True:
            try:
                client, address = self.socket.accept()
                
                # Receive credentials
                try:
                    credentials = client.recv(RECV_BUFFER).decode().strip()
                except:
                    client.close()
                    continue
                    
                if not credentials or "\\n" not in credentials:
                    # In python strings from network, split by \n
                    if "\n" in credentials:
                        parts = credentials.split("\n", 1)
                    else:
                        client.send("AUTH_FAIL: Invalid credentials format.\n".encode())
                        client.close()
                        continue
                else:
                    parts = credentials.split("\n", 1)
                
                if len(parts) != 2:
                    client.send("AUTH_FAIL: Username and password required.\n".encode())
                    client.close()
                    continue
                    
                username, password = parts[0].strip(), parts[1].strip()
                
                # Input validation
                if not username or " " in username or not password:
                    client.send("AUTH_FAIL: Invalid username or empty password.\n".encode())
                    client.close()
                    continue

                # Check failed login protection
                if username in self.failed_attempts:
                    info = self.failed_attempts[username]
                    if info["count"] >= MAX_FAILED_ATTEMPTS:
                        if time.time() - info["timestamp"] < LOCKOUT_DURATION:
                            client.send(f"AUTH_FAIL: Account temporarily locked out. Try again later.\n".encode())
                            self.log_security("LOGIN_REJECTED", f"User '{username}' blocked due to too many failed attempts (IP: {address[0]}).")
                            client.close()
                            continue
                        else:
                            # Reset after duration
                            self.failed_attempts[username] = {"count": 0, "timestamp": 0}

                # Authentication
                hashed_pw = self.hash_password(password)
                with self.lock:
                    if username in self.user_db:
                        if self.user_db[username] != hashed_pw:
                            # Failed attempt
                            if username not in self.failed_attempts:
                                self.failed_attempts[username] = {"count": 0, "timestamp": 0}
                            self.failed_attempts[username]["count"] += 1
                            self.failed_attempts[username]["timestamp"] = time.time()
                            
                            client.send("AUTH_FAIL: Incorrect password.\n".encode())
                            self.log_security("LOGIN_FAILED", f"Failed login for '{username}' from IP {address[0]}.")
                            client.close()
                            continue
                    else:
                        # Auto-register new user
                        self.save_user(username, hashed_pw)
                        self.log_security("USER_REGISTERED", f"New user '{username}' registered.")
                        
                # Check for duplicate login
                duplicate = False
                with self.lock:
                    for existing_client, info in self.clients.items():
                        if info["username"] == username and info["status"] == "Online":
                            duplicate = True
                            break
                            
                if duplicate:
                    client.send("AUTH_FAIL: User already logged in from another location.\n".encode())
                    self.log_security("LOGIN_REJECTED", f"Duplicate login attempt for '{username}' from IP {address[0]}.")
                    client.close()
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
                        "last_activity": time.time()
                    }

                client.send("AUTH_SUCCESS\n".encode())
                
                online_count = len([c for c in self.clients.values() if c["status"] == "Online"])
                print(f"{username} connected from {address[0]} (Online: {online_count})")
                self.log_connection("CONNECTED", username, address[0])
                self.log_security("LOGIN_SUCCESS", f"User '{username}' logged in successfully from IP {address[0]}.")
                
                self.send_last_messages(client)
                self.broadcast_system(f"\n*** {username} joined the chat ***\n")
                self.broadcast_userlist()
                self.show_statistics()

                threading.Thread(target=self.handle_client, args=(client,), daemon=True).start()

            except OSError:
                break
            except Exception as e:
                print(f"Error accepting client: {e}")

    # ------------------------------------------------------------ run

    def run(self):
        print("=" * 50)
        print("   Secure Multi-Client Chat Server (Assignment 7)")
        print("=" * 50)
        self.accept_clients()


if __name__ == "__main__":
    server = ChatServer(HOST, PORT)
    server.run()
