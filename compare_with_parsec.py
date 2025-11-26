#!/usr/bin/env python3
"""
Compare cache replacement policies using memory-intensive benchmarks.
This version uses longer-running workloads to show real differences.

Usage:
    python3 compare_with_parsec.py [--max-insts <N>] [--quick]
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Parse arguments
parser = argparse.ArgumentParser(
    description="Compare cache replacement policies with memory benchmarks"
)
parser.add_argument(
    "--max-insts",
    type=int,
    default=1_000_000_000,  # 1 billion instructions - should show differences
    help="Maximum instructions per run (default: 1B)",
)
parser.add_argument(
    "--quick",
    action="store_true",
    help="Quick test with 100M instructions",
)
parser.add_argument(
    "--gem5-bin",
    type=str,
    default="./build/X86/gem5.opt",
    help="Path to gem5 binary",
)
parser.add_argument(
    "--output-dir",
    type=str,
    default="./parsec_results",
    help="Output directory",
)

args = parser.parse_args()

if args.quick:
    args.max_insts = 100_000_000  # 100M for quick testing

# Validate gem5 binary
if not os.path.exists(args.gem5_bin):
    print(f"Error: gem5 binary not found at {args.gem5_bin}")
    print("Please build gem5 first with: scons build/X86/gem5.opt -j$(nproc)")
    sys.exit(1)

# Create output directory
output_dir = Path(args.output_dir)
output_dir.mkdir(exist_ok=True)

print("=" * 80)
print("Cache Replacement Policy Comparison")
print("=" * 80)
print(f"Workload: memory_benchmark")
print(f"Max Instructions: {args.max_insts:,}")
print(f"Output Directory: {output_dir}")
print("=" * 80)

policies = ["LRU", "AIP", "LvP"]
results = {}

for policy in policies:
    print(f"\n{'='*80}")
    print(f"Running with {policy} replacement policy...")
    print(f"{'='*80}")

    # Create output directory for this run
    run_dir = output_dir / f"memory_benchmark_{policy}"
    run_dir.mkdir(exist_ok=True)

    # Build command
    cmd = [
        args.gem5_bin,
        "--outdir",
        str(run_dir),
        "configs/example/parsec_simple.py",
        "--workload",
        "memory_benchmark",
        "--replacement-policy",
        policy,
        "--max-insts",
        str(args.max_insts),
    ]

    print(f"Command: {' '.join(cmd)}\n")

    # Run simulation
    try:
        result = subprocess.run(
            cmd,
            capture_output=False,  # Show output in real-time
            text=True,
            timeout=7200,  # 2 hour timeout
        )

        if result.returncode != 0:
            print(
                f"\n⚠ Warning: Simulation exited with code {result.returncode}"
            )
        else:
            print(f"\n✓ Simulation completed successfully")

        # Parse stats
        stats_file = run_dir / "stats.txt"
        if stats_file.exists():
            results[policy] = parse_stats(stats_file)
            print(f"\nQuick Stats:")
            print(f"  IPC: {results[policy].get('ipc', 'N/A'):.4f}")
            print(
                f"  L2 Miss Rate: {results[policy].get('l2_miss_rate', 'N/A'):.2%}"
            )
            print(
                f"  L2 Accesses: {results[policy].get('l2_accesses', 'N/A'):,}"
            )
            print(
                f"  Simulation Ticks: {results[policy].get('sim_ticks', 'N/A'):,}"
            )
        else:
            print(f"\n⚠ Warning: stats.txt not found")
            results[policy] = None

    except subprocess.TimeoutExpired:
        print(f"\n✗ Timeout after 2 hours")
        results[policy] = None
    except Exception as e:
        print(f"\n✗ Error: {e}")
        results[policy] = None

# Save results
summary_file = output_dir / "comparison_summary.json"
with open(summary_file, "w") as f:
    json.dump(results, f, indent=2)

print(f"\n\n{'='*80}")
print("PERFORMANCE COMPARISON")
print(f"{'='*80}\n")

# Comparison table
print(
    f"{'Policy':<15} {'IPC':<12} {'L2 Misses':<15} {'L2 Miss Rate':<15} {'Ticks':<20}"
)
print("-" * 80)

baseline_ipc = results.get("LRU", {}).get("ipc", 1.0)

for policy in policies:
    stats = results.get(policy)
    if stats:
        ipc = stats.get("ipc", 0)
        misses = stats.get("l2_misses", 0)
        miss_rate = stats.get("l2_miss_rate", 0)
        ticks = stats.get("sim_ticks", 0)
        speedup = (ipc / baseline_ipc) if baseline_ipc > 0 else 0

        speedup_str = f"({speedup:.3f}x)" if policy != "LRU" else ""
        print(
            f"{policy:<15} {ipc:<12.4f} {misses:<15,} {miss_rate*100:<15.2f} {ticks:<20,}"
        )
        if speedup_str:
            print(f"{'':15} {speedup_str}")
    else:
        print(f"{policy:<15} {'N/A':<12} {'N/A':<15} {'N/A':<15} {'N/A':<20}")

print("-" * 80)

# Calculate improvements
if all(results.get(p) for p in policies):
    lru_ipc = results["LRU"]["ipc"]
    aip_ipc = results["AIP"]["ipc"]
    lvp_ipc = results["LvP"]["ipc"]

    aip_improvement = (
        ((aip_ipc - lru_ipc) / lru_ipc * 100) if lru_ipc > 0 else 0
    )
    lvp_improvement = (
        ((lvp_ipc - lru_ipc) / lru_ipc * 100) if lru_ipc > 0 else 0
    )

    print(f"\nPerformance vs LRU:")
    print(f"  AIP: {aip_improvement:+.2f}%")
    print(f"  LvP: {lvp_improvement:+.2f}%")

print(f"\nResults saved to: {summary_file}")
print(f"Individual stats in: {output_dir}/memory_benchmark_<policy>/stats.txt")

# Try to generate visualization
print(f"\n{'='*80}")
print("Generating visualization...")
try:
    visualize_results(results, output_dir)
    print(f"✓ Graphs saved to: {output_dir}/comparison_graphs.png")
except Exception as e:
    print(f"⚠ Could not generate visualization: {e}")

print(f"{'='*80}\n")


def parse_stats(stats_file):
    """Parse gem5 stats.txt file."""
    stats = {}

    with open(stats_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            stat_name = parts[0]
            stat_value = parts[1]

            try:
                if "simTicks" in stat_name:
                    stats["sim_ticks"] = int(stat_value)
                elif "sim_insts" in stat_name or "simInsts" in stat_name:
                    stats["sim_insts"] = int(stat_value)
                elif "system.cpu.ipc" in stat_name:
                    stats["ipc"] = float(stat_value)
                elif "system.l2cache.overallMissRate::total" in stat_name:
                    stats["l2_miss_rate"] = float(stat_value)
                elif "system.l2cache.overallMisses::total" in stat_name:
                    stats["l2_misses"] = int(stat_value)
                elif "system.l2cache.overallAccesses::total" in stat_name:
                    stats["l2_accesses"] = int(stat_value)
            except (ValueError, IndexError):
                continue

    return stats


def visualize_results(results, output_dir):
    """Generate comparison graphs."""
    try:
        import matplotlib

        matplotlib.use("Agg")  # Non-interactive backend
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("matplotlib not available, skipping visualization")
        return

    policies = ["LRU", "AIP", "LvP"]

    # Extract data
    ipc_values = [
        results[p].get("ipc", 0) if results.get(p) else 0 for p in policies
    ]
    miss_rates = [
        results[p].get("l2_miss_rate", 0) * 100 if results.get(p) else 0
        for p in policies
    ]
    l2_misses = [
        results[p].get("l2_misses", 0) if results.get(p) else 0
        for p in policies
    ]

    # Create figure with subplots
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    # IPC comparison
    bars1 = axes[0].bar(
        policies, ipc_values, color=["#3498db", "#e74c3c", "#2ecc71"]
    )
    axes[0].set_ylabel("IPC (Instructions Per Cycle)")
    axes[0].set_title("Performance Comparison")
    axes[0].set_ylim(0, max(ipc_values) * 1.2 if max(ipc_values) > 0 else 1)
    axes[0].grid(axis="y", alpha=0.3)

    # Add value labels on bars
    for bar in bars1:
        height = bar.get_height()
        axes[0].text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{height:.4f}",
            ha="center",
            va="bottom",
        )

    # Miss rate comparison
    bars2 = axes[1].bar(
        policies, miss_rates, color=["#3498db", "#e74c3c", "#2ecc71"]
    )
    axes[1].set_ylabel("L2 Miss Rate (%)")
    axes[1].set_title("L2 Cache Miss Rate")
    axes[1].set_ylim(0, max(miss_rates) * 1.2 if max(miss_rates) > 0 else 1)
    axes[1].grid(axis="y", alpha=0.3)

    for bar in bars2:
        height = bar.get_height()
        axes[1].text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{height:.2f}%",
            ha="center",
            va="bottom",
        )

    # L2 misses comparison
    bars3 = axes[2].bar(
        policies, l2_misses, color=["#3498db", "#e74c3c", "#2ecc71"]
    )
    axes[2].set_ylabel("Total L2 Misses")
    axes[2].set_title("L2 Cache Misses")
    axes[2].set_ylim(0, max(l2_misses) * 1.2 if max(l2_misses) > 0 else 1)
    axes[2].grid(axis="y", alpha=0.3)

    for bar in bars3:
        height = bar.get_height()
        axes[2].text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{int(height):,}",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    plt.suptitle(
        "Cache Replacement Policy Comparison\nMemory-Intensive Benchmark",
        fontsize=14,
        fontweight="bold",
    )
    plt.tight_layout()
    plt.savefig(
        output_dir / "comparison_graphs.png", dpi=300, bbox_inches="tight"
    )
    plt.close()


if __name__ == "__main__":
    pass  # Already executed above
