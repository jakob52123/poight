"""VA2-only sprite packing, additive to V1's mapping; no protected atlas writes."""
import hashlib
import json
from pathlib import Path

from PIL import Image


def build(base, mapping, output):
    for key, spec in json.loads((base / 'VA2/贴图映射.json').read_text()).items():
        raw = (base / 'VA2' / spec['source']).read_bytes()
        width, height = Image.open(base / 'VA2' / spec['source']).size
        mapping['effects'][key] = {
            **{k: v for k, v in spec.items() if k != 'source'},
            'width': width, 'height': height,
            'file': output('animation-va2-' + hashlib.sha256(raw).hexdigest()[:16] + '.png', raw),
        }


def runtime(root):
    return (root / '招式动画-VA2.js').read_text()


def sources(root, output):
    for name in ['招式动画-VA2.js', '招式动画/VA2素材.py', '招式动画/VA2/贴图映射.json',
                 '招式动画/VA2/来源.json']:
        raw = (root / name).read_bytes()
        suffix = '.json' if Path(name).suffix == '.json' else '.txt'
        output('animation-source-' + hashlib.sha256(raw).hexdigest()[:16] + suffix, raw)
