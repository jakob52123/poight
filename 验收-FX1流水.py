"""Single wrapper/port/slot: baseline, rebuild, appearance, all 37 serial PERF suites."""
import hashlib
import json
import subprocess
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/FX1'
OUT.mkdir(parents=True, exist_ok=True)
stages = []
commands = []
if '--reuse-baseline' in sys.argv and not (OUT / '改前.json').exists():
    # Ship the original FX1 pre-change receipt through remote sync (reports are excluded).
    fixture = ROOT / 'tests/M8X-FX1-baseline.tar.gz'
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == (
        'b4eed70345c00c5c5ddfbead8a416a95db8ff17d7677da3ddfe83ac7a65a00e5')
    with tarfile.open(fixture) as archive:
        archive.extractall(OUT, filter='data')
if '--reuse-baseline' not in sys.argv:
    commands.append(('改前', ['验收-VA2外观.py', '--baseline']))
commands.extend([
    ('构建', ['构建完整版.py']),
    ('冷首开', ['验收-首开加载.py']),
    ('外观', ['验收-VA2外观.py']),
    ('VA2专套', ['验收-招式动画-VA2.py']),
    ('37套', ['scripts/PERF-全量.py', 'FX1-final', '--serial', '--port', '8997', '--in-process']),
])
def source_hash():
    files = [ROOT / '招式动画-VA2.js', ROOT / '招式动画/VA2素材.py',
             ROOT / '招式动画/VA2/制作贴图.py', *sorted((ROOT / '招式动画/VA2').glob('*.png'))]
    return hashlib.sha256(b''.join(p.read_bytes() for p in files)).hexdigest()


built_sources = source_hash()
if '--m9-receipts' in sys.argv:
    label = sys.argv[sys.argv.index('--m9-receipts') + 1]
    directory = ROOT / '验收记录/首开加载' / label
    proof = json.loads((ROOT / '验收记录/M9/final-inputs.json').read_text())
    current = hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest()
    assert current == proof['candidateSHA256'] == (directory / 'candidate-sha256.txt').read_text().strip()
    assert hashlib.sha256((ROOT / '候选发布清单.json').read_bytes()).hexdigest() == proof['manifestSHA256']
    assert built_sources == proof['FX1SourceSHA256']
    rows = json.loads((directory / 'summary.json').read_text())
    original = ['首开加载', '体型移速', '体型招式回归', '生图实战', '绿宝石', '草丛', '竞技场',
                '场地比例', '去护栏', '主角八招', '手感', '手机操作', '演示模式', '选人页',
                '水溅跃', '头顶血条', '草丛藏身', '平衡钩子', '打击感瞄准', '出招反馈', '界面方案',
                '跳跃', '招式第1批', '招式第2批', '招式第3批', '异常状态', '咬类招式',
                '大地图通行', '集成联动', '桥梁通行', '丰缘全图', '招式动画核心',
                '招式动画-VB1', '招式动画-VA2', '立绘', 'MX联动', 'M7联动']
    assert len(original) == 37
    by_name = {r['test']: r for r in rows}
    assert len(by_name) == len(rows) and set(original + ['VA2外观']).issubset(by_name)
    def good(name):
        r = by_name[name]
        return r['passed'] > 0 and not (r['exitCode'] or r['failed'] or r['jsErrors'])
    stages = [{'stage': '构建同SHA/源码稳定', 'exitCode': 0},
              {'stage': '冻结改前收据', 'exitCode': int(not (OUT / '改前.json').exists())},
              {'stage': '冷首开', 'exitCode': int(not good('首开加载'))},
              {'stage': '外观', 'exitCode': int(not good('VA2外观'))},
              {'stage': 'VA2专套', 'exitCode': int(not good('招式动画-VA2'))},
              {'stage': '37套', 'exitCode': int(not all(good(n) for n in original))}]
    report = {'passed': sum(not r['exitCode'] for r in stages),
              'failed': sum(bool(r['exitCode']) for r in stages), 'jsErrors': 0,
              'candidateSHA256': current, 'stages': stages,
              'receiptSource': str(directory.relative_to(ROOT)),
              'mode': 'same-SHA union receipts, no duplicate browser/build run'}
    (OUT / 'M9流水.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(bool(report['failed']))
for label, command in commands:
    print('STAGE', label, flush=True)
    start = time.monotonic()
    with (OUT / (label + '.log')).open('w') as log:
        result = subprocess.run([sys.executable, *command], cwd=ROOT,
                                stdout=log, stderr=subprocess.STDOUT, check=False)
    stages.append({'stage': label, 'exitCode': result.returncode,
                   'seconds': round(time.monotonic()-start, 2)})
    (OUT / '流水.json').write_text(json.dumps(stages, ensure_ascii=False, indent=2)+'\n')
    print(label, result.returncode, (OUT / (label + '.log')).read_text()[-5000:], flush=True)
    if result.returncode and label != '37套':
        break
check_sources = source_hash()
stages.append({'stage': 'source-stability', 'exitCode': int(check_sources != built_sources),
               'sourceSHA256': check_sources})
(OUT / '流水.json').write_text(json.dumps(stages, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(stages, ensure_ascii=False), flush=True)
raise SystemExit(any(s['exitCode'] for s in stages))
