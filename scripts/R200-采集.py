"""Incremental curl archives; four workers, two retries; never overwrite original 50."""
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / '数值资料/体型校准'
ids = json.loads((ROOT / '首发200.json').read_text())['ids']
source = json.loads((HERE / '来源.json').read_text())
existing = {s['id']: s for s in source['species']}


def one(n):
    if n in existing:
        return existing[n]
    url = f'https://pokeapi.co/api/v2/pokemon/{n}/'
    path = HERE / f'原始响应/{n:04}.json'
    if not path.exists():
        tmp = path.with_suffix('.part')
        subprocess.run(['curl', '-fLsS', '--retry', '2', '--max-time', '60', url, '-o', str(tmp)], check=True)
        data = json.loads(tmp.read_bytes())
        assert data['id'] == n and data['is_default']
        tmp.replace(path)
    raw = path.read_bytes()
    data = json.loads(raw)
    assert data['id'] == n and data['is_default']
    print('archived', n, flush=True)
    return dict(id=n, name=data['name'], heightDm=data['height'], weightHg=data['weight'],
                baseSpeed=next(s['base_stat'] for s in data['stats'] if s['stat']['name'] == 'speed'),
                isDefault=True, sourceURL=url, raw=str(path.relative_to(HERE)),
                sha256=hashlib.sha256(raw).hexdigest(), cached=False)


with ThreadPoolExecutor(max_workers=4) as pool:
    records = list(pool.map(one, ids))
source.update(count=len(records), species=records, errors=[],
              R200='curl --retry 2, concurrency 4; original 50 response bytes and receipts preserved')
(HERE / '来源.json').write_text(json.dumps(source, ensure_ascii=False, indent=2) + '\n')
print('body sources', len(records))
