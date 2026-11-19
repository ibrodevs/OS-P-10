"""TLB на K записей c вытеснением LRU; EAT для одно- и двухуровневой таблицы."""
from __future__ import annotations

import argparse
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from translate import PAGE_SIZE, ROOT, PageFault, Translation, read_page_table, read_references, split_address


@dataclass(frozen=True)
class Access:
    address: int
    page: int
    tlb_hit: bool
    physical: int | None
    page_fault: bool


class TLB:
    def __init__(self, capacity: int, table: dict[int, int | None]):
        if capacity < 0:
            raise ValueError('Число записей TLB не может быть отрицательным')
        self.capacity = capacity
        self.table = table
        self.entries: OrderedDict[int, int] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.page_faults = 0

    def access(self, address: int) -> Access:
        page, offset = split_address(address)
        if page in self.entries:
            self.hits += 1
            self.entries.move_to_end(page)  # LRU обновляется при КАЖДОМ попадании
            return Access(address, page, True, self.entries[page] * PAGE_SIZE + offset, False)
        self.misses += 1
        frame = self.table.get(page)
        if frame is None:
            self.page_faults += 1
            return Access(address, page, False, None, True)
        if self.capacity:
            if len(self.entries) >= self.capacity:
                self.entries.popitem(last=False)
            self.entries[page] = frame
        return Access(address, page, False, frame * PAGE_SIZE + offset, False)

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


def simulate(references: list[int], capacity: int, table: dict[int, int | None]) -> TLB:
    tlb = TLB(capacity, table)
    for address in references:
        tlb.access(address)
    return tlb


def effective_access_ns(hit_rate: float, memory_ns: float = 100,
                        tlb_ns: float = 10, levels: int = 1) -> float:
    """При отсутствии page faults: hit = TLB + RAM, miss = TLB + levels*RAM + RAM."""
    if not 0 <= hit_rate <= 1 or memory_ns < 0 or tlb_ns < 0 or levels < 1:
        raise ValueError('Недопустимые параметры времени/доли попаданий/уровней')
    return tlb_ns + memory_ns * (1 + levels * (1 - hit_rate))


def two_level_indices(address: int, first_level_bits: int = 2) -> tuple[int, int, int]:
    """16 страниц = 4 внешние записи x 4 внутренние; 10-битное смещение."""
    page, offset = split_address(address)
    if not 1 <= first_level_bits < 4:
        raise ValueError('Число бит внешнего индекса должно быть от 1 до 3')
    inner_bits = 4 - first_level_bits
    return page >> inner_bits, page & ((1 << inner_bits) - 1), offset


@dataclass(frozen=True)
class WalkResult:
    translation: Translation
    page_table_reads: int
    total_memory_accesses: int


class TwoLevelPageTable:
    """Два уровня: 2 старших бита номера страницы и 2 младших бита."""

    def __init__(self, flat_table: dict[int, int | None]):
        self.outer: dict[int, dict[int, int | None]] = {}
        for page, frame in flat_table.items():
            if frame is not None:
                outer, inner, _ = two_level_indices(page * PAGE_SIZE)
                self.outer.setdefault(outer, {})[inner] = frame

    def walk(self, address: int) -> WalkResult:
        outer, inner, offset = two_level_indices(address)
        page, _ = split_address(address)
        level_2 = self.outer.get(outer)  # 1 чтение памяти: запись первого уровня
        if level_2 is None:
            raise PageFault(address, page)
        frame = level_2.get(inner)       # 2 чтение памяти: запись второго уровня
        if frame is None:
            raise PageFault(address, page)
        physical = frame * PAGE_SIZE + offset
        # 3 чтение памяти: сами данные по физическому адресу
        return WalkResult(Translation(address, page, offset, frame, physical), 2, 3)


def main() -> None:
    parser = argparse.ArgumentParser(description='Модель TLB (LRU)')
    parser.add_argument('--size', type=int, default=3)
    parser.add_argument('--walk', type=int, default=None, help='Двухуровневая трансляция указанного адреса')
    parser.add_argument('--table', type=Path, default=ROOT / 'pagetable.txt')
    parser.add_argument('--refs', type=Path, default=ROOT / 'refs.txt')
    args = parser.parse_args()
    table = read_page_table(args.table)
    if args.walk is not None:
        try:
            w = TwoLevelPageTable(table).walk(args.walk)
            print(f'Два уровня: {two_level_indices(args.walk)} (outer, inner, offset), '
                  f'физический адрес={w.translation.physical}; '
                  f'чтений таблиц={w.page_table_reads}, чтений памяти вместе с данными={w.total_memory_accesses}')
        except PageFault as exc:
            print(f'Двухуровневая таблица: {exc}')
    tlb = TLB(args.size, table)
    print('Адрес | TLB | физический адрес / ошибка')
    for address in read_references(args.refs):
        try:
            a = tlb.access(address)
        except ValueError as exc:
            print(f'{address:5} | ERR | {exc}')
            continue
        print(f'{address:5} | {"HIT " if a.tlb_hit else "MISS"} | {"PAGE FAULT" if a.page_fault else a.physical}')
    print(f'TLB K={args.size}: hit={tlb.hits}, miss={tlb.misses}, '
          f'page faults={tlb.page_faults}, hit rate={tlb.hit_rate:.2%}')
    print('EAT (только завершённые обращения, без штрафа за page fault): '
          f'{effective_access_ns(tlb.hit_rate):.2f} нс (один уровень), '
          f'{effective_access_ns(tlb.hit_rate, levels=2):.2f} нс (два уровня)')
    print('Внимание: EAT по всем обращениям является оценкой при условии отсутствия page faults; '
          'при реальных отказах нужен отдельный штраф и модель обработки.')


if __name__ == '__main__':
    main()
