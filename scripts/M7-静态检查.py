"""Local, no browser: changed-file syntax/lint and immutable combat/art guards."""
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = '53d1940'
OUT = ROOT / '验收记录/M7'
OUT.mkdir(parents=True, exist_ok=True)
changed = subprocess.check_output(['git', 'diff', '--name-only', '-z', BASE], cwd=ROOT).decode().split('\0')
changed += subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
changed = sorted({p for p in changed if p and (ROOT / p).is_file()})
js = [p for p in changed if p.endswith('.js')]
for name in js:
    subprocess.run(['node', '--check', name], cwd=ROOT, check=True)
python = []
for name in changed:
    if not name.endswith('.py'):
        continue
    old = subprocess.run(['git', 'show', 'base:' + name], cwd=ROOT,
                         capture_output=True, text=True, check=False)
    results = []
    for text in [old.stdout if old.returncode == 0 else '', (ROOT / name).read_text()]:
        result = subprocess.run([str(Path.home() / '.local/bin/ruff'), 'check', '--output-format', 'json',
                                 '--stdin-filename', str(ROOT / name), '-'], input=text,
                                cwd=ROOT, capture_output=True, text=True, check=False)
        results.append(Counter((row['code'], row['message']) for row in json.loads(result.stdout)))
    added = results[1] - results[0]
    python.append({'path': name, 'baseline': sum(results[0].values()),
                   'current': sum(results[1].values()), 'added': list(added.elements())})
    assert not added, (name, added)
protected = ['体型判定.js', '体型数据.py', '游戏数据.py', '手感参数.js', '跳跃.js',
             '世界地图.js', '桥梁通行.js', '丰缘接缝.js', '异常状态.js',
             '招式动画引擎.js', '招式动画接入.js', '主角招式外观.js']
for name in protected:
    assert (ROOT / name).read_bytes() == subprocess.check_output(
        ['git', 'show', BASE + ':' + name], cwd=ROOT), name
count = 0
for folder in ('素材/角色库', '素材/绿宝石场景', '素材/火红场景', '素材/竞技场'):
    for source in (ROOT.parent / 'M' / folder).rglob('*'):
        if source.is_file() and source.suffix.lower() in ('.png', '.jpg', '.gif', '.webp'):
            target = ROOT / source.relative_to(ROOT.parent / 'M')
            assert target.is_file() and source.read_bytes() == target.read_bytes(), target
            count += 1
record = json.loads((ROOT / '招式特效/生图重做/实景预览/构建记录.json').read_text())['assets']
stone = hashlib.sha256((ROOT / record['stoneedge']['output']).read_bytes()).hexdigest()
assert stone == 'ec3849ad57d94f0a64a8b95e2f9e188051659d7eb0f5ccc2b836f6684c66ed39'
subprocess.run(['git', 'diff', '--check'], cwd=ROOT, check=True)
report = {'nodeFiles': len(js), 'nodePassed': len(js), 'pythonFiles': len(python),
          'newRuffDiagnostics': 0, 'protectedSources': len(protected),
          'originalRasterFiles': count, 'changedRasterFiles': 0,
          'stoneedgeSHA256': stone, 'python': python}
(OUT / '静态检查.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in report.items() if k != 'python'}, ensure_ascii=False))
