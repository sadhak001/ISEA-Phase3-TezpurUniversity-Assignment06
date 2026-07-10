import socket
import threading
import time
import csv
import os
from datetime import datetime

HOST = "10.0.0.1"
PORT = 5000
RECV_BUFFER = 1024

CHAT_LOG = "chat_log.csv"
CONNECTION_LOG = "connection_log.csv"


class ChatServer:
    def __init__(self, host, port):
        self.clients = {}          # socket -> {username, ip, port, login_time, status}
        self.lock = threading.Lock()
        self.chat_history = []     # recent messages, shown to newly joined clients

        self.message_count = 0
        self.broadcast_count = 0
        self.private_count = 0

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((host, port))
        self.socket.listen()

    # ---------------------------------------------------------- utilities

    @staticmethod
    def timestamp():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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

                message = data.decode().strip()

                print(f"[{username}] {message}")

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

        with self.lock:
            self.clients.pop(client, None)

        client.close()

    # ------------------------------------------------------------ accept

    def accept_clients(self):
        """Continuously accept new client connections."""
        print(f"\nServer listening on {HOST}:{PORT}")
        print("Waiting for clients...\n")

        while True:
            try:
                client, address = self.socket.accept()
                username = client.recv(RECV_BUFFER).decode().strip()

                with self.lock:
                    self.clients[client] = {
                        "username": username,
                        "ip": address[0],
                        "port": address[1],
                        "login_time": self.timestamp(),
                        "status": "Online",
                    }

                online_count = len([c for c in self.clients.values() if c["status"] == "Online"])
                print(f"{username} connected from {address[0]} (Online: {online_count})")
                self.log_connection("CONNECTED", username, address[0])
                self.send_last_messages(client)
                self.broadcast_system(f"\n*** {username} joined the chat ***\n")
                self.broadcast_userlist()
                self.show_statistics()

                threading.Thread(target=self.handle_client, args=(client,), daemon=True).start()

            except OSError:
                break

    # ------------------------------------------------------------ run

    def run(self):
        print("=" * 50)
        print("   Multi-Client Chat Server (Assignment 6)")
        print("=" * 50)
        self.accept_clients()


if __name__ == "__main__":
    server = ChatServer(HOST, PORT)
    server.run()
