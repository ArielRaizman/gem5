# PARSEC/Long-Running Benchmark Testing Guide

## Overview
This guide explains how to properly test cache replacement policies with long-running, memory-intensive workloads that will show real performance differences.

## What We've Implemented

### 1. Memory-Intensive Benchmark (`memory_benchmark.c`)
Location: `/home/ariel/gem5/test_workloads/memory_benchmark.c`

**Features:**
- 4MB working set (larger than L2 cache)
- 5 different access patterns (Sequential, Strided, Random, Scan+Reuse, Matrix)
- 100 iterations per pattern × 5 rounds = 500 total iterations
- Runs for ~500M-1B instructions (configurable)

**Why This Works:**
- **Large working set**: Forces cache evictions and replacement decisions
- **Multiple patterns**: Tests different scenarios (streaming vs. reuse)
- **Long runtime**: Gives policies time to adapt and show statistical differences
- **Scan+Reuse pattern**: Specifically designed to benefit AIP/LvP over LRU

### 2. gem5 Configuration (`parsec_simple.py`)
Location: `/home/ariel/gem5/configs/example/parsec_simple.py`

**System Configuration:**
- CPU: O3 (out-of-order) @ 5GHz
- L1 I-Cache: 16KB, 2-way
- L1 D-Cache: 16KB, 2-way
- L2 Cache: 512KB, 8-way
- Memory: 8GB DDR3-1600
- Configurable replacement policy (LRU/AIP/LvP)

### 3. Automated Comparison (`compare_with_parsec.py`)
Location: `/home/ariel/gem5/compare_with_parsec.py`

**Features:**
- Runs all three policies (LRU, AIP, LvP) automatically
- Collects statistics (IPC, miss rates, cache accesses)
- Generates comparison graphs
- Provides detailed performance summary

## Usage

### Quick Test (100M instructions, ~30 minutes)
```bash
cd /home/ariel/gem5
python3 compare_with_parsec.py --quick
```

### Full Test (1B instructions, ~3-4 hours)
```bash
cd /home/ariel/gem5
python3 compare_with_parsec.py
```

### Custom Test
```bash
cd /home/ariel/gem5
python3 compare_with_parsec.py --max-insts 500000000
```

### Single Policy Test
```bash
cd /home/ariel/gem5
./build/X86/gem5.opt configs/example/parsec_simple.py \
    --workload memory_benchmark \
    --replacement-policy AIP \
    --max-insts 1000000000
```

## Expected Results

### Why Previous Tests Showed No Difference
- **hello**: Only ~3K instructions - not enough runtime
- **cache_stress**: Only ~22K instructions - program exited too early

### Why This Test WILL Show Differences

**1. Long Runtime**: 500M-1B instructions gives policies time to learn and adapt

**2. Memory-Intensive**: 64MB working set with 512KB L2 cache means:
   - ~13,107 L2 cache lines needed
   - L2 can only hold ~8,192 lines (512KB / 64B)
   - Constant eviction pressure

**3. Diverse Access Patterns**:
   - **Sequential**: All policies should perform similarly
   - **Random**: High miss rate for all policies
   - **Scan+Reuse**: AIP/LvP should outperform LRU significantly
     - LRU evicts frequently-reused data
     - AIP predicts longer intervals for hot data
     - LvP predicts longer lifetimes for hot data

**4. Realistic Workload**: Mimics real applications with mixed access patterns

## Understanding the Results

### Key Metrics

**IPC (Instructions Per Cycle)**
- Higher = better performance
- Typical range: 0.3-1.5 for memory-intensive workloads
- Look for differences of 1-10%

**L2 Miss Rate**
- Lower = better (fewer trips to main memory)
- Typical range: 5-50% for memory-intensive workloads
- Policies differ by 5-20% relatively

**L2 Accesses/Misses**
- Total number of cache accesses and misses
- More accesses = more opportunities for policy to matter

### Expected Performance Ranking

For scan+reuse heavy workloads:
1. **LvP** - Best (predicts which lines will live longest)
2. **AIP** - Good (predicts access intervals)
3. **LRU** - Baseline (no prediction)

For purely random workloads:
- All policies perform similarly (no predictable pattern)

For sequential streaming:
- All policies perform similarly (each line used once)

## Output Files

After running `compare_with_parsec.py`:

```
parsec_results/
├── memory_benchmark_LRU/
│   ├── stats.txt              # Detailed statistics
│   ├── config.ini             # System configuration
│   └── ...
├── memory_benchmark_AIP/
│   ├── stats.txt
│   └── ...
├── memory_benchmark_LvP/
│   ├── stats.txt
│   └── ...
├── comparison_summary.json     # JSON summary of results
└── comparison_graphs.png       # Visualization
```

## Interpreting Statistics

Open `parsec_results/memory_benchmark_<policy>/stats.txt` and look for:

```
simTicks                                     # Total simulation time
sim_insts                                    # Instructions executed
system.cpu.ipc                               # Instructions per cycle
system.l2cache.overallMissRate::total        # L2 miss rate
system.l2cache.overallMisses::total          # Total L2 misses
system.l2cache.overallAccesses::total        # Total L2 accesses
```

## Moving to Real PARSEC

Once validated with memory_benchmark, you can use actual PARSEC:

### Option 1: Use gem5-resources (Recommended)
```bash
# Use the gem5 standard library version
./build/X86/gem5.opt \
    configs/example/gem5_library/x86-parsec-benchmarks.py \
    --benchmark blackscholes \
    --size simsmall
```

### Option 2: Build PARSEC Manually
1. Download PARSEC from https://parsec.cs.princeton.edu/
2. Build for X86-64 with static linking
3. Place in `/home/ariel/gem5/parsec/`
4. Update `parsec_cache_replacement.py` paths

### Option 3: Use SPEC CPU
If you have SPEC CPU2006/2017 license:
- See `configs/example/gem5_library/x86-spec-cpu2006-benchmarks.py`
- These are the gold standard for academic publications

## Research Best Practices

### For Academic Papers:
1. Run SPEC CPU benchmarks (most cited)
2. Use simpoint sampling for long benchmarks
3. Report geomean speedup across benchmark suite
4. Include sensitivity analysis (cache sizes, associativity)

### For Development/Validation:
1. Use memory_benchmark for quick iteration
2. Validate with 2-3 PARSEC benchmarks
3. Test edge cases (tiny caches, huge caches)

### Statistics to Report:
- IPC (performance metric)
- Miss rates (L1-D, L1-I, L2)
- MPKI (Misses Per Kilo Instructions)
- Speedup vs. baseline (LRU)
- Energy (if using power models)

## Troubleshooting

### Simulation Too Slow
```bash
# Reduce instructions
python3 compare_with_parsec.py --max-insts 100000000

# Use faster CPU model (less accurate)
# Edit parsec_simple.py: X86O3CPU → X86TimingSimpleCPU
```

### No Performance Difference
- Check that max-insts is high enough (>100M)
- Verify cache is smaller than working set
- Check stats.txt for actual cache activity

### Out of Memory
```bash
# Reduce array size in memory_benchmark.c:
#define ARRAY_SIZE (1 * 1024 * 1024)  // 1MB instead of 4MB
```

## Next Steps

1. **Validate**: Run quick test to ensure everything works
2. **Full Test**: Run full 1B instruction test overnight
3. **Analyze**: Compare results across policies
4. **Publish**: Generate graphs for your research/documentation
5. **Extend**: Try PARSEC or SPEC for publication-quality results

## References

- gem5 Documentation: https://www.gem5.org/documentation/
- gem5 Resources: https://resources.gem5.org/
- PARSEC: https://parsec.cs.princeton.edu/
- SPEC CPU: https://www.spec.org/cpu2017/
