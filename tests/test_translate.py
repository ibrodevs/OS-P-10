import unittest
from pathlib import Path
import tempfile

from analysis import make_references, save_svg
from tlb import TLB, TwoLevelPageTable, effective_access_ns, simulate, two_level_indices
from translate import (PAGE_SIZE, PageFault, read_page_table,
                       read_references, split_address, translate_address)


class TranslationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = read_page_table()

    def test_manual_examples(self):
        r1 = translate_address(1200, self.table)
        self.assertEqual((r1.page, r1.offset, r1.frame, r1.physical), (1, 176, 2, 2224))
        r2 = translate_address(3100, self.table)
        self.assertEqual((r2.page, r2.offset, r2.frame, r2.physical), (3, 28, 0, 28))
        with self.assertRaises(PageFault):
            translate_address(5000, self.table)

    def test_edges_and_bad_addresses(self):
        self.assertEqual(split_address(0), (0, 0))
        self.assertEqual(split_address(16383), (15, 1023))
        for a in (-1, 16384):
            with self.assertRaises(ValueError):
                split_address(a)

    def test_table_parser_rejects_duplicate(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'table.txt'
            p.write_text('0 5\n0 6\n')
            with self.assertRaises(ValueError):
                read_page_table(p)

    def test_first_three_refs(self):
        self.assertEqual(read_references()[:3], [1200, 3100, 5000])


class TLBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = read_page_table()

    def test_lru_updates_on_hit(self):
        tlb = TLB(2, self.table)
        # 0,1 -> 0(hit),2 (вытесняет 1), 0 (hit),1 (miss)
        hits = [tlb.access(a * PAGE_SIZE).tlb_hit for a in [0, 1, 0, 2, 0, 1]]
        self.assertEqual(hits, [False, False, True, False, True, False])
        self.assertEqual((tlb.hits, tlb.misses), (2, 4))

    def test_fault_not_cached(self):
        tlb = TLB(2, self.table)
        self.assertTrue(tlb.access(5000).page_fault)
        self.assertTrue(tlb.access(5000).page_fault)
        self.assertEqual((tlb.hits, tlb.misses, tlb.page_faults), (0, 2, 2))

    def test_zero_size(self):
        tlb = simulate([0, 0, 0], 0, self.table)
        self.assertEqual((tlb.hits, tlb.misses), (0, 3))

    def test_effective_time(self):
        self.assertEqual(effective_access_ns(0), 210)
        self.assertEqual(effective_access_ns(0.5), 160)
        self.assertAlmostEqual(effective_access_ns(0.9), 120)
        self.assertEqual(effective_access_ns(1), 110)
        self.assertEqual(effective_access_ns(0, levels=2), 310)
        self.assertEqual(effective_access_ns(1, levels=2), 110)

    def test_two_level_split(self):
        self.assertEqual(two_level_indices(3100), (0, 3, 28))
        self.assertEqual(two_level_indices(15000), (3, 2, 664))

    def test_two_level_walk(self):
        table = TwoLevelPageTable(self.table)
        r = table.walk(1200)
        self.assertEqual((r.translation.physical, r.page_table_reads, r.total_memory_accesses), (2224, 2, 3))
        with self.assertRaises(PageFault):
            table.walk(5000)

    def test_locality_generator(self):
        self.assertEqual(make_references(300, seed=5), make_references(300, seed=5))
        self.assertNotIn(4, {a // PAGE_SIZE for a in make_references(200)})

    def test_chart_generated(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'test.svg'
            save_svg(p, [(1, 0.5, 0.1), (2, 0.9, 0.3)])
            self.assertIn('<svg', p.read_text())


if __name__ == '__main__':
    unittest.main()
