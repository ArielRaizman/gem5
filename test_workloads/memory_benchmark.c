/*
 * Memory-intensive benchmark designed to stress cache replacement policies.
 * This version runs for a much longer time to show policy differences.
 *
 * Compile: gcc -O2 -static -o memory_benchmark memory_benchmark.c -lm
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdint.h>

#define ARRAY_SIZE (4 * 1024 * 1024)  // 4MB (larger than L2)
#define ITERATIONS 100                 // Many iterations
#define NUM_PATTERNS 5

// Pattern types
typedef enum {
    SEQUENTIAL,
    STRIDED,
    RANDOM,
    SCAN_REUSE,
    MATRIX_TRAVERSE
} AccessPattern;

// Global arrays to stress cache
uint64_t *data_array;
uint64_t *index_array;
uint64_t checksum = 0;

// Simple random number generator (LCG)
uint32_t rand_seed = 12345;
uint32_t simple_rand() {
    rand_seed = (rand_seed * 1103515245 + 12345) & 0x7fffffff;
    return rand_seed;
}

void init_arrays() {
    printf("Allocating arrays...\n");
    data_array = (uint64_t*)malloc(ARRAY_SIZE * sizeof(uint64_t));
    index_array = (uint64_t*)malloc(ARRAY_SIZE * sizeof(uint64_t));

    if (!data_array || !index_array) {
        fprintf(stderr, "Failed to allocate memory\n");
        exit(1);
    }

    // Initialize with pseudo-random data
    for (size_t i = 0; i < ARRAY_SIZE; i++) {
        data_array[i] = i * 17 + 42;
        index_array[i] = (i * 13) % ARRAY_SIZE;
    }
    printf("Arrays initialized (size: %zu MB)\n",
           (2 * ARRAY_SIZE * sizeof(uint64_t)) / (1024*1024));
}

void sequential_access() {
    for (size_t i = 0; i < ARRAY_SIZE; i++) {
        checksum += data_array[i];
        data_array[i] += 1;
    }
}

void strided_access(size_t stride) {
    for (size_t i = 0; i < ARRAY_SIZE; i += stride) {
        checksum += data_array[i];
        data_array[i] += 1;
    }
}

void random_access() {
    for (size_t i = 0; i < ARRAY_SIZE / 4; i++) {
        size_t idx = simple_rand() % ARRAY_SIZE;
        checksum += data_array[idx];
        data_array[idx] += 1;
    }
}

void scan_with_reuse() {
    // Access pattern that should benefit AIP/LvP:
    // Scan once, then scan with high reuse

    // First pass: full scan (will evict many lines)
    for (size_t i = 0; i < ARRAY_SIZE; i++) {
        checksum += data_array[i];
    }

    // Second pass: access only part of array repeatedly (should be kept in cache)
    size_t hot_set_size = ARRAY_SIZE / 32;  // Small hot set
    for (int repeat = 0; repeat < 10; repeat++) {
        for (size_t i = 0; i < hot_set_size; i++) {
            checksum += data_array[i];
            data_array[i] += 1;
        }
    }
}

void matrix_traverse() {
    // Simulate matrix operations with row-major and column-major access
    size_t rows = 1024;
    size_t cols = ARRAY_SIZE / rows;

    // Row-major access
    for (size_t i = 0; i < rows; i++) {
        for (size_t j = 0; j < cols; j++) {
            size_t idx = i * cols + j;
            if (idx < ARRAY_SIZE) {
                checksum += data_array[idx];
            }
        }
    }

    // Column-major access (poor cache behavior)
    for (size_t j = 0; j < cols; j++) {
        for (size_t i = 0; i < rows; i++) {
            size_t idx = i * cols + j;
            if (idx < ARRAY_SIZE) {
                data_array[idx] += 1;
            }
        }
    }
}

void run_pattern(AccessPattern pattern, int iter) {
    switch(pattern) {
        case SEQUENTIAL:
            sequential_access();
            break;
        case STRIDED:
            strided_access(16);  // Skip every 16 elements
            break;
        case RANDOM:
            random_access();
            break;
        case SCAN_REUSE:
            scan_with_reuse();
            break;
        case MATRIX_TRAVERSE:
            matrix_traverse();
            break;
    }
}

const char* pattern_name(AccessPattern p) {
    switch(p) {
        case SEQUENTIAL: return "Sequential";
        case STRIDED: return "Strided";
        case RANDOM: return "Random";
        case SCAN_REUSE: return "Scan+Reuse";
        case MATRIX_TRAVERSE: return "Matrix";
        default: return "Unknown";
    }
}

int main(int argc, char *argv[]) {
    printf("========================================\n");
    printf("Memory-Intensive Cache Benchmark\n");
    printf("========================================\n");
    printf("Array size: %zu elements (%.2f MB)\n",
           ARRAY_SIZE, (ARRAY_SIZE * sizeof(uint64_t)) / (1024.0*1024.0));
    printf("Iterations: %d per pattern\n", ITERATIONS);
    printf("========================================\n\n");

    init_arrays();

    AccessPattern patterns[] = {
        SEQUENTIAL,
        STRIDED,
        RANDOM,
        SCAN_REUSE,
        MATRIX_TRAVERSE
    };

    // Run all patterns multiple times
    for (int round = 0; round < 5; round++) {
        printf("Round %d/%d\n", round + 1, 5);

        for (int p = 0; p < NUM_PATTERNS; p++) {
            printf("  Running %s pattern... ", pattern_name(patterns[p]));
            fflush(stdout);

            for (int iter = 0; iter < ITERATIONS; iter++) {
                run_pattern(patterns[p], iter);
            }

            printf("Done (checksum: %llu)\n", (unsigned long long)checksum);
        }
    }

    printf("\n========================================\n");
    printf("Benchmark Complete\n");
    printf("Final checksum: %llu\n", (unsigned long long)checksum);
    printf("========================================\n");

    free(data_array);
    free(index_array);

    return 0;
}
