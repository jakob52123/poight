"""LOCAL ONLY: build all arena B variants with the unchanged real builder and node check."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from VC预构建加载 import catalog_key, inputs

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tests/VC预构建'
OUT.mkdir(exist_ok=True)
path = ROOT / '素材/竞技场/竞技场目录.json'
original = path.read_bytes()
catalog = json.loads(original)
variants = {}


def build():
    key = catalog_key(ROOT)
    folder = OUT / key
    folder.mkdir(exist_ok=True)
    with (folder / 'build.log').open('w') as log:
        subprocess.run([sys.executable, '构建完整版.py'], cwd=ROOT, stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    files = {}
    for name in ['候选试玩.html', '候选发布清单.json']:
        raw = (ROOT / name).read_bytes()
        (folder / name).write_bytes(raw)
        files[name] = hashlib.sha256(raw).hexdigest()
    variants[key] = files


try:
    for scene in catalog['scenes']:
        changed = json.loads(original)
        next(s for s in changed['scenes'] if s['id'] == scene['id'])['variant'] = 'B'
        path.write_text(json.dumps(changed, ensure_ascii=False, indent=2) + '\n')
        build()
finally:
    path.write_bytes(original)
    build()
(OUT / '来源.json').write_text(json.dumps({'inputs': inputs(ROOT), 'variants': variants},
                                      ensure_ascii=False, indent=2) + '\n')
print('Local node-checked arena builds:', len(variants))
