#!/usr/bin/env python3
"""
Read parsec_results/comparison_summary.json and plot IPC, speedup vs LRU,
and L2 miss rate for LRU, AIP, LvP. Saves a PNG alongside the JSON.

Usage:
  python3 tools/plot_summary_json.py \
    --in parsec_results/comparison_summary.json \
    --out parsec_results/comparison_summary_plot.png
"""

import argparse
import json
import os


def main():
    ap = argparse.ArgumentParser(
        description="Plot IPC, speedup, and L2 miss rate from summary JSON."
    )
    ap.add_argument(
        "--in",
        dest="in_path",
        default="parsec_results/comparison_summary.json",
    )
    ap.add_argument(
        "--out",
        dest="out_path",
        default="parsec_results/comparison_summary_plot.png",
    )
    args = ap.parse_args()

    with open(args.in_path) as fh:
        d = json.load(fh)

    labels = ["LRU", "AIP", "LvP"]
    ipc = [
        d.get("LRU", {}).get("ipc"),
        d.get("AIP", {}).get("ipc"),
        d.get("LvP", {}).get("ipc"),
    ]
    base = ipc[0]
    speed = [((x / base - 1.0) * 100.0) if (x and base) else 0.0 for x in ipc]
    miss_rate = [
        d.get("LRU", {}).get("l2_miss_rate"),
        d.get("AIP", {}).get("l2_miss_rate"),
        d.get("LvP", {}).get("l2_miss_rate"),
    ]

    try:
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"warn: matplotlib not available: {e}")
        return

    fig, ax = plt.subplots(1, 3, figsize=(12, 4))

    ax[0].bar(labels, ipc, color=["#1f77b4", "#2ca02c", "#ff7f0e"])
    ax[0].set_title("IPC")
    ax[0].set_ylabel("IPC")
    # Tight y-axis around data to make small differences visible
    if all(isinstance(x, (int, float)) for x in ipc) and None not in ipc:
        ymin = min(ipc)
        ymax = max(ipc)
        span = max(1e-6, ymax - ymin)
        ax[0].set_ylim(ymin - 0.2 * span, ymax + 0.2 * span)

    # Speedup plot: exclude LRU (always 0%), show only AIP and LvP
    speed_labels = ["AIP", "LvP"]
    speed_values = speed[1:]
    ax[1].bar(speed_labels, speed_values, color=["#2ca02c", "#ff7f0e"])
    ax[1].set_title("Speedup vs LRU (%)")
    ax[1].axhline(0, color="black", lw=0.8)
    if speed_values:
        ymin = min(speed_values)
        ymax = max(speed_values)
        span = max(1e-6, ymax - ymin)
        ax[1].set_ylim(ymin - 0.3 * span, ymax + 0.3 * span)

    ax[2].bar(labels, miss_rate, color=["#1f77b4", "#2ca02c", "#ff7f0e"])
    ax[2].set_title("L2 Miss Rate (fraction)")
    ax[2].set_ylabel("Miss rate")
    # Tight y-axis around miss rate values
    if (
        all(isinstance(x, (int, float)) for x in miss_rate)
        and None not in miss_rate
    ):
        ymin = min(miss_rate)
        ymax = max(miss_rate)
        span = max(1e-6, ymax - ymin)
        ax[2].set_ylim(ymin - 0.2 * span, ymax + 0.2 * span)

    fig.tight_layout()
    os.makedirs(os.path.dirname(args.out_path), exist_ok=True)
    plt.savefig(args.out_path, bbox_inches="tight")
    print(f"wrote: {args.out_path}")


if __name__ == "__main__":
    main()
