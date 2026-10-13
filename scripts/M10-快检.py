"""Serial quick-check lane. Run only through the authorized preview wrapper."""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
lane = sys.argv[1]
OUT = ROOT / '验收记录/M10' / lane
OUT.mkdir(parents=True, exist_ok=True)
sha = hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest()
groups = {
    'local': [(['验收-战斗音乐.py'], '战斗音乐'), (['验收-首开加载.py'], '首开加载'), (['验收-埋点.py'], '埋点')],
    'local复验': [(['验收-界面GBA.py'], '界面GBA'), (['验收-战斗音乐.py'], '战斗音乐')],
    'Jade基线': [(['验收-界面GBA.py'], '界面GBA')],
    'Jade': [(['验收-界面GBA.py'], '界面GBA'), (['验收-选人页.py'], '选人页'),
             (['逐精灵验收.py', '--tag', 'M10'], '逐精灵'), (['scripts/R200-冒烟.py'], '200只冒烟')],
}
reports = {'战斗音乐': '战斗音乐/report.json', '首开加载': '首开加载/验收.json',
           '埋点': '埋点/验收.json', '界面GBA': 'UI2/summary.json',
           '选人页': '选人页/浏览器验收.json', '逐精灵': 'R200/逐精灵验收-M10.json',
           '200只冒烟': 'R200/冒烟.json'}
summary = []
for args, name in groups[lane]:
    start = time.monotonic()
    print('RUN', lane, name, sha, flush=True)
    try:
        p = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True,
                           text=True, timeout=1800)
        text, code = p.stdout + p.stderr, p.returncode
    except subprocess.TimeoutExpired as exc:
        text, code = str(exc), 124
    (OUT / (name + '.log')).write_text(text)
    objects = []
    for i, char in enumerate(text):
        if char != '{':
            continue
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[i:])
            if isinstance(obj, dict) and 'passed' in obj:
                objects.append(obj)
        except ValueError:
            pass
    report = ROOT / '验收记录' / reports[name]
    if report.exists() and report.stat().st_mtime >= time.time() - (time.monotonic() - start) - 2:
        obj = json.loads(report.read_text())
    else:
        obj = objects[-1] if objects else {'passed': 0, 'failed': 1, 'jsErrors': None}
    (OUT / (name + '.json')).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    row = dict(suite=name, host=lane, candidateSHA256=sha, exitCode=code,
               passed=obj['passed'], failed=obj.get('failed'), jsErrors=obj.get('jsErrors'),
               seconds=round(time.monotonic()-start, 2))
    summary.append(row)
    (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print('RESULT', json.dumps(row, ensure_ascii=False), flush=True)
    if code:
        print(text[-5000:], flush=True)
assert hashlib.sha256((ROOT/'候选试玩.html').read_bytes()).hexdigest() == sha
raise SystemExit(any(r['exitCode'] or r['failed'] or r['jsErrors'] for r in summary))
