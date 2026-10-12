"""离线构建接入：状态表为唯一概率来源；贴图仅复制、不改原素材。"""
import csv


def apply(moves, root, output):
    with (root / '招式状态表.tsv').open() as f:
        for row in csv.DictReader(f, delimiter='\t'):
            moves[row['id']].setdefault('statuses', []).append({
                'id': row['状态'], 'chance': float(row['概率']),
                'line': int(row['来源行']),
            })
    return {code: output('status-' + code + '.png',
                         (root / '素材/原版数据/状态贴图' / (code + '.png')).read_bytes())
            for code in ('par', 'brn', 'frz', 'psn', 'crystal')}
