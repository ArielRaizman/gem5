#!/usr/bin/env python3
"""
Aggregate PARSEC/gem5 comparison results to compute speedups for AIP/LvP
vs LRU (512KB) and a storage-overhead proxy LRU (576KB), then emit a
summary JSON/CSV and a simple bar chart.

Usage examples:

  python3 tools/compare_speedups.py \
    --lru512 comparison_results/lru_short.json \
    --aip512 comparison_results/aip_short.json \
    --lvp512 comparison_results/lvp_short.json \
    --lru576 comparison_results/lru_576k_short.json \
    --out-json parsec_results/comparison_summary.json \
    --out-csv parsec_results/comparison_summary.csv \
    --out-plot parsec_results/comparison_summary.png

If you have multiple per-app JSONs, you can pass directories or globs
instead of single files; the tool will merge by app name.
"""

import argparse
import json
import os
import sys
from glob import glob
from typing import (
    Dict,
    List,
    Tuple,
)


def _load_jsons(paths_or_globs: List[str]) -> List[Dict]:
    files: List[str] = []
    for p in paths_or_globs:
        if os.path.isdir(p):
            for root, _, fnames in os.walk(p):
                files.extend(
                    [
                        os.path.join(root, f)
                        for f in fnames
                        if f.endswith(".json")
                    ]
                )
        else:
            files.extend(glob(p))
    results = []
    for f in files:
        try:
            with open(f) as fh:
                data = json.load(fh)
                # Allow top-level dict with multiple app entries or single
                if (
                    isinstance(data, dict)
                    and "results" in data
                    and isinstance(data["results"], list)
                ):
                    for r in data["results"]:
                        r["_source_file"] = f
                        results.append(r)
                elif isinstance(data, list):
                    for r in data:
                        r["_source_file"] = f
                        results.append(r)
                elif isinstance(data, dict):
                    data["_source_file"] = f
                    results.append(data)
        except Exception as e:
            print(f"warn: failed to read {f}: {e}", file=sys.stderr)
    return results


def _index_by_app(entries: List[Dict]) -> Dict[str, Dict]:
    out: Dict[str, Dict] = {}
    for e in entries:
        # Try to find app name
        app = (
            e.get("app")
            or e.get("benchmark")
            or e.get("name")
            or _infer_app_from_path(e.get("_source_file", ""))
        )
        if not app:
            continue
        # Normalize metrics
        metrics = {
            "IPC": e.get("IPC")
            or e.get("ipc")
            or e.get("sim_IPC")
            or e.get("cpu.IPC"),
            "L2_MissRate": e.get("L2_MissRate")
            or e.get("l2_miss_rate")
            or e.get("L2.miss_rate"),
            "Ticks": e.get("Ticks") or e.get("ticks") or e.get("sim_ticks"),
        }
        # Also retain everything for debugging
        out[app] = {**e, **metrics}
    return out


def _infer_app_from_path(path: str) -> str:
    base = os.path.basename(path)
    # Try patterns like gcc_LRU.json or directories like .../gcc_LRU/
    stem = os.path.splitext(base)[0]
    for delim in ["_", "-"]:
        parts = stem.split(delim)
        if parts:
            return parts[0]
    return stem


def merge_sets(
    lru512_paths: List[str],
    aip_paths: List[str],
    lvp_paths: List[str],
    lru576_paths: List[str],
) -> Tuple[Dict[str, Dict], Dict[str, Dict], Dict[str, Dict], Dict[str, Dict]]:
    lru512 = _index_by_app(_load_jsons(lru512_paths))
    aip512 = _index_by_app(_load_jsons(aip_paths))
    lvp512 = _index_by_app(_load_jsons(lvp_paths))
    lru576 = _index_by_app(_load_jsons(lru576_paths))
    return lru512, aip512, lvp512, lru576


def compute_speedups(
    lru512: Dict[str, Dict], other: Dict[str, Dict]
) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for app, base in lru512.items():
        ipc_base = base.get("IPC")
        cur = other.get(app)
        ipc_other = cur.get("IPC") if cur else None
        if ipc_base and ipc_other and ipc_base > 0:
            out[app] = (ipc_other / ipc_base - 1.0) * 100.0
    return out


def average(values: Dict[str, float]) -> float:
    if not values:
        return 0.0
    return sum(values.values()) / len(values)


def write_json(path: str, payload: Dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=2)


def write_csv(path: str, rows: List[List[str]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        for r in rows:
            fh.write(",".join(str(x) for x in r) + "\n")


def try_plot_bar(
    apps: List[str], series: Dict[str, Dict[str, float]], out_path: str
) -> None:
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception as e:
        print(
            f"warn: plotting skipped (matplotlib not available): {e}",
            file=sys.stderr,
        )
        return

    labels = apps
    x = np.arange(len(labels))
    width = 0.25

    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 0.8), 4.5))
    offs = [-width, 0, width]
    colors = ["#1f77b4", "#2ca02c", "#ff7f0e"]
    keys = list(series.keys())
    bars = []
    for i, key in enumerate(keys[:3]):
        values = [series[key].get(a, 0.0) for a in labels]
        bars.append(
            ax.bar(
                x + offs[i],
                values,
                width,
                label=key,
                color=colors[i % len(colors)],
            )
        )

    ax.set_ylabel("Speedup vs LRU-512KB (%)")
    ax.set_title("Cache Replacement Speedups (short runs)")
    ax.set_xticks(x, labels, rotation=30, ha="right")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.legend()
    fig.tight_layout()

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(
        description="Compute speedups and storage-overhead proxy, then plot."
    )
    ap.add_argument(
        "--lru512",
        nargs="+",
        required=True,
        help="JSON files/dirs/globs for LRU 512KB runs",
    )
    ap.add_argument(
        "--aip512",
        nargs="+",
        required=False,
        default=[],
        help="JSON files/dirs/globs for AIP 512KB runs",
    )
    ap.add_argument(
        "--lvp512",
        nargs="+",
        required=False,
        default=[],
        help="JSON files/dirs/globs for LvP 512KB runs",
    )
    ap.add_argument(
        "--lru576",
        nargs="+",
        required=False,
        default=[],
        help="JSON files/dirs/globs for LRU 576KB runs (storage overhead proxy)",
    )
    ap.add_argument(
        "--out-json", default="parsec_results/comparison_summary.json"
    )
    ap.add_argument(
        "--out-csv", default="parsec_results/comparison_summary.csv"
    )
    ap.add_argument(
        "--out-plot", default="parsec_results/comparison_summary.png"
    )
    args = ap.parse_args()

    lru512, aip512, lvp512, lru576 = merge_sets(
        args.lru512, args.aip512, args.lvp512, args.lru576
    )
    if not lru512:
        print("error: no LRU-512KB entries found", file=sys.stderr)
        sys.exit(2)

    apps = sorted(lru512.keys())

    speed_aip = compute_speedups(lru512, aip512) if aip512 else {}
    speed_lvp = compute_speedups(lru512, lvp512) if lvp512 else {}
    speed_lru576 = compute_speedups(lru512, lru576) if lru576 else {}

    summary = {
        "apps": apps,
        "averages": {
            "AIP_vs_LRU512_%": average(speed_aip) if speed_aip else None,
            "LvP_vs_LRU512_%": average(speed_lvp) if speed_lvp else None,
            "LRU576_vs_LRU512_%": (
                average(speed_lru576) if speed_lru576 else None
            ),
        },
        "per_app": {
            app: {
                "baseline_IPC": lru512.get(app, {}).get("IPC"),
                "AIP_speedup_%": speed_aip.get(app),
                "LvP_speedup_%": speed_lvp.get(app),
                "LRU576_speedup_%": speed_lru576.get(app),
            }
            for app in apps
        },
    }

    write_json(args.out_json, summary)

    # CSV: app, baseline_IPC, AIP%, LvP%, LRU576%
    rows = [
        [
            "app",
            "baseline_IPC",
            "AIP_speedup_%",
            "LvP_speedup_%",
            "LRU576_speedup_%",
        ]
    ]
    for app in apps:
        rows.append(
            [
                app,
                summary["per_app"][app]["baseline_IPC"],
                summary["per_app"][app]["AIP_speedup_%"],
                summary["per_app"][app]["LvP_speedup_%"],
                summary["per_app"][app]["LRU576_speedup_%"],
            ]
        )
    # Add averages row
    rows.append(
        [
            "AVERAGE",
            "",
            summary["averages"]["AIP_vs_LRU512_%"],
            summary["averages"]["LvP_vs_LRU512_%"],
            summary["averages"]["LRU576_vs_LRU512_%"],
        ]
    )
    write_csv(args.out_csv, rows)

    series = {
        "AIP vs LRU-512KB": speed_aip,
        "LvP vs LRU-512KB": speed_lvp,
        "LRU-576KB vs LRU-512KB": speed_lru576,
    }
    try_plot_bar(apps, series, args.out_plot)

    print(f"wrote: {args.out_json}")
    print(f"wrote: {args.out_csv}")
    if os.path.exists(args.out_plot):
        print(f"wrote: {args.out_plot}")


if __name__ == "__main__":
    main()
