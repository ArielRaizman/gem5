"""
Simplified PARSEC-style benchmark configuration for cache replacement testing.
This uses longer-running workloads to properly test replacement policies.

Usage:
    ./build/X86/gem5.opt configs/example/parsec_simple.py \
        --workload <name> \
        --replacement-policy <LRU|AIP|LvP> \
        [--max-insts <N>]
"""

import argparse
import os
import sys

import m5
from m5.objects import *
from m5.util import fatal

# Add path for common configs
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "common"))

# Parse arguments
parser = argparse.ArgumentParser(
    description="Cache Replacement Policy Test with Memory-Intensive Workloads"
)
parser.add_argument(
    "--workload",
    type=str,
    default="cache_stress",
    help="Workload to run (default: cache_stress)",
)
parser.add_argument(
    "--replacement-policy",
    type=str,
    default="LRU",
    choices=["LRU", "AIP", "LvP"],
    help="Cache replacement policy to use",
)
parser.add_argument(
    "--max-insts",
    type=int,
    default=500_000_000,  # 500M instructions - enough to see differences
    help="Maximum instructions to execute (default: 500M)",
)
parser.add_argument(
    "--output-dir",
    type=str,
    default="m5out",
    help="Output directory for stats",
)

args = parser.parse_args()

# Create the system
system = System()
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = "5GHz"
system.clk_domain.voltage_domain = VoltageDomain()

# Set up memory
system.mem_mode = "timing"
system.mem_ranges = [AddrRange("8GB")]

# Create CPU
system.cpu = X86O3CPU()

# Set up cache replacement policy
if args.replacement_policy == "LRU":
    l1i_repl = LRURP()
    l1d_repl = LRURP()
    l2_repl = LRURP()
elif args.replacement_policy == "AIP":
    l1i_repl = AIPRP()
    l1d_repl = AIPRP()
    l2_repl = AIPRP()
elif args.replacement_policy == "LvP":
    l1i_repl = LvPRP()
    l1d_repl = LvPRP()
    l2_repl = LvPRP()
else:
    fatal(f"Unknown replacement policy: {args.replacement_policy}")

# L1 Instruction Cache
system.cpu.icache = Cache(
    size="16kB",
    assoc=2,
    tag_latency=2,
    data_latency=2,
    response_latency=2,
    mshrs=4,
    tgts_per_mshr=20,
    replacement_policy=l1i_repl,
)

# L1 Data Cache
system.cpu.dcache = Cache(
    size="16kB",
    assoc=2,
    tag_latency=2,
    data_latency=2,
    response_latency=2,
    mshrs=4,
    tgts_per_mshr=20,
    replacement_policy=l1d_repl,
)

# L2 Bus
system.l2bus = L2XBar()

# Connect L1 caches to CPU and L2 bus
system.cpu.icache.cpu_side = system.cpu.icache_port
system.cpu.dcache.cpu_side = system.cpu.dcache_port
system.cpu.icache.mem_side = system.l2bus.cpu_side_ports
system.cpu.dcache.mem_side = system.l2bus.cpu_side_ports

# L2 Cache
system.l2cache = Cache(
    size="512kB",
    assoc=8,
    tag_latency=10,
    data_latency=10,
    response_latency=10,
    mshrs=20,
    tgts_per_mshr=12,
    replacement_policy=l2_repl,
)

# Connect L2 cache
system.l2cache.cpu_side = system.l2bus.mem_side_ports

# Memory bus
system.membus = SystemXBar()

# Connect L2 to memory bus
system.l2cache.mem_side = system.membus.cpu_side_ports

# Memory controller
system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR3_1600_8x8()
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports

# Interrupt controller
system.cpu.createInterruptController()
system.cpu.interrupts[0].pio = system.membus.mem_side_ports
system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports

# System port
system.system_port = system.membus.cpu_side_ports

# Set up workload
workload_path = f"/home/ariel/gem5/test_workloads/{args.workload}"
if not os.path.exists(workload_path):
    fatal(
        f"Workload not found: {workload_path}\n"
        f"Available workloads should be in /home/ariel/gem5/test_workloads/"
    )

binary = workload_path
system.workload = SEWorkload.init_compatible(binary)

process = Process()
process.cmd = [binary]
system.cpu.workload = process
system.cpu.createThreads()

# Set max instructions
system.cpu.max_insts_any_thread = args.max_insts

# Create root and run
root = Root(full_system=False, system=system)
m5.instantiate()

print("=" * 70)
print(f"Configuration Summary:")
print(f"  Workload: {args.workload}")
print(f"  Replacement Policy: {args.replacement_policy}")
print(f"  L1 I-Cache: 16KB, 2-way, {args.replacement_policy}")
print(f"  L1 D-Cache: 16KB, 2-way, {args.replacement_policy}")
print(f"  L2 Cache: 512KB, 8-way, {args.replacement_policy}")
print(f"  Memory: 8GB DDR3-1600")
print(f"  Max Instructions: {args.max_insts:,}")
print(f"  CPU: O3 @ 5GHz")
print(f"  Output: {args.output_dir}")
print("=" * 70)

print("\nBeginning simulation...")
exit_event = m5.simulate()

print(f"\nExiting @ tick {m5.curTick()} because {exit_event.getCause()}")
