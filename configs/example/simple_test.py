#!/usr/bin/env python3
"""
Simple test to verify AIP and LvP replacement policies are working correctly.

This script creates a minimal test that exercises the replacement policies
without requiring full SPEC2000 benchmarks.
"""

import subprocess
import sys
from pathlib import Path


def run_simple_test(policy_name):
    """Run a simple test with the specified replacement policy."""

    print(f"\n{'='*60}")
    print(f"Testing {policy_name} Replacement Policy")
    print(f"{'='*60}")

    # Use a simple test program
    test_program = "tests/test-progs/hello/bin/x86/linux/hello"

    if not Path(test_program).exists():
        print(f"ERROR: Test program not found: {test_program}")
        print("Please build gem5 test programs first")
        return False

    output_dir = f"simple_test_{policy_name.lower()}"

    cmd = [
        "build/X86/gem5.opt",
        "--outdir",
        output_dir,
        "configs/example/cache_replacement_test.py",
        "--replacement-policy",
        policy_name,
        "--benchmark",
        test_program,
        "--fast-forward",
        "0",
        "--max-insts",
        "1000000",
    ]

    try:
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300
        )

        if result.returncode != 0:
            print(f"ERROR: Test failed with return code {result.returncode}")
            print(f"STDERR: {result.stderr}")
            return False

        # Parse basic stats
        stats_file = Path(output_dir) / "stats.txt"
        if stats_file.exists():
            with open(stats_file) as f:
                for line in f:
                    if "system.cpu.ipc" in line and "total" in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            print(f"IPC: {parts[1]}")
                    elif "system.l2cache.overall_miss_rate::total" in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            print(f"L2 Miss Rate: {float(parts[1])*100:.2f}%")

        print(f"✓ {policy_name} test PASSED")
        return True

    except subprocess.TimeoutExpired:
        print(f"ERROR: Test timed out")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def main():
    """Run tests for all implemented policies."""

    print("\n" + "=" * 60)
    print("Cache Replacement Policy Simple Test Suite")
    print("=" * 60)

    # Check if gem5 is built
    if not Path("build/X86/gem5.opt").exists():
        print("ERROR: gem5 binary not found at build/X86/gem5.opt")
        print("Please build gem5 first: scons build/X86/gem5.opt -j$(nproc)")
        sys.exit(1)

    policies = ["LRU", "AIP", "LvP"]
    results = {}

    for policy in policies:
        results[policy] = run_simple_test(policy)

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    all_passed = True
    for policy, passed in results.items():
        status = "PASSED ✓" if passed else "FAILED ✗"
        print(f"{policy:10s}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n✓ All tests PASSED!")
        sys.exit(0)
    else:
        print("\n✗ Some tests FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
