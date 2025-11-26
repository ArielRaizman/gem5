#!/usr/bin/env python3
"""
Visualization and analysis tool for cache replacement policy benchmarks.

This script generates comprehensive graphs comparing different replacement
policies across various metrics.

Usage:
    python3 analyze_results.py benchmark_results_20251122_120000.json
"""

import argparse
import json
import sys
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from matplotlib.gridspec import GridSpec


class ResultAnalyzer:
    """Class to analyze and visualize benchmark results."""

    def __init__(self, results_file):
        """Initialize analyzer with results from JSON file."""
        with open(results_file) as f:
            self.results = json.load(f)

        self.benchmarks = list(self.results.keys())
        self.policies = self._get_all_policies()

        # Set up plotting style
        sns.set_style("whitegrid")
        plt.rcParams["figure.figsize"] = (14, 8)
        plt.rcParams["font.size"] = 10

        # Color scheme for policies
        self.policy_colors = {
            "LRU": "#1f77b4",  # Blue (baseline)
            "AIP": "#ff7f0e",  # Orange
            "LvP": "#2ca02c",  # Green
            "LFU": "#d62728",  # Red
            "MRU": "#9467bd",  # Purple
            "Random": "#8c564b",  # Brown
            "BRRIP": "#e377c2",  # Pink
            "SHiPPC": "#7f7f7f",  # Gray
        }

    def _get_all_policies(self):
        """Extract all unique policies from results."""
        policies = set()
        for benchmark_data in self.results.values():
            policies.update(benchmark_data.keys())
        return sorted(list(policies))

    def calculate_speedup(self, baseline_policy="LRU"):
        """
        Calculate speedup relative to baseline policy.

        Returns:
            dict: {benchmark: {policy: speedup}}
        """
        speedup_data = {}

        for benchmark, policies in self.results.items():
            speedup_data[benchmark] = {}

            baseline_ipc = None
            if baseline_policy in policies and policies[baseline_policy]:
                baseline_ipc = policies[baseline_policy].get("ipc")

            if baseline_ipc and baseline_ipc > 0:
                for policy, stats in policies.items():
                    if stats and stats.get("ipc"):
                        speedup = stats["ipc"] / baseline_ipc
                        speedup_data[benchmark][policy] = speedup
                    else:
                        speedup_data[benchmark][policy] = None
            else:
                # No valid baseline
                for policy in policies.keys():
                    speedup_data[benchmark][policy] = None

        return speedup_data

    def plot_ipc_comparison(self, output_dir):
        """Generate IPC comparison bar chart."""
        fig, ax = plt.subplots(figsize=(16, 8))

        x = np.arange(len(self.benchmarks))
        width = 0.8 / len(self.policies)

        for i, policy in enumerate(self.policies):
            ipcs = []
            for benchmark in self.benchmarks:
                if (
                    benchmark in self.results
                    and policy in self.results[benchmark]
                    and self.results[benchmark][policy]
                ):
                    ipcs.append(self.results[benchmark][policy].get("ipc", 0))
                else:
                    ipcs.append(0)

            offset = (i - len(self.policies) / 2) * width + width / 2
            ax.bar(
                x + offset,
                ipcs,
                width,
                label=policy,
                color=self.policy_colors.get(policy, "#333333"),
            )

        ax.set_xlabel("Benchmark", fontsize=12, fontweight="bold")
        ax.set_ylabel(
            "Instructions Per Cycle (IPC)", fontsize=12, fontweight="bold"
        )
        ax.set_title(
            "IPC Comparison Across Replacement Policies",
            fontsize=14,
            fontweight="bold",
        )
        ax.set_xticks(x)
        ax.set_xticklabels(self.benchmarks, rotation=45, ha="right")
        ax.legend(loc="upper left", ncol=2)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        output_file = Path(output_dir) / "ipc_comparison.png"
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        print(f"Saved: {output_file}")
        plt.close()

    def plot_speedup_comparison(self, output_dir, baseline="LRU"):
        """Generate speedup comparison chart."""
        speedup_data = self.calculate_speedup(baseline)

        fig, ax = plt.subplots(figsize=(16, 8))

        x = np.arange(len(self.benchmarks))
        width = 0.8 / (len(self.policies) - 1)  # Exclude baseline

        plot_policies = [p for p in self.policies if p != baseline]

        for i, policy in enumerate(plot_policies):
            speedups = []
            for benchmark in self.benchmarks:
                if (
                    benchmark in speedup_data
                    and policy in speedup_data[benchmark]
                    and speedup_data[benchmark][policy] is not None
                ):
                    speedups.append(speedup_data[benchmark][policy])
                else:
                    speedups.append(1.0)

            offset = (i - len(plot_policies) / 2) * width + width / 2
            bars = ax.bar(
                x + offset,
                speedups,
                width,
                label=policy,
                color=self.policy_colors.get(policy, "#333333"),
            )

            # Highlight bars above 1.0
            for j, (bar, speedup) in enumerate(zip(bars, speedups)):
                if speedup > 1.0:
                    bar.set_edgecolor("darkgreen")
                    bar.set_linewidth(2)

        # Add baseline line at 1.0
        ax.axhline(
            y=1.0,
            color="black",
            linestyle="--",
            linewidth=2,
            label=f"{baseline} (Baseline)",
            alpha=0.7,
        )

        ax.set_xlabel("Benchmark", fontsize=12, fontweight="bold")
        ax.set_ylabel(f"Speedup vs {baseline}", fontsize=12, fontweight="bold")
        ax.set_title(
            f"Speedup Comparison (Baseline: {baseline})",
            fontsize=14,
            fontweight="bold",
        )
        ax.set_xticks(x)
        ax.set_xticklabels(self.benchmarks, rotation=45, ha="right")
        ax.legend(loc="upper left", ncol=2)
        ax.grid(True, alpha=0.3, axis="y")

        plt.tight_layout()
        output_file = Path(output_dir) / f"speedup_vs_{baseline}.png"
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        print(f"Saved: {output_file}")
        plt.close()

    def plot_miss_rate_comparison(self, output_dir):
        """Generate L2 miss rate comparison chart."""
        fig, ax = plt.subplots(figsize=(16, 8))

        x = np.arange(len(self.benchmarks))
        width = 0.8 / len(self.policies)

        for i, policy in enumerate(self.policies):
            miss_rates = []
            for benchmark in self.benchmarks:
                if (
                    benchmark in self.results
                    and policy in self.results[benchmark]
                    and self.results[benchmark][policy]
                ):
                    mr = self.results[benchmark][policy].get(
                        "l2_overall_miss_rate", 0
                    )
                    miss_rates.append(mr * 100)  # Convert to percentage
                else:
                    miss_rates.append(0)

            offset = (i - len(self.policies) / 2) * width + width / 2
            ax.bar(
                x + offset,
                miss_rates,
                width,
                label=policy,
                color=self.policy_colors.get(policy, "#333333"),
            )

        ax.set_xlabel("Benchmark", fontsize=12, fontweight="bold")
        ax.set_ylabel("L2 Cache Miss Rate (%)", fontsize=12, fontweight="bold")
        ax.set_title(
            "L2 Cache Miss Rate Comparison", fontsize=14, fontweight="bold"
        )
        ax.set_xticks(x)
        ax.set_xticklabels(self.benchmarks, rotation=45, ha="right")
        ax.legend(loc="upper left", ncol=2)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        output_file = Path(output_dir) / "miss_rate_comparison.png"
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        print(f"Saved: {output_file}")
        plt.close()

    def plot_average_metrics(self, output_dir):
        """Generate average performance metrics across all benchmarks."""
        fig = plt.figure(figsize=(16, 10))
        gs = GridSpec(2, 2, figure=fig)

        # Calculate averages
        avg_ipc = {}
        avg_speedup = {}
        avg_miss_rate = {}
        avg_l2_hits = {}

        speedup_data = self.calculate_speedup("LRU")

        for policy in self.policies:
            ipcs = []
            speedups = []
            miss_rates = []
            hits = []

            for benchmark in self.benchmarks:
                if (
                    benchmark in self.results
                    and policy in self.results[benchmark]
                    and self.results[benchmark][policy]
                ):

                    stats = self.results[benchmark][policy]
                    if stats.get("ipc"):
                        ipcs.append(stats["ipc"])
                    if stats.get("l2_overall_miss_rate"):
                        miss_rates.append(stats["l2_overall_miss_rate"])
                    if stats.get("l2_overall_hits"):
                        hits.append(stats["l2_overall_hits"])

                    if (
                        benchmark in speedup_data
                        and policy in speedup_data[benchmark]
                        and speedup_data[benchmark][policy]
                    ):
                        speedups.append(speedup_data[benchmark][policy])

            avg_ipc[policy] = np.mean(ipcs) if ipcs else 0
            avg_speedup[policy] = np.mean(speedups) if speedups else 1.0
            avg_miss_rate[policy] = np.mean(miss_rates) if miss_rates else 0
            avg_l2_hits[policy] = np.mean(hits) if hits else 0

        # Plot 1: Average IPC
        ax1 = fig.add_subplot(gs[0, 0])
        policies = list(avg_ipc.keys())
        ipcs = [avg_ipc[p] for p in policies]
        colors = [self.policy_colors.get(p, "#333333") for p in policies]
        ax1.bar(policies, ipcs, color=colors)
        ax1.set_ylabel("Average IPC", fontweight="bold")
        ax1.set_title("Average IPC Across All Benchmarks", fontweight="bold")
        ax1.tick_params(axis="x", rotation=45)
        ax1.grid(True, alpha=0.3, axis="y")

        # Plot 2: Average Speedup
        ax2 = fig.add_subplot(gs[0, 1])
        speedups = [avg_speedup[p] for p in policies]
        bars = ax2.bar(policies, speedups, color=colors)
        ax2.axhline(
            y=1.0, color="black", linestyle="--", linewidth=2, alpha=0.7
        )
        ax2.set_ylabel("Average Speedup vs LRU", fontweight="bold")
        ax2.set_title(
            "Average Speedup Across All Benchmarks", fontweight="bold"
        )
        ax2.tick_params(axis="x", rotation=45)
        ax2.grid(True, alpha=0.3, axis="y")

        # Highlight bars above 1.0
        for bar, speedup in zip(bars, speedups):
            if speedup > 1.0:
                bar.set_edgecolor("darkgreen")
                bar.set_linewidth(2)

        # Plot 3: Average Miss Rate
        ax3 = fig.add_subplot(gs[1, 0])
        miss_rates = [avg_miss_rate[p] * 100 for p in policies]
        ax3.bar(policies, miss_rates, color=colors)
        ax3.set_ylabel("Average L2 Miss Rate (%)", fontweight="bold")
        ax3.set_title(
            "Average L2 Miss Rate Across All Benchmarks", fontweight="bold"
        )
        ax3.tick_params(axis="x", rotation=45)
        ax3.grid(True, alpha=0.3, axis="y")

        # Plot 4: Summary Table
        ax4 = fig.add_subplot(gs[1, 1])
        ax4.axis("tight")
        ax4.axis("off")

        table_data = []
        for policy in policies:
            speedup_pct = (avg_speedup[policy] - 1.0) * 100
            table_data.append(
                [
                    policy,
                    f"{avg_ipc[policy]:.4f}",
                    f"{speedup_pct:+.2f}%",
                    f"{avg_miss_rate[policy]*100:.2f}%",
                ]
            )

        table = ax4.table(
            cellText=table_data,
            colLabels=["Policy", "Avg IPC", "Avg Speedup", "Avg Miss Rate"],
            cellLoc="center",
            loc="center",
            colWidths=[0.2, 0.2, 0.25, 0.25],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 2)

        # Style table header
        for i in range(4):
            table[(0, i)].set_facecolor("#4CAF50")
            table[(0, i)].set_text_props(weight="bold", color="white")

        plt.suptitle(
            "Average Performance Metrics Summary",
            fontsize=16,
            fontweight="bold",
            y=0.98,
        )
        plt.tight_layout()

        output_file = Path(output_dir) / "average_metrics.png"
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        print(f"Saved: {output_file}")
        plt.close()

    def plot_heatmap(self, output_dir, metric="ipc"):
        """Generate heatmap showing metric across benchmarks and policies."""
        # Prepare data matrix
        data_matrix = []
        for benchmark in self.benchmarks:
            row = []
            for policy in self.policies:
                if (
                    benchmark in self.results
                    and policy in self.results[benchmark]
                    and self.results[benchmark][policy]
                ):
                    value = self.results[benchmark][policy].get(metric, 0)
                    if metric == "l2_overall_miss_rate":
                        value *= 100  # Convert to percentage
                    row.append(value)
                else:
                    row.append(0)
            data_matrix.append(row)

        data_matrix = np.array(data_matrix)

        # Create heatmap
        fig, ax = plt.subplots(figsize=(12, 8))

        im = ax.imshow(data_matrix, cmap="RdYlGn", aspect="auto")

        # Set ticks
        ax.set_xticks(np.arange(len(self.policies)))
        ax.set_yticks(np.arange(len(self.benchmarks)))
        ax.set_xticklabels(self.policies)
        ax.set_yticklabels(self.benchmarks)

        # Rotate x labels
        plt.setp(
            ax.get_xticklabels(),
            rotation=45,
            ha="right",
            rotation_mode="anchor",
        )

        # Add colorbar
        cbar = ax.figure.colorbar(im, ax=ax)
        cbar.ax.set_ylabel(
            metric.upper(), rotation=-90, va="bottom", fontweight="bold"
        )

        # Add values to cells
        for i in range(len(self.benchmarks)):
            for j in range(len(self.policies)):
                text = ax.text(
                    j,
                    i,
                    f"{data_matrix[i, j]:.3f}",
                    ha="center",
                    va="center",
                    color="black",
                    fontsize=8,
                )

        metric_title = metric.upper().replace("_", " ")
        ax.set_title(
            f"Heatmap: {metric_title} by Benchmark and Policy",
            fontsize=14,
            fontweight="bold",
        )

        plt.tight_layout()
        output_file = Path(output_dir) / f"heatmap_{metric}.png"
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        print(f"Saved: {output_file}")
        plt.close()

    def plot_policy_comparison_radar(self, output_dir):
        """Generate radar chart comparing policies across multiple metrics."""
        # Calculate normalized metrics for each policy
        metrics = ["avg_ipc", "avg_speedup", "low_miss_rate", "consistency"]

        policy_scores = {}
        speedup_data = self.calculate_speedup("LRU")

        for policy in self.policies:
            ipcs = []
            speedups = []
            miss_rates = []

            for benchmark in self.benchmarks:
                if (
                    benchmark in self.results
                    and policy in self.results[benchmark]
                    and self.results[benchmark][policy]
                ):

                    stats = self.results[benchmark][policy]
                    if stats.get("ipc"):
                        ipcs.append(stats["ipc"])
                    if stats.get("l2_overall_miss_rate"):
                        miss_rates.append(stats["l2_overall_miss_rate"])

                    if (
                        benchmark in speedup_data
                        and policy in speedup_data[benchmark]
                        and speedup_data[benchmark][policy]
                    ):
                        speedups.append(speedup_data[benchmark][policy])

            avg_ipc = np.mean(ipcs) if ipcs else 0
            avg_speedup = np.mean(speedups) if speedups else 1.0
            avg_miss_rate = np.mean(miss_rates) if miss_rates else 1.0
            consistency = 1.0 - (np.std(speedups) if speedups else 0)

            policy_scores[policy] = {
                "avg_ipc": avg_ipc,
                "avg_speedup": avg_speedup,
                "low_miss_rate": 1.0
                - avg_miss_rate,  # Inverted so higher is better
                "consistency": max(0, consistency),
            }

        # Normalize scores to 0-1 range
        for metric in metrics:
            values = [policy_scores[p][metric] for p in self.policies]
            max_val = max(values) if values else 1
            min_val = min(values) if values else 0
            range_val = max_val - min_val if max_val > min_val else 1

            for policy in self.policies:
                normalized = (
                    policy_scores[policy][metric] - min_val
                ) / range_val
                policy_scores[policy][metric] = normalized

        # Create radar chart
        num_vars = len(metrics)
        angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
        angles += angles[:1]

        fig, ax = plt.subplots(
            figsize=(10, 10), subplot_kw=dict(projection="polar")
        )

        for policy in ["LRU", "AIP", "LvP"]:  # Focus on main policies
            values = [policy_scores[policy][m] for m in metrics]
            values += values[:1]

            ax.plot(
                angles,
                values,
                "o-",
                linewidth=2,
                label=policy,
                color=self.policy_colors.get(policy, "#333333"),
            )
            ax.fill(
                angles,
                values,
                alpha=0.15,
                color=self.policy_colors.get(policy, "#333333"),
            )

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(
            ["Avg IPC", "Avg Speedup", "Low Miss Rate", "Consistency"],
            fontsize=11,
            fontweight="bold",
        )
        ax.set_ylim(0, 1)
        ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
        ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], fontsize=9)
        ax.grid(True)
        ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))

        plt.title(
            "Policy Comparison Across Multiple Metrics\n(Normalized Scores)",
            fontsize=14,
            fontweight="bold",
            y=1.08,
        )

        plt.tight_layout()
        output_file = Path(output_dir) / "policy_radar_comparison.png"
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        print(f"Saved: {output_file}")
        plt.close()

    def generate_all_plots(self, output_dir):
        """Generate all visualization plots."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print(f"\nGenerating plots in: {output_path}")
        print("=" * 80)

        self.plot_ipc_comparison(output_path)
        self.plot_speedup_comparison(output_path, baseline="LRU")
        self.plot_miss_rate_comparison(output_path)
        self.plot_average_metrics(output_path)
        self.plot_heatmap(output_path, metric="ipc")
        self.plot_heatmap(output_path, metric="l2_overall_miss_rate")
        self.plot_policy_comparison_radar(output_path)

        print("=" * 80)
        print(f"All plots generated successfully in: {output_path}")

    def generate_summary_report(self, output_dir):
        """Generate a text summary report."""
        output_file = Path(output_dir) / "summary_report.txt"

        with open(output_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("CACHE REPLACEMENT POLICY BENCHMARK SUMMARY REPORT\n")
            f.write("=" * 80 + "\n\n")

            # Overall averages
            f.write("OVERALL AVERAGE PERFORMANCE\n")
            f.write("-" * 80 + "\n")

            speedup_data = self.calculate_speedup("LRU")

            for policy in self.policies:
                ipcs = []
                speedups = []
                miss_rates = []

                for benchmark in self.benchmarks:
                    if (
                        benchmark in self.results
                        and policy in self.results[benchmark]
                        and self.results[benchmark][policy]
                    ):

                        stats = self.results[benchmark][policy]
                        if stats.get("ipc"):
                            ipcs.append(stats["ipc"])
                        if stats.get("l2_overall_miss_rate"):
                            miss_rates.append(stats["l2_overall_miss_rate"])

                        if (
                            benchmark in speedup_data
                            and policy in speedup_data[benchmark]
                            and speedup_data[benchmark][policy]
                        ):
                            speedups.append(speedup_data[benchmark][policy])

                avg_ipc = np.mean(ipcs) if ipcs else 0
                avg_speedup = np.mean(speedups) if speedups else 1.0
                avg_miss_rate = np.mean(miss_rates) if miss_rates else 0
                speedup_pct = (avg_speedup - 1.0) * 100

                f.write(f"\n{policy}:\n")
                f.write(f"  Average IPC:        {avg_ipc:.4f}\n")
                f.write(
                    f"  Average Speedup:    {avg_speedup:.4f} ({speedup_pct:+.2f}%)\n"
                )
                f.write(f"  Average Miss Rate:  {avg_miss_rate*100:.2f}%\n")

            # Per-benchmark details
            f.write("\n\n" + "=" * 80 + "\n")
            f.write("PER-BENCHMARK DETAILED RESULTS\n")
            f.write("=" * 80 + "\n")

            for benchmark in self.benchmarks:
                f.write(f"\n{benchmark.upper()}\n")
                f.write("-" * 80 + "\n")

                for policy in self.policies:
                    if (
                        benchmark in self.results
                        and policy in self.results[benchmark]
                        and self.results[benchmark][policy]
                    ):

                        stats = self.results[benchmark][policy]
                        ipc = stats.get("ipc", 0)
                        miss_rate = stats.get("l2_overall_miss_rate", 0)

                        speedup = ""
                        if (
                            benchmark in speedup_data
                            and policy in speedup_data[benchmark]
                            and speedup_data[benchmark][policy]
                        ):
                            sp = speedup_data[benchmark][policy]
                            speedup_pct = (sp - 1.0) * 100
                            speedup = f" (Speedup: {speedup_pct:+.2f}%)"

                        f.write(
                            f"  {policy:10s}: IPC={ipc:.4f}, "
                            f"Miss Rate={miss_rate*100:.2f}%{speedup}\n"
                        )

        print(f"Saved: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze and visualize cache replacement policy benchmark results"
    )

    parser.add_argument(
        "results_file",
        type=str,
        help="JSON file containing benchmark results",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="analysis_output",
        help="Directory for output plots and reports (default: analysis_output)",
    )

    args = parser.parse_args()

    if not Path(args.results_file).exists():
        print(f"ERROR: Results file not found: {args.results_file}")
        sys.exit(1)

    # Create analyzer
    analyzer = ResultAnalyzer(args.results_file)

    # Generate all plots
    analyzer.generate_all_plots(args.output_dir)

    # Generate summary report
    analyzer.generate_summary_report(args.output_dir)

    print(f"\nAnalysis complete! Check {args.output_dir}/ for results.")


if __name__ == "__main__":
    main()
