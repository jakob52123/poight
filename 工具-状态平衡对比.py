"""对照 M4 与 S1 的同计划7350局及固定20局；只报告，不调参。"""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/异常状态'


def load(name):
    return [json.loads(line) for line in (OUT / name).read_text().splitlines()]


def main():
    plan = json.loads((OUT / '全量计划.json').read_text())
    expected = [(j['a'], j['b'], j['seed'] + i) for j in plan for i in range(j['n'])]
    assert len(expected) == 7350
    roster = {r['id']: r['name'] for r in json.loads((OUT / 'catalog.json').read_text())['roster']}
    before, after = load('M4-all.jsonl'), load('S1-all.jsonl')
    result = {}
    for label, rows in [('M4', before), ('S1', after)]:
        assert [(r['a'], r['b'], r['seed']) for r in rows] == expected
        assert all(r['tier'] == r['playerTier'] == 'great' and r['hpMultiplier'] == 6 for r in rows)
        counts = defaultdict(Counter)
        for r in rows:
            for side, other in [('a', 'b'), ('b', 'a')]:
                c = counts[r[side]]
                c['n'] += 1
                c['wins'] += r['winner'] == side
                c['losses'] += r['winner'] == other
                c['timeouts'] += r['winner'] == 'timeout'
                c['draws'] += r['winner'] == 'draw'
                net = sum(e['amount'] * (-1 if e['kind'] == 'heal' else 1)
                          for e in r['composition'] if e['target'] == side)
                assert abs(net - (r['maxHP'][side] - r['hp'][side])) < 1e-7
        assert len(counts) == 50 and all(c['n'] == 294 for c in counts.values())
        result[label] = {n: {**c, 'name': roster[n], 'winPercent': c['wins'] / c['n'] * 100}
                         for n, c in counts.items()}
    pair1, pair2 = OUT / 'S1-pair-1.jsonl', OUT / 'S1-pair-2.jsonl'
    assert pair1.read_bytes() == pair2.read_bytes()
    pair = {label: median(r['seconds'] for r in load(filename)) for label, filename in
            [('M4', 'M4-pair.jsonl'), ('S1', 'S1-pair-1.jsonl')]}
    ranked = {label: sorted(rows, key=lambda n: (-rows[n]['winPercent'], n))
              for label, rows in result.items()}
    lines = ['# S1 状态平衡对比', '',
             '同T9全员计划：50选2，左右各3局，great，HP×6；每版本7350局、每只294局。',
             '胜率=胜场/全部对局，超时保留为删失，不按剩余血量判胜。', '',
             (f"固定25 vs 6 / poke / n20 / seed1：M4中位数 {pair['M4']:.6f}s；"
              f"S1 {pair['S1']:.6f}s；变化 {pair['S1']-pair['M4']:+.6f}s。"),
             'S1两次JSONL逐字节一致，SHA256：' + hashlib.sha256(pair1.read_bytes()).hexdigest(), '']
    for label in ['M4', 'S1']:
        for title, ids in [('最高5只', ranked[label][:5]), ('最低5只', ranked[label][-5:])]:
            lines += [f'## {label} {title}', '', '|精灵|M4胜率|S1胜率|变化百分点|', '|---|---:|---:|---:|']
            for n in ids:
                b, a = result['M4'][n]['winPercent'], result['S1'][n]['winPercent']
                lines.append(f'|{n} {roster[n]}|{b:.4f}%|{a:.4f}%|{a-b:+.4f}|')
            lines.append('')
    lines += ['仅报告：未修改伤害基础值、冷却、射程、体力或全局HP倍率。']
    report = {'gamesEach': 7350, 'pairMedians': pair, 'byteIdentical': True,
              'ranked': ranked, 'species': result}
    (OUT / '平衡对比.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    (OUT / '平衡对比.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
