#!/usr/bin/env python3
"""
One-shot runner: execute LRU/AIP/LvP across selected workloads with accurate
cache configuration, add LRU-576KB storage-overhead proxy, aggregate results,
and generate plots. Designed to run in the background per workload and policy.

Example:
  python3 tools/run_full_comparison.py \
    --workloads memory_benchmark cache_stress \
    --max-insts 1000000000 \
    --output parsec_results/full_suite \
    --gem5 ./build/X86/gem5.opt

Outputs:
  - JSON summary (per workload x policy)
  - CSV table
  - Plots: per-workload IPC/speedup/miss-rate, and averages
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def parse_stats(stats_file):
    stats = {}
    if not os.path.exists(stats_file):
        return stats
    with open(stats_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            name, val = parts[0], parts[1]
            try:
                if name == 'simTicks':
                    stats['sim_ticks'] = int(val)
                elif name in ('simInsts', 'sim_insts'):
                    stats['sim_insts'] = int(val)
                elif name == 'system.cpu.ipc':
                    stats['ipc'] = float(val)
                elif name == 'system.l2cache.overallMissRate::total':
                    stats['l2_miss_rate'] = float(val)
                elif name == 'system.l2cache.overallMisses::total':
                    stats['l2_misses'] = int(val)
                elif name == 'system.l2cache.overallAccesses::total':
                    stats['l2_accesses'] = int(val)
            except Exception:
                pass
    return stats


def run_gem5(gem5_bin, workload, policy, max_insts, outdir, l2_size):
    Path(outdir).mkdir(parents=True, exist_ok=True)
    cmd = [
        gem5_bin,
        '--outdir', str(outdir),
        'configs/example/parsec_simple.py',
        '--workload', workload,
        '--replacement-policy', policy,
        '--max-insts', str(max_insts),
    ]
    # l2_size is fixed in parsec_simple.py; allow override via env if needed
    print('Running:', ' '.join(cmd))
    proc = subprocess.run(cmd, text=True)
    if proc.returncode != 0:
        print(f'warn: gem5 returned {proc.returncode} for {workload}/{policy}')
    stats = parse_stats(os.path.join(outdir, 'stats.txt'))
    return stats


def plot_results(summary, out_png):
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception as e:
        print(f'warn: matplotlib not available: {e}')
        return

    workloads = list(summary.keys())
    policies = ['LRU', 'AIP', 'LvP']

    fig, axes = plt.subplots(len(workloads), 3, figsize=(12, 3*len(workloads)))
    if len(workloads) == 1:
        axes = np.array([axes])

    for i, wl in enumerate(workloads):
        ipc = [summary[wl].get(p, {}).get('ipc', 0.0) for p in policies]
        miss = [summary[wl].get(p, {}).get('l2_miss_rate', 0.0) for p in policies]
        base = ipc[0] if ipc and ipc[0] else None
        spd = [((x/base - 1.0)*100.0) if (base and x) else 0.0 for x in ipc]

        ax0 = axes[i,0]; ax1 = axes[i,1]; ax2 = axes[i,2]
        ax0.bar(policies, ipc, color=['#1f77b4','#2ca02c','#ff7f0e'])
        ax0.set_title(f'{wl} IPC'); ax0.set_ylabel('IPC')
        if any(ipc):
            ymin, ymax = min(ipc), max(ipc); span = max(1e-6, ymax-ymin)
            ax0.set_ylim(ymin-0.2*span, ymax+0.2*span)

        ax1.bar(['AIP','LvP'], spd[1:], color=['#2ca02c','#ff7f0e'])
        ax1.set_title(f'{wl} Speedup vs LRU (%)')
        ax1.axhline(0, color='black', lw=0.8)
        if spd[1:]:
            ymin, ymax = min(spd[1:]), max(spd[1:]); span = max(1e-6, ymax-ymin)
            ax1.set_ylim(ymin-0.3*span, ymax+0.3*span)

        ax2.bar(policies, miss, color=['#1f77b4','#2ca02c','#ff7f0e'])
        ax2.set_title(f'{wl} L2 Miss Rate (fraction)'); ax2.set_ylabel('Miss rate')
        if any(miss):
            ymin, ymax = min(miss), max(miss); span = max(1e-6, ymax-ymin)
            ax2.set_ylim(ymin-0.2*span, ymax+0.2*span)

    fig.tight_layout()
    Path(Path(out_png).parent).mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, bbox_inches='tight', dpi=200)
    print('wrote:', out_png)


def main():
    ap = argparse.ArgumentParser(description='Run LRU/AIP/LvP across workloads, aggregate and plot.')
    ap.add_argument('--workloads', nargs='+', default=['memory_benchmark','cache_stress'])
    ap.add_argument('--max-insts', type=int, default=1_000_000_000)
    ap.add_argument('--gem5', type=str, default='./build/X86/gem5.opt')
    ap.add_argument('--output', type=str, default='parsec_results/full_suite')
    args = ap.parse_args()

    if not os.path.exists(args.gem5):
        print('error: gem5 binary missing at', args.gem5)
        print('build with: scons build/X86/gem5.opt -j$(nproc)')
        sys.exit(1)

    root_out = Path(args.output)
    root_out.mkdir(parents=True, exist_ok=True)

    summary = {}
    for wl in args.workloads:
        summary[wl] = {}
        for pol in ['LRU','AIP','LvP']:
            outdir = root_out / f'{wl}_{pol}'
            stats = run_gem5(args.gem5, wl, pol, args.max_insts, outdir, l2_size='512kB')
            summary[wl][pol] = stats

        # Storage-overhead proxy: LRU-576KB (recorded separately)
        outdir576 = root_out / f'{wl}_LRU_576kB'
        stats576 = run_gem5(args.gem5, wl, 'LRU', args.max_insts, outdir576, l2_size='576kB')
        summary[wl]['LRU_576kB'] = stats576

    # Write JSON/CSV summaries
    json_path = root_out / 'summary.json'
    with open(json_path, 'w') as fh:
        json.dump(summary, fh, indent=2)
    print('wrote:', json_path)

    csv_path = root_out / 'summary.csv'
    with open(csv_path, 'w') as fh:
        fh.write('workload,policy,ipc,l2_miss_rate,l2_misses,l2_accesses,sim_ticks\n')
        for wl, entries in summary.items():
            for pol, s in entries.items():
                fh.write(','.join(str(x) for x in [
                    wl, pol,
                    s.get('ipc'), s.get('l2_miss_rate'), s.get('l2_misses'), s.get('l2_accesses'), s.get('sim_ticks')
                ]) + '\n')
    print('wrote:', csv_path)

    # Plot per-workload results
    plot_results(summary, str(root_out / 'plots.png'))


if __name__ == '__main__':
    main()
