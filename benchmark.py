"""
Performance Benchmark Script
Assignment 8 - Measures delay, throughput, CPU and memory usage

Usage:
    Start the server first, then run:
    python3 benchmark.py [server_ip] [password]

    Defaults: server_ip=10.0.0.1, password=benchpass
"""

import socket
import time
import csv
import sys
import os
import threading
import json


def load_config():
    defaults = {"port": 5000, "recv_buffer": 4096}
    try:
        with open("config.json", "r") as f:
            cfg = json.load(f)
        client_cfg = cfg.get("client", {})
        defaults["port"] = client_cfg.get("port", defaults["port"])
        defaults["recv_buffer"] = client_cfg.get("recv_buffer", defaults["recv_buffer"])
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return defaults


CONFIG = load_config()
SERVER_IP = sys.argv[1] if len(sys.argv) > 1 else "10.0.0.1"
PASSWORD = sys.argv[2] if len(sys.argv) > 2 else "benchpass"
MESSAGES_PER_CLIENT = 20
CSV_FILE = "performance_results.csv"


def create_client(username):
    """Connect and authenticate a single benchmark client."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    s.connect((SERVER_IP, CONFIG["port"]))
    s.send(f"{username}\n{PASSWORD}".encode())
    resp = s.recv(CONFIG["recv_buffer"]).decode().strip()
    if "AUTH_SUCCESS" not in resp:
        raise Exception(f"Auth failed for {username}: {resp}")
    s.settimeout(None)
    return s


def drain_receiver(sock, stop_event):
    """Background thread to drain incoming messages so the socket buffer doesn't block."""
    while not stop_event.is_set():
        try:
            sock.settimeout(0.5)
            data = sock.recv(CONFIG["recv_buffer"])
            if not data:
                break
        except socket.timeout:
            continue
        except OSError:
            break


def run_benchmark(num_clients):
    """Run a benchmark with the specified number of concurrent clients."""
    print(f"\n{'='*50}")
    print(f"  Benchmark: {num_clients} concurrent clients")
    print(f"  Messages per client: {MESSAGES_PER_CLIENT}")
    print(f"{'='*50}")

    sockets = []
    drainers = []
    stop_events = []

    # Connect all clients
    print(f"Connecting {num_clients} clients...")
    for i in range(num_clients):
        username = f"bench_user_{i}"
        try:
            s = create_client(username)
            sockets.append(s)
            stop_event = threading.Event()
            stop_events.append(stop_event)
            t = threading.Thread(target=drain_receiver, args=(s, stop_event), daemon=True)
            t.start()
            drainers.append(t)
            print(f"  Connected: {username}")
        except Exception as e:
            print(f"  Failed to connect {username}: {e}")

    if not sockets:
        print("No clients connected. Aborting benchmark.")
        return None

    time.sleep(1)  # Let connections stabilize

    actual_clients = len(sockets)
    total_messages = actual_clients * MESSAGES_PER_CLIENT

    # Measure CPU and memory before
    try:
        import psutil
        process = psutil.Process(os.getpid())
        cpu_before = psutil.cpu_percent(interval=0.5)
        mem_before = process.memory_info().rss / (1024 * 1024)  # MB
    except ImportError:
        cpu_before = 0
        mem_before = 0

    # Send messages and measure delay
    print(f"Sending {total_messages} total messages...")
    delays = []
    start_time = time.time()

    for s in sockets:
        for j in range(MESSAGES_PER_CLIENT):
            msg = f"Benchmark message {j}"
            send_time = time.time()
            try:
                s.send(msg.encode())
                delay = time.time() - send_time
                delays.append(delay)
            except (OSError, BrokenPipeError):
                pass

    end_time = time.time()
    elapsed = end_time - start_time

    # Measure CPU and memory after
    try:
        import psutil
        cpu_after = psutil.cpu_percent(interval=0.5)
        mem_after = process.memory_info().rss / (1024 * 1024)  # MB
    except ImportError:
        cpu_after = 0
        mem_after = 0

    # Calculate results
    avg_delay = sum(delays) / len(delays) if delays else 0
    max_delay = max(delays) if delays else 0
    throughput = total_messages / elapsed if elapsed > 0 else 0
    avg_cpu = (cpu_before + cpu_after) / 2
    avg_mem = (mem_before + mem_after) / 2

    print(f"\nResults for {actual_clients} clients:")
    print(f"  Total time:     {elapsed:.3f} s")
    print(f"  Avg delay:      {avg_delay*1000:.3f} ms")
    print(f"  Max delay:      {max_delay*1000:.3f} ms")
    print(f"  Throughput:     {throughput:.1f} msg/s")
    print(f"  Avg CPU:        {avg_cpu:.1f}%")
    print(f"  Avg Memory:     {avg_mem:.1f} MB")

    # Cleanup
    for stop_event in stop_events:
        stop_event.set()
    for s in sockets:
        try:
            s.send("/logout\n".encode())
            time.sleep(0.05)
            s.close()
        except OSError:
            pass

    time.sleep(1)  # Let server process disconnections

    return {
        "clients": actual_clients,
        "total_messages": total_messages,
        "elapsed_s": round(elapsed, 3),
        "avg_delay_ms": round(avg_delay * 1000, 3),
        "max_delay_ms": round(max_delay * 1000, 3),
        "throughput_msg_s": round(throughput, 1),
        "avg_cpu_percent": round(avg_cpu, 1),
        "avg_memory_mb": round(avg_mem, 1),
    }


def main():
    print("Assignment 8 - Performance Benchmark")
    print(f"Server: {SERVER_IP}:{CONFIG['port']}")

    results = []
    for n in [5, 8, 10]:
        result = run_benchmark(n)
        if result:
            results.append(result)
        time.sleep(2)

    if not results:
        print("\nNo results collected.")
        return

    # Write CSV
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults saved to {CSV_FILE}")
    print("Run generate_graphs.py to create visualizations.")


if __name__ == "__main__":
    main()
