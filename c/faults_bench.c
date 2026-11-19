#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#include <fcntl.h>

/* File-backed mapping: minor/major faults depend on page cache and swap. */
static double seconds(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + ts.tv_nsec / 1000000000.0;
}

static int stat_faults(unsigned long long *minor, unsigned long long *major) {
    FILE *fp = fopen("/proc/self/stat", "r");
    if (!fp) return -1;
    char buf[4096];
    if (!fgets(buf, sizeof(buf), fp)) { fclose(fp); return -1; }
    fclose(fp);
    char *end_comm = strrchr(buf, ')');
    if (!end_comm || end_comm[1] != ' ') return -1;
    char *save = NULL;
    int field = 3;
    for (char *token = strtok_r(end_comm + 2, " ", &save); token; token = strtok_r(NULL, " ", &save), ++field) {
        if (field == 10) *minor = strtoull(token, NULL, 10);
        if (field == 12) { *major = strtoull(token, NULL, 10); return 0; }
    }
    return -1;
}

int main(int argc, char **argv) {
    size_t mib = 32, rounds = 2;
    int random_access = 0;
    for (int i = 1; i < argc; ++i) {
        if (i + 1 < argc && !strcmp(argv[i], "--mib")) mib = (size_t)strtoull(argv[++i], NULL, 10);
        else if (i + 1 < argc && !strcmp(argv[i], "--rounds")) rounds = (size_t)strtoull(argv[++i], NULL, 10);
        else if (!strcmp(argv[i], "--random")) random_access = 1;
        else { fprintf(stderr, "Usage: %s [--mib N] [--rounds N] [--random]\n", argv[0]); return 2; }
    }
    if (!mib || mib > SIZE_MAX / 1048576U || !rounds) return 2;
    size_t bytes = mib * 1048576U;
    long ps = sysconf(_SC_PAGESIZE);
    if (ps < 1) return 1;
    const size_t pages = bytes / (size_t)ps;
    char filename[] = "/tmp/os-p10-faults-XXXXXX";
    int fd = mkstemp(filename);
    if (fd < 0) { perror("mkstemp"); return 1; }
    unlink(filename);
    if (ftruncate(fd, (off_t)bytes) < 0) { perror("ftruncate"); close(fd); return 1; }
    /* Fill every page: file-backed read faults can trigger actual disk IO. */
    unsigned char mark = 1;
    for (size_t i = 0; i < pages; ++i) {
        if (pwrite(fd, &mark, 1, (off_t)(i * (size_t)ps)) != 1) {
            perror("pwrite"); close(fd); return 1;
        }
    }
    if (fsync(fd) != 0) perror("fsync");
    unsigned char *array = mmap(NULL, bytes, PROT_READ, MAP_SHARED, fd, 0);
    if (array == MAP_FAILED) { perror("mmap"); close(fd); return 1; }
    /* Hint only: DONTNEED may not remove cached pages under memory pressure. */
    if (posix_fadvise(fd, 0, (off_t)bytes, POSIX_FADV_DONTNEED))
        fputs("posix_fadvise hint failed\n", stderr);
    struct rusage before, after;
    unsigned long long m1 = 0, M1 = 0, m2 = 0, M2 = 0;
    stat_faults(&m1, &M1);
    getrusage(RUSAGE_SELF, &before);
    volatile unsigned char *view = array;
    volatile uint64_t sum = 0;
    /* Multiplier coprime with page counts divisible by 2 and 3: 4099 is prime. */
    double start = seconds();
    for (size_t round = 0; round < rounds; ++round) {
        for (size_t i = 0; i < pages; ++i) {
            size_t index = random_access ? (i * 4099ULL) % pages : i;
            sum += view[index * (size_t)ps];
        }
    }
    double elapsed = seconds() - start;
    getrusage(RUSAGE_SELF, &after);
    stat_faults(&m2, &M2);
    printf("pattern=%s bytes=%zu pages=%zu rounds=%zu elapsed=%.6f s checksum=%" PRIu64 "\n",
           random_access ? "strided/random-like" : "sequential", bytes, pages, rounds, elapsed, sum);
    printf("getrusage: minor=%ld major=%ld maxrss=%ld KiB\n",
           after.ru_minflt - before.ru_minflt, after.ru_majflt - before.ru_majflt, after.ru_maxrss);
    printf("/proc/self/stat: minor=%llu major=%llu\n", m2 - m1, M2 - M1);
    munmap(array, bytes);
    close(fd);
    return 0;
}
