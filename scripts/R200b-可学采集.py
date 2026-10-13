"""Archive new-150 default-form learnsets via curl, <=4 workers, two retries.
Keep original 50 audit rows byte-for-byte (their Gen IX scope is historical).
R200b explicitly uses ANY generation/method for the new 150 only.
"""
import csv
import hashlib
import io
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from 游戏数据 import MOVES

HERE = ROOT / '数值资料/Pi-20261011'
RAW = HERE / 'learnset-原始'
RAW.mkdir(exist_ok=True)
old = set(json.loads((ROOT / '首发50.json').read_text())['ids'])
ids = [n for n in json.loads((ROOT / '首发200.json').read_text())['ids'] if n not in old]
assert len(ids) == 150
# Use the existing audited canonical slugs, not display-name/type inference.
move_audit = json.loads((HERE / 'move-audit.json').read_text())['moves']
catalog = {mid: move_audit[mid]['name'] for mid in MOVES if mid != 'splash'}
assert len(catalog) == 120


def one(n):
    url = f'https://pokeapi.co/api/v2/pokemon/{n}/'
    path = RAW / f'{n:04}.json'
    if not path.exists():
        tmp = path.with_suffix('.part')
        subprocess.run(['curl', '-fLsS', '--retry', '2', '--retry-all-errors',
                        '--max-time', '60', url, '-o', str(tmp)], check=True)
        data = json.loads(tmp.read_bytes())
        assert data['id'] == n and data['is_default']
        tmp.replace(path)
    raw = path.read_bytes()
    data = json.loads(raw)
    assert data['id'] == n and data['is_default']
    # A returned move must have an actual version/method learning entry.
    available = {m['move']['name'] for m in data['moves'] if m['version_group_details']}
    learned = [mid for mid, slug in catalog.items() if slug in available]
    print('learnset archived', n, len(learned), flush=True)
    return dict(id=n, name=data['name'], runtimeMoveIDs=learned,
                sourceURL=url, raw=str(path.relative_to(HERE)),
                sha256=hashlib.sha256(raw).hexdigest())


with ThreadPoolExecutor(max_workers=4) as executor:
    records = list(executor.map(one, ids))
path = HERE / 'learnset-audit.tsv'
original = path.read_bytes().splitlines(keepends=True)
keep = [line for line in original[1:] if int(line.split(b'\t')[0]) in old]
assert len(keep) == 50
buffer = io.StringIO(newline='')
writer = csv.writer(buffer, delimiter='\t', lineterminator='\r\n')
for r in records:
    writer.writerow([r['id'], r['name'], 'Any generation / all methods (R200b)',
                     len(r['runtimeMoveIDs']), ','.join(r['runtimeMoveIDs'])])
path.write_bytes(original[0] + b''.join(keep) + buffer.getvalue().encode())
receipt = dict(policy='New 150 only: any version_group / all listed methods in default-form pokemon/{id}.moves intersect existing 120 runtime moves; splash excluded. Original 50 Gen IX rows unchanged.',
               retrievedUTC=datetime.now(timezone.utc).isoformat(), workers=4, retries=2,
               records=records)
(HERE / 'learnset-R200b来源.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
print('new150', len(records), 'original50RowsUnchanged', len(keep), flush=True)
