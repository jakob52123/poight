"""Only register VA1 textures; no changes to combat data or the shared effect keys."""
import hashlib
from pathlib import Path


def build_va1(base, output, mapping, data):
    # V1p has 113 converted IDs and omits moonblast. Register only this reviewed
    # visual recipe, not a combat move or an automatic Showdown impact callback.
    data['moves'].setdefault('moonblast', {
        'id': 'moonblast', 'impactMs': 0, 'durationMs': 260, 'events': [],
        'source': 'VA1 authored moon symbol; physics-driven shot recipe',
    })
    folder = base / 'VA1素材'
    for path in sorted(folder.glob('*.png')):
        raw = path.read_bytes()
        mapping['effects']['va1-' + path.stem] = {
            'file': output('animation-va1-' + hashlib.sha256(raw).hexdigest()[:16] + '.png', raw),
            'width': 32, 'height': 32, 'frames': [[0, 0, 32, 32]],
        }
    # The recoloring generator's inputs accompany the portable corresponding source too.
    for path in sorted((folder / '原版').glob('*.png')):
        raw = path.read_bytes()
        output('animation-source-va1-original-' + hashlib.sha256(raw).hexdigest()[:16] + '.png', raw)
    for path in [base / 'VA1飞行弹.js', base / '生成VA1贴图.py', Path(__file__), folder / '来源.json']:
        raw = path.read_bytes()
        output('animation-source-va1-' + hashlib.sha256(raw).hexdigest()[:16] + '.txt', raw)
