"""Вариант B: воспроизводимая длинная строка с локальностью и SVG-график TLB."""
from __future__ import annotations

import argparse
import random
from pathlib import Path

from tlb import effective_access_ns, simulate
from translate import PAGE_SIZE, ROOT, read_page_table, read_references


def make_references(length: int = 2000, seed: int = 11, local: bool = True) -> list[int]:
    if length < 0:
        raise ValueError('length должен быть неотрицательным')
    rng = random.Random(seed)
    # Страница 4 отсутствует. Исключаем её, чтобы сравнение попаданий не
    # смешивалось со штрафами за обработку страничного отказа.
    pages = [0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    hot = [0, 1, 2]
    return [(rng.choice(hot) if local and rng.random() < 0.90 else rng.choice(pages)) * PAGE_SIZE
            + rng.randrange(PAGE_SIZE) for _ in range(length)]


def save_svg(path: Path, rates: list[tuple[int, float, float]]) -> None:
    """Сохранить готовый график без внешних Python-зависимостей."""
    path.parent.mkdir(parents=True, exist_ok=True)
    W, H, x0, y0, pw, ph = 820, 460, 85, 55, 660, 320
    def y(value: float) -> float:
        return y0 + ph * (1 - value)
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" '
             'aria-label="TLB hit rate as a function of TLB size">',
             '<rect width="100%" height="100%" fill="#fff"/>',
             '<text x="410" y="30" text-anchor="middle" font-family="Arial" font-size="20">'
             'TLB: размер и доля попаданий</text>']
    for v in range(0, 101, 20):
        yy = y(v / 100)
        lines += [f'<line x1="{x0}" y1="{yy:.1f}" x2="{x0 + pw}" y2="{yy:.1f}" stroke="#e5e7eb"/>',
                  f'<text x="{x0 - 10}" y="{yy + 4:.1f}" text-anchor="end" font-family="Arial" font-size="13">{v}%</text>']
    lines.append(f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y0 + ph}" stroke="#555"/>')
    for k, *_ in rates:
        xx = x0 + pw * k / 16
        lines.append(f'<text x="{xx:.1f}" y="{y0 + ph + 22}" text-anchor="middle" font-family="Arial" font-size="13">{k}</text>')
    for ix, (column, color, legend) in enumerate([(1, '#2563eb', 'Локальность'), (2, '#ef4444', 'Случайная')]):
        points = [(x0 + pw * k / 16, y(rate)) for k, *vals in rates for rate in [vals[column - 1]]]
        joined = ' '.join(f'{xx:.1f},{yy:.1f}' for xx, yy in points)
        lines.append(f'<polyline points="{joined}" fill="none" stroke="{color}" stroke-width="3"/>')
        for xx, yy in points:
            lines.append(f'<circle cx="{xx:.1f}" cy="{yy:.1f}" r="3" fill="{color}"/>')
        lines.append(f'<line x1="{170 + ix * 255}" x2="{208 + ix * 255}" y1="{H - 34}" y2="{H - 34}" stroke="{color}" stroke-width="3"/>')
        lines.append(f'<text x="{216 + ix * 255}" y="{H - 30}" font-family="Arial" font-size="15">{legend}</text>')
    lines.append(f'<text x="{x0 + pw / 2}" y="{y0 + ph + 49}" text-anchor="middle" font-family="Arial" font-size="14">Количество записей TLB (K)</text>')
    lines.append('<text x="16" y="48" font-family="Arial" font-size="13">Hit rate</text></svg>')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--length', type=int, default=2000)
    parser.add_argument('--seed', type=int, default=11)
    parser.add_argument('--output', type=Path, default=ROOT / 'figures/tlb_hit_rate.svg')
    args = parser.parse_args()
    table = read_page_table()
    local_refs = make_references(args.length, args.seed, True)
    random_refs = make_references(args.length, args.seed, False)
    print('K | локальная hit rate | случайная hit rate')
    rates = []
    for k in range(1, 17):
        local = simulate(local_refs, k, table)
        random_case = simulate(random_refs, k, table)
        rates.append((k, local.hit_rate, random_case.hit_rate))
        print(f'{k:2} | {local.hit_rate:16.2%} | {random_case.hit_rate:16.2%}')
    save_svg(args.output, rates)
    print(f'График сохранён: {args.output}')
    short = read_references()
    print('\nrefs.txt:')
    for k in (1, 2, 3, 4, 8):
        s = simulate(short, k, table)
        print(f'K={k}: hit={s.hits}, miss={s.misses}, page faults={s.page_faults}, '
              f'hit rate={s.hit_rate:.2%}, EAT≈{effective_access_ns(s.hit_rate):.2f} нс*')
    print('*EAT без стоимости page faults, поэтому для трассы с отсутствующей страницей '
          'это условная оценка.')
    print('Теоретическое EAT при h=0,0.5,0.9,1:')
    for h in (0, 0.5, 0.9, 1):
        print(f'h={h:.0%}: {effective_access_ns(h):.0f} нс')


if __name__ == '__main__':
    main()
