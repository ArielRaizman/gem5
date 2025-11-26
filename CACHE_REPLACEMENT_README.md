# Cache Replacement Policy Implementation: AIP and LvP

This project implements two advanced counter-based cache replacement algorithms in gem5:
- **AIP (Access Interval Predictor)**: Counts accesses to the set between consecutive accesses to a line
- **LvP (Live-time Predictor)**: Counts accesses to the line itself during its generation time

## Overview

Both algorithms use a 40KB prediction table to learn access patterns and predict when cache lines should be evicted, significantly improving performance over traditional LRU for memory-intensive workloads.

### Key Features

- **Counter-based prediction**: Uses 4-bit saturating counters to track access patterns
- **Prediction table**: 256×256 table indexed by hashed PC and line address
- **Confidence bits**: Ensures high-quality predictions before early eviction
- **MRU protection**: Never evicts the most recently used block
- **Fallback to LRU**: Uses LRU when no blocks have expired

## Implementation Details

### File Structure

```
src/mem/cache/replacement_policies/
├── aip_rp.hh              # AIP header file
├── aip_rp.cc              # AIP implementation
├── lvp_rp.hh              # LvP header file
├── lvp_rp.cc              # LvP implementation
├── ReplacementPolicies.py # Python bindings
└── SConscript             # Build configuration

configs/example/
├── cache_replacement_test.py  # Configuration script
├── run_benchmark.py           # Benchmark runner
└── analyze_results.py         # Analysis and visualization
```

### Architecture Parameters

Based on the research specification:
- **Processor**: 6-issue dynamic superscalar, 5 GHz
- **L1 Caches**: 16 KB, 2-way, 64B lines, 2-cycle latency
- **L2 Cache**: 512 KB, 8-way, 64B lines, 10-cycle latency, Write-Back
- **Prediction Table**: 40 KB (256×256 with 4-bit entries)

### AIP Algorithm

**Per-line metadata (21 bits per 64B line):**
- hashedPC: 8 bits
- eventCounter: 4 bits (saturating)
- maxCountPast: 4 bits
- maxCountPresent: 4 bits
- confidence: 1 bit

**Operation:**
1. On any set access: Increment all blocks' event counters in the set
2. On cache hit: Update maxCountPresent, reset event counter
3. On cache miss: Evict expired blocks (counter > both maxCountPast and maxCountPresent)

### LvP Algorithm

**Per-line metadata (17 bits per 64B line):**
- hashedPC: 8 bits
- eventCounter: 4 bits (saturating)
- maxCountPast: 4 bits
- confidence: 1 bit

**Operation:**
1. On cache hit: Increment only the hit block's counter
2. On cache miss: Evict expired blocks (counter >= maxCountPast)

## Building gem5

```bash
# Navigate to gem5 directory
cd /home/ariel/gem5

# Build gem5 for X86
scons build/X86/gem5.opt -j$(nproc)
```

## Running Benchmarks

### Single Benchmark Test

```bash
# Test with LRU (baseline)
build/X86/gem5.opt configs/example/cache_replacement_test.py \
    --replacement-policy=LRU \
    --benchmark=/path/to/benchmark \
    --fast-forward=2000000000 \
    --max-insts=3000000000

# Test with AIP
build/X86/gem5.opt configs/example/cache_replacement_test.py \
    --replacement-policy=AIP \
    --benchmark=/path/to/benchmark \
    --fast-forward=2000000000 \
    --max-insts=3000000000

# Test with LvP
build/X86/gem5.opt configs/example/cache_replacement_test.py \
    --replacement-policy=LvP \
    --benchmark=/path/to/benchmark \
    --fast-forward=2000000000 \
    --max-insts=3000000000
```

### Comprehensive Benchmark Suite

```bash
# Run all Group A benchmarks with all policies
python3 configs/example/run_benchmark.py \
    --gem5-binary=build/X86/gem5.opt \
    --benchmarks-dir=/path/to/spec2000 \
    --output-dir=benchmark_results
```

This will:
1. Run 10 SPEC2000 benchmarks (ammp, apsi, art, bzip2, gcc, mcf, mgrid, swim, twolf, vpr)
2. Test 7 replacement policies (LRU, AIP, LvP, LFU, Random, BRRIP, SHiPPC)
3. Fast-forward 2B instructions, then simulate 1B instructions in detail
4. Collect comprehensive statistics
5. Save results to JSON file

## Analyzing Results

```bash
# Generate all visualizations and reports
python3 configs/example/analyze_results.py \
    benchmark_results/benchmark_results_TIMESTAMP.json \
    --output-dir=analysis_output
```

This generates:
- **ipc_comparison.png**: IPC comparison across all policies
- **speedup_vs_LRU.png**: Speedup relative to baseline LRU
- **miss_rate_comparison.png**: L2 cache miss rates
- **average_metrics.png**: Summary of average performance
- **heatmap_ipc.png**: IPC heatmap by benchmark and policy
- **heatmap_l2_overall_miss_rate.png**: Miss rate heatmap
- **policy_radar_comparison.png**: Multi-dimensional policy comparison
- **summary_report.txt**: Detailed text report

## Expected Results

Based on the research paper, you should observe:

### Group A Benchmarks (Memory-Intensive)
- **Average Speedup**: ~11% for both AIP and LvP vs LRU
- **Peak Speedup**: Up to 40% (e.g., gcc)
- **Coverage**: ~76% of optimal (OPT) evictions correctly predicted
- **Accuracy**: 95-96% correct predictions

### Key Metrics to Monitor
- **IPC (Instructions Per Cycle)**: Higher is better
- **L2 Miss Rate**: Lower is better
- **Speedup vs LRU**: > 1.0 indicates improvement
- **Consistency**: Similar performance across benchmarks

## Available Replacement Policies

The implementation supports comparison with:
- **LRU**: Least Recently Used (baseline)
- **AIP**: Access Interval Predictor (new)
- **LvP**: Live-time Predictor (new)
- **LFU**: Least Frequently Used
- **MRU**: Most Recently Used
- **Random**: Random replacement
- **BRRIP**: Bimodal RRIP
- **SHiPPC**: Signature-based Hit Predictor (PC-based)

## Technical Implementation Notes

### Hashing Functions
- XOR-folding used for both PC and address hashing
- Distributes values uniformly across 8-bit space (0-255)

### Counter Management
- 4-bit saturating counters (max value: 15)
- Prevents overflow while maintaining meaningful counts

### MRU Detection
- Uses lastTouchTick (highest value = MRU)
- Ensures MRU blocks are never evicted prematurely

### Prediction Table Updates
- Updated on eviction with the evicted block's information
- Confidence set based on predictability (consistency between generations)

## Debugging and Troubleshooting

### Enable Debug Flags
```bash
# Run with cache debug information
build/X86/gem5.opt --debug-flags=Cache configs/example/cache_replacement_test.py ...

# Run with replacement policy debug information
build/X86/gem5.opt --debug-flags=CacheRepl configs/example/cache_replacement_test.py ...
```

### Check Statistics
```bash
# View key statistics
grep -E "(ipc|miss_rate|overall_hits)" m5out/stats.txt
```

### Common Issues

1. **Build errors**: Ensure all header files are properly included
2. **Missing PC information**: Some accesses may not have PC (handled gracefully)
3. **Performance lower than expected**: Verify benchmark is memory-intensive (Group A)

## Performance Optimization

### For AIP
- Set access tracking happens on every set access
- Consider hardware implementation with parallel counter updates

### For LvP
- Simpler than AIP (no maxCountPresent)
- Lower metadata overhead (17 vs 21 bits per line)

## Research Reference

These implementations are based on the methodology described in counter-based cache replacement research, specifically targeting:
- Capacity miss reduction in LLC (Last Level Cache)
- Predictable access patterns in memory-intensive applications
- Hardware-efficient prediction mechanisms

## Contributing

To add new replacement policies:
1. Create `.hh` and `.cc` files in `src/mem/cache/replacement_policies/`
2. Add entries to `ReplacementPolicies.py`
3. Update `SConscript`
4. Implement required methods: `invalidate()`, `touch()`, `reset()`, `getVictim()`, `instantiateEntry()`

## License

These implementations follow gem5's BSD-style license. See individual file headers for details.

## Contact and Support

For issues, questions, or contributions related to these implementations, please refer to the gem5 community resources.

---

**Implementation Date**: November 2025
**gem5 Version**: Compatible with gem5 stable branch
**Target Architecture**: X86 (easily adaptable to other ISAs)
