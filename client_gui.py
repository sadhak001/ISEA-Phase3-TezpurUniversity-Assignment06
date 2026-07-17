"""
GUI-Based Multi-Client Chat Application (Client)
Assignment 7 - Secure Network Application Development

Modules used: tkinter, tkinter.ttk, tkinter.scrolledtext, threading, socket, time
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import socket
import time


PORT = 5000
RECV_BUFFER = 4096


class ChatClient:
    """
    Handles all TCP socket communication.
    Networking logic kept separate from GUI code.
    Updated for Assignment 7 to support authentication.
    """

    def __init__(self):
        self.socket = None
        self.connected = False
        self.username = ""

    def connect(self, server_ip, username, password):
        """Connect to the chat server and send credentials."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((server_ip, PORT))
        self.username = username
        
        # Send credentials
        credentials = f"{username}\n{password}"
        self.socket.send(credentials.encode())
        
        # Wait for authentication response
        response = self.socket.recv(RECV_BUFFER).decode().strip()
        
        if response == "AUTH_SUCCESS":
            self.connected = True
        else:
            self.socket.close()
            self.socket = None
            if response.startswith("AUTH_FAIL:"):
                raise Exception(response[10:].strip())
            else:
                raise Exception(f"Unknown response from server: {response}")

    def send_message(self, message):
        """Send a message to the server."""
        if self.connected and self.socket:
            self.socket.send(message.encode())

    def receive_message(self):
        """Receive a message from the server (blocking call)."""
        if self.connected and self.socket:
            return self.socket.recv(RECV_BUFFER).decode()
        return ""

    def disconnect(self):
        """Close the connection."""
        if self.connected and self.socket:
            try:
                self.socket.send("/logout\n".encode())
                time.sleep(0.1) # Give it a moment to send
                self.socket.close()
            except OSError:
                pass
        self.connected = False
        self.socket = None


class LoginWindow:
    """
    GUI Login Window.
    Widgets used: Tk, Frame, Label, Entry, Button, StringVar, Messagebox
    """

    def __init__(self, root):
        self.root = root
        self.root.title("Chat Application - Login")
        self.root.geometry("400x320")
        self.root.resizable(False, False)

        self.client = ChatClient()

        # ---- StringVar for Entry widgets ----
        self.server_ip_var = tk.StringVar(value="10.0.0.1")
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()

        self._build_ui()

    def _build_ui(self):
        """Build the login form using Frames, Labels, Entry boxes, and Buttons."""

        # --- Title Frame ---
        title_frame = tk.Frame(self.root)
        title_frame.pack(pady=15)

        tk.Label(title_frame, text="Secure Multi-Client Chat",
                 font=("Arial", 16, "bold")).pack()
        tk.Label(title_frame, text="Assignment 7 - Security Implementation",
                 font=("Arial", 9)).pack()

        # --- Form Frame ---
        form_frame = tk.Frame(self.root)
        form_frame.pack(pady=10, padx=30)

        # Server IP
        tk.Label(form_frame, text="Server IP:", font=("Arial", 10)).grid(
            row=0, column=0, sticky="w", pady=5)
        tk.Entry(form_frame, textvariable=self.server_ip_var, width=25,
                 font=("Arial", 10)).grid(row=0, column=1, pady=5, padx=5)

        # Username
        tk.Label(form_frame, text="Username:", font=("Arial", 10)).grid(
            row=1, column=0, sticky="w", pady=5)
        self.username_entry = tk.Entry(form_frame, textvariable=self.username_var,
                                        width=25, font=("Arial", 10))
        self.username_entry.grid(row=1, column=1, pady=5, padx=5)

        # Password
        tk.Label(form_frame, text="Password:", font=("Arial", 10)).grid(
            row=2, column=0, sticky="w", pady=5)
        tk.Entry(form_frame, textvariable=self.password_var, show="*",
                 width=25, font=("Arial", 10)).grid(row=2, column=1, pady=5, padx=5)

        # --- Button Frame ---
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=10)

        self.connect_btn = tk.Button(btn_frame, text="Connect / Register", font=("Arial", 11, "bold"),
                                      width=20, command=self.on_connect)
        self.connect_btn.pack()

        # --- Status Label ---
        self.status_label = tk.Label(self.root, text="", font=("Arial", 9))
        self.status_label.pack(pady=5)

        # Bind Enter key to connect
        self.root.bind("<Return>", lambda e: self.on_connect())
        self.username_entry.focus_set()

    def on_connect(self):
        """Validate input and attempt connection."""
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        server_ip = self.server_ip_var.get().strip()

        # --- Input validation ---
        if not username:
            messagebox.showerror("Error", "Username cannot be empty!")
            return
            
        if not password:
            messagebox.showerror("Error", "Password cannot be empty!")
            return

        if not server_ip:
            messagebox.showerror("Error", "Server IP cannot be empty!")
            return

        if " " in username:
            messagebox.showerror("Error", "Username cannot contain spaces!")
            return

        # --- Attempt connection ---
        self.status_label.config(text="Connecting and Authenticating...", fg="orange")
        self.connect_btn.config(state="disabled")
        self.root.update()

        try:
            self.client.connect(server_ip, username, password)
            self.status_label.config(text="Connected!", fg="green")
            self.root.after(500, self._open_chat_window)
        except ConnectionRefusedError:
            messagebox.showerror("Connection Failed",
                                 "Server is not running or refused the connection.")
            self.status_label.config(text="Connection refused.", fg="red")
            self.connect_btn.config(state="normal")
        except socket.gaierror:
            messagebox.showerror("Connection Failed",
                                 f"Invalid server address: {server_ip}")
            self.status_label.config(text="Invalid address.", fg="red")
            self.connect_btn.config(state="normal")
        except Exception as e:
            messagebox.showerror("Authentication Failed", str(e))
            self.status_label.config(text="Authentication failed.", fg="red")
            self.connect_btn.config(state="normal")

    def _open_chat_window(self):
        """Destroy login window and open the chat window."""
        self.root.destroy()
        chat_root = tk.Tk()
        ChatWindow(chat_root, self.client)
        chat_root.mainloop()


class ChatWindow:
    """
    Main Chat Interface.
    Widgets used: Tk, Frame, Label, Entry, Button, Listbox, ScrolledText,
                  Scrollbar, StringVar, Messagebox
    """

    def __init__(self, root, client):
        self.root = root
        self.client = client
        self.root.title(f"Secure Chat - {client.username}")
        self.root.geometry("750x500")
        self.root.minsize(600, 400)

        self.message_var = tk.StringVar()
        self.online_users = []

        self._build_ui()
        self._start_receive_thread()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_disconnect)

    def _build_ui(self):
        """Build the chat interface using Frames and widgets."""

        # ============================================================
        # TOP FRAME - Title and Status
        # ============================================================
        top_frame = tk.Frame(self.root, bd=1, relief="raised")
        top_frame.pack(fill="x", padx=5, pady=(5, 0))

        tk.Label(top_frame, text=f"  Logged in as: {self.client.username}",
                 font=("Arial", 10, "bold")).pack(side="left", padx=5, pady=3)

        self.status_label = tk.Label(top_frame, text=" ● Connected ",
                                      font=("Arial", 10), fg="green")
        self.status_label.pack(side="right", padx=5, pady=3)

        # ============================================================
        # CENTER FRAME - Chat Area + Online Users
        # ============================================================
        center_frame = tk.Frame(self.root)
        center_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # --- Chat messages (left side) ---
        chat_frame = tk.Frame(center_frame)
        chat_frame.pack(side="left", fill="both", expand=True)

        self.chat_area = scrolledtext.ScrolledText(
            chat_frame, wrap="word", state="disabled",
            font=("Courier", 10), bg="#f5f5f5"
        )
        self.chat_area.pack(fill="both", expand=True)

        # --- Online users panel (right side) ---
        users_frame = tk.Frame(center_frame, width=160, bd=1, relief="sunken")
        users_frame.pack(side="right", fill="y", padx=(5, 0))
        users_frame.pack_propagate(False)

        tk.Label(users_frame, text="Online Users",
                 font=("Arial", 10, "bold")).pack(pady=(5, 2))

        # Listbox with Scrollbar
        listbox_frame = tk.Frame(users_frame)
        listbox_frame.pack(fill="both", expand=True, padx=3, pady=3)

        self.users_scrollbar = tk.Scrollbar(listbox_frame)
        self.users_scrollbar.pack(side="right", fill="y")

        self.users_listbox = tk.Listbox(
            listbox_frame, font=("Arial", 10),
            yscrollcommand=self.users_scrollbar.set,
            selectmode="single"
        )
        self.users_listbox.pack(fill="both", expand=True)
        self.users_scrollbar.config(command=self.users_listbox.yview)

        # Double-click on user to start private message
        self.users_listbox.bind("<Double-Button-1>", self.on_user_double_click)

        # ============================================================
        # BOTTOM FRAME - Message Input + Buttons
        # ============================================================
        bottom_frame = tk.Frame(self.root, bd=1, relief="raised")
        bottom_frame.pack(fill="x", padx=5, pady=(0, 5))

        self.message_entry = tk.Entry(
            bottom_frame, textvariable=self.message_var,
            font=("Arial", 11)
        )
        self.message_entry.pack(side="left", fill="x", expand=True, padx=5, pady=5)

        self.send_btn = tk.Button(
            bottom_frame, text="Send", font=("Arial", 10, "bold"),
            width=8, command=self.on_send
        )
        self.send_btn.pack(side="left", padx=(0, 5), pady=5)

        self.disconnect_btn = tk.Button(
            bottom_frame, text="Disconnect / Logout", font=("Arial", 10),
            width=18, command=self.on_disconnect
        )
        self.disconnect_btn.pack(side="left", padx=(0, 5), pady=5)

        # Bind Enter key to send
        self.message_entry.bind("<Return>", lambda e: self.on_send())
        self.message_entry.focus_set()

    # -------------------------------------------------------- sending

    def on_send(self):
        """Send the message typed in the entry box."""
        message = self.message_var.get().strip()
        if not message:
            return

        if not self.client.connected:
            messagebox.showwarning("Disconnected",
                                   "You are not connected to the server.")
            return

        try:
            self.client.send_message(message)

            # Display own broadcast message locally
            if not message.startswith("/"):
                self.append_chat(f"[You] {message}\n")
            elif message == "/list" or message == "/users":
                pass  # response will come from server
            elif message == "/logout":
                self.on_disconnect()
                return
            # /msg echoes are handled by server response

        except Exception:
            self.append_chat("*** Failed to send message ***\n")

        self.message_var.set("")
        self.message_entry.focus_set()

    def on_user_double_click(self, event):
        """Pre-fill /msg <username> when a user is double-clicked."""
        selection = self.users_listbox.curselection()
        if selection:
            selected_user = self.users_listbox.get(selection[0])
            if selected_user != self.client.username:
                self.message_var.set(f"/msg {selected_user} ")
                self.message_entry.focus_set()
                self.message_entry.icursor("end")

    # -------------------------------------------------------- receiving

    def _start_receive_thread(self):
        """Start a background thread to receive messages from the server."""
        receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        receive_thread.start()

    def _receive_loop(self):
        """
        Background thread: continuously receive messages from the server.
        Uses root.after() to safely update the GUI from a non-main thread.
        This keeps the GUI responsive.
        """
        buffer = ""
        while self.client.connected:
            try:
                data = self.client.receive_message()
                if not data:
                    break

                buffer += data
                # Split into individual lines
                lines = buffer.split("\n")
                # Last element may be incomplete — keep it in the buffer
                buffer = lines.pop()

                for line in lines:
                    line = line.strip()
                    if line:
                        self.root.after(0, self._process_line, line)

            except OSError:
                break
            except Exception:
                break

        # Process any remaining data in the buffer
        if buffer.strip():
            self.root.after(0, self._process_line, buffer.strip())

        # Connection lost
        self.root.after(0, self._on_connection_lost)

    def _process_line(self, line):
        """Process a single line/message from the server."""
        
        if line == "TIMEOUT":
            self.append_chat("\n*** Disconnected due to inactivity ***\n")
            return

        if line.startswith("ERROR:"):
            self.append_chat(f"\n*** {line} ***\n")
            return

        # Handle USERLIST protocol message
        if line.startswith("USERLIST:"):
            userlist_str = line[len("USERLIST:"):]
            if userlist_str:
                users = userlist_str.split(",")
            else:
                users = []
            self._update_user_list(users)
            return

        # Display the message in the chat area
        self.append_chat(line + "\n")

    def _update_user_list(self, users):
        """Update the online users Listbox."""
        self.online_users = users
        self.users_listbox.delete(0, tk.END)
        for user in sorted(users):
            self.users_listbox.insert(tk.END, user)

    def _on_connection_lost(self):
        """Handle connection loss."""
        self.client.connected = False
        self.status_label.config(text=" ● Disconnected ", fg="red")
        self.send_btn.config(state="disabled")
        self.append_chat("\n*** Disconnected from server ***\n")
        self.users_listbox.delete(0, tk.END)

    # -------------------------------------------------------- chat area

    def append_chat(self, text):
        """Append text to the chat ScrolledText area and auto-scroll."""
        self.chat_area.config(state="normal")
        self.chat_area.insert(tk.END, text)
        self.chat_area.see(tk.END)  # Auto-scroll to bottom
        self.chat_area.config(state="disabled")

    # -------------------------------------------------------- disconnect

    def on_disconnect(self):
        """Disconnect from server and close the window."""
        if self.client.connected:
            confirm = messagebox.askyesno("Disconnect",
                                           "Are you sure you want to log out and disconnect?")
            if not confirm:
                return

        self.client.disconnect()
        self.root.destroy()


# ================================================================
# Application Entry Point
# ================================================================

if __name__ == "__main__":
    root = tk.Tk()
    LoginWindow(root)
    root.mainloop()
