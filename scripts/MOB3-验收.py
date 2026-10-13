"""Same-candidate serial release receipt. Run through HOST=local wrapper, port 8984."""
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '验收记录/MOB3/最终'
OUT.mkdir(parents=True, exist_ok=True)
sha = hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest()
evt_build = re.search(r'b: "([0-9a-f]{8})", p: encoded', (ROOT / '候选试玩.html').read_text()).group(1)
build_commit = subprocess.check_output(['git', 'rev-parse', evt_build], cwd=ROOT, text=True).strip()
source_hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                 for name in ['界面-GBA.css', '界面-GBA.js']}
assert all(hashlib.sha256(subprocess.check_output(['git', 'show', build_commit + ':' + name], cwd=ROOT)).hexdigest() == digest
           for name, digest in source_hashes.items()), 'Candidate build must name the committed production source tree'
commands = [
    ['scripts/MOB3-静态.py'],
    ['scripts/MOB2-验收.py', '--matrix-only'],
    ['scripts/M9-手机汇总.py'],
    ['scripts/M7-批次.py', 'MOB3-final', '界面GBA', '手机操作', '选人页', '头顶血条', 'M7联动', '首开加载', '埋点', '演示模式', '--keep-going'],
    ['scripts/MOB3-首屏.py', '最终首屏'],
    ['scripts/MOB3-状态.py', '最终结算'],
    ['scripts/MOB3-极矮屏.py'],
    ['scripts/MOB3-桌面对照.py'],
]
rows = []
print('CANDIDATE_SHA256 ' + sha, flush=True)
for arguments in commands:
    print('MOB3_RUN ' + ' '.join(arguments), flush=True)
    started = time.monotonic()
    log = OUT / (str(len(rows) + 1) + '.log')
    with log.open('w') as stream:
        result = subprocess.run([sys.executable, *arguments], cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=False)
    print(log.read_text()[-14000:], flush=True)
    row = {'command': arguments, 'exitCode': result.returncode, 'seconds': round(time.monotonic() - started, 2)}
    rows.append(row)
    assert hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest() == sha
    assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in source_hashes.items())
    (OUT / 'pipeline.json').write_text(json.dumps({'candidateSHA256': sha, 'buildCommit': build_commit,
        'sourceSHA256': source_hashes, 'runs': rows}, ensure_ascii=False, indent=2))
    print('MOB3_DONE ' + json.dumps(row, ensure_ascii=False), flush=True)
raise SystemExit(any(r['exitCode'] for r in rows))
