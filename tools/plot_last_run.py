#!/usr/bin/env python3
"""
Parse the latest m5out_* run directories and plot IPC and simTicks for
LRU, AIP, LvP side-by-side. Also compute speedup vs LRU.

Usage:
  python3 tools/plot_last_run.py \
    --dirs m5out_lru m5out_aip m5out_lvp \
    --out parsec_results/last_run_metrics.png
"""

import argparse
import os
import re
from typing import Dict


def parse_stats(path: str) -> Dict[str, float]:
    metrics = {}
    if not os.path.exists(path):
        return metrics
    pat = {
        "IPC": re.compile(r"^system\.cpu\.ipc\s+(\S+)"),
        "simTicks": re.compile(r"^simTicks\s+(\S+)"),
    }
    with open(path) as fh:
        for line in fh:
            for key, rx in pat.items():
                m = rx.match(line.strip())
                if m:
                    try:
                        metrics[key] = float(m.group(1))
                    except Exception:
                        pass
    return metrics


def main():
    ap = argparse.ArgumentParser(
        description="Plot IPC and simTicks from m5out_* directories."
    )
    ap.add_argument(
        "--dirs", nargs="+", default=["m5out_lru", "m5out_aip", "m5out_lvp"]
    )
    ap.add_argument("--out", default="parsec_results/last_run_metrics.png")
    args = ap.parse_args()

    labels = []
    ipc = []
    ticks = []
    data = {}

    for d in args.dirs:
        stats = parse_stats(os.path.join(d, "stats.txt"))
        label = d.replace("m5out_", "").upper()
        labels.append(label)
        ipc.append(stats.get("IPC", 0.0))
        ticks.append(stats.get("simTicks", 0.0))
        data[label] = stats

    # Compute speedups vs LRU
    base_ipc = data.get("LRU", {}).get("IPC") or data.get("M5OUT_LRU", {}).get(
        "IPC"
    )
    speedups = []
    for label in labels:
        val = data.get(label, {}).get("IPC")
        if base_ipc and val:
            speedups.append((val / base_ipc - 1.0) * 100.0)
        else:
            speedups.append(0.0)

    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception as e:
        print(f"warn: matplotlib not available; install it to plot: {e}")
        return

    x = np.arange(len(labels))
    width = 0.3
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))

    # IPC bar
    ax[0].bar(x, ipc, width, color="#1f77b4")
    ax[0].set_title("IPC by Policy")
    ax[0].set_xticks(x, labels)
    ax[0].set_ylabel("IPC")

    # Speedup bar
    ax[1].bar(x, speedups, width, color="#2ca02c")
    ax[1].set_title("Speedup vs LRU (%)")
    ax[1].set_xticks(x, labels)
    ax[1].set_ylabel("%")
    ax[1].axhline(0, color="black", linewidth=0.8)

    fig.tight_layout()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    plt.savefig(args.out, bbox_inches="tight")
    print(f"wrote: {args.out}")


if __name__ == "__main__":
    main()
