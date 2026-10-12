"""No browser: syntax, new Ruff diagnostics, protected source and raster guard."""
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 'ff19573'
OUT = ROOT / '验收记录/MX联动'
OUT.mkdir(parents=True, exist_ok=True)
changed = subprocess.check_output(['git', 'diff', '--name-only', '-z', BASE], cwd=ROOT).decode().split('\0')
changed += subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
changed = sorted({p for p in changed if p})
js = [p for p in changed if p.endswith('.js')]
for name in js:
    subprocess.run(['node', '--check', name], cwd=ROOT, check=True)
ruff = str(Path.home() / '.local/bin/ruff')
python = []
for name in changed:
    if not name.endswith('.py'):
        continue
    old = subprocess.run(['git', 'show', BASE + ':' + name], cwd=ROOT,
                         capture_output=True, text=True, check=False)
    texts = [old.stdout if old.returncode == 0 else '', (ROOT / name).read_text()]
    results = []
    for text in texts:
        result = subprocess.run([ruff, 'check', '--output-format', 'json',
                                 '--stdin-filename', str(ROOT / name), '-'], input=text,
                                cwd=ROOT, capture_output=True, text=True, check=False)
        results.append(Counter((row['code'], row['message']) for row in json.loads(result.stdout)))
    added = results[1] - results[0]
    python.append({'path': name, 'baseline': sum(results[0].values()),
                   'current': sum(results[1].values()), 'added': list(added.elements())})
    assert not added, (name, added)
protected = ['体型判定.js', '体型数据.py', '游戏数据.py', '手感参数.js', '跳跃.js',
             '世界地图.js', '桥梁通行.js', '丰缘接缝.js', '招式特效/主角锚点.json']
for name in protected:
    assert (ROOT / name).read_bytes() == subprocess.check_output(
        ['git', 'show', BASE + ':' + name], cwd=ROOT), name
count, changed_assets = 0, []
reference = ROOT.parent / 'W2'
for folder in ('素材', '画面'):
    for source in (reference / folder).rglob('*'):
        if source.is_file() and source.suffix.lower() in ('.png', '.jpg', '.gif', '.webp'):
            count += 1
            target = ROOT / source.relative_to(reference)
            if not target.is_file() or source.read_bytes() != target.read_bytes():
                changed_assets.append(str(target))
assert not changed_assets, changed_assets
record = json.loads((ROOT / '招式特效/生图重做/实景预览/构建记录.json').read_text())['assets']
stone = hashlib.sha256((ROOT / record['stoneedge']['output']).read_bytes()).hexdigest()
assert stone == 'ec3849ad57d94f0a64a8b95e2f9e188051659d7eb0f5ccc2b836f6684c66ed39'
subprocess.run(['git', 'diff', '--check'], cwd=ROOT, check=True)
report = {'nodeFiles': len(js), 'nodePassed': len(js), 'pythonFiles': len(python),
          'newRuffDiagnostics': 0, 'protectedSources': len(protected),
          'originalRasterFiles': count, 'changedRasterFiles': len(changed_assets),
          'stoneedgeSHA256': stone, 'python': python}
(OUT / '静态检查.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in report.items() if k != 'python'}, ensure_ascii=False))
