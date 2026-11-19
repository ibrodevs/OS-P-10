#define _POSIX_C_SOURCE 200809L
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static double now(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}
int main(int argc, char **argv) {
    size_t n = 2048;
    if (argc > 1) n = (size_t)strtoull(argv[1], NULL, 10);
    if (!n || n > SIZE_MAX / n || n * n > (size_t)1024 * 1024 * 1024) {
        fputs("Size must be 1..32768 with matrix <= 1 GiB\n", stderr); return 2;
    }
    unsigned char *raw = malloc(n * n);
    if (!raw) { perror("malloc"); return 1; }
    for (size_t i = 0; i < n * n; i++) raw[i] = (unsigned char)(i % 251);
    volatile unsigned char *a = raw;
    uint64_t sum_row = 0, sum_col = 0;
    double begin = now();
    for (size_t r = 0; r < n; ++r)
        for (size_t c = 0; c < n; ++c) sum_row += a[r * n + c];
    double row_time = now() - begin;
    begin = now();
    for (size_t c = 0; c < n; ++c)
        for (size_t r = 0; r < n; ++r) sum_col += a[r * n + c];
    double col_time = now() - begin;
    printf("matrix=%zux%zu bytes=%zu\nrow-major=%.6f s checksum=%" PRIu64
           "\ncolumn-major=%.6f s checksum=%" PRIu64 "\ncolumn/row=%.2fx\n",
           n, n, n*n, row_time, sum_row, col_time, sum_col,
           row_time > 0 ? col_time / row_time : 0.0);
    free(raw);
    return sum_row == sum_col ? 0 : 1;
}
