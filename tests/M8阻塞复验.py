"""Run independent M8-r3 gates without losing later results after a failure."""
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '验收记录/集成批次' / sys.argv[1]
OUT.mkdir(parents=True, exist_ok=True)
# Remote transport excludes old reports; these are frozen inputs, not new baselines.
expected = json.loads((ROOT / 'tests/VB2远程输入SHA.json').read_text())
with zipfile.ZipFile(ROOT / 'tests/VB2远程输入.zip') as archive:
    assert set(archive.namelist()) == set(expected)
    for name, digest in expected.items():
        target = ROOT / name
        assert target.resolve().is_relative_to(ROOT)
        data = archive.read(name)
        assert hashlib.sha256(data).hexdigest() == digest
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
with zipfile.ZipFile(ROOT / 'tests/M8历史夹具.zip') as archive:
    frozen = json.loads((ROOT / 'tests/M8历史夹具SHA.json').read_text())
    assert set(archive.namelist()) == set(frozen)
    for name, digest in frozen.items():
        data = archive.read(name)
        assert hashlib.sha256(data).hexdigest() == digest
        target = ROOT / name
        assert target.resolve().is_relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
# The full historical driver generated this receipt via 招式第3批 before the visual
# suites. A blocker-only batch must stage its identical, already-frozen nine hashes.
guard = ROOT / '验收记录/招式第3批/受保护图集.json'
guard.parent.mkdir(parents=True, exist_ok=True)
guard.write_bytes((ROOT / 'tests/VB2保护图集.json').read_bytes())
rows = []
for name in sys.argv[2:]:
    env = os.environ.copy()
    if name == '招式动画-VA1':
        env['POIGHT_VA1_CAPTURE'] = '1'
    print('RUN ' + name, flush=True)
    try:
        result = subprocess.run([sys.executable, str(ROOT / f'验收-{name}.py')],
                                cwd=ROOT, env=env, capture_output=True, text=True,
                                timeout=int(env.get('POIGHT_SUITE_TIMEOUT', '1800')), check=False)
        output = result.stdout + result.stderr
        rc = result.returncode
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or b'').decode() + (exc.stderr or b'').decode()
        output += '\nM8 SUITE TIMEOUT\n'
        rc = 124
    (OUT / f'{name}.log').write_text(output)
    obj = None
    for line in reversed(output.splitlines()):
        try:
            value = json.loads(line)
            if isinstance(value, dict) and 'passed' in value:
                obj = value
                break
        except ValueError:
            pass
    if obj is None:
        for pos, char in enumerate(output):
            if char != '{':
                continue
            try:
                value, _ = json.JSONDecoder().raw_decode(output[pos:])
                if isinstance(value, dict) and 'passed' in value:
                    obj = value
                    break
            except ValueError:
                pass
    row = {'test': name, 'exitCode': rc,
           'passed': obj['passed'] if obj else 0,
           'failed': max(obj.get('failed', 0), int(bool(rc))) if obj else 1,
           'jsErrors': obj.get('jsErrors', len(obj.get('errors', []))) if obj else None}
    rows.append(row)
    (OUT / 'summary.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    print(name + ' ' + json.dumps({k: row[k] for k in ['passed', 'failed', 'jsErrors']},
                                 ensure_ascii=False), flush=True)
    if rc:
        detail_path = ROOT / '验收记录' / name / '浏览器验收.json'
        if detail_path.exists():
            detail = json.loads(detail_path.read_text())
            if detail.get('failure'):
                print('EXCEPTION ' + detail['failure'], flush=True)
        for line in [line for line in output.splitlines() if line.startswith('FAIL ')][:50]:
            print(line, flush=True)
        print(output[-2000:], flush=True)
proof = {'candidateSHA256': hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest(),
         'manifestSHA256': hashlib.sha256((ROOT / '候选发布清单.json').read_bytes()).hexdigest(),
         'probes': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in sorted((ROOT / 'tests').glob('*.js'))},
         'tests': {name: hashlib.sha256((ROOT / f'验收-{name}.py').read_bytes()).hexdigest()
                   for name in sys.argv[2:]}, 'results': rows}
(OUT / 'proof.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n')
total = {'suites': len(rows), 'passed': sum(r['passed'] for r in rows),
         'failed': sum(r['failed'] for r in rows),
         'jsErrors': sum(r['jsErrors'] or 0 for r in rows),
         'incomplete': sum(r['jsErrors'] is None for r in rows)}
# Keep the required screenshots and all numeric receipts in the normal return tree.
# Retain bulky optional movies/sheets byte-for-byte on Jade, under a SHA-addressed
# directory excluded by the transport. This does not skip or alter any assertion.
archive_root = ROOT / '.remote-run/M8-heavy-evidence' / proof['candidateSHA256']
parked = []
for path in (ROOT / '验收记录').rglob('*'):
    if not path.is_file():
        continue
    heavy = path.suffix == '.gif' or (path.suffix == '.png' and path.stat().st_size > 65536
            and '实战-' not in path.name and 'composite' not in path.name
            and 'P6' not in path.parts and '首开加载' not in path.parts)
    if not heavy:
        continue
    relative = path.relative_to(ROOT)
    target = archive_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    parked.append({'path': str(relative), 'archive': str(target.relative_to(ROOT)),
                   'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size})
    path.replace(target)
(OUT / '远端大图索引.json').write_text(json.dumps(parked, ensure_ascii=False, indent=2) + '\n')
print('TOTAL ' + json.dumps(total), flush=True)
raise SystemExit(int(bool(total['failed'] or total['jsErrors'] or total['incomplete'])))
