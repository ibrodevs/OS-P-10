#define _GNU_SOURCE
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/wait.h>

/* PFNs are visible only with CAP_SYS_ADMIN on recent Linux kernels.
   Child/parent will compare numeric PFNs if the OS allows it. */
static uint64_t physical_frame(void *address) {
    long ps = sysconf(_SC_PAGESIZE);
    int fd = open("/proc/self/pagemap", O_RDONLY);
    if (ps < 1 || fd < 0) return 0;
    uint64_t raw = 0;
    off_t offset = (off_t)((uintptr_t)address / (uintptr_t)ps * 8ULL);
    ssize_t count = pread(fd, &raw, sizeof(raw), offset);
    close(fd);
    if (count != sizeof(raw) || !(raw & (1ULL << 63))) return 0;
    return raw & ((1ULL << 55) - 1);
}

/* Two processes use different virtual addresses mapping the same file page. */
int main(void) {
    long size = sysconf(_SC_PAGESIZE);
    char name[] = "/tmp/os-p10-share-XXXXXX";
    int fd = mkstemp(name);
    if (fd < 0) { perror("mkstemp"); return 1; }
    unlink(name); /* Do not leave test data on disk. */
    if (ftruncate(fd, size) != 0) { perror("ftruncate"); close(fd); return 1; }
    unsigned char *parent = mmap(NULL, (size_t)size, PROT_READ | PROT_WRITE,
                                 MAP_SHARED, fd, 0);
    if (parent == MAP_FAILED) { perror("mmap parent"); close(fd); return 1; }
    parent[0] = 17;
    uint64_t pfn_parent = physical_frame(parent);
    setvbuf(stdout, NULL, _IONBF, 0);
    printf("parent PID=%ld virtual=%p initial=%u pfn=%" PRIu64 "\n",
           (long)getpid(), (void*)parent, parent[0], pfn_parent);
    pid_t child = fork();
    if (child < 0) { perror("fork"); return 1; }
    if (child == 0) {
        /* The inherited mapping remains occupied, so this SECOND mmap is distinct. */
        unsigned char *other = mmap(NULL, (size_t)size, PROT_READ | PROT_WRITE,
                                    MAP_SHARED, fd, 0);
        if (other == MAP_FAILED) { perror("mmap child"); _exit(2); }
        printf("child  PID=%ld virtual=%p initial=%u (same file, offset 0)\n",
               (long)getpid(), (void*)other, other[0]);
        if (other == parent) { fputs("Unexpected identical virtual mapping\n", stderr); _exit(3); }
        other[0] = 99;
        uint64_t pfn_child = physical_frame(other);
        printf("child pfn=%" PRIu64 " (compare with parent PFN when both nonzero)\n", pfn_child);
        if (pfn_parent && pfn_child && pfn_parent != pfn_child) {
            fputs("Unexpected PFN mismatch!\n", stderr);
            _exit(4);
        }
        if (!pfn_parent || !pfn_child)
            puts("PFN unavailable (kernel masks it without CAP_SYS_ADMIN); shared write is still observable.");
        printf("child changed data; inherited_mapping_reads=%u\n", parent[0]);
        munmap(other, (size_t)size);
        _exit(0);
    }
    int status = 0;
    if (waitpid(child, &status, 0) < 0) { perror("waitpid"); return 1; }
    printf("parent reads after child=%u; child exited=%d\n",
           parent[0], WIFEXITED(status) ? WEXITSTATUS(status) : -1);
    munmap(parent, (size_t)size);
    close(fd);
    return WIFEXITED(status) && WEXITSTATUS(status) == 0 && parent != NULL ? 0 : 1;
}
