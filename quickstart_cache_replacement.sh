#!/bin/bash
# Quick-start script for building and testing AIP/LvP replacement policies

set -e  # Exit on error

echo "=========================================="
echo "gem5 Cache Replacement Policy Quick Start"
echo "=========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the gem5 directory
if [ ! -f "SConstruct" ]; then
    echo -e "${RED}ERROR: This script must be run from the gem5 root directory${NC}"
    exit 1
fi

# Function to print status
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Parse command line arguments
BUILD_ONLY=false
TEST_ONLY=false
ANALYZE_ONLY=false
FULL_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --build-only)
            BUILD_ONLY=true
            shift
            ;;
        --test-only)
            TEST_ONLY=true
            shift
            ;;
        --analyze-only)
            ANALYZE_ONLY=true
            shift
            ;;
        --full-run)
            FULL_RUN=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --build-only     Only build gem5, don't run tests"
            echo "  --test-only      Only run tests (skip building)"
            echo "  --analyze-only   Only analyze existing results"
            echo "  --full-run       Build, test, and analyze"
            echo "  --help           Show this help message"
            echo ""
            echo "If no options are specified, only building is performed."
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# If no flags set, default to build only
if [ "$BUILD_ONLY" = false ] && [ "$TEST_ONLY" = false ] && \
   [ "$ANALYZE_ONLY" = false ] && [ "$FULL_RUN" = false ]; then
    BUILD_ONLY=true
fi

# Step 1: Build gem5
if [ "$BUILD_ONLY" = true ] || [ "$FULL_RUN" = true ]; then
    echo ""
    echo "Step 1: Building gem5 with AIP and LvP replacement policies..."
    echo "--------------------------------------------------------------"

    # Check if build already exists
    if [ -f "build/X86/gem5.opt" ]; then
        print_warning "Existing build found at build/X86/gem5.opt"
        read -p "Rebuild? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Using existing build"
        else
            print_status "Starting build (this may take 10-30 minutes)..."
            scons build/X86/gem5.opt -j$(nproc) || {
                print_error "Build failed!"
                exit 1
            }
            print_status "Build completed successfully!"
        fi
    else
        print_status "Starting build (this may take 10-30 minutes)..."
        scons build/X86/gem5.opt -j$(nproc) || {
            print_error "Build failed!"
            exit 1
        }
        print_status "Build completed successfully!"
    fi
fi

# Step 2: Run quick test
if [ "$TEST_ONLY" = true ] || [ "$FULL_RUN" = true ]; then
    echo ""
    echo "Step 2: Running quick validation test..."
    echo "----------------------------------------"

    # Check if gem5 binary exists
    if [ ! -f "build/X86/gem5.opt" ]; then
        print_error "gem5 binary not found. Please build first with --build-only"
        exit 1
    fi

    # Create a simple test program if it doesn't exist
    if [ ! -f "tests/test-progs/hello/bin/x86/linux/hello" ]; then
        print_warning "SPEC2000 benchmarks not available for quick test"
        print_warning "Please set up benchmarks for comprehensive testing"
    else
        print_status "Running quick test with hello world program..."

        mkdir -p test_output

        # Test LRU
        print_status "Testing LRU policy..."
        build/X86/gem5.opt --outdir=test_output/lru \
            configs/example/cache_replacement_test.py \
            --replacement-policy=LRU \
            --benchmark=tests/test-progs/hello/bin/x86/linux/hello \
            --fast-forward=0 \
            --max-insts=1000000 > /dev/null 2>&1 || {
            print_error "LRU test failed"
            exit 1
        }
        print_status "LRU test passed"

        # Test AIP
        print_status "Testing AIP policy..."
        build/X86/gem5.opt --outdir=test_output/aip \
            configs/example/cache_replacement_test.py \
            --replacement-policy=AIP \
            --benchmark=tests/test-progs/hello/bin/x86/linux/hello \
            --fast-forward=0 \
            --max-insts=1000000 > /dev/null 2>&1 || {
            print_error "AIP test failed"
            exit 1
        }
        print_status "AIP test passed"

        # Test LvP
        print_status "Testing LvP policy..."
        build/X86/gem5.opt --outdir=test_output/lvp \
            configs/example/cache_replacement_test.py \
            --replacement-policy=LvP \
            --benchmark=tests/test-progs/hello/bin/x86/linux/hello \
            --fast-forward=0 \
            --max-insts=1000000 > /dev/null 2>&1 || {
            print_error "LvP test failed"
            exit 1
        }
        print_status "LvP test passed"

        print_status "All policies validated successfully!"

        # Show quick stats comparison
        echo ""
        echo "Quick Stats Comparison:"
        echo "----------------------"
        for policy in lru aip lvp; do
            ipc=$(grep "^system.cpu.ipc " test_output/$policy/stats.txt | awk '{print $2}')
            echo "$policy: IPC = $ipc"
        done
    fi
fi

# Step 3: Analyze results
if [ "$ANALYZE_ONLY" = true ] || [ "$FULL_RUN" = true ]; then
    echo ""
    echo "Step 3: Analyzing results..."
    echo "---------------------------"

    # Check for Python dependencies
    python3 -c "import matplotlib, seaborn, numpy" 2>/dev/null || {
        print_error "Missing Python dependencies"
        echo "Please install: pip3 install matplotlib seaborn numpy"
        exit 1
    }

    # Find most recent results file
    RESULTS_FILE=$(ls -t benchmark_results/benchmark_results_*.json 2>/dev/null | head -1)

    if [ -z "$RESULTS_FILE" ]; then
        print_warning "No benchmark results found to analyze"
        print_warning "Run benchmarks first with --full-run or manually"
    else
        print_status "Found results file: $RESULTS_FILE"
        print_status "Generating visualizations..."

        python3 configs/example/analyze_results.py "$RESULTS_FILE" \
            --output-dir=analysis_output || {
            print_error "Analysis failed"
            exit 1
        }

        print_status "Analysis complete! Check analysis_output/ for graphs"
    fi
fi

# Final summary
echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="
echo ""

if [ "$BUILD_ONLY" = true ] && [ "$FULL_RUN" = false ]; then
    print_status "gem5 built successfully with AIP and LvP policies"
    echo ""
    echo "Next steps:"
    echo "  1. Run validation: $0 --test-only"
    echo "  2. Run benchmarks: python3 configs/example/run_benchmark.py --benchmarks-dir=/path/to/spec2000"
    echo "  3. See CACHE_REPLACEMENT_README.md for detailed instructions"
fi

if [ "$TEST_ONLY" = true ] && [ "$FULL_RUN" = false ]; then
    print_status "Validation tests completed successfully"
    echo ""
    echo "Next steps:"
    echo "  1. Run full benchmarks: python3 configs/example/run_benchmark.py --benchmarks-dir=/path/to/spec2000"
    echo "  2. Analyze results: $0 --analyze-only"
fi

if [ "$ANALYZE_ONLY" = true ] && [ "$FULL_RUN" = false ]; then
    print_status "Analysis completed successfully"
    echo ""
    echo "Check analysis_output/ directory for:"
    echo "  - IPC comparison graphs"
    echo "  - Speedup charts"
    echo "  - Miss rate comparisons"
    echo "  - Summary report"
fi

if [ "$FULL_RUN" = true ]; then
    print_status "Complete workflow finished successfully!"
    echo ""
    echo "Results available in:"
    echo "  - benchmark_results/ - Raw benchmark data"
    echo "  - analysis_output/ - Visualizations and reports"
fi

echo ""
print_status "Done!"
