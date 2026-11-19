#define _GNU_SOURCE
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/wait.h>

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
    setvbuf(stdout, NULL, _IONBF, 0);
    printf("parent PID=%ld virtual=%p initial=%u\n", (long)getpid(), (void*)parent, parent[0]);
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
