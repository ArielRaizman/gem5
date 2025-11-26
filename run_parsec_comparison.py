#!/usr/bin/env python3
"""
Automated script to compare cache replacement policies using PARSEC benchmarks.
This will run each policy with PARSEC workloads and generate comparison graphs.

Usage:
    python3 run_parsec_comparison.py [--benchmarks <list>] [--max-insts <N>]
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Parse arguments
parser = argparse.ArgumentParser(
    description="Compare cache replacement policies with PARSEC benchmarks"
)
parser.add_argument(
    "--benchmarks",
    type=str,
    nargs="+",
    default=["blackscholes", "canneal", "streamcluster"],
    help="PARSEC benchmarks to run (default: blackscholes, canneal, streamcluster)",
)
parser.add_argument(
    "--policies",
    type=str,
    nargs="+",
    default=["LRU", "AIP", "LvP"],
    help="Replacement policies to test (default: LRU, AIP, LvP)",
)
parser.add_argument(
    "--max-insts",
    type=int,
    default=100_000_000,  # 100M instructions
    help="Maximum instructions per benchmark (default: 100M)",
)
parser.add_argument(
    "--gem5-bin",
    type=str,
    default="./build/X86/gem5.opt",
    help="Path to gem5 binary",
)
parser.add_argument(
    "--output-base",
    type=str,
    default="./parsec_results",
    help="Base directory for output",
)

args = parser.parse_args()

# Validate gem5 binary exists
if not os.path.exists(args.gem5_bin):
    print(f"Error: gem5 binary not found at {args.gem5_bin}")
    print("Please build gem5 first with: scons build/X86/gem5.opt -j$(nproc)")
    sys.exit(1)

# Create output directory
output_base = Path(args.output_base)
output_base.mkdir(exist_ok=True)

print("=" * 80)
print("PARSEC Cache Replacement Policy Comparison")
print("=" * 80)
print(f"Benchmarks: {', '.join(args.benchmarks)}")
print(f"Policies: {', '.join(args.policies)}")
print(f"Max Instructions: {args.max_insts:,}")
print(f"Output Directory: {output_base}")
print("=" * 80)

# Store results
results = {}

# Run each combination
total_runs = len(args.benchmarks) * len(args.policies)
current_run = 0

for benchmark in args.benchmarks:
    results[benchmark] = {}

    for policy in args.policies:
        current_run += 1
        print(
            f"\n[{current_run}/{total_runs}] Running {benchmark} with {policy}..."
        )

        # Create output directory for this run
        run_dir = output_base / f"{benchmark}_{policy}"
        run_dir.mkdir(exist_ok=True)

        # Build command
        cmd = [
            args.gem5_bin,
            "--outdir",
            str(run_dir),
            "configs/example/parsec_cache_replacement.py",
            "--benchmark",
            benchmark,
            "--replacement-policy",
            policy,
            "--max-insts",
            str(args.max_insts),
        ]

        # Run simulation
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout
            )

            if result.returncode != 0:
                print(
                    f"  ⚠ Warning: Simulation exited with code {result.returncode}"
                )
                print(f"  stderr: {result.stderr[:200]}")
            else:
                print(f"  ✓ Completed successfully")

            # Parse stats
            stats_file = run_dir / "stats.txt"
            if stats_file.exists():
                stats = parse_stats(stats_file)
                results[benchmark][policy] = stats
                print(
                    f"  Stats: IPC={stats.get('ipc', 'N/A'):.4f}, "
                    f"L2 Miss Rate={stats.get('l2_miss_rate', 'N/A'):.2%}"
                )
            else:
                print(f"  ⚠ Warning: stats.txt not found")
                results[benchmark][policy] = None

        except subprocess.TimeoutExpired:
            print(f"  ✗ Timeout after 1 hour")
            results[benchmark][policy] = None
        except Exception as e:
            print(f"  ✗ Error: {e}")
            results[benchmark][policy] = None

# Save results summary
summary_file = output_base / "comparison_summary.json"
with open(summary_file, "w") as f:
    json.dump(results, f, indent=2)

print(f"\n{'='*80}")
print(f"Results saved to: {summary_file}")
print(f"{'='*80}\n")

# Generate comparison table
print("\nPerformance Summary:")
print("-" * 80)
print(
    f"{'Benchmark':<20} {'Policy':<10} {'IPC':<10} {'L2 Miss Rate':<15} {'Ticks':<15}"
)
print("-" * 80)

for benchmark in args.benchmarks:
    for policy in args.policies:
        stats = results[benchmark].get(policy)
        if stats:
            ipc = stats.get("ipc", 0)
            miss_rate = stats.get("l2_miss_rate", 0)
            ticks = stats.get("sim_ticks", 0)
            print(
                f"{benchmark:<20} {policy:<10} {ipc:<10.4f} {miss_rate:<15.2%} {ticks:<15,}"
            )
        else:
            print(
                f"{benchmark:<20} {policy:<10} {'N/A':<10} {'N/A':<15} {'N/A':<15}"
            )

print("-" * 80)

# Visualization
print("\nGenerating visualization...")
try:
    visualize_results(results, output_base)
    print(f"✓ Graphs saved to: {output_base}/comparison_graphs.png")
except Exception as e:
    print(f"⚠ Could not generate visualization: {e}")

print("\n" + "=" * 80)
print("Comparison complete!")
print("=" * 80)


def parse_stats(stats_file):
    """Parse gem5 stats.txt file and extract key metrics."""
    stats = {}

    with open(stats_file) as f:
        content = f.read()

        # Extract simulation ticks
        for line in content.split("\n"):
            if line.startswith("simTicks"):
                stats["sim_ticks"] = int(line.split()[1])
            elif line.startswith("sim_insts"):
                stats["sim_insts"] = int(line.split()[1])
            elif line.startswith("system.cpu.ipc"):
                stats["ipc"] = float(line.split()[1])
            elif "system.l2cache.overallMissRate::total" in line:
                stats["l2_miss_rate"] = float(line.split()[1])
            elif "system.l2cache.overallMisses::total" in line:
                stats["l2_misses"] = int(line.split()[1])
            elif "system.l2cache.overallAccesses::total" in line:
                stats["l2_accesses"] = int(line.split()[1])

    return stats


def visualize_results(results, output_dir):
    """Generate comparison graphs using matplotlib."""
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("matplotlib not available, skipping visualization")
        return

    benchmarks = list(results.keys())
    policies = ["LRU", "AIP", "LvP"]

    # Prepare data
    ipc_data = {policy: [] for policy in policies}
    miss_rate_data = {policy: [] for policy in policies}

    for benchmark in benchmarks:
        for policy in policies:
            stats = results[benchmark].get(policy)
            if stats:
                ipc_data[policy].append(stats.get("ipc", 0))
                miss_rate_data[policy].append(
                    stats.get("l2_miss_rate", 0) * 100
                )
            else:
                ipc_data[policy].append(0)
                miss_rate_data[policy].append(0)

    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # IPC comparison
    x = np.arange(len(benchmarks))
    width = 0.25

    for i, policy in enumerate(policies):
        axes[0].bar(x + i * width, ipc_data[policy], width, label=policy)

    axes[0].set_ylabel("IPC")
    axes[0].set_title("IPC Comparison by Benchmark")
    axes[0].set_xticks(x + width)
    axes[0].set_xticklabels(benchmarks, rotation=45, ha="right")
    axes[0].legend()
    axes[0].grid(axis="y", alpha=0.3)

    # Miss rate comparison
    for i, policy in enumerate(policies):
        axes[1].bar(x + i * width, miss_rate_data[policy], width, label=policy)

    axes[1].set_ylabel("L2 Miss Rate (%)")
    axes[1].set_title("L2 Cache Miss Rate by Benchmark")
    axes[1].set_xticks(x + width)
    axes[1].set_xticklabels(benchmarks, rotation=45, ha="right")
    axes[1].legend()
    axes[1].grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(
        output_dir / "comparison_graphs.png", dpi=300, bbox_inches="tight"
    )
    plt.close()


if __name__ == "__main__":
    pass  # Already executed above
