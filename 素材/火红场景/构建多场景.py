"""离线重排已有 FireRed 像素。保留原草地图；不联网、不生图、不改原图。
图片、障碍、出生点、边界共同写入场景目录，不能仅换背景。
"""
from pathlib import Path
from PIL import Image, ImageOps
from collections import deque
import hashlib
import json
import math
import random

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '多场景'
OUT.mkdir(exist_ok=True)
ATLAS = Image.open(ROOT / '元瓦片.png').convert('RGBA')
OLD = json.loads((ROOT / '场景包.json').read_text())
OBJECTS = Image.open(ROOT / OLD['objects']).convert('RGBA')
WORLD = {'width': 1600, 'height': 1000}
DEFAULT_BOUNDS = {'left': 55, 'right': 1545, 'top': 77, 'bottom': 939}
used = set()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tile(n):
    used.add(n)
    return ATLAS.crop((n % 16 * 16, n // 16 * 16, (n % 16 + 1) * 16, (n // 16 + 1) * 16))


def fill_texture(im, texture):
    for y in range(0, im.height, texture.height):
        for x in range(0, im.width, texture.width):
            im.alpha_composite(texture, (x, y))


def place_rectangle(im, x, y, cols, rows, grid):
    """边、角使用原始瓦片；不画几何图来冒充生成素材。"""
    for cy in range(rows):
        for cx in range(cols):
            a = 0 if cx == 0 else 2 if cx == cols - 1 else 1
            b = 0 if cy == 0 else 2 if cy == rows - 1 else 1
            im.alpha_composite(tile(grid[b][a]), (x + cx * 16, y + cy * 16))


def grass(seed):
    rng = random.Random(seed)
    im = Image.new('RGBA', (800, 500))
    for y in range(0, 500, 16):
        for x in range(0, 800, 16):
            im.alpha_composite(tile(rng.choice([1, 1, 1, 8, 9, 0x10, 0x11, 0x13])), (x, y))
    tree = Image.open(ROOT / '树木.png').convert('RGBA')
    for x in range(-16, 816, 24):
        im.alpha_composite(tree, (x, -17))
        im.alpha_composite(tree, (x, 474))
    for y in range(0, 500, 28):
        im.alpha_composite(tree, (-16, y))
        im.alpha_composite(tree, (786, y))
    return im


def relocated(layout):
    sprites, collisions = [], []
    for index, (source_index, x, y) in enumerate(layout):
        old_s, old_c = OLD['sprites'][source_index], OLD['collisionContract'][source_index]
        sprite = dict(old_s, index=index, x=x, y=y + old_s['y'] - old_c['y'], z=y + old_c['h'])
        collision = dict(old_c, x=x, y=y)
        sprites.append(sprite)
        collisions.append(collision)
    return sprites, collisions


def free(scene, x, y, r=21):
    b = scene['bounds']
    return b['left'] <= x <= b['right'] and b['top'] <= y <= b['bottom'] and all(
        math.hypot(x - max(o['x'], min(x, o['x'] + o['w'])), y - max(o['y'], min(y, o['y'] + o['h']))) >= r
        for o in scene['collisionContract'])


def verify_scene(scene):
    assert scene['world'] == WORLD
    for spawn in scene['spawns'].values():
        assert free(scene, spawn['x'], spawn['y'], 24), (scene['id'], 'blocked spawn')
    assert len(scene['sprites']) == len(scene['collisionContract'])
    for s, c in zip(scene['sprites'], scene['collisionContract']):
        assert s['x'] == c['x'] and s['z'] == c['y'] + c['h']
        assert s['y'] <= c['y'] and abs(s['w'] * s['scale'] - c['w']) <= 1
        assert s['y'] + s['h'] * s['scale'] - s['z'] in (0, 1)
    # Both spawns connect, and there are no sealed pockets on the AI's 40px grid.
    cells = {(x, y) for x in range(40) for y in range(25) if free(scene, x * 40 + 20, y * 40 + 20)}
    nearest = lambda p: min(cells, key=lambda q: (q[0] * 40 + 20 - p['x']) ** 2 + (q[1] * 40 + 20 - p['y']) ** 2)
    start, goal = (nearest(scene['spawns'][s]) for s in ('player', 'enemy'))
    queue, seen = deque([start]), {start}
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x + dx, y + dy)
            if q in cells and q not in seen:
                seen.add(q)
                queue.append(q)
    assert goal in seen and cells == seen, (scene['id'], 'disconnected navigation')
    return {'walkableCells': len(cells), 'connectedCells': len(seen), 'spawnClearancePx': 24, 'obstacles': len(scene['collisionContract'])}


def finish(scene, ground):
    if scene['id'] != 'forest':
        path = OUT / (scene['id'] + '-底图.png')
        ground.convert('RGB').save(path, optimize=True)
        scene['ground'] = str(path.relative_to(ROOT))
    preview = ground.convert('RGBA').resize((1600, 1000), Image.Resampling.NEAREST)
    for s in sorted(scene['sprites'], key=lambda s: s['z']):
        part = OBJECTS.crop((s['sx'], s['sy'], s['sx'] + s['w'], s['sy'] + s['h']))
        preview.alpha_composite(part.resize((s['w'] * s['scale'], s['h'] * s['scale']), Image.Resampling.NEAREST), (s['x'], s['y']))
    full = OUT / (scene['id'] + '-全景.png')
    preview.save(full, optimize=True)
    thumb = OUT / (scene['id'] + '-缩略图.png')
    preview.resize((400, 250), Image.Resampling.NEAREST).save(thumb, optimize=True)
    scene['preview'] = str(thumb.relative_to(ROOT))
    scene['objects'] = OLD['objects']
    scene['groundNativeSize'] = [800, 500]
    for field in ('ground', 'objects', 'preview'):
        scene[field + 'SHA256'] = sha(ROOT / scene[field])
    scene['sourceCommit'] = OLD['sourceCommit']
    return verify_scene(scene)


forest = dict(OLD, id='forest', name='林间草地', description='原来的草地场。岩台、绿篱与树丛，适合绕掩体。', bounds=DEFAULT_BOUNDS,
              spawns={'player': {'x': 215, 'y': 280, 'a': 0}, 'enemy': {'x': 585, 'y': 280, 'a': math.pi}})
reports = {'forest': finish(forest, Image.open(ROOT / OLD['ground']))}

used.clear()
yard = grass(20261011)
# Middle plaza: use the texture center and actual stone edging, not a tinted grass image.
place_rectangle(yard, 80, 64, 40, 24, [[0x1B8, 0x1B9, 0x1BA], [0x1C8, 0x196, 0x1CA], [0x1C8, 0x196, 0x1CA]])
# Bottom edge from original top tiles, flipped as a raster (no repainting).
for x in range(40):
    n = 0x1B8 if x == 0 else 0x1BA if x == 39 else 0x1B9
    yard.alpha_composite(ImageOps.flip(tile(n)), (80 + x * 16, 64 + 23 * 16))
# Native diamond paving forms two paths; do not repeat the bottom edging on every plaza row.
stone_core = tile(0x1C9).crop((0, 0, 16, 12))
for rect in ((80, 240, 640, 32), (384, 64, 32, 384)):
    x, y, w, h = rect
    path = Image.new('RGBA', (w, h))
    fill_texture(path, stone_core)
    yard.alpha_composite(path, (x, y))
sprites, collisions = relocated([(2, 340, 240), (4, 1160, 240), (6, 340, 680), (8, 1160, 680), (1, 745, 210), (7, 735, 760)])
courtyard = {'id': 'courtyard', 'name': '石板庭院', 'description': '石板与十字步道。中路开阔，四角树坛和南北绿篱能挡招。', 'world': dict(WORLD), 'bounds': dict(DEFAULT_BOUNDS),
             'spawns': {'player': {'x': 600, 'y': 500, 'a': 0}, 'enemy': {'x': 1000, 'y': 500, 'a': math.pi}},
             'sprites': sprites, 'collisionContract': collisions, 'usedMetatiles': [f'0x{n:03X}' for n in sorted(used)],
             'notes': ['全新布局，仅重排现有原版瓦片；不是官方地点复刻。', '中心石纹和浅色步道均可行走，只有有实体外观的树坛／绿篱阻挡。']}
reports['courtyard'] = finish(courtyard, yard)

used.clear()
beach = Image.new('RGBA', (800, 500))
fill_texture(beach, tile(0x1ED))
# Continuous sand shore. Sand core is a crop from an existing native sand tile.
sand = tile(0x11D).crop((0, 0, 16, 10))
sand_area = Image.new('RGBA', (46 * 16, 27 * 16))
fill_texture(sand_area, sand)
beach.alpha_composite(sand_area, (32, 32))
for x in range(46):
    beach.alpha_composite(tile(0x10C if x == 0 else 0x10E if x == 45 else 0x10D), (32 + x * 16, 32))
    beach.alpha_composite(tile(0x11C if x == 0 else 0x11E if x == 45 else 0x11D), (32 + x * 16, 448))
for y in range(1, 26):
    beach.alpha_composite(tile(0x114), (32, 32 + y * 16))
    beach.alpha_composite(ImageOps.mirror(tile(0x114)), (752, 32 + y * 16))
sprites, collisions = relocated([(3, 360, 270), (5, 1100, 270), (0, 740, 660), (9, 1130, 735), (5, 260, 730)])
coast = {'id': 'coast', 'name': '海岸沙洲', 'description': '浅黄沙滩与海岸。绕岩台对射；海水是场外边界，不能进入。', 'world': dict(WORLD),
         'bounds': {'left': 112, 'right': 1488, 'top': 112, 'bottom': 896},
         'spawns': {'player': {'x': 600, 'y': 510, 'a': 0}, 'enemy': {'x': 1000, 'y': 510, 'a': math.pi}},
         'sprites': sprites, 'collisionContract': collisions, 'usedMetatiles': [f'0x{n:03X}' for n in sorted(used)],
         'notes': ['只复用原版沙地、海水、岸线与岩台像素；非AI生图。', '海面是静态像素底图；本轮未加入游泳、潮汐或飞行越界。', '可行走边界收在干沙上；与草地不同，碰撞、寻路与出生点随场景切换。']}
reports['coast'] = finish(coast, beach)

catalog = {'default': 'forest', 'scenes': [forest, courtyard, coast], 'sourceAtlasSHA256': sha(ROOT / '元瓦片.png'), 'sourceObjectsSHA256': sha(ROOT / OLD['objects']), 'provenance': '原始/来源.json；仅本地像素裁切、拼贴与缩略图，没有新增生成API调用。'}
(ROOT / '场景目录.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
(OUT / '构建核验.json').write_text(json.dumps({'maps': reports, 'sourceCommit': OLD['sourceCommit'], 'originalForestUnchanged': sha(ROOT / OLD['ground']) == OLD['groundSHA256'], 'paidAPICalls': 0}, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'scenes': [s['name'] for s in catalog['scenes']], 'checks': reports}, ensure_ascii=False))
