"""Local coordinator; browsers only via authorized Jade wrapper on 8931/8932/8933."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
label = sys.argv[1]
groups = [
    ['体型移速', '体型招式回归', '生图实战', '绿宝石', '草丛', '竞技场', '场地比例',
     '去护栏', '主角八招', '手感', '手机操作', '演示模式'],
    ['选人页', '水溅跃', '头顶血条', '草丛藏身', '平衡钩子', '打击感瞄准',
     '出招反馈', '界面方案', '跳跃', '招式第1批', '招式第2批', '招式第3批',
     '异常状态', '咬类招式'],
    ['大地图通行', '集成联动', '桥梁通行', '丰缘全图', '招式动画核心',
     '招式动画-VB1', '招式动画-VA2', '立绘', 'MX联动', 'M7联动'],
]
ports = (8931, 8932, 8933)
processes = []
sha = hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest()
for port, suites in ([] if '--collect-only' in sys.argv else zip(ports, groups)):
    log = (ROOT / f'验收记录/M7/{label}-{port}.log').open('w')
    command = ['bash', str(ROOT.parent / 'tools/远程执行.sh'), str(port), str(ROOT),
               'python', 'scripts/M7-批次.py', f'{label}-{port}', *suites]
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
    processes.append((process, log, port))
    print(' '.join(command), 'PID', process.pid, flush=True)
if processes:
    (ROOT / f'验收记录/M7/{label}-processes.json').write_text(json.dumps([
        {'port': port, 'pid': process.pid} for process, _, port in processes], indent=2) + '\n')
failed = []
for process, log, port in processes:
    code = process.wait()
    log.close()
    print(port, 'exitCode', code, flush=True)
    if code:
        failed.append([port, code])
if failed:
    raise SystemExit(str(failed))
summary = []
for port, expected in zip(ports, groups):
    directory = ROOT / f'验收记录/集成批次/{label}-{port}'
    rows = json.loads((directory / 'summary.json').read_text())
    assert [row['test'] for row in rows] == expected
    assert all(row['exitCode'] == row['failed'] == row['jsErrors'] == 0 for row in rows)
    assert (directory / 'candidate-sha256.txt').read_text().strip() == sha
    summary.extend(rows)
assert len({row['test'] for row in summary}) == len(summary)
assert hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest() == sha
out = ROOT / f'验收记录/集成批次/{label}'
out.mkdir(parents=True, exist_ok=True)
(out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
lines = [row['test'] + ' ' + json.dumps({key: row[key] for key in
         ('passed', 'failed', 'jsErrors')}, ensure_ascii=False) for row in summary]
lines.append('TOTAL ' + json.dumps({'suites': len(summary), 'passed': sum(r['passed'] for r in summary),
                                  'failed': 0, 'jsErrors': 0}, ensure_ascii=False))
text = '\n'.join(lines) + '\n'
(out / '原样摘要.txt').write_text(text)
(out / 'candidate-sha256.txt').write_text(sha + '\n')
print(text, end='', flush=True)
