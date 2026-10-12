"""Local coordinator: only shared remote wrappers may launch browsers."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
label = sys.argv[1]
groups = [
    ['体型移速', '体型招式回归', '生图实战', '绿宝石', '草丛',
     '场地比例', '竞技场', '手感', '手机操作'],
    ['主角八招', '招式第1批', '招式第2批', '招式第3批', '水溅跃',
     '平衡钩子', '打击感瞄准', '头顶血条'],
    ['选人页', '草丛藏身', '大地图通行', '集成联动', '出招反馈',
     '界面方案', '跳跃', '桥梁通行', '丰缘全图'],
]
if '--demo' in sys.argv:
    groups[1] += ['演示模式', 'MX联动']
processes = []
for port, suites in ([] if '--collect-only' in sys.argv else zip((8923, 8924, 8925), groups)):
    log = (ROOT / f'验收记录/{label}-{port}.log').open('w')
    command = ['bash', str(ROOT.parent / 'tools/远程执行.sh'), str(port), str(ROOT),
               'python', 'scripts/MX-远程批次.py', f'{label}-{port}', *suites]
    if port == 8925:
        command.append('--performance')
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
    processes.append((process, log, port))
    print(' '.join(command), 'PID', process.pid, flush=True)
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
for port, expected in zip((8923, 8924, 8925), groups):
    rows = json.loads((ROOT / f'验收记录/集成批次/{label}-{port}/summary.json').read_text())
    assert [row['test'] for row in rows] == expected
    assert all(row['exitCode'] == row['failed'] == row['jsErrors'] == 0 for row in rows)
    summary.extend(rows)
assert len({row['test'] for row in summary}) == len(summary)
total = {'suites': len(summary), 'passed': sum(row['passed'] for row in summary),
         'failed': sum(row['failed'] for row in summary),
         'jsErrors': sum(row['jsErrors'] for row in summary)}
out = ROOT / f'验收记录/集成批次/{label}'
out.mkdir(parents=True, exist_ok=True)
(out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
lines = [row['test'] + ' ' + json.dumps({key: row[key] for key in
         ('passed', 'failed', 'jsErrors')}, ensure_ascii=False) for row in summary]
lines.append('TOTAL ' + json.dumps(total, ensure_ascii=False))
text = '\n'.join(lines) + '\n'
(out / '原样摘要.txt').write_text(text)
(out / 'candidate-sha256.txt').write_text(hashlib.sha256(
    (ROOT / '候选试玩.html').read_bytes()).hexdigest() + '\n')
print(text, end='', flush=True)
