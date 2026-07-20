"""
Graph Generation Script
Assignment 8 - Reads performance_results.csv and creates comparison graphs

Usage:
    python3 generate_graphs.py
"""

import csv
import os

try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt
except ImportError:
    print("matplotlib is required. Install it with: pip3 install matplotlib")
    exit(1)

CSV_FILE = "performance_results.csv"
GRAPHS_DIR = "graphs"


def load_results():
    """Load benchmark results from CSV."""
    if not os.path.exists(CSV_FILE):
        print(f"Error: {CSV_FILE} not found. Run benchmark.py first.")
        exit(1)

    results = []
    with open(CSV_FILE, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append({
                "clients": int(row["clients"]),
                "avg_delay_ms": float(row["avg_delay_ms"]),
                "max_delay_ms": float(row["max_delay_ms"]),
                "throughput_msg_s": float(row["throughput_msg_s"]),
                "avg_cpu_percent": float(row["avg_cpu_percent"]),
                "avg_memory_mb": float(row["avg_memory_mb"]),
            })
    return results


def create_graphs(results):
    """Generate and save comparison graphs."""
    os.makedirs(GRAPHS_DIR, exist_ok=True)

    clients = [r["clients"] for r in results]
    x_labels = [f"{c} Clients" for c in clients]

    # Graph 1: Average Message Delay
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(x_labels, [r["avg_delay_ms"] for r in results],
                  color=["#4CAF50", "#FF9800", "#F44336"], edgecolor="black")
    ax.set_title("Average Message Delay vs Number of Clients", fontsize=14, fontweight="bold")
    ax.set_xlabel("Number of Clients")
    ax.set_ylabel("Average Delay (ms)")
    for bar, val in zip(bars, [r["avg_delay_ms"] for r in results]):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                f"{val:.3f}", ha="center", va="bottom", fontweight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(GRAPHS_DIR, "avg_delay.png"), dpi=150)
    plt.close()
    print("  Created: avg_delay.png")

    # Graph 2: Throughput
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(x_labels, [r["throughput_msg_s"] for r in results],
                  color=["#2196F3", "#9C27B0", "#E91E63"], edgecolor="black")
    ax.set_title("Throughput vs Number of Clients", fontsize=14, fontweight="bold")
    ax.set_xlabel("Number of Clients")
    ax.set_ylabel("Throughput (messages/sec)")
    for bar, val in zip(bars, [r["throughput_msg_s"] for r in results]):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                f"{val:.1f}", ha="center", va="bottom", fontweight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(GRAPHS_DIR, "throughput.png"), dpi=150)
    plt.close()
    print("  Created: throughput.png")

    # Graph 3: CPU Usage
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(x_labels, [r["avg_cpu_percent"] for r in results],
                  color=["#00BCD4", "#CDDC39", "#FF5722"], edgecolor="black")
    ax.set_title("CPU Usage vs Number of Clients", fontsize=14, fontweight="bold")
    ax.set_xlabel("Number of Clients")
    ax.set_ylabel("CPU Usage (%)")
    for bar, val in zip(bars, [r["avg_cpu_percent"] for r in results]):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
                f"{val:.1f}%", ha="center", va="bottom", fontweight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(GRAPHS_DIR, "cpu_usage.png"), dpi=150)
    plt.close()
    print("  Created: cpu_usage.png")

    # Graph 4: Memory Usage
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(x_labels, [r["avg_memory_mb"] for r in results],
                  color=["#673AB7", "#3F51B5", "#009688"], edgecolor="black")
    ax.set_title("Memory Usage vs Number of Clients", fontsize=14, fontweight="bold")
    ax.set_xlabel("Number of Clients")
    ax.set_ylabel("Memory Usage (MB)")
    for bar, val in zip(bars, [r["avg_memory_mb"] for r in results]):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                f"{val:.1f}", ha="center", va="bottom", fontweight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(GRAPHS_DIR, "memory_usage.png"), dpi=150)
    plt.close()
    print("  Created: memory_usage.png")

    # Graph 5: Combined Overview
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Assignment 8 - Performance Evaluation Summary",
                 fontsize=16, fontweight="bold")

    # Delay
    axes[0, 0].bar(x_labels, [r["avg_delay_ms"] for r in results],
                    color=["#4CAF50", "#FF9800", "#F44336"])
    axes[0, 0].set_title("Avg Message Delay (ms)")
    axes[0, 0].set_ylabel("ms")

    # Throughput
    axes[0, 1].bar(x_labels, [r["throughput_msg_s"] for r in results],
                    color=["#2196F3", "#9C27B0", "#E91E63"])
    axes[0, 1].set_title("Throughput (msg/s)")
    axes[0, 1].set_ylabel("msg/s")

    # CPU
    axes[1, 0].bar(x_labels, [r["avg_cpu_percent"] for r in results],
                    color=["#00BCD4", "#CDDC39", "#FF5722"])
    axes[1, 0].set_title("CPU Usage (%)")
    axes[1, 0].set_ylabel("%")

    # Memory
    axes[1, 1].bar(x_labels, [r["avg_memory_mb"] for r in results],
                    color=["#673AB7", "#3F51B5", "#009688"])
    axes[1, 1].set_title("Memory Usage (MB)")
    axes[1, 1].set_ylabel("MB")

    plt.tight_layout()
    plt.savefig(os.path.join(GRAPHS_DIR, "performance_summary.png"), dpi=150)
    plt.close()
    print("  Created: performance_summary.png")


def main():
    print("Assignment 8 - Graph Generation")
    print(f"Reading data from {CSV_FILE}...")
    results = load_results()
    print(f"Found {len(results)} data points.")
    print("\nGenerating graphs...")
    create_graphs(results)
    print(f"\nAll graphs saved to {GRAPHS_DIR}/ directory.")


if __name__ == "__main__":
    main()
