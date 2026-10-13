"""Local coordinator: the PERF contract explicitly authorizes three Jade lanes."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
label = sys.argv[1]
# FX1 has one assigned port and must not open parallel browsers or PERF-owned ports.
in_process = '--in-process' in sys.argv
serial = '--serial' in sys.argv or in_process
serial_port = int(sys.argv[sys.argv.index('--port') + 1]) if '--port' in sys.argv else 8997
groups = [
    ['首开加载', '体型移速', '体型招式回归', '生图实战', '绿宝石', '草丛', '竞技场',
     '场地比例', '去护栏', '主角八招', '手感', '手机操作', '演示模式'],
    ['选人页', '水溅跃', '头顶血条', '草丛藏身', '平衡钩子', '打击感瞄准',
     '出招反馈', '界面方案', '跳跃', '招式第1批', '招式第2批', '招式第3批',
     '异常状态', '咬类招式'],
    ['大地图通行', '集成联动', '桥梁通行', '丰缘全图', '招式动画核心',
     '招式动画-VB1', '招式动画-VA2', '立绘', 'MX联动', 'M7联动'],
]
# M9 is the union, not duplicate executions of nested branch pipelines.
if '--with-m9' in sys.argv:
    # VA1's full gate verifies current-source GIF fingerprints; never reuse upstream movies.
    os.environ['POIGHT_VA1_CAPTURE'] = '1'
    groups[0] += ['界面GBA', '招式动画-VA1', '战斗音乐', '埋点']
    groups[1] += ['招式动画-VB2', '招式动画-VC', 'B2平衡', 'M8联动']
    groups[2] += ['P6b全招', '爆点空心', 'P6b离线', 'VA2外观']
expected_count = sum(map(len, groups)) + int('--with-gba' in sys.argv)
# UI branches can reuse the same 37-suite inventory on their own single allotted lane.
ports = tuple(int(p) for p in os.environ.get('POIGHT_PERF_PORTS', '8961,8962,8963').split(','))
if len(ports) == 1:
    groups = [[name for group in groups for name in group]]
assert len(ports) == len(groups)
if '--with-gba' in sys.argv:
    groups[0].insert(0, '界面GBA')
out = ROOT / '验收记录/首开加载' / label
out.mkdir(parents=True, exist_ok=True)
sha = hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest()
lane_root = Path(os.environ['POIGHT_PERF_LANES']) if os.environ.get('POIGHT_PERF_LANES') else None
processes = []
# EVT: run inside the authorized wrapper, serially on its one allocated port.
if '--serial' in sys.argv:
    for port, suites in zip(ports, groups):
        command = [sys.executable, 'scripts/M7-批次.py', f'{label}-{port}',
                   '--keep-going', *suites]
        with (out / f'{port}.log').open('w') as log:
            code = subprocess.run(command, cwd=ROOT, stdout=log,
                                  stderr=subprocess.STDOUT, check=False).returncode
        print('serial group', port, 'exitCode', code, flush=True)
for port, suites in ([] if '--collect-only' in sys.argv or '--serial' in sys.argv else zip(ports, groups)):
    log = (out / f'{port}.log').open('w')
    work = lane_root / str(port) / 'M9' if lane_root else ROOT
    command = ['bash', str(ROOT.parent / 'tools/远程执行.sh'),
               str(serial_port if serial else port), str(work),
               'python', 'scripts/M7-批次.py', f'{label}-{port}', '--keep-going', *suites]
    if in_process:
        command = [sys.executable, 'scripts/M7-批次.py', f'{label}-{port}',
                   '--keep-going', *suites]
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
    processes.append((process, log, port))
    print(' '.join(command), 'PID', process.pid, flush=True)
    if serial:
        code = process.wait()
        print(port, 'serial exitCode', code, flush=True)
(out / 'processes.json').write_text(json.dumps([
    {'port': port, 'pid': process.pid} for process, _, port in processes], indent=2))
for process, log, port in processes:
    code = process.wait()
    log.close()
    print(port, 'exitCode', code, flush=True)
rows = []
for port, expected in zip(ports, groups):
    work = lane_root / str(port) / 'M9' if lane_root else ROOT
    if lane_root:
        info = json.loads((lane_root / 'lane-info.json').read_text())
        assert hashlib.sha256((work / '候选试玩.html').read_bytes()).hexdigest() == sha
        # Only newly produced evidence; never overwrite another lane with stale copied reports.
        for path in (work / '验收记录').rglob('*'):
            if path.is_file() and path.stat().st_mtime_ns > info[str(port)]['readyNs']:
                dest = ROOT / path.relative_to(work)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest)
    directory = work / f'验收记录/集成批次/{label}-{port}'
    batch = json.loads((directory / 'summary.json').read_text())
    assert [r['test'] for r in batch] == expected, (port, batch)
    assert (directory / 'candidate-sha256.txt').read_text().strip() == sha
    rows.extend(batch)
assert len(rows) == len({r['test'] for r in rows}) == expected_count
assert hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest() == sha
(out / 'summary.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2))
lines = [r['test'] + ' ' + json.dumps({k: r[k] for k in ('passed', 'failed', 'jsErrors')},
                                    ensure_ascii=False) for r in rows]
total = {'suites': len(rows), 'passed': sum(r['passed'] for r in rows),
         'failed': sum(r['failed'] for r in rows), 'jsErrors': sum(r['jsErrors'] for r in rows)}
lines.append('TOTAL ' + json.dumps(total))
text = '\n'.join(lines) + '\n'
(out / '原样摘要.txt').write_text(text)
(out / 'candidate-sha256.txt').write_text(sha + '\n')
print(text, end='', flush=True)
# Report raw failures; known poison contrast is not silently relabelled a pass.
raise SystemExit(bool(total['failed'] or total['jsErrors']))
