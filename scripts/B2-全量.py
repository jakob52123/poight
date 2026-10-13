"""Exact PERF-release 37-suite manifest; run only inside the queued wrapper.

Reuse M7's immutable input prelude, but don't abort the other 36 suites when a
legacy script raises before printing JSON. Such a crash is an explicit failure.
"""
import ast
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
tree = ast.parse((ROOT / 'scripts/PERF-全量.py').read_text())
groups = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == 'groups' for t in n.targets))
names = [name for group in groups for name in group]
assert len(names) == len(set(names)) == 37
label = sys.argv[1] if len(sys.argv) > 1 else 'B2-release'
subprocess.run([sys.executable, '验收-B2平衡.py', 'after'], cwd=ROOT, check=True)
# Same archive, SHA validation, reference environment and atexit cleanup as M7.
# Execute only its setup, no suites/CLI/exit handling; fixture files live until our exit.
setup_path = ROOT / 'scripts/M7-批次.py'
prefix, separator, _ = setup_path.read_text().partition('\nfor name in names:')
assert separator
old_argv = sys.argv
sys.argv = [str(setup_path), label]
try:
    exec(compile(prefix, str(setup_path), 'exec'), {'__file__': str(setup_path)})  # noqa: S102 - trusted repository setup, not external input
finally:
    sys.argv = old_argv
out = ROOT / '验收记录/集成批次' / label
artifact = hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest()
rows = []
for name in names:
    if name == '丰缘全图':
        perf = subprocess.run([sys.executable, '验收-丰缘性能.py'], cwd=ROOT,
                              env={**os.environ, 'POIGHT_BENCH_REPLAY': '1'},
                              capture_output=True, text=True, timeout=1800, check=False)
        (out / '丰缘性能.log').write_text(perf.stdout + perf.stderr)
        print('PERFORMANCE ' + perf.stdout[-3000:] + perf.stderr[-3000:], flush=True)
        assert perf.returncode == 0, '丰缘性能 preflight failed'
    print('RUN ' + name, flush=True)
    try:
        result = subprocess.run([sys.executable, f'验收-{name}.py'], cwd=ROOT,
                                capture_output=True, text=True, timeout=1800, check=False)
        stdout, stderr, code = result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or b''
        stderr = exc.stderr or b''
        stdout = stdout.decode() if isinstance(stdout, bytes) else stdout
        stderr = stderr.decode() if isinstance(stderr, bytes) else stderr
        code = 124
    (out / f'{name}.log').write_text(stdout + stderr)
    obj = None
    for pos, char in enumerate(stdout):
        if char != '{':
            continue
        try:
            candidate, _ = json.JSONDecoder().raw_decode(stdout[pos:])
            if isinstance(candidate, dict) and 'passed' in candidate:
                obj = candidate
                break
        except ValueError:
            pass
    if obj is None:
        obj = {'passed': 0, 'failed': 1, 'jsErrors': 0,
               'failure': 'No acceptance JSON; inspect log (JS error count unavailable)'}
    row = {'test': name, 'exitCode': code, 'passed': obj['passed'],
           'failed': max(obj.get('failed', sum(not c['ok'] for c in obj.get('checks', []))),
                         int(bool(obj.get('failure') or code))),
           'jsErrors': obj.get('jsErrors', len(obj.get('errors', [])))}
    rows.append(row)
    (out / f'{name}.json').write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    (out / 'summary.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    print(name + ' ' + json.dumps({k: row[k] for k in ('passed', 'failed', 'jsErrors')},
                                 ensure_ascii=False), flush=True)
    if row['exitCode'] or row['failed'] or row['jsErrors']:
        for item in obj.get('checks', []):
            if not item['ok']:
                print('FAIL ' + json.dumps(item, ensure_ascii=False), flush=True)
        print(stdout[-6000:] + stderr[-3000:], flush=True)
assert len(rows) == 37 and [row['test'] for row in rows] == names
assert hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest() == artifact
(out / 'candidate-sha256.txt').write_text(artifact + '\n')
lines = [r['test'] + ' ' + json.dumps({k: r[k] for k in ('passed', 'failed', 'jsErrors')},
                                    ensure_ascii=False) for r in rows]
total = {'suites': len(rows), 'passed': sum(r['passed'] for r in rows),
         'failed': sum(r['failed'] for r in rows), 'jsErrors': sum(r['jsErrors'] for r in rows)}
lines.append('TOTAL ' + json.dumps(total))
text = '\n'.join(lines) + '\n'
(out / '原样摘要.txt').write_text(text)
print(text, end='', flush=True)
raise SystemExit(bool(total['failed'] or total['jsErrors']))
