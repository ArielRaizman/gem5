#!/usr/bin/env python3
"""
Comprehensive comparison of LRU, AIP, and LvP cache replacement policies.
Runs benchmarks and generates detailed comparative analysis graphs.

Usage:
    python3 compare_policies.py [--workloads hello,custom] [--output-dir results]
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Add matplotlib/seaborn for graphing
try:
    import matplotlib.patches as mpatches
    import matplotlib.pyplot as plt
    import numpy as np
    import seaborn as sns
    from matplotlib.gridspec import GridSpec
except ImportError:
    print("ERROR: Required packages not found. Install with:")
    print("  pip install matplotlib seaborn numpy")
    sys.exit(1)

# Set style for professional-looking graphs
sns.set_style("whitegrid")
plt.rcParams["figure.dpi"] = 300
plt.rcParams["savefig.dpi"] = 300
plt.rcParams["font.size"] = 10
plt.rcParams["axes.titlesize"] = 12
plt.rcParams["axes.labelsize"] = 11
plt.rcParams["legend.fontsize"] = 9

# Policies to compare
POLICIES = ["LRU", "AIP", "LvP"]

# Color scheme for policies
COLORS = {
    "LRU": "#3498db",  # Blue
    "AIP": "#e74c3c",  # Red
    "LvP": "#2ecc71",  # Green
}

# Built-in workloads
WORKLOADS = {
    "hello": {
        "path": "tests/test-progs/hello/bin/x86/linux/hello",
        "name": "Hello World",
        "max_insts": 100000,
    },
    "cache_stress": {
        "path": "test_workloads/cache_stress",
        "name": "Cache Stress Test",
        "max_insts": 50000000,  # 50M instructions for meaningful results
    },
}


def run_simulation(policy, workload_path, max_insts, output_dir):
    """Run gem5 simulation for a specific policy and workload."""

    # gem5 uses m5out by default, but we'll redirect it
    policy_dir = Path(f"m5out_{policy.lower()}")

    cmd = [
        "build/X86/gem5.opt",
        f"--outdir={policy_dir}",
        "configs/example/cache_replacement_test.py",
        f"--replacement-policy={policy}",
        f"--benchmark={workload_path}",
        "--fast-forward=0",
        f"--max-insts={max_insts}",
    ]

    print(f"  Running {policy}...", end="", flush=True)
    start_time = time.time()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        elapsed = time.time() - start_time

        if result.returncode != 0:
            print(f" FAILED (exit code {result.returncode})")
            print(f"    Error: {result.stderr[:200]}")
            return None

        print(f" ✓ ({elapsed:.1f}s)")

        # Check if stats file exists
        stats_file = policy_dir / "stats.txt"
        if not stats_file.exists():
            print(f"    Warning: stats.txt not found at {stats_file}")
            return None

        return stats_file

    except subprocess.TimeoutExpired:
        print(" TIMEOUT")
        return None
    except Exception as e:
        print(f" ERROR: {e}")
        return None


def parse_stats(stats_file):
    """Parse gem5 stats.txt file and extract relevant metrics."""

    stats = {}

    try:
        with open(stats_file) as f:
            content = f.read()

        # Helper function to extract stat value
        def get_stat(name, default=0.0):
            for line in content.split("\n"):
                if name in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            return float(parts[1])
                        except ValueError:
                            pass
            return default

        # Extract key metrics
        stats["sim_seconds"] = get_stat("sim_seconds")
        stats["sim_insts"] = get_stat("sim_insts")
        stats["ipc"] = get_stat("ipc")

        # L1 I-Cache
        stats["icache_accesses"] = get_stat(
            "system.cpu.icache.overallAccesses::total"
        )
        stats["icache_hits"] = get_stat("system.cpu.icache.overallHits::total")
        stats["icache_misses"] = get_stat(
            "system.cpu.icache.overallMisses::total"
        )
        stats["icache_miss_rate"] = get_stat(
            "system.cpu.icache.overallMissRate::total"
        )

        # L1 D-Cache
        stats["dcache_accesses"] = get_stat(
            "system.cpu.dcache.overallAccesses::total"
        )
        stats["dcache_hits"] = get_stat("system.cpu.dcache.overallHits::total")
        stats["dcache_misses"] = get_stat(
            "system.cpu.dcache.overallMisses::total"
        )
        stats["dcache_miss_rate"] = get_stat(
            "system.cpu.dcache.overallMissRate::total"
        )

        # L2 Cache
        stats["l2_accesses"] = get_stat(
            "system.l2cache.overallAccesses::total"
        )
        stats["l2_hits"] = get_stat("system.l2cache.overallHits::total")
        stats["l2_misses"] = get_stat("system.l2cache.overallMisses::total")
        stats["l2_miss_rate"] = get_stat(
            "system.l2cache.overallMissRate::total"
        )

        # Memory accesses
        stats["mem_reads"] = get_stat("system.mem_ctrl.num_reads::total")
        stats["mem_writes"] = get_stat("system.mem_ctrl.num_writes::total")

        return stats

    except Exception as e:
        print(f"Error parsing stats: {e}")
        return None


def create_comparison_graphs(results, output_dir):
    """Create comprehensive comparison graphs."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract data for plotting
    policies = list(results.keys())

    # Create figure with multiple subplots
    fig = plt.figure(figsize=(16, 12))
    gs = GridSpec(3, 3, figure=fig, hspace=0.3, wspace=0.3)

    # 1. IPC Comparison (Top Left)
    ax1 = fig.add_subplot(gs[0, 0])
    ipcs = [results[p]["ipc"] for p in policies]
    bars1 = ax1.bar(
        policies,
        ipcs,
        color=[COLORS[p] for p in policies],
        alpha=0.8,
        edgecolor="black",
    )
    ax1.set_ylabel("Instructions Per Cycle (IPC)")
    ax1.set_title("Performance: IPC Comparison", fontweight="bold")
    ax1.grid(axis="y", alpha=0.3)

    # Add value labels on bars
    for bar, val in zip(bars1, ipcs):
        height = bar.get_height()
        ax1.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{val:.3f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    # 2. Speedup vs LRU (Top Middle)
    ax2 = fig.add_subplot(gs[0, 1])
    lru_ipc = results["LRU"]["ipc"]
    speedups = [(results[p]["ipc"] / lru_ipc) for p in policies]
    bars2 = ax2.bar(
        policies,
        speedups,
        color=[COLORS[p] for p in policies],
        alpha=0.8,
        edgecolor="black",
    )
    ax2.axhline(y=1.0, color="gray", linestyle="--", linewidth=1, alpha=0.7)
    ax2.set_ylabel("Speedup (relative to LRU)")
    ax2.set_title("Speedup vs LRU Baseline", fontweight="bold")
    ax2.grid(axis="y", alpha=0.3)

    for bar, val in zip(bars2, speedups):
        height = bar.get_height()
        ax2.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{val:.3f}x",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    # 3. L2 Miss Rate (Top Right)
    ax3 = fig.add_subplot(gs[0, 2])
    l2_miss_rates = [results[p]["l2_miss_rate"] * 100 for p in policies]
    bars3 = ax3.bar(
        policies,
        l2_miss_rates,
        color=[COLORS[p] for p in policies],
        alpha=0.8,
        edgecolor="black",
    )
    ax3.set_ylabel("Miss Rate (%)")
    ax3.set_title("L2 Cache Miss Rate", fontweight="bold")
    ax3.grid(axis="y", alpha=0.3)

    for bar, val in zip(bars3, l2_miss_rates):
        height = bar.get_height()
        ax3.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{val:.2f}%",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    # 4. L1 Cache Performance (Middle Left)
    ax4 = fig.add_subplot(gs[1, 0])
    x = np.arange(len(policies))
    width = 0.35
    icache_miss = [results[p]["icache_miss_rate"] * 100 for p in policies]
    dcache_miss = [results[p]["dcache_miss_rate"] * 100 for p in policies]

    bars4a = ax4.bar(
        x - width / 2,
        icache_miss,
        width,
        label="I-Cache",
        alpha=0.8,
        edgecolor="black",
    )
    bars4b = ax4.bar(
        x + width / 2,
        dcache_miss,
        width,
        label="D-Cache",
        alpha=0.8,
        edgecolor="black",
    )
    ax4.set_ylabel("Miss Rate (%)")
    ax4.set_title("L1 Cache Miss Rates", fontweight="bold")
    ax4.set_xticks(x)
    ax4.set_xticklabels(policies)
    ax4.legend()
    ax4.grid(axis="y", alpha=0.3)

    # 5. Memory Bandwidth (Middle Middle)
    ax5 = fig.add_subplot(gs[1, 1])
    mem_reads = [results[p]["mem_reads"] for p in policies]
    mem_writes = [results[p]["mem_writes"] for p in policies]

    bars5a = ax5.bar(
        x - width / 2,
        mem_reads,
        width,
        label="Reads",
        alpha=0.8,
        edgecolor="black",
    )
    bars5b = ax5.bar(
        x + width / 2,
        mem_writes,
        width,
        label="Writes",
        alpha=0.8,
        edgecolor="black",
    )
    ax5.set_ylabel("Number of Operations")
    ax5.set_title("Main Memory Access Patterns", fontweight="bold")
    ax5.set_xticks(x)
    ax5.set_xticklabels(policies)
    ax5.legend()
    ax5.grid(axis="y", alpha=0.3)

    # 6. Cache Hierarchy Hit Rates (Middle Right)
    ax6 = fig.add_subplot(gs[1, 2])
    cache_levels = ["L1-I", "L1-D", "L2"]

    for i, policy in enumerate(policies):
        hit_rates = [
            (1 - results[policy]["icache_miss_rate"]) * 100,
            (1 - results[policy]["dcache_miss_rate"]) * 100,
            (1 - results[policy]["l2_miss_rate"]) * 100,
        ]
        ax6.plot(
            cache_levels,
            hit_rates,
            marker="o",
            label=policy,
            color=COLORS[policy],
            linewidth=2,
            markersize=8,
        )

    ax6.set_ylabel("Hit Rate (%)")
    ax6.set_title("Cache Hierarchy Hit Rates", fontweight="bold")
    ax6.legend()
    ax6.grid(alpha=0.3)
    ax6.set_ylim([0, 105])

    # 7. Execution Time (Bottom Left)
    ax7 = fig.add_subplot(gs[2, 0])
    sim_times = [
        results[p]["sim_seconds"] * 1000 for p in policies
    ]  # Convert to ms
    bars7 = ax7.bar(
        policies,
        sim_times,
        color=[COLORS[p] for p in policies],
        alpha=0.8,
        edgecolor="black",
    )
    ax7.set_ylabel("Simulated Time (ms)")
    ax7.set_title("Total Execution Time", fontweight="bold")
    ax7.grid(axis="y", alpha=0.3)

    for bar, val in zip(bars7, sim_times):
        height = bar.get_height()
        ax7.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{val:.2f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    # 8. Cache Access Distribution (Bottom Middle)
    ax8 = fig.add_subplot(gs[2, 1])
    cache_stats = ["L1-I\nAccess", "L1-D\nAccess", "L2\nAccess"]

    for i, policy in enumerate(policies):
        accesses = [
            results[policy]["icache_accesses"],
            results[policy]["dcache_accesses"],
            results[policy]["l2_accesses"],
        ]
        x_pos = np.arange(len(cache_stats))
        ax8.plot(
            x_pos,
            accesses,
            marker="s",
            label=policy,
            color=COLORS[policy],
            linewidth=2,
            markersize=8,
        )

    ax8.set_xticks(x_pos)
    ax8.set_xticklabels(cache_stats)
    ax8.set_ylabel("Number of Accesses")
    ax8.set_title("Cache Access Distribution", fontweight="bold")
    ax8.legend()
    ax8.grid(alpha=0.3)

    # 9. Summary Table (Bottom Right)
    ax9 = fig.add_subplot(gs[2, 2])
    ax9.axis("tight")
    ax9.axis("off")

    # Create summary table
    table_data = [
        ["Metric", "LRU", "AIP", "LvP"],
        [
            "IPC",
            f"{results['LRU']['ipc']:.3f}",
            f"{results['AIP']['ipc']:.3f}",
            f"{results['LvP']['ipc']:.3f}",
        ],
        [
            "L2 Miss %",
            f"{results['LRU']['l2_miss_rate']*100:.2f}",
            f"{results['AIP']['l2_miss_rate']*100:.2f}",
            f"{results['LvP']['l2_miss_rate']*100:.2f}",
        ],
        ["Speedup", "1.00x", f"{speedups[1]:.3f}x", f"{speedups[2]:.3f}x"],
        [
            "Mem Reads",
            f"{int(results['LRU']['mem_reads'])}",
            f"{int(results['AIP']['mem_reads'])}",
            f"{int(results['LvP']['mem_reads'])}",
        ],
    ]

    table = ax9.table(
        cellText=table_data,
        cellLoc="center",
        loc="center",
        colWidths=[0.3, 0.23, 0.23, 0.23],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 2)

    # Style header row
    for i in range(4):
        table[(0, i)].set_facecolor("#34495e")
        table[(0, i)].set_text_props(weight="bold", color="white")

    # Alternate row colors
    for i in range(1, len(table_data)):
        for j in range(4):
            if i % 2 == 0:
                table[(i, j)].set_facecolor("#ecf0f1")

    ax9.set_title("Performance Summary", fontweight="bold", pad=20)

    # Main title
    fig.suptitle(
        "Cache Replacement Policy Comparison: LRU vs AIP vs LvP",
        fontsize=16,
        fontweight="bold",
        y=0.98,
    )

    # Save figure
    output_file = output_dir / "policy_comparison.png"
    plt.savefig(output_file, bbox_inches="tight", dpi=300)
    print(f"\n✓ Saved comparison graph: {output_file}")

    plt.close()


def create_detailed_report(results, output_dir):
    """Create a detailed text report."""

    output_file = Path(output_dir) / "comparison_report.txt"

    with open(output_file, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("CACHE REPLACEMENT POLICY COMPARISON REPORT\n")
        f.write("=" * 80 + "\n\n")

        f.write("Policies Tested: LRU (baseline), AIP, LvP\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Performance Metrics
        f.write("-" * 80 + "\n")
        f.write("1. PERFORMANCE METRICS\n")
        f.write("-" * 80 + "\n\n")

        lru_ipc = results["LRU"]["ipc"]

        for policy in POLICIES:
            f.write(f"{policy}:\n")
            f.write(f"  IPC: {results[policy]['ipc']:.4f}\n")
            speedup = results[policy]["ipc"] / lru_ipc
            f.write(
                f"  Speedup vs LRU: {speedup:.3f}x ({(speedup-1)*100:+.1f}%)\n"
            )
            f.write(
                f"  Execution Time: {results[policy]['sim_seconds']*1000:.2f} ms\n"
            )
            f.write(f"  Instructions: {int(results[policy]['sim_insts'])}\n\n")

        # Cache Performance
        f.write("-" * 80 + "\n")
        f.write("2. CACHE PERFORMANCE\n")
        f.write("-" * 80 + "\n\n")

        for policy in POLICIES:
            f.write(f"{policy}:\n")
            f.write(f"  L1 I-Cache:\n")
            f.write(
                f"    Accesses: {int(results[policy]['icache_accesses'])}\n"
            )
            f.write(f"    Hits: {int(results[policy]['icache_hits'])}\n")
            f.write(f"    Misses: {int(results[policy]['icache_misses'])}\n")
            f.write(
                f"    Miss Rate: {results[policy]['icache_miss_rate']*100:.2f}%\n"
            )

            f.write(f"  L1 D-Cache:\n")
            f.write(
                f"    Accesses: {int(results[policy]['dcache_accesses'])}\n"
            )
            f.write(f"    Hits: {int(results[policy]['dcache_hits'])}\n")
            f.write(f"    Misses: {int(results[policy]['dcache_misses'])}\n")
            f.write(
                f"    Miss Rate: {results[policy]['dcache_miss_rate']*100:.2f}%\n"
            )

            f.write(f"  L2 Cache:\n")
            f.write(f"    Accesses: {int(results[policy]['l2_accesses'])}\n")
            f.write(f"    Hits: {int(results[policy]['l2_hits'])}\n")
            f.write(f"    Misses: {int(results[policy]['l2_misses'])}\n")
            f.write(
                f"    Miss Rate: {results[policy]['l2_miss_rate']*100:.2f}%\n\n"
            )

        # Memory Traffic
        f.write("-" * 80 + "\n")
        f.write("3. MEMORY TRAFFIC\n")
        f.write("-" * 80 + "\n\n")

        for policy in POLICIES:
            f.write(f"{policy}:\n")
            f.write(f"  Memory Reads: {int(results[policy]['mem_reads'])}\n")
            f.write(f"  Memory Writes: {int(results[policy]['mem_writes'])}\n")
            total_mem = (
                results[policy]["mem_reads"] + results[policy]["mem_writes"]
            )
            f.write(f"  Total Memory Operations: {int(total_mem)}\n\n")

        # Comparative Analysis
        f.write("-" * 80 + "\n")
        f.write("4. COMPARATIVE ANALYSIS\n")
        f.write("-" * 80 + "\n\n")

        # L2 miss rate reduction
        lru_l2_miss = results["LRU"]["l2_miss_rate"]
        aip_l2_miss = results["AIP"]["l2_miss_rate"]
        lvp_l2_miss = results["LvP"]["l2_miss_rate"]

        f.write(f"L2 Miss Rate Reduction:\n")
        if lru_l2_miss > 0:
            f.write(
                f"  AIP vs LRU: {(lru_l2_miss - aip_l2_miss)*100:.2f} percentage points "
                f"({((lru_l2_miss - aip_l2_miss)/lru_l2_miss)*100:+.1f}%)\n"
            )
            f.write(
                f"  LvP vs LRU: {(lru_l2_miss - lvp_l2_miss)*100:.2f} percentage points "
                f"({((lru_l2_miss - lvp_l2_miss)/lru_l2_miss)*100:+.1f}%)\n\n"
            )
        else:
            f.write(f"  AIP: {aip_l2_miss*100:.2f}%\n")
            f.write(f"  LvP: {lvp_l2_miss*100:.2f}%\n")
            f.write(f"  (LRU has zero L2 misses - too small workload)\n\n")

        # Memory traffic reduction
        lru_mem = results["LRU"]["mem_reads"]
        aip_mem = results["AIP"]["mem_reads"]
        lvp_mem = results["LvP"]["mem_reads"]

        f.write(f"Memory Read Reduction:\n")
        if lru_mem > 0:
            f.write(
                f"  AIP vs LRU: {int(lru_mem - aip_mem)} reads "
                f"({((lru_mem - aip_mem)/lru_mem)*100:+.1f}%)\n"
            )
            f.write(
                f"  LvP vs LRU: {int(lru_mem - lvp_mem)} reads "
                f"({((lru_mem - lvp_mem)/lru_mem)*100:+.1f}%)\n\n"
            )
        else:
            f.write(f"  AIP: {int(aip_mem)} reads\n")
            f.write(f"  LvP: {int(lvp_mem)} reads\n")
            f.write(f"  (No memory reads in workload)\n\n")

        # Summary
        f.write("-" * 80 + "\n")
        f.write("5. SUMMARY\n")
        f.write("-" * 80 + "\n\n")

        best_ipc = max(results[p]["ipc"] for p in POLICIES)
        best_policy = [p for p in POLICIES if results[p]["ipc"] == best_ipc][0]

        f.write(f"Best Overall Performance: {best_policy}\n")
        f.write(f"  Highest IPC: {best_ipc:.4f}\n")
        f.write(f"  Speedup vs LRU: {(best_ipc/lru_ipc):.3f}x\n\n")

        f.write("Key Findings:\n")
        aip_speedup = results["AIP"]["ipc"] / lru_ipc
        lvp_speedup = results["LvP"]["ipc"] / lru_ipc

        if aip_speedup > 1.0:
            f.write(
                f"  • AIP provides {(aip_speedup-1)*100:.1f}% performance improvement over LRU\n"
            )
        if lvp_speedup > 1.0:
            f.write(
                f"  • LvP provides {(lvp_speedup-1)*100:.1f}% performance improvement over LRU\n"
            )

        if results["AIP"]["l2_miss_rate"] < results["LRU"]["l2_miss_rate"]:
            improvement = ((lru_l2_miss - aip_l2_miss) / lru_l2_miss) * 100
            f.write(f"  • AIP reduces L2 miss rate by {improvement:.1f}%\n")

        if results["LvP"]["l2_miss_rate"] < results["LRU"]["l2_miss_rate"]:
            improvement = ((lru_l2_miss - lvp_l2_miss) / lru_l2_miss) * 100
            f.write(f"  • LvP reduces L2 miss rate by {improvement:.1f}%\n")

        f.write("\n" + "=" * 80 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 80 + "\n")

    print(f"✓ Saved detailed report: {output_file}")


def main():
    """Main execution function."""

    parser = argparse.ArgumentParser(
        description="Compare cache replacement policies"
    )
    parser.add_argument(
        "--output-dir",
        default="comparison_results",
        help="Output directory for results",
    )
    parser.add_argument(
        "--workload",
        default="hello",
        choices=WORKLOADS.keys(),
        help="Workload to run",
    )
    parser.add_argument(
        "--max-insts",
        type=int,
        default=100000,
        help="Maximum instructions to simulate",
    )

    args = parser.parse_args()

    # Setup
    print("=" * 80)
    print("CACHE REPLACEMENT POLICY COMPARISON")
    print("=" * 80)
    print(f"\nPolicies: {', '.join(POLICIES)}")
    print(f"Workload: {args.workload}")
    print(f"Max Instructions: {args.max_insts:,}")
    print(f"Output Directory: {args.output_dir}\n")

    # Get workload info
    if args.workload in WORKLOADS:
        workload_path = WORKLOADS[args.workload]["path"]
    else:
        workload_path = args.workload

    # Run simulations
    print("Running simulations...")
    print("-" * 80)

    results = {}

    for policy in POLICIES:
        stats_file = run_simulation(
            policy, workload_path, args.max_insts, args.output_dir
        )

        if stats_file and stats_file.exists():
            stats = parse_stats(stats_file)
            if stats:
                results[policy] = stats
            else:
                print(f"  ✗ Failed to parse stats for {policy}")
        else:
            print(f"  ✗ No stats file for {policy}")

    # Check if we have results for all policies
    if len(results) != len(POLICIES):
        print(
            f"\n✗ ERROR: Only got results for {len(results)}/{len(POLICIES)} policies"
        )
        sys.exit(1)

    print("\n" + "=" * 80)
    print("GENERATING ANALYSIS")
    print("=" * 80 + "\n")

    # Create comparison graphs
    print("Creating comparison graphs...")
    create_comparison_graphs(results, args.output_dir)

    # Create detailed report
    print("Creating detailed report...")
    create_detailed_report(results, args.output_dir)

    # Quick summary
    print("\n" + "=" * 80)
    print("QUICK SUMMARY")
    print("=" * 80 + "\n")

    lru_ipc = results["LRU"]["ipc"]

    for policy in POLICIES:
        speedup = results[policy]["ipc"] / lru_ipc
        l2_miss = results[policy]["l2_miss_rate"] * 100

        print(
            f"{policy:6s}: IPC={results[policy]['ipc']:.4f}  "
            f"Speedup={speedup:.3f}x  L2 Miss={l2_miss:.2f}%"
        )

    print("\n" + "=" * 80)
    print(f"✓ All results saved to: {args.output_dir}/")
    print("  - policy_comparison.png  (comprehensive graphs)")
    print("  - comparison_report.txt  (detailed analysis)")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
