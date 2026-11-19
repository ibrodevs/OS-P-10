"""Дополнительные регрессионные и инвариантные тесты задания №10."""
import random
import unittest

from tlb import TLB, TwoLevelPageTable, effective_access_ns, simulate, two_level_indices
from translate import PAGE_COUNT, PAGE_SIZE, PageFault, read_page_table, read_references, translate_address


class PagingProperties(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = read_page_table()

    def test_all_valid_addresses_match_two_level_walk(self):
        walker = TwoLevelPageTable(self.table)
        for page in range(PAGE_COUNT):
            for offset in (0, 1, PAGE_SIZE // 2, PAGE_SIZE - 1):
                addr = page * PAGE_SIZE + offset
                if self.table[page] is None:
                    with self.assertRaises(PageFault):
                        walker.walk(addr)
                else:
                    direct = translate_address(addr, self.table)
                    nested = walker.walk(addr)
                    self.assertEqual(direct, nested.translation)
                    self.assertEqual((nested.page_table_reads, nested.total_memory_accesses), (2, 3))

    def test_index_splits_all_pages(self):
        for bits in (1, 2, 3):
            for page in range(PAGE_COUNT):
                for off in (0, 1023):
                    outer, inner, offset = two_level_indices(page * PAGE_SIZE + off, bits)
                    self.assertEqual((outer << (4 - bits)) | inner, page)
                    self.assertEqual(offset, off)

    def test_eat_rejects_out_of_range_parameters(self):
        for h in (-0.01, 1.01, float('nan')):
            with self.assertRaises(ValueError):
                effective_access_ns(h)
        for kw in ({'memory_ns': -1}, {'tlb_ns': -1}, {'levels': 0}):
            with self.assertRaises(ValueError):
                effective_access_ns(0.5, **kw)


class TLBProperties(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = read_page_table()

    def test_faults_excluded_from_successful_hit_rate(self):
        tlb = simulate(read_references(), 3, self.table)
        self.assertEqual((tlb.hits, tlb.misses, tlb.page_faults), (15, 15, 2))
        self.assertEqual(tlb.successful_accesses, 28)
        self.assertAlmostEqual(tlb.hit_rate, 0.5)
        self.assertAlmostEqual(tlb.successful_hit_rate, 15 / 28)
        self.assertAlmostEqual(effective_access_ns(tlb.successful_hit_rate), 156.42857142857)

    def test_only_page_faults_have_undefined_success_rate(self):
        tlb = simulate([5000, 5001], 4, self.table)
        self.assertEqual((tlb.hits, tlb.misses, tlb.page_faults), (0, 2, 2))
        self.assertEqual(tlb.successful_accesses, 0)
        self.assertIsNone(tlb.successful_hit_rate)
        self.assertEqual(tlb.hit_rate, 0)

    def test_zero_references(self):
        tlb = simulate([], 2, self.table)
        self.assertEqual(tlb.successful_accesses, 0)
        self.assertIsNone(tlb.successful_hit_rate)

    def test_lru_matches_simple_reference_implementation(self):
        rng = random.Random(2026)
        for capacity in range(0, 9):
            for _ in range(20):
                pages = [rng.randrange(PAGE_COUNT) for __ in range(70)]
                # A minimal, intentionally independent LRU implementation.
                recent = []  # least recently used -> most recently used
                expected_hits = expected_faults = 0
                got = TLB(capacity, self.table)
                for page in pages:
                    addr = page * PAGE_SIZE + rng.randrange(PAGE_SIZE)
                    is_hit = page in recent
                    expected_hits += is_hit
                    if is_hit:
                        recent.remove(page)
                        recent.append(page)
                    elif self.table[page] is None:
                        expected_faults += 1
                    elif capacity:
                        if len(recent) == capacity:
                            recent.pop(0)
                        recent.append(page)
                    access = got.access(addr)
                    self.assertEqual(access.tlb_hit, is_hit)
                    self.assertEqual(access.page_fault, self.table[page] is None)
                self.assertEqual(got.hits, expected_hits)
                self.assertEqual(got.page_faults, expected_faults)
                self.assertEqual(got.misses, len(pages) - expected_hits)

    def test_stack_property_hit_counts_do_not_decrease(self):
        rng = random.Random(24)
        valid_pages = [page for page, frame in self.table.items() if frame is not None]
        sequence = [rng.choice(valid_pages) * PAGE_SIZE for _ in range(800)]
        hits = [simulate(sequence, cap, self.table).hits for cap in range(17)]
        self.assertEqual(hits, sorted(hits))


if __name__ == '__main__':
    unittest.main()
