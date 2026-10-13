"""Load hash-verified local builder outputs on the browser-only remote host."""
import hashlib
import json
import shutil
from pathlib import Path


def catalog_key(root):
    catalog = json.loads((root / '素材/竞技场/竞技场目录.json').read_text())
    return hashlib.sha256(json.dumps(catalog, sort_keys=True).encode()).hexdigest()


def inputs(root):
    paths = [p for pattern in ['*.js', '*.py', '*.css', '*模板.html', '页面.html']
             for p in root.glob(pattern)]
    paths += list((root / '招式动画').glob('*.py'))
    paths += list((root / '素材/竞技场').glob('*.png'))
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(set(paths))}


def restore(root):
    archive = root / 'tests/VC预构建'
    receipt = json.loads((archive / '来源.json').read_text())
    assert inputs(root) == receipt['inputs'], 'Prebuilt candidate source drift'
    entry = receipt['variants'][catalog_key(root)]
    for name, sha in entry.items():
        source = archive / catalog_key(root) / name
        assert hashlib.sha256(source.read_bytes()).hexdigest() == sha, name
        shutil.copyfile(source, root / name)
    print('Local node-checked arena variant restored:', catalog_key(root), flush=True)


if __name__ == '__main__':
    restore(Path(__file__).resolve().parents[1])
