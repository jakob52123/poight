"""R200 incremental flight packs. Preserve all original eight packs byte-for-byte.
Native airborne/wing poses, SpriteCollab green body markers and directional reorder.
Doduo/Dodrio have no wings: native Hop aerial poses, explicitly not flapping flight.
"""
import hashlib
import json
import math
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
LIB = HERE.parent
ROOT = LIB.parents[1]
OUT = ROOT / '验收记录/R200/飞行'
OUT.mkdir(parents=True, exist_ok=True)
ORDER = [0, 7, 6, 5, 4, 3, 2, 1]
# Per-species pose choices reviewed in source contact sheets, not grounded Walk raised in Y.
CHOICES = {
    12: ('Walk', list(range(12)), '原生空中振翅'),
    16: ('FlapAround', [5, 6, 7, 8], '原生振翅段'),
    17: ('FlapAround', [5, 6, 7, 8], '原生振翅段'),
    18: ('FlapAround', [5, 6, 7, 8], '原生振翅段'),
    22: ('Hover', [4, 5, 6, 7], '原生悬停振翅段'),
    41: ('Walk', list(range(8)), '原生蝙蝠空中振翅'),
    42: ('Walk', list(range(8)), '原生蝙蝠空中振翅'),
    83: ('Hop', [3, 4, 5, 6], '原生腾空姿态重编排，非专用飞行循环'),
    84: ('Hop', [3, 4, 5, 6], '无翼：原生腾空姿态重编排，不宣称振翅'),
    85: ('Hop', [3, 4, 5, 6], '无翼：原生腾空姿态重编排，不宣称振翅'),
    142: ('Hover', [4, 5, 6, 7], '原生悬停翼姿'),
    227: ('Hop', [3, 4, 5, 6], '原生腾空翼姿重编排，非专用飞行循环'),
    249: ('Hover', [3, 4, 5, 6], '原生悬停翼姿'),
    250: ('Hover', [5, 6, 7, 8, 9], '原生悬停振翅段'),
    373: ('Hop', [3, 4, 5, 6], '原生腾空翼姿重编排，非专用飞行循环'),
    384: ('Walk', list(range(12)), '无翼：原生空中蜿蜒'),
}
receipts = []


def rawfile(n, name, suffix):
    path = LIB / f'原始/{n:04}/{name}-{suffix}.png'
    url = f'https://raw.githubusercontent.com/PMDCollab/SpriteCollab/master/sprite/{n:04}/{name}-{suffix}.png'
    if not path.exists():
        subprocess.run(['curl', '-fLsS', '--retry', '2', '--max-time', '60', url, '-o', str(path)], check=True)
    with Image.open(path) as im:
        im.verify()
    receipts.append(dict(id=n, url=url, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    return Image.open(path).convert('RGBA')


def dims(n, name):
    anim = next(a for a in ET.parse(LIB / f'原始/{n:04}/AnimData.xml').getroot().findall('.//Anim') if a.findtext('Name') == name)
    return int(anim.findtext('FrameWidth')), int(anim.findtext('FrameHeight'))


def marker(tile, body=True):
    matches = [(x, y) for y in range(tile.height) for x in range(tile.width)
               if (tile.getpixel((x, y))[1] == 255 and tile.getpixel((x, y))[3] == 255
                   if body else tile.getpixel((x, y)) == (255, 255, 255, 255))]
    assert len(matches) == 1, matches
    return matches[0]


def contact(n, im, fw, fh, frames, label):
    sheet = Image.new('RGBA', (fw * len(frames), (fh + 16) * 8), '#b5c3c8')
    draw = ImageDraw.Draw(sheet)
    for row in range(8):
        directions = ['S', 'SE', 'E', 'NE', 'N', 'NW', 'W', 'SW'] if label.startswith('source-') else ['S', 'SW', 'W', 'NW', 'N', 'NE', 'E', 'SE']
        draw.text((0, row * (fh + 16)), f'{n:04} {label} row:{row} {directions[row]}', fill='black')
        for col, frame in enumerate(frames):
            tile = im.crop((frame * fw, row * fh, (frame + 1) * fw, (row + 1) * fh))
            sheet.alpha_composite(tile, (col * fw, row * (fh + 16) + 16))
    sheet.convert('RGB').save(OUT / f'{n:04}-{label}.png')


packs = json.loads((HERE / '飞行包.json').read_text())
for n, (name, frames, note) in CHOICES.items():
    fw, fh = dims(n, name)
    im, off = rawfile(n, name, 'Anim'), rawfile(n, name, 'Offsets')
    assert im.size == off.size and im.height == fh * 8
    contact(n, im, fw, fh, list(range(im.width // fw)), 'source-' + name)
    cells, bounds, unique = [], [], []
    for row in ORDER:
        poses = set()
        for frame in frames:
            box = (frame * fw, row * fh, (frame + 1) * fw, (row + 1) * fh)
            tile = im.crop(box)
            x, y = marker(off.crop(box))
            b = tile.getbbox()
            assert b
            bounds.append((b[0]-x, b[1]-y, b[2]-x, b[3]-y))
            cells.append((tile, x, y))
            poses.add(hashlib.sha256(tile.crop(b).tobytes()).hexdigest())
        unique.append(len(poses))
    assert min(unique) >= 2, (n, unique)
    lx, ly = min(b[0] for b in bounds), min(b[1] for b in bounds)
    rx, ry = max(b[2] for b in bounds), max(b[3] for b in bounds)
    cw, ch = math.ceil((rx-lx+4)/2)*2, math.ceil((ry-ly+4)/2)*2
    ax, ay = 2-lx, 2-ly
    atlas = Image.new('RGBA', (cw*len(frames), ch*8))
    for i, (tile, x, y) in enumerate(cells):
        cell = Image.new('RGBA', (cw, ch))
        cell.paste(tile, (ax-x, ay-y))
        assert sum(v > 0 for v in cell.getchannel('A').get_flattened_data()) == sum(v > 0 for v in tile.getchannel('A').get_flattened_data())
        b = cell.getbbox()
        assert 0 < b[0] < b[2] < cw and 0 < b[1] < b[3] < ch
        atlas.paste(cell, (i % len(frames)*cw, i // len(frames)*ch))
    path = HERE / f'{n:04}-Air.png'
    atlas.save(path, optimize=True)
    contact(n, atlas, cw, ch, list(range(len(frames))), 'Air')
    c = json.loads((LIB / f'{n:04}/角色.json').read_text())
    offsets = {}
    for role in ['shoot', 'melee', 'hurt']:
        old = c['art'][role]
        action = old['sourceAnimation']
        w, h = dims(n, action)
        marks, shadow = rawfile(n, action, 'Offsets'), rawfile(n, action, 'Shadow')
        values = []
        for row in ORDER if old['rows'] == 8 else [0]:
            rx, ry = marker(shadow.crop((0, row*h, w, (row+1)*h)), body=False)
            line = []
            for frame in range(old['frames']):
                gx, gy = marker(marks.crop((frame*w, row*h, (frame+1)*w, (row+1)*h)))
                line.append([gx-rx, gy-ry])
            values.append(line)
        offsets[role] = values
    durations = [.10 if n in [12, 41, 42] else .14] * len(frames)
    packs[str(n)] = dict(art=dict(file=str(path.relative_to(LIB)), frameWidth=cw, frameHeight=ch,
        frames=len(frames), rows=8, anchorX=ax, anchorY=ay, durations=durations,
        totalDuration=sum(durations), hitFrame=None, hitTime=None, sourceAnimation='Air-'+name, roleFallback=False),
        audit=dict(rows=8, frames=len(frames), distinctPoses=unique, pixelCountPreserved=True,
                   clippedFrames=0, sha256=hashlib.sha256(path.read_bytes()).hexdigest()),
        sourceAnimation=name, sourceFrames=frames, flightHeight=56 if n == 384 else 48,
        method=note+'；逐帧Offsets躯干锚点对齐，移除跳跃轨迹', roles=['idle', 'walk', 'dash'], bodyOffsets=offsets)
    print('flight', n, unique, flush=True)
assert len(packs) == 24
for ident, pack in packs.items():
    if int(ident) not in CHOICES:
        art = pack['art']
        contact(int(ident), Image.open(LIB / art['file']).convert('RGBA'),
                art['frameWidth'], art['frameHeight'], list(range(art['frames'])), 'Air')
(HERE / '飞行包.json').write_text(json.dumps(packs, ensure_ascii=False, indent=2)+'\n')
(HERE / 'R200-动作来源.json').write_text(json.dumps(receipts, ensure_ascii=False, indent=2)+'\n')
print('airborne packs', len(packs))
