"""Single allocated wrapper/slot; preserve every failure and continue unrelated suites."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '验收记录/M8X/最终验收'
OUT.mkdir(parents=True, exist_ok=True)
artifact = hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest()
summary = []
for name in ['埋点', '首开加载', '招式动画核心', 'P6b全招', '主角八招',
             '演示模式', '选人页', '战斗音乐', '手感']:
    print('RUN ' + name, flush=True)
    try:
        result = subprocess.run([sys.executable, f'验收-{name}.py'], cwd=ROOT,
                                capture_output=True, text=True, timeout=1800, check=False)
        text = result.stdout + result.stderr
        code = result.returncode
    except subprocess.TimeoutExpired as exc:
        text = str(exc)
        code = 124
    (OUT / (name + '.log')).write_text(text)
    obj = None
    for pos, char in enumerate(text):
        if char != '{':
            continue
        try:
            candidate, _ = json.JSONDecoder().raw_decode(text[pos:])
            if isinstance(candidate, dict) and 'passed' in candidate:
                obj = candidate
                break
        except ValueError:
            pass
    row = {'test': name, 'exitCode': code, 'passed': obj['passed'] if obj else 0,
           'failed': max(obj.get('failed', 0), int(bool(code))) if obj else 1,
           'jsErrors': obj.get('jsErrors', len(obj.get('errors', []))) if obj else None}
    summary.append(row)
    if obj:
        (OUT / (name + '.json')).write_text(json.dumps(obj, ensure_ascii=False, indent=2))
    else:
        print(text[-2000:], flush=True)
    print(name + ' ' + json.dumps({k: row[k] for k in ['passed', 'failed', 'jsErrors']}, ensure_ascii=False), flush=True)
    (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
assert hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest() == artifact
(OUT / 'candidate-sha256.txt').write_text(artifact + '\n')
unknown = [r['test'] for r in summary if r['jsErrors'] is None]
print('TOTAL ' + json.dumps({'suites': len(summary), 'passed': sum(r['passed'] for r in summary),
      'failed': sum(r['failed'] for r in summary),
      'jsErrors': sum(r['jsErrors'] or 0 for r in summary), 'incomplete': unknown}, ensure_ascii=False), flush=True)
raise SystemExit(any(r['exitCode'] or r['failed'] or r['jsErrors'] is None or r['jsErrors'] for r in summary))
