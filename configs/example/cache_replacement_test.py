# Copyright (c) 2025
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met: redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer;
# redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution;
# neither the name of the copyright holders nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
Configuration script for testing cache replacement policies (AIP, LvP, LRU).

This script creates a system with the architecture parameters specified:
- 6-issue dynamic superscalar processor at 5 GHz
- L1 I/D caches: 16 KB, 2-way, 64B lines, 2-cycle latency
- L2 unified cache: 512 KB, 8-way, 64B lines, 10-cycle latency, Write-Back
- Configurable replacement policy (LRU, AIP, LvP)

Usage:
    build/X86/gem5.opt configs/example/cache_replacement_test.py \
        --replacement-policy=LRU \
        --benchmark=/path/to/binary \
        --fast-forward=2000000000 \
        --max-insts=3000000000
"""

import argparse
import sys

import m5
from m5.objects import *
from m5.util import addToPath

addToPath("../")

from common import (
    CacheConfig,
    MemConfig,
    Options,
    Simulation,
)
from common.cpu2000 import *


def create_cache_hierarchy(system, replacement_policy):
    """
    Create the cache hierarchy with specified replacement policy.

    Args:
        system: The system object
        replacement_policy: String specifying the policy (LRU, AIP, LvP, etc.)
    """

    # Set replacement policy
    if replacement_policy == "LRU":
        rp = LRURP()
    elif replacement_policy == "AIP":
        rp = AIPRP()
    elif replacement_policy == "LvP":
        rp = LvPRP()
    elif replacement_policy == "LFU":
        rp = LFURP()
    elif replacement_policy == "MRU":
        rp = MRURP()
    elif replacement_policy == "Random":
        rp = RandomRP()
    elif replacement_policy == "BRRIP":
        rp = BRRIPRP()
    elif replacement_policy == "SHiPPC":
        rp = SHiPPCRP()
    else:
        print(f"Unknown replacement policy: {replacement_policy}")
        print("Available: LRU, AIP, LvP, LFU, MRU, Random, BRRIP, SHiPPC")
        sys.exit(1)

    # L1 Data Cache: 16 KB, 2-way, 64B lines, 2-cycle latency
    system.cpu.dcache = Cache(
        size="16kB",
        assoc=2,
        tag_latency=2,
        data_latency=2,
        response_latency=2,
        mshrs=4,
        tgts_per_mshr=20,
        writeback_clean=False,
    )

    # L1 Instruction Cache: 16 KB, 2-way, 64B lines, 2-cycle latency
    system.cpu.icache = Cache(
        size="16kB",
        assoc=2,
        tag_latency=2,
        data_latency=2,
        response_latency=2,
        mshrs=4,
        tgts_per_mshr=20,
        writeback_clean=False,
    )

    # L2 Unified Cache: 512 KB, 8-way, 64B lines, 10-cycle latency
    system.l2cache = Cache(
        size="512kB",
        assoc=8,
        tag_latency=10,
        data_latency=10,
        response_latency=10,
        mshrs=20,
        tgts_per_mshr=12,
        writeback_clean=False,
        replacement_policy=rp,
    )

    # Connect L1 caches to CPU
    system.cpu.icache.cpu_side = system.cpu.icache_port
    system.cpu.dcache.cpu_side = system.cpu.dcache_port

    # Create L2 bus
    system.l2bus = L2XBar()

    # Connect L1 caches to L2 bus
    system.cpu.icache.mem_side = system.l2bus.cpu_side_ports
    system.cpu.dcache.mem_side = system.l2bus.cpu_side_ports

    # Connect L2 cache
    system.l2cache.cpu_side = system.l2bus.mem_side_ports

    # Connect L2 to memory bus
    system.l2cache.mem_side = system.membus.cpu_side_ports


def create_system(args):
    """Create and configure the system."""

    # Create the system
    system = System()

    # Set clock frequency to 5 GHz (200 ps period)
    system.clk_domain = SrcClockDomain()
    system.clk_domain.clock = "200ps"  # 5 GHz
    system.clk_domain.voltage_domain = VoltageDomain()

    # Create CPU: 6-issue out-of-order CPU
    system.cpu = X86O3CPU()
    system.cpu.fetchWidth = 6
    system.cpu.decodeWidth = 6
    system.cpu.renameWidth = 6
    system.cpu.dispatchWidth = 6
    system.cpu.issueWidth = 6
    system.cpu.wbWidth = 6
    system.cpu.commitWidth = 6

    # Set up memory
    system.mem_mode = "timing"
    system.mem_ranges = [AddrRange("8GB")]

    # Create memory bus
    system.membus = SystemXBar()

    # Create cache hierarchy
    create_cache_hierarchy(system, args.replacement_policy)

    # Connect CPU interrupt ports
    system.cpu.createInterruptController()

    # For X86, connect interrupts to memory bus
    system.cpu.interrupts[0].pio = system.membus.mem_side_ports
    system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
    system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports

    # For x86, connect I/O
    system.system_port = system.membus.cpu_side_ports

    # Create memory controller
    system.mem_ctrl = MemCtrl()
    system.mem_ctrl.dram = DDR3_1600_8x8()
    system.mem_ctrl.dram.range = system.mem_ranges[0]
    system.mem_ctrl.port = system.membus.mem_side_ports

    return system


def main():
    """Main function to set up and run the simulation."""

    parser = argparse.ArgumentParser(
        description="Cache replacement policy testing configuration"
    )

    parser.add_argument(
        "--replacement-policy",
        type=str,
        default="LRU",
        help="Replacement policy to test (LRU, AIP, LvP, LFU, MRU, Random, "
        "BRRIP, SHiPPC)",
    )

    parser.add_argument(
        "--benchmark",
        type=str,
        required=True,
        help="Path to the benchmark binary to run",
    )

    parser.add_argument(
        "--benchmark-args",
        type=str,
        default="",
        help="Arguments to pass to the benchmark",
    )

    parser.add_argument(
        "--fast-forward",
        type=int,
        default=2000000000,
        help="Number of instructions to fast-forward (default: 2 billion)",
    )

    parser.add_argument(
        "--max-insts",
        type=int,
        default=3000000000,
        help="Maximum instructions to simulate after fast-forward "
        "(default: 3 billion total, so 1 billion detailed)",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="m5out",
        help="Directory for output statistics",
    )

    args = parser.parse_args()

    # Create the system
    system = create_system(args)

    # Set up the workload
    process = Process()
    process.cmd = (
        [args.benchmark] + args.benchmark_args.split()
        if args.benchmark_args
        else [args.benchmark]
    )
    system.workload = SEWorkload.init_compatible(args.benchmark)
    system.cpu.workload = process
    system.cpu.createThreads()

    # Set up the root and instantiate
    root = Root(full_system=False, system=system)
    m5.instantiate()

    # Fast-forward if requested
    if args.fast_forward > 0:
        print(f"Fast-forwarding {args.fast_forward} instructions...")
        m5.stats.reset()
        exit_event = m5.simulate(args.fast_forward)
        print(f"Fast-forward complete. Event: {exit_event.getCause()}")
        m5.stats.reset()

    # Run detailed simulation
    print(
        f"Running detailed simulation for {args.max_insts - args.fast_forward} "
        f"instructions..."
    )
    exit_event = m5.simulate(args.max_insts - args.fast_forward)

    print(f"Simulation complete!")
    print(f"Exit event: {exit_event.getCause()}")

    # Dump statistics
    m5.stats.dump()

    print(f"\nResults written to {args.output_dir}/stats.txt")


if __name__ == "__m5_main__":
    main()
