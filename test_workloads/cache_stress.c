/*
 * Cache Stress Test - Designed to show differences in cache replacement policies
 *
 * This program creates memory access patterns that stress the cache hierarchy
 * and demonstrate the benefits of intelligent replacement policies like AIP/LvP.
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

#define ARRAY_SIZE (2 * 1024 * 1024)  // 2MB - larger than L2 cache
#define ITERATIONS 10
#define STRIDE 64  // Cache line size

// Prevent compiler optimization
volatile uint64_t sink = 0;

/*
 * Sequential scan - baseline cache behavior
 */
void sequential_scan(uint64_t *array, int size) {
    uint64_t sum = 0;
    for (int i = 0; i < size; i++) {
        sum += array[i];
    }
    sink = sum;
}

/*
 * Strided access - creates predictable misses
 */
void strided_access(uint64_t *array, int size, int stride) {
    uint64_t sum = 0;
    for (int i = 0; i < size; i += stride) {
        sum += array[i];
    }
    sink = sum;
}

/*
 * Random access - thrashing pattern
 */
void random_access(uint64_t *array, int size, int iterations) {
    uint64_t sum = 0;
    unsigned int seed = 42;

    for (int iter = 0; iter < iterations; iter++) {
        for (int i = 0; i < 1000; i++) {
            int idx = rand_r(&seed) % size;
            sum += array[idx];
        }
    }
    sink = sum;
}

/*
 * Scanning with reuse - good for smart replacement
 * Simulates a scenario where AIP/LvP should outperform LRU
 */
void scan_with_reuse(uint64_t *array, int size) {
    uint64_t sum = 0;

    // First pass - establish working set
    for (int i = 0; i < size / 4; i++) {
        sum += array[i];
    }

    // Second pass - streaming data (should be evicted quickly)
    for (int i = size / 4; i < size; i++) {
        sum += array[i];
    }

    // Third pass - reuse initial working set (should still be cached with AIP/LvP)
    for (int i = 0; i < size / 4; i++) {
        sum += array[i];
    }

    sink = sum;
}

/*
 * Matrix-like access pattern
 */
void matrix_traverse(uint64_t *array, int size) {
    uint64_t sum = 0;
    int dim = 512;  // 512x512 matrix

    // Row-major traversal
    for (int i = 0; i < dim; i++) {
        for (int j = 0; j < dim; j++) {
            int idx = (i * dim + j) % size;
            sum += array[idx];
        }
    }

    // Column-major traversal (poor cache locality)
    for (int j = 0; j < dim; j++) {
        for (int i = 0; i < dim; i++) {
            int idx = (i * dim + j) % size;
            sum += array[idx];
        }
    }

    sink = sum;
}

int main() {
    printf("Cache Replacement Policy Stress Test\n");
    printf("=====================================\n");
    printf("Array size: %d elements (%.2f MB)\n",
           ARRAY_SIZE, (ARRAY_SIZE * sizeof(uint64_t)) / (1024.0 * 1024.0));

    // Allocate and initialize array
    uint64_t *array = (uint64_t *)malloc(ARRAY_SIZE * sizeof(uint64_t));
    if (!array) {
        printf("Memory allocation failed!\n");
        return 1;
    }

    for (int i = 0; i < ARRAY_SIZE; i++) {
        array[i] = i * 7 + 3;  // Simple pattern
    }

    printf("\n1. Sequential scan...\n");
    for (int i = 0; i < ITERATIONS; i++) {
        sequential_scan(array, ARRAY_SIZE);
    }

    printf("2. Strided access (stride=%d)...\n", STRIDE);
    for (int i = 0; i < ITERATIONS; i++) {
        strided_access(array, ARRAY_SIZE, STRIDE);
    }

    printf("3. Random access...\n");
    random_access(array, ARRAY_SIZE, ITERATIONS);

    printf("4. Scan with reuse (tests smart replacement)...\n");
    for (int i = 0; i < ITERATIONS; i++) {
        scan_with_reuse(array, ARRAY_SIZE);
    }

    printf("5. Matrix traversal...\n");
    for (int i = 0; i < ITERATIONS / 2; i++) {
        matrix_traverse(array, ARRAY_SIZE);
    }

    printf("\nTest complete! Result: %lu\n", sink);

    free(array);
    return 0;
}
