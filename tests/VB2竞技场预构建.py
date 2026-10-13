"""Local-only arena variants for remote browser acceptance (real builder + node)."""
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / '素材/竞技场/竞技场目录.json'
original = CATALOG.read_bytes()
index = {'inputs': {}, 'builds': {}}
files = {}
try:
    scenes = json.loads(original)['scenes']
    variants = [('default', original)]
    for scene in scenes:
        if not scene.get('enabled', True):
            continue
        changed = json.loads(original)
        next(s for s in changed['scenes'] if s['id'] == scene['id'])['variant'] = 'B'
        variants.append((scene['id'] + '-B',
                         (json.dumps(changed, ensure_ascii=False, indent=2) + '\n').encode()))
    for label, catalog in variants:
        CATALOG.write_bytes(catalog)
        subprocess.run([sys.executable, '构建完整版.py'], cwd=ROOT,
                       stdout=subprocess.DEVNULL, check=True)
        key = hashlib.sha256(catalog).hexdigest()
        index['builds'][key] = {}
        for name in ['候选试玩.html', '候选发布清单.json']:
            data = (ROOT / name).read_bytes()
            archive_name = label + '/' + name
            files[archive_name] = data
            index['builds'][key][name] = {
                'file': archive_name, 'sha256': hashlib.sha256(data).hexdigest(),
            }
finally:
    CATALOG.write_bytes(original)
    subprocess.run([sys.executable, '构建完整版.py'], cwd=ROOT,
                   stdout=subprocess.DEVNULL, check=True)
# Catch stale builds after any JS/runtime/packager change; fixtures are not a lint bypass.
inputs = [*ROOT.glob('*.js'), ROOT / '构建完整版.py', ROOT / '游戏数据.py',
          ROOT / '体型数据.py', ROOT / '空中判定.py', ROOT / '构建竞技场.py',
          *ROOT.glob('招式动画/*.py'), *ROOT.glob('招式特效/*.py')]
index['inputs'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(inputs)}
files['index.json'] = (json.dumps(index, ensure_ascii=False, indent=2) + '\n').encode()
with zipfile.ZipFile(ROOT / 'tests/VB2竞技场预构建.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    for name, data in files.items():
        archive.writestr(name, data)
print(f'LOCAL ARENA BUILDS {len(variants)}; real builder/node checks passed; default restored')
