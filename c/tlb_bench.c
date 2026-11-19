#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/mman.h>
#include <unistd.h>

/* Repeated sampled reads on pre-faulted anonymous pages; use perf for dTLB stats. */
static double seconds(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + ts.tv_nsec / 1000000000.0;
}

int main(int argc, char **argv) {
    size_t mib = 64, stride = 4096, rounds = 10;
    int huge = 0;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--huge")) huge = 1;
        else if (i + 1 < argc && !strcmp(argv[i], "--mib")) mib = (size_t)strtoull(argv[++i], NULL, 10);
        else if (i + 1 < argc && !strcmp(argv[i], "--stride")) stride = (size_t)strtoull(argv[++i], NULL, 10);
        else if (i + 1 < argc && !strcmp(argv[i], "--rounds")) rounds = (size_t)strtoull(argv[++i], NULL, 10);
        else { fprintf(stderr, "Usage: %s [--mib N] [--stride N] [--rounds N] [--huge]\n", argv[0]); return 2; }
    }
    if (!mib || mib > SIZE_MAX / (1024U * 1024U) || !stride || !rounds) return 2;
    size_t bytes = mib * 1024U * 1024U;
    unsigned char *array = mmap(NULL, bytes, PROT_READ | PROT_WRITE,
                                MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (array == MAP_FAILED) { perror("mmap"); return 1; }
    if (huge) {
#ifdef MADV_HUGEPAGE
        if (madvise(array, bytes, MADV_HUGEPAGE)) perror("madvise(MADV_HUGEPAGE)");
#else
        puts("MADV_HUGEPAGE not supported by build platform");
#endif
    }
    long page = sysconf(_SC_PAGESIZE);
    for (size_t p = 0; p < bytes; p += (size_t)page) array[p] = (unsigned char)(p >> 12);
    volatile unsigned char *view = array;
    volatile uint64_t sum = 0;
    const size_t visits = (bytes - 1) / stride + 1;
    double begin = seconds();
    for (size_t round = 0; round < rounds; ++round)
        for (size_t p = 0; p < bytes; p += stride) sum += view[p];
    double elapsed = seconds() - begin;
    printf("bytes=%zu stride=%zu rounds=%zu visits=%zu elapsed=%.6f s ns/access=%.2f "
           "huge_hint=%d checksum=%" PRIu64 "\n", bytes, stride, rounds,
           visits * rounds, elapsed, elapsed * 1e9 / (double)(visits * rounds), huge, sum);
    puts("For dTLB counts: perf stat -e dTLB-load-misses,dTLB-loads -- ./c/bin/tlb_bench ...");
    munmap(array, bytes);
    return 0;
}
