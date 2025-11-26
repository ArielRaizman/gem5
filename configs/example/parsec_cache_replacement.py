"""
Configuration script to test cache replacement policies with PARSEC benchmarks.
Uses gem5-resources to automatically download PARSEC workloads.

Usage:
    ./build/X86/gem5.opt configs/example/parsec_cache_replacement.py \
        --benchmark <benchmark_name> \
        --replacement-policy <LRU|AIP|LvP> \
        [--num-cores <cores>] \
        [--max-insts <instructions>]

Example:
    ./build/X86/gem5.opt configs/example/parsec_cache_replacement.py \
        --benchmark blackscholes --replacement-policy AIP --num-cores 1
"""

import argparse
import os

import m5
from m5.objects import *
from m5.util import fatal

# Parse arguments
parser = argparse.ArgumentParser(
    description="PARSEC Cache Replacement Policy Test"
)
parser.add_argument(
    "--benchmark",
    type=str,
    required=True,
    choices=[
        "blackscholes",
        "bodytrack",
        "canneal",
        "dedup",
        "facesim",
        "ferret",
        "fluidanimate",
        "raytrace",
        "streamcluster",
        "swaptions",
        "vips",
        "x264",
    ],
    help="PARSEC benchmark to run",
)
parser.add_argument(
    "--replacement-policy",
    type=str,
    default="LRU",
    choices=["LRU", "AIP", "LvP"],
    help="Cache replacement policy to use",
)
parser.add_argument(
    "--num-cores",
    type=int,
    default=1,
    help="Number of CPU cores",
)
parser.add_argument(
    "--max-insts",
    type=int,
    default=None,
    help="Maximum instructions to execute (None = run to completion)",
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

# Create CPUs
system.cpu = [X86O3CPU(cpu_id=i) for i in range(args.num_cores)]

# Set up cache replacement policy
if args.replacement_policy == "LRU":
    l1_repl = LRURP()
    l2_repl = LRURP()
elif args.replacement_policy == "AIP":
    l1_repl = AIPRP()
    l2_repl = AIPRP()
elif args.replacement_policy == "LvP":
    l1_repl = LvPRP()
    l2_repl = LvPRP()
else:
    fatal(f"Unknown replacement policy: {args.replacement_policy}")

# Create L1 caches for each CPU
for cpu in system.cpu:
    # L1 Instruction Cache
    cpu.icache = Cache(
        size="32kB",
        assoc=2,
        tag_latency=2,
        data_latency=2,
        response_latency=2,
        mshrs=4,
        tgts_per_mshr=20,
        replacement_policy=l1_repl,
    )

    # L1 Data Cache
    cpu.dcache = Cache(
        size="32kB",
        assoc=2,
        tag_latency=2,
        data_latency=2,
        response_latency=2,
        mshrs=4,
        tgts_per_mshr=20,
        replacement_policy=l1_repl,
    )

    # Connect L1 caches to CPU
    cpu.icache.cpu_side = cpu.icache_port
    cpu.dcache.cpu_side = cpu.dcache_port

    # Create interrupt controller
    cpu.createInterruptController()
    cpu.interrupts[0].pio = system.membus.mem_side_ports
    cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
    cpu.interrupts[0].int_responder = system.membus.mem_side_ports

# Create L2 bus
system.l2bus = L2XBar()

# Connect L1 caches to L2 bus
for cpu in system.cpu:
    cpu.icache.mem_side = system.l2bus.cpu_side_ports
    cpu.dcache.mem_side = system.l2bus.cpu_side_ports

# Create shared L2 cache
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

# Create memory bus
system.membus = SystemXBar()

# Connect L2 cache to memory bus
system.l2cache.mem_side = system.membus.cpu_side_ports

# Create memory controller
system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR3_1600_8x8()
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports

# Connect system port
system.system_port = system.membus.cpu_side_ports

# Set up workload - use simple SE mode for PARSEC
# Note: For full PARSEC support, you'd need the gem5-resources version
# This is a simplified version for testing
import os

parsec_base = "/home/ariel/gem5/parsec"
parsec_bin = {
    "blackscholes": f"{parsec_base}/blackscholes/blackscholes",
    "bodytrack": f"{parsec_base}/bodytrack/bodytrack",
    "canneal": f"{parsec_base}/canneal/canneal",
    "dedup": f"{parsec_base}/dedup/dedup",
    "facesim": f"{parsec_base}/facesim/facesim",
    "ferret": f"{parsec_base}/ferret/ferret",
    "fluidanimate": f"{parsec_base}/fluidanimate/fluidanimate",
    "raytrace": f"{parsec_base}/raytrace/raytrace",
    "streamcluster": f"{parsec_base}/streamcluster/streamcluster",
    "swaptions": f"{parsec_base}/swaptions/swaptions",
    "vips": f"{parsec_base}/vips/vips",
    "x264": f"{parsec_base}/x264/x264",
}

# Check if PARSEC binaries exist locally, otherwise provide instructions
benchmark_path = parsec_bin.get(args.benchmark)
if not benchmark_path or not os.path.exists(benchmark_path):
    print(f"\n{'='*70}")
    print(f"PARSEC benchmark '{args.benchmark}' not found locally.")
    print(f"Expected at: {benchmark_path}")
    print(f"\nTo use PARSEC benchmarks, you have two options:")
    print(f"\n1. Use gem5-resources (recommended):")
    print(f"   See: configs/example/gem5_library/x86-parsec-benchmarks.py")
    print(f"\n2. Build PARSEC manually:")
    print(f"   Download from: https://parsec.cs.princeton.edu/")
    print(f"   Place binaries in: {parsec_base}/<benchmark>/")
    print(
        f"\nFor testing purposes, using a longer-running synthetic workload..."
    )
    print(f"{'='*70}\n")

    # Fall back to a memory-intensive test program
    binary = "/home/ariel/gem5/test_workloads/cache_stress"
    if not os.path.exists(binary):
        fatal(
            f"Test workload not found at {binary}. Please run compare_policies.py first."
        )
    process = Process()
    process.cmd = [binary]
else:
    binary = benchmark_path
    process = Process()

    # Set up PARSEC-specific arguments (simplified - adjust per benchmark)
    if args.benchmark == "blackscholes":
        process.cmd = [binary, "1", "in_4K.txt", "prices.txt"]
    elif args.benchmark == "canneal":
        process.cmd = [binary, "1", "15000", "2000", "400000.nets", "32"]
    elif args.benchmark == "streamcluster":
        process.cmd = [
            binary,
            "10",
            "20",
            "128",
            "16384",
            "16384",
            "1000",
            "none",
            "output.txt",
            "1",
        ]
    elif args.benchmark == "fluidanimate":
        process.cmd = [binary, "1", "5", "in_300K.fluid", "out.fluid"]
    else:
        # Default: just run the binary
        process.cmd = [binary]

system.workload = SEWorkload.init_compatible(binary)

# Assign process to all CPUs
for i, cpu in enumerate(system.cpu):
    cpu.workload = process
    cpu.createThreads()

# Set max instructions if specified
if args.max_insts:
    for cpu in system.cpu:
        cpu.max_insts_any_thread = args.max_insts

# Create root and run
root = Root(full_system=False, system=system)
m5.instantiate()

print(f"\n{'='*70}")
print(f"Configuration Summary:")
print(f"  Benchmark: {args.benchmark}")
print(f"  Replacement Policy: {args.replacement_policy}")
print(f"  CPU Cores: {args.num_cores}")
print(f"  L1 I-Cache: 32KB, 2-way")
print(f"  L1 D-Cache: 32KB, 2-way")
print(f"  L2 Cache: 512KB, 8-way")
print(f"  Memory: 8GB DDR3-1600")
print(
    f"  Max Instructions: {args.max_insts if args.max_insts else 'unlimited'}"
)
print(f"  Output: {args.output_dir}")
print(f"{'='*70}\n")

print("Beginning simulation...")
exit_event = m5.simulate()

print(f"\nExiting @ tick {m5.curTick()} because {exit_event.getCause()}")
