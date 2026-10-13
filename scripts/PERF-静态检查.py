"""Local-only syntax/lint, manifest and immutable asset checks."""
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '验收记录/首开加载'
OUT.mkdir(parents=True, exist_ok=True)
changed = subprocess.check_output(
    ['git', 'diff', '--name-only', '-z', '2ba2ee4'], cwd=ROOT).decode().split('\0')
changed += subprocess.check_output(
    ['git', 'ls-files', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
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
        run = subprocess.run([str(Path.home() / '.local/bin/ruff'), 'check', '--output-format',
                              'json', '--stdin-filename', str(ROOT / name), '-'],
                             input=text, cwd=ROOT, capture_output=True, text=True, check=False)
        results.append(Counter((r['code'], r['message']) for r in json.loads(run.stdout)))
    added = results[1] - results[0]
    python.append({'path': name, 'baseline': sum(results[0].values()),
                   'current': sum(results[1].values()), 'added': list(added.elements())})
    assert not added, (name, added)
protected = ['体型判定.js', '体型数据.py', '游戏数据.py', '手感参数.js', '跳跃.js',
             '世界地图.js', '桥梁通行.js', '丰缘接缝.js', '主角招式外观.js',
             '招式第3批.js', '招式动画-VA2.js', '招式动画近身VB1.js']
for name in protected:
    assert (ROOT / name).read_bytes() == subprocess.check_output(
        ['git', 'show', '2ba2ee4:' + name], cwd=ROOT), name
changed_rasters = [p for p in changed if Path(p).suffix.lower() in ('.png', '.jpg', '.gif', '.webp')
                   and p.startswith(('素材/', '招式特效/'))]
assert not changed_rasters, changed_rasters
record = json.loads((ROOT / '招式特效/生图重做/实景预览/构建记录.json').read_text())['assets']
stone = hashlib.sha256((ROOT / record['stoneedge']['output']).read_bytes()).hexdigest()
assert stone == 'ec3849ad57d94f0a64a8b95e2f9e188051659d7eb0f5ccc2b836f6684c66ed39'
manifest = json.loads((ROOT / '候选发布清单.json').read_text())
for name, spec in manifest['assets'].items():
    assert Path(name).suffix in {'.png', '.html', '.gz', '.txt', '.json', '.ico', '.webmanifest'}, name
    raw = (ROOT / name).read_bytes()
    assert len(raw) == spec['bytes'] and hashlib.sha256(raw).hexdigest() == spec['sha256'], name
html = (ROOT / '候选试玩.html').read_bytes()
assert hashlib.sha256(html).hexdigest() == manifest['candidateSHA256']
subprocess.run(['git', 'diff', '--check'], cwd=ROOT, check=True)
report = {'nodeFiles': len(js), 'nodePassed': len(js), 'pythonFiles': len(python),
          'newRuffDiagnostics': 0, 'protectedSources': len(protected),
          'changedRasterFiles': len(changed_rasters), 'stoneedgeSHA256': stone,
          'manifestAssets': len(manifest['assets']),
          'manifestAssetBytes': sum(a['bytes'] for a in manifest['assets'].values()),
          'releaseFilesIncludingHTML': 1 + len(manifest['assets']),
          'releaseBytesIncludingHTML': len(html) + sum(a['bytes'] for a in manifest['assets'].values()),
          'python': python}
(OUT / '静态检查.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in report.items() if k != 'python'}, ensure_ascii=False))
