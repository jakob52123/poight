"""Single tool invocation/8977 slot; all browser suites execute serially."""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '验收记录/MOB2'
OUT.mkdir(parents=True, exist_ok=True)
commands = [
    ['验收-手机操作.py'],
    ['验收-手机兜底.py', '--stage', 'live'],
    ['scripts/PERF-全量.py', 'MOB2-release', '--serial'],
    ['验收-手机适配.py'],
    ['验收-手机兜底.py', '--stage', 'matrix'],
]
# M9 runs the 37-suite union independently on the same SHA; avoid a duplicate serial run.
if '--matrix-only' in sys.argv:
    commands = commands[-2:]
rows = []
sha = hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest()
for arguments in commands:
    started = time.monotonic()
    print('MOB2_RUN ' + ' '.join(arguments), flush=True)
    result = subprocess.run([sys.executable, *arguments], cwd=ROOT, check=False)
    rows.append({'command': arguments, 'exitCode': result.returncode,
                 'seconds': round(time.monotonic() - started, 2)})
    (OUT / 'pipeline.json').write_text(json.dumps({'candidateSHA256': sha, 'runs': rows}, indent=2) + '\n')
    assert hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest() == sha
    print('MOB2_DONE ' + json.dumps(rows[-1]), flush=True)
    if result.returncode and (arguments[-1] == 'live' or arguments[0] == '验收-手机操作.py'):
        break
raise SystemExit(any(r['exitCode'] for r in rows))
