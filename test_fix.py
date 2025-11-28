#!/usr/bin/env python3
# Quick test to verify the fix works
import subprocess
import sys

print("Testing compare_with_parsec.py syntax...")
result = subprocess.run(
    ["python3", "-m", "py_compile", "compare_with_parsec.py"],
    capture_output=True
)

if result.returncode == 0:
    print("✓ Syntax is valid!")
else:
    print("✗ Syntax error:")
    print(result.stderr.decode())
    sys.exit(1)

print("\nYou can now run:")
print("  python3 compare_with_parsec.py --quick")
print("  python3 compare_with_parsec.py  # Full test (no timeout)")
