"""No-browser source integrity, Python syntax/lint, node syntax and complete candidate manifest."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '验收记录/MOB3'
protected = ['体型判定.js', '体型数据.py', '游戏数据.py', '手感参数.js', '跳跃.js',
             '世界地图.js', '桥梁通行.js', '丰缘接缝.js', '异常状态.js']
for name in protected:
    assert (ROOT / name).read_bytes() == subprocess.check_output(['git', 'show', '3491d05:' + name], cwd=ROOT), name
subprocess.run(['node', '--check', '界面-GBA.js'], cwd=ROOT, check=True)
python_files = sorted((ROOT / 'scripts').glob('MOB3-*.py'))
for path in python_files:
    compile(path.read_text(), str(path), 'exec')
subprocess.run([str(Path.home() / '.local/bin/ruff'), 'check', *map(str, python_files)], cwd=ROOT, check=True)
record = json.loads((ROOT / '招式特效/生图重做/实景预览/构建记录.json').read_text())['assets']
stone = hashlib.sha256((ROOT / record['stoneedge']['output']).read_bytes()).hexdigest()
assert stone == 'ec3849ad57d94f0a64a8b95e2f9e188051659d7eb0f5ccc2b836f6684c66ed39'
manifest = json.loads((ROOT / '候选发布清单.json').read_text())
for name, spec in manifest['assets'].items():
    raw = (ROOT / name).read_bytes()
    assert len(raw) == spec['bytes'] and hashlib.sha256(raw).hexdigest() == spec['sha256'], name
sha = hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest()
assert sha == manifest['candidateSHA256']
frozen = json.loads((ROOT / '验收记录/M9/final-inputs.json').read_text())
original_manifest = json.dumps({'candidateSHA256': frozen['candidateSHA256'], 'assets': manifest['assets']}, ensure_ascii=False, indent=2) + '\n'
assert hashlib.sha256(original_manifest.encode()).hexdigest() == frozen['manifestSHA256']
subprocess.run(['git', 'diff', '--check'], cwd=ROOT, check=True)
changes = subprocess.check_output(['git', 'diff', '--name-only', '-z', '3491d05', '--', '*.js', '*.css', '页面.html', '构建完整版.py', '游戏数据.py'], cwd=ROOT).decode().strip('\0').split('\0')
assert sorted(changes) == ['界面-GBA.css', '界面-GBA.js'], changes
baseline_changes = subprocess.check_output(['git', 'diff', '--name-only', '3491d05', '860bf85', '--', '*.js', '*.css', '*.html', '构建完整版.py', '游戏数据.py'], cwd=ROOT)
assert not baseline_changes
report = {'passed': 17 + len(python_files) + len(manifest['assets']), 'failed': 0, 'nodePassed': 1,
          'candidateSHA256': sha, 'protectedSources': len(protected), 'pythonFiles': len(python_files),
          'productionChanges': changes, 'stoneedgeSHA256': stone, 'manifestAssets': len(manifest['assets']),
          'allAssetBytesEqual3491d05': True, 'originalManifestSHA256': frozen['manifestSHA256'],
          'baselineCandidateSHA256': hashlib.sha256((OUT / '改前/候选试玩.html').read_bytes()).hexdigest(),
          'baselineProductionSourcesEqual': '3491d05 == 860bf85 (JS/CSS/HTML/builder/game data)'}
(OUT / '静态检查.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print('STATIC_SUMMARY ' + json.dumps(report, ensure_ascii=False), flush=True)
