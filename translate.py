"""Практическая №10: трансляция 16-КиБ адресного пространства по таблице страниц."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

PAGE_SIZE = 1024
PAGE_COUNT = 16
ROOT = Path(__file__).resolve().parent


class PageFault(Exception):
    """Страница отсутствует в оперативной памяти."""

    def __init__(self, address: int, page: int):
        self.address = address
        self.page = page
        super().__init__(f"Страничный отказ: адрес {address}, страница {page} отсутствует")


@dataclass(frozen=True)
class Translation:
    logical: int
    page: int
    offset: int
    frame: int
    physical: int


def read_page_table(path: str | Path = ROOT / 'pagetable.txt') -> dict[int, int | None]:
    """Формат: `page frame`, '-' означает отсутствие; строки с # игнорируются."""
    table: dict[int, int | None] = {}
    for line_number, line in enumerate(Path(path).read_text(encoding='utf-8').splitlines(), 1):
        data = line.split('#', 1)[0].strip()
        if not data:
            continue
        parts = data.split()
        if len(parts) != 2:
            raise ValueError(f"Некорректная строка {line_number}: {line!r}")
        page = int(parts[0])
        if not 0 <= page < PAGE_COUNT or page in table:
            raise ValueError(f"Страница {page}: вне диапазона или повторяется (строка {line_number})")
        frame = None if parts[1].lower() in {'-', 'absent', 'none', 'отсутствует'} else int(parts[1])
        if frame is not None and frame < 0:
            raise ValueError('Номер кадра не может быть отрицательным')
        table[page] = frame
    # Не перечисленные страницы трактуются как отсутствующие.
    return {page: table.get(page) for page in range(PAGE_COUNT)}


def read_references(path: str | Path = ROOT / 'refs.txt') -> list[int]:
    result: list[int] = []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        result.extend(int(part) for part in line.split('#', 1)[0].split())
    return result


def split_address(address: int) -> tuple[int, int]:
    if not 0 <= address < PAGE_COUNT * PAGE_SIZE:
        raise ValueError(f"Логический адрес {address} вне диапазона 0…{PAGE_COUNT * PAGE_SIZE - 1}")
    return address // PAGE_SIZE, address % PAGE_SIZE


def translate_address(address: int, table: dict[int, int | None]) -> Translation:
    page, offset = split_address(address)
    frame = table.get(page)
    if frame is None:
        raise PageFault(address, page)
    return Translation(address, page, offset, frame, frame * PAGE_SIZE + offset)


def main() -> None:
    parser = argparse.ArgumentParser(description='Виртуальный адрес -> физический адрес, 1 КБ/страница')
    parser.add_argument('--table', type=Path, default=ROOT / 'pagetable.txt')
    parser.add_argument('--refs', type=Path, default=ROOT / 'refs.txt')
    args = parser.parse_args()
    table = read_page_table(args.table)
    faults = 0
    print(f"{'Адрес':>7} {'Страница':>8} {'Смещение':>9} {'Кадр':>6} {'Физ. адрес / результат'}")
    for address in read_references(args.refs):
        try:
            r = translate_address(address, table)
            print(f'{r.logical:7} {r.page:8} {r.offset:9} {r.frame:6} {r.physical}')
        except PageFault as exc:
            faults += 1
            print(f'{address:7} {exc.page:8} {address % PAGE_SIZE:9} {"—":>6} СТРАНИЧНЫЙ ОТКАЗ')
        except ValueError as exc:
            print(f'{address:7} ОШИБКА: {exc}')
    print(f'Страничных отказов: {faults}')


if __name__ == '__main__':
    main()
