"""One wrapper/one port, serial EVT acceptance then all 37 unmodified behavioral suites."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '验收记录/埋点'
OUT.mkdir(parents=True, exist_ok=True)
os.chdir(ROOT)
assert os.environ['POIGHT_TEST_URL'] == 'http://localhost:8999/'
for command in [
    ['node', 'tests/evt-client.cjs'],
    [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_evt_report.py', '-v'],
    [sys.executable, '验收-埋点.py'],
]:
    subprocess.run(command, cwd=ROOT, check=True)
subprocess.run([sys.executable, 'scripts/perf_network.py'], cwd=ROOT,
               env={**os.environ, 'PERF_LABEL': 'EVT-final-wire'}, check=True)
receipt = json.loads((ROOT / 'tests/EVT-回归基线.json').read_text())
network = json.loads((ROOT / '验收记录/首开加载/EVT-final-wire/network.json').read_text())
budget = {'before': receipt['beforeSelection'], 'after': network['selection'],
          'wireDeltaBytes': network['selection']['bytes'] - receipt['beforeSelection']['bytes'],
          'rawBeforeBytes': receipt['rawBeforeBytes'],
          'rawAfterBytes': (ROOT / '候选试玩.html').stat().st_size,
          'moduleSourceBytes': (ROOT / '埋点.js').stat().st_size}
budget['rawDeltaBytes'] = budget['rawAfterBytes'] - budget['rawBeforeBytes']
(OUT / '字节预算.json').write_text(json.dumps(budget, ensure_ascii=False, indent=2) + '\n')
print('EVT byte budget ' + json.dumps(budget, ensure_ascii=False), flush=True)
assert budget['wireDeltaBytes'] <= 10 * 1024 and budget['rawDeltaBytes'] <= 8 * 1024
assert not network['errors']
code = subprocess.run([sys.executable, 'scripts/PERF-全量.py', 'EVT-final', '--serial'],
                      cwd=ROOT, check=False).returncode
# The wrapper excludes acceptance outputs on upload; use the preserved baseline receipt.
baseline = receipt['suites']
after = json.loads((ROOT / '验收记录/首开加载/EVT-final/summary.json').read_text())
assert len(baseline) == len(after) == 37
assert set(baseline) == {r['test'] for r in after}
new = [r for r in after if r['failed'] > baseline[r['test']]['failed'] or
       r['jsErrors'] > baseline[r['test']]['jsErrors']]
new_vb1 = json.loads((ROOT / '验收记录/招式动画-VB1/浏览器验收.json').read_text())
old_failed = set(receipt['failedVB1Names'])
new_failed = {c['name'] for c in new_vb1['checks'] if not c['ok']}
if new_failed - old_failed or new_vb1.get('failure'):
    new.append({'test': '招式动画-VB1', 'newFailedNames': sorted(new_failed - old_failed),
                'failure': new_vb1.get('failure')})
result = {'suites': 37, 'rawPERFExitCode': code,
          'passed': sum(r['passed'] for r in after), 'failed': sum(r['failed'] for r in after),
          'jsErrors': sum(r['jsErrors'] for r in after), 'newFailures': new,
          'baselineFailedNames': sorted(old_failed), 'currentFailedNames': sorted(new_failed),
          'candidateSHA256': hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest()}
(OUT / '全量比较.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print('EVT regression comparison ' + json.dumps(result, ensure_ascii=False), flush=True)
raise SystemExit(bool(new))
