#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>

static volatile unsigned char sample = 42;

/* Returns 0 on success. PFN may be zeroed by the kernel without CAP_SYS_ADMIN. */
int read_pagemap(void *addr, uint64_t *entry) {
    long page_size = sysconf(_SC_PAGESIZE);
    if (page_size <= 0) return -1;
    int fd = open("/proc/self/pagemap", O_RDONLY);
    if (fd < 0) return -1;
    off_t position = (off_t)((uintptr_t)addr / (uintptr_t)page_size * 8ULL);
    ssize_t count = pread(fd, entry, sizeof(*entry), position);
    close(fd);
    return count == (ssize_t)sizeof(*entry) ? 0 : -1;
}

static void show_mapping(void *addr) {
    FILE *fp = fopen("/proc/self/maps", "r");
    if (!fp) { perror("maps"); return; }
    char line[1024];
    while (fgets(line, sizeof(line), fp)) {
        unsigned long start = 0, end = 0;
        if (sscanf(line, "%lx-%lx", &start, &end) == 2 &&
            (uintptr_t)addr >= (uintptr_t)start &&
            (uintptr_t)addr < (uintptr_t)end) {
            printf("/proc/self/maps: %s", line);
            break;
        }
    }
    fclose(fp);
}

int main(void) {
    sample++;
    void *addr = (void *)&sample;
    long page_size = sysconf(_SC_PAGESIZE);
    printf("PID=%ld variable=%p page_size=%ld value=%d\n", (long)getpid(),
           addr, page_size, sample);
    show_mapping(addr);
    uint64_t entry = 0;
    if (read_pagemap(addr, &entry) != 0) {
        perror("pagemap (access may be restricted)");
        return 0; /* demonstration is still informative without CAP_SYS_ADMIN */
    }
    int present = (int)((entry >> 63) & 1);
    int swapped = (int)((entry >> 62) & 1);
    uint64_t pfn = entry & ((1ULL << 55) - 1);
    printf("pagemap=0x%016" PRIx64 " present=%d swapped=%d pfn=%" PRIu64 "\n",
           entry, present, swapped, pfn);
    if (present && pfn != 0) {
        uint64_t physical = pfn * (uint64_t)page_size + ((uintptr_t)addr % (uintptr_t)page_size);
        printf("physical_address=0x%" PRIx64 "\n", physical);
    } else {
        puts("Physical frame number unavailable or page not present. "
             "Linux masks PFN without CAP_SYS_ADMIN (even root in some containers).");
    }
    return 0;
}
