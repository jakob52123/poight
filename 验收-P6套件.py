"""Run disjoint halves of VH's unmodified suite inventory on assigned Jade ports."""
import json
import os
import subprocess
import sys
import tarfile
from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Original historical receipts/atlases, staged inside this task only (never a sibling checkout).
with tarfile.open(ROOT / 'P6-fixtures.tar') as archive:
    archive.extractall(ROOT, filter='data')
os.environ['POIGHT_T5_BASELINE'] = str(ROOT / 'P6-T5-fixture')
NAMES = import_module('验收-VH全量').NAMES
part = sys.argv[1]
names = NAMES[:12] if part == 'A' else NAMES[12:]
out = Path(ROOT) / '验收记录/集成批次' / ('P6-' + part)
out.mkdir(parents=True, exist_ok=True)
rows = []
for name in names:
    print('RUN ' + name, flush=True)
    r = subprocess.run([sys.executable, f'验收-{name}.py'], env=os.environ.copy(),
                       capture_output=True, text=True, timeout=1800, check=False)
    (out / (name + '.log')).write_text(r.stdout + r.stderr)
    obj = None
    for i, char in enumerate(r.stdout):
        if char != '{':
            continue
        try:
            candidate, _ = json.JSONDecoder().raw_decode(r.stdout[i:])
            if isinstance(candidate, dict) and 'passed' in candidate:
                obj = candidate
                break
        except ValueError:
            pass
    if obj is None:
        print(r.stdout[-3000:] + r.stderr[-3000:], flush=True)
        raise SystemExit(r.returncode or 1)
    row = {'test': name, 'exitCode': r.returncode, 'passed': obj['passed'],
           'failed': obj.get('failed', sum(not c['ok'] for c in obj.get('checks', []))),
           'jsErrors': obj.get('jsErrors', len(obj.get('errors', [])))}
    rows.append(row)
    (out / 'summary.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(row, ensure_ascii=False), flush=True)
    if r.returncode or row['failed'] or row['jsErrors']:
        print(r.stderr[-3000:], flush=True)
        raise SystemExit(1)
total = {'suites': len(rows), 'passed': sum(s['passed'] for s in rows),
         'failed': sum(s['failed'] for s in rows), 'jsErrors': sum(s['jsErrors'] for s in rows)}
(out / 'total.json').write_text(json.dumps(total, ensure_ascii=False, indent=2) + '\n')
print('TOTAL ' + json.dumps(total, ensure_ascii=False), flush=True)
