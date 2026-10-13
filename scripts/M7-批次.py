"""Jade-only serial acceptance with byte-verified historical inputs and explicit suites."""
import atexit
import hashlib
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
label, *names = sys.argv[1:]
keep_going = '--keep-going' in names
if keep_going:
    names.remove('--keep-going')
out = ROOT / '验收记录/集成批次' / label
out.mkdir(parents=True, exist_ok=True)
if os.environ.get('POIGHT_FIXTURES_STAGED') != '1':
    with tarfile.open(ROOT / 'MX-夹具.tar.gz') as archive:
        archive.extractall(ROOT, filter='data')
hashes = json.loads((ROOT / 'MX-夹具-sha256.json').read_text())
assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
           for name, digest in hashes.items())
print(f'Verified {len(hashes)} unchanged historical inputs', flush=True)


def clean_staged_inputs():
    if os.environ.get('POIGHT_KEEP_FIXTURES') == '1':
        return  # M9 has three local lanes sharing these immutable inputs.
    # The immutable archive/hash manifest is retained. Do not copy 20k temporary
    # fixture rasters back as if they were new acceptance evidence.
    for name, digest in hashes.items():
        if not name.startswith(('验收记录/MX-夹具/', '验收记录/丰缘全图/M-fd1eb0f/', 'MX-远程bin/')):
            continue
        path = ROOT / name
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
            path.unlink()


atexit.register(clean_staged_inputs)
os.environ.update(POIGHT_T5_BASELINE=str(ROOT / '验收记录/MX-夹具/T5'),
                  POIGHT_A1_REFERENCE=str(ROOT / '验收记录/MX-夹具/关键帧核查.jpg'))
# V1's immutable R3 atlas receipt ships in the starting M6b commit, but not in
# MX's pre-V1 fixture archive. Restore that input, never synthesize it from output.
receipts = json.loads((ROOT / 'tests/M6b基线/远程收据.json').read_text())
relative = '招式第3批/受保护图集.json'
receipt = ROOT / '验收记录' / relative
receipt.parent.mkdir(parents=True, exist_ok=True)
receipt.write_text(receipts[relative])
summary = []
artifact = hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest()
for name in names:
    if name == '丰缘全图':
        performance = subprocess.run([sys.executable, '验收-丰缘性能.py'], cwd=ROOT,
            env={**os.environ, 'POIGHT_BENCH_REPLAY': '1'},
            capture_output=True, text=True, timeout=1800, check=False)
        (out / '丰缘性能.log').write_text(performance.stdout + performance.stderr)
        print('PERFORMANCE ' + performance.stdout[-3000:] + performance.stderr[-3000:], flush=True)
        if performance.returncode:
            raise SystemExit(performance.returncode)
    print('RUN ' + name, flush=True)
    result = subprocess.run([sys.executable, f'验收-{name}.py'], cwd=ROOT,
                            capture_output=True, text=True, timeout=1800, check=False)
    (out / f'{name}.log').write_text(result.stdout + result.stderr)
    obj = None
    for pos, char in enumerate(result.stdout):
        if char != '{':
            continue
        try:
            candidate, _ = json.JSONDecoder().raw_decode(result.stdout[pos:])
            if isinstance(candidate, dict) and 'passed' in candidate:
                obj = candidate
                break
        except ValueError:
            pass
    if obj is None:
        print(result.stdout[-3000:] + result.stderr[-3000:], flush=True)
        if not keep_going:
            raise SystemExit(result.returncode or 1)
        obj = {'passed': 0, 'failed': 1, 'failure': 'Suite exited without a structured report',
               'checks': [{'name': 'missing structured report (JS count unverified)',
                           'ok': False, 'detail': result.stderr[-3000:]}]}
    row = {'test': name, 'exitCode': result.returncode, 'passed': obj['passed'],
           'failed': max(obj.get('failed', sum(not c['ok'] for c in obj.get('checks', []))),
                         int(bool(obj.get('failure') or result.returncode))),
           'jsErrors': obj.get('jsErrors', len(obj.get('errors', [])))}
    summary.append(row)
    (out / f'{name}.json').write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(name + ' ' + json.dumps({k: row[k] for k in ('passed', 'failed', 'jsErrors')},
                                 ensure_ascii=False), flush=True)
    if row['exitCode'] or row['failed'] or row['jsErrors']:
        for item in obj.get('checks', []):
            if not item['ok']:
                print('FAIL ' + json.dumps(item, ensure_ascii=False), flush=True)
        print(result.stdout[-6000:] + result.stderr[-3000:], flush=True)
        if not keep_going:
            raise SystemExit(1)
assert hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest() == artifact
(out / 'candidate-sha256.txt').write_text(artifact + '\n')
total = {'suites': len(summary), 'passed': sum(s['passed'] for s in summary),
         'failed': sum(s['failed'] for s in summary), 'jsErrors': sum(s['jsErrors'] for s in summary)}
print('TOTAL ' + json.dumps(total), flush=True)
if total['failed'] or total['jsErrors']:
    raise SystemExit(1)
