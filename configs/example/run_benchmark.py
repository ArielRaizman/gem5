#!/usr/bin/env python3
"""
Benchmark runner for cache replacement policy comparison.

This script runs multiple benchmarks with different replacement policies
and collects statistics for comparison.

Usage:
    python3 run_benchmark.py --benchmarks-dir /path/to/spec2000 --gem5-binary build/X86/gem5.opt
"""

import argparse
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path


class BenchmarkRunner:
    """Class to manage benchmark execution and data collection."""

    # Group A benchmarks (expected to show significant improvement)
    GROUP_A_BENCHMARKS = [
        "ammp",
        "apsi",
        "art",
        "bzip2",
        "gcc",
        "mcf",
        "mgrid",
        "swim",
        "twolf",
        "vpr",
    ]

    REPLACEMENT_POLICIES = [
        "LRU",
        "AIP",
        "LvP",
        "LFU",
        "Random",
        "BRRIP",
        "SHiPPC",
    ]

    def __init__(
        self, gem5_binary, config_script, benchmarks_dir, output_base
    ):
        self.gem5_binary = gem5_binary
        self.config_script = config_script
        self.benchmarks_dir = Path(benchmarks_dir)
        self.output_base = Path(output_base)
        self.results = {}

    def get_benchmark_path(self, benchmark_name):
        """Get the full path to a benchmark binary."""
        # This is a simplified version - adjust based on your SPEC2000 setup
        benchmark_path = self.benchmarks_dir / benchmark_name / benchmark_name
        return str(benchmark_path)

    def run_single_benchmark(
        self, benchmark, policy, fast_forward=2000000000, max_insts=3000000000
    ):
        """
        Run a single benchmark with a specific replacement policy.

        Returns:
            dict: Statistics extracted from the run
        """
        output_dir = self.output_base / f"{benchmark}_{policy}"
        output_dir.mkdir(parents=True, exist_ok=True)

        benchmark_path = self.get_benchmark_path(benchmark)

        cmd = [
            self.gem5_binary,
            "--outdir",
            str(output_dir),
            self.config_script,
            "--replacement-policy",
            policy,
            "--benchmark",
            benchmark_path,
            "--fast-forward",
            str(fast_forward),
            "--max-insts",
            str(max_insts),
        ]

        print(f"\n{'='*80}")
        print(f"Running: {benchmark} with {policy} policy")
        print(f"Output directory: {output_dir}")
        print(f"{'='*80}\n")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=7200,  # 2 hour timeout per benchmark
            )

            if result.returncode != 0:
                print(
                    f"ERROR: Benchmark failed with return code {result.returncode}"
                )
                print(f"STDERR: {result.stderr}")
                return None

            # Parse statistics
            stats = self.parse_stats(output_dir / "stats.txt")
            return stats

        except subprocess.TimeoutExpired:
            print(f"ERROR: Benchmark timed out after 2 hours")
            return None
        except Exception as e:
            print(f"ERROR: Exception during benchmark: {e}")
            return None

    def parse_stats(self, stats_file):
        """
        Parse gem5 statistics file and extract relevant metrics.

        Returns:
            dict: Extracted statistics
        """
        stats = {}

        if not stats_file.exists():
            print(f"ERROR: Stats file not found: {stats_file}")
            return stats

        with open(stats_file) as f:
            content = f.read()

        # Extract key statistics using regex
        patterns = {
            "sim_seconds": r"sim_seconds\s+([\d.]+)",
            "sim_insts": r"sim_insts\s+([\d]+)",
            "ipc": r"ipc\s+([\d.]+)",
            "l2_overall_miss_rate": r"system\.l2cache\.overall_miss_rate::total\s+([\d.]+)",
            "l2_overall_hits": r"system\.l2cache\.overall_hits::total\s+([\d]+)",
            "l2_overall_misses": r"system\.l2cache\.overall_misses::total\s+([\d]+)",
            "l2_overall_accesses": r"system\.l2cache\.overall_accesses::total\s+([\d]+)",
            "dcache_miss_rate": r"system\.cpu\.dcache\.overall_miss_rate::total\s+([\d.]+)",
            "icache_miss_rate": r"system\.cpu\.icache\.overall_miss_rate::total\s+([\d.]+)",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, content)
            if match:
                try:
                    value = (
                        float(match.group(1))
                        if "." in match.group(1)
                        else int(match.group(1))
                    )
                    stats[key] = value
                except ValueError:
                    stats[key] = None
            else:
                stats[key] = None

        return stats

    def run_all_benchmarks(self, benchmarks=None, policies=None):
        """
        Run all specified benchmarks with all specified policies.

        Args:
            benchmarks: List of benchmark names (default: GROUP_A_BENCHMARKS)
            policies: List of replacement policies (default: all policies)
        """
        if benchmarks is None:
            benchmarks = self.GROUP_A_BENCHMARKS

        if policies is None:
            policies = self.REPLACEMENT_POLICIES

        total_runs = len(benchmarks) * len(policies)
        current_run = 0

        for benchmark in benchmarks:
            if benchmark not in self.results:
                self.results[benchmark] = {}

            for policy in policies:
                current_run += 1
                print(f"\n{'#'*80}")
                print(f"# Progress: {current_run}/{total_runs}")
                print(f"# Benchmark: {benchmark}, Policy: {policy}")
                print(f"{'#'*80}")

                stats = self.run_single_benchmark(benchmark, policy)

                if stats:
                    self.results[benchmark][policy] = stats
                    print(f"\nCompleted: {benchmark} - {policy}")
                    print(f"  IPC: {stats.get('ipc', 'N/A')}")
                    print(
                        f"  L2 Miss Rate: {stats.get('l2_overall_miss_rate', 'N/A')}"
                    )
                else:
                    print(f"\nFailed: {benchmark} - {policy}")
                    self.results[benchmark][policy] = None

    def save_results(self, filename=None):
        """Save results to JSON file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = self.output_base / f"benchmark_results_{timestamp}.json"

        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2)

        print(f"\nResults saved to: {filename}")
        return filename

    def print_summary(self):
        """Print a summary of results."""
        print("\n" + "=" * 80)
        print("BENCHMARK SUMMARY")
        print("=" * 80)

        for benchmark, policies in self.results.items():
            print(f"\n{benchmark}:")

            # Get baseline LRU IPC
            lru_ipc = None
            if "LRU" in policies and policies["LRU"]:
                lru_ipc = policies["LRU"].get("ipc")

            for policy, stats in policies.items():
                if stats:
                    ipc = stats.get("ipc", 0)
                    miss_rate = stats.get("l2_overall_miss_rate", 0)

                    speedup = ""
                    if lru_ipc and lru_ipc > 0 and policy != "LRU":
                        speedup_pct = ((ipc - lru_ipc) / lru_ipc) * 100
                        speedup = f" (Speedup: {speedup_pct:+.2f}%)"

                    print(
                        f"  {policy:10s}: IPC={ipc:.4f}, L2 Miss Rate={miss_rate:.4f}{speedup}"
                    )
                else:
                    print(f"  {policy:10s}: FAILED")


def main():
    parser = argparse.ArgumentParser(
        description="Run cache replacement policy benchmarks"
    )

    parser.add_argument(
        "--gem5-binary",
        type=str,
        default="build/X86/gem5.opt",
        help="Path to gem5 binary (default: build/X86/gem5.opt)",
    )

    parser.add_argument(
        "--config-script",
        type=str,
        default="configs/example/cache_replacement_test.py",
        help="Path to configuration script",
    )

    parser.add_argument(
        "--benchmarks-dir",
        type=str,
        required=True,
        help="Directory containing SPEC2000 benchmarks",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="benchmark_results",
        help="Base directory for output files",
    )

    parser.add_argument(
        "--benchmarks",
        type=str,
        nargs="+",
        help="Specific benchmarks to run (default: Group A benchmarks)",
    )

    parser.add_argument(
        "--policies",
        type=str,
        nargs="+",
        help="Specific policies to test (default: all policies)",
    )

    parser.add_argument(
        "--fast-forward",
        type=int,
        default=2000000000,
        help="Instructions to fast-forward (default: 2 billion)",
    )

    parser.add_argument(
        "--max-insts",
        type=int,
        default=3000000000,
        help="Total instructions to simulate (default: 3 billion)",
    )

    args = parser.parse_args()

    # Create benchmark runner
    runner = BenchmarkRunner(
        args.gem5_binary,
        args.config_script,
        args.benchmarks_dir,
        args.output_dir,
    )

    # Run benchmarks
    runner.run_all_benchmarks(
        benchmarks=args.benchmarks, policies=args.policies
    )

    # Save results
    results_file = runner.save_results()

    # Print summary
    runner.print_summary()

    print(f"\n{'='*80}")
    print(f"All benchmarks complete!")
    print(f"Results saved to: {results_file}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
