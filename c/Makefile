CC ?= cc
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Wpedantic
TARGETS = pagemap_demo shared_mmap tlb_bench locality_bench faults_bench

.PHONY: all clean
all: $(addprefix bin/,$(TARGETS))

bin:
	mkdir -p bin

bin/%: %.c | bin
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -rf bin
