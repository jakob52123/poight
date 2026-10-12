"""把已核验像素动作内嵌成一个HTML；无网络、无框架、无npm依赖。"""
from pathlib import Path
from PIL import Image
import base64
import hashlib
import json
import math
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
ART = ROOT / '素材/动作优化'
meta = json.loads((ART / '动作包.json').read_text())
assert meta['directions'] == ['S', 'SW', 'W', 'NW', 'N', 'NE', 'E', 'SE']
assert set(meta['actions']) == {'idle', 'walk', 'shoot', 'melee', 'hurt', 'dash'}
allowed = ['frameWidth', 'frameHeight', 'frames', 'rows', 'anchorX', 'anchorY', 'durations', 'hitFrame', 'hitTime', 'totalDuration']
pack = {'directions': meta['directions'], 'actions': {}}
proof = []
for name, a in meta['actions'].items():
    path = (ART / a['file']).resolve()
    assert path.parent == ART.resolve() and path.suffix == '.png'
    data = path.read_bytes()
    assert len(data) < 300_000
    with Image.open(path) as im:
        im.load()
        assert im.mode == 'RGBA'
        assert im.size == (a['frameWidth'] * a['frames'], a['frameHeight'] * a['rows'])
        assert im.getchannel('A').getextrema() == (0, 255)
        assert a['rows'] in (1, 8) and 1 < a['frames'] <= 32
        assert 0 < a['anchorX'] < a['frameWidth'] <= 128
        assert 0 < a['anchorY'] < a['frameHeight'] <= 128
        poses = []
        for row in range(a['rows']):
            hashes = set()
            for frame in range(a['frames']):
                tile = im.crop((frame*a['frameWidth'],row*a['frameHeight'],(frame+1)*a['frameWidth'],(row+1)*a['frameHeight']))
                box = tile.getbbox()
                assert box and box[0] > 0 and box[1] > 0 and box[2] < a['frameWidth'] and box[3] < a['frameHeight']
                hashes.add(hashlib.sha256(tile.crop(box).tobytes()).hexdigest())
            assert len(hashes) > 1, (name, row, 'static pose only')
            poses.append(len(hashes))
    assert len(a['durations']) == a['frames']
    assert all(math.isfinite(v) and v > 0 for v in a['durations'])
    assert abs(sum(a['durations']) - a['totalDuration']) < 1e-9
    if a['hitFrame'] is not None:
        assert 0 <= a['hitFrame'] < a['frames']
        assert abs(sum(a['durations'][:a['hitFrame']]) - a['hitTime']) < 1e-9
    item = {key: a[key] for key in allowed}
    item['src'] = 'data:image/png;base64,' + base64.b64encode(data).decode()
    pack['actions'][name] = item
    proof.append({'action': name, 'source': a['sourceAnimation'], 'rows': a['rows'], 'frames': a['frames'], 'distinct_poses_by_row': poses, 'png_bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
template = (ROOT / '试玩模板.html').read_text()
assert template.count('__ANIMATION_PACKAGE__') == 1
html = template.replace('__ANIMATION_PACKAGE__', json.dumps(pack, ensure_ascii=True, separators=(',', ':')))
assert '__ANIMATION_PACKAGE__' not in html
script = re.search(r'<script>(.*?)</script>', html, re.S)[1]
with tempfile.NamedTemporaryFile(mode='w', suffix='.js') as f:
    f.write(script)
    f.flush()
    subprocess.run(['node', '--check', f.name], check=True)
path = ROOT / '候选试玩.html'
path.write_text(html)
result = {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'actions': proof, 'external_runtime_requests': 0}
(ROOT / '构建核验.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'bytes': result['bytes'], 'actions': len(proof), 'distinct_poses': {p['action']: p['distinct_poses_by_row'] for p in proof}}, ensure_ascii=False))
