"""从固定的 Showdown moves.ts 提取本作招式状态，不联网、不猜测概率。"""
import csv
import hashlib
import json
import re
from pathlib import Path

from 游戏数据 import MOVES

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / '素材/原版数据/showdown-moves.ts'


def main():
    text = SOURCE.read_text()
    starts = list(re.finditer(r'^\t([a-z0-9]+): \{', text, re.MULTILINE))
    rows = []
    for i, match in enumerate(starts):
        mid = match[1]
        if mid not in MOVES:
            continue
        block = text[match.start():starts[i + 1].start() if i + 1 < len(starts) else len(text)]
        base = text[:match.start()].count('\n') + 1
        for status in re.finditer(r"\bstatus: '(par|brn|frz|psn|tox)'", block):
            preceding = block[:status.start()]
            chances = list(re.finditer(r'chance: (\d+)', preceding))
            chance = int(chances[-1][1]) if chances else 100
            rows.append([mid, MOVES[mid]['name'], 'psn' if status[1] == 'tox' else status[1],
                         chance, base + preceding.count('\n')])
        # 三重攻击由 secondary.onHit 等概率抽样三个状态，不是三个独立20%。
        if mid == 'triattack':
            assert "this.sample(['brn', 'par', 'frz'])" in block
            chance = int(re.search(r'chance: (\d+)', block)[1])
            line = base + block[:block.index('const status')].count('\n')
            rows.extend([mid, MOVES[mid]['name'], s, chance / 3, line]
                        for s in ('brn', 'par', 'frz'))
    with (ROOT / '招式状态表.tsv').open('w') as f:
        writer = csv.writer(f, delimiter='\t', lineterminator='\n')
        writer.writerow(['id', '中文名', '状态', '概率', '来源行'])
        writer.writerows(rows)
    receipt = {
        'url': 'https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/moves.ts',
        'downloadDate': '2026-10-11', 'license': 'MIT',
        'sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'rows': len(rows), 'moves': len({r[0] for r in rows}),
        'policy': '命中后条件概率；tox→psn；三重攻击20%内等概率三选一；不导入畏缩/睡眠/混乱。',
    }
    (ROOT / '素材/原版数据/来源收据.json').write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()
