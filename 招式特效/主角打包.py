"""Shared atlas hooks: R2 opt-ins plus immutable T5 hero replacement slots."""
import json

from 招式特效.第2批参数 import finish as finish_ranged
from 招式特效.第2批参数 import prepare as prepare_ranged
from 游戏数据 import HERO_MOVES


def pack_frames(image, output, anchor='center'):
    """Shared 2x2 -> vertical RGBA atlas; crop/resample only, no drawn pixels."""
    from PIL import Image
    im = image.convert('RGBA')
    if im.getchannel('A').getextrema()[0] == 255:
        raise ValueError('Generated artwork must have real alpha; do not fake a background')
    w, h = im.size
    cells = [im.crop((x*w//2, y*h//2, (x+1)*w//2, (y+1)*h//2))
             for y in range(2) for x in range(2)]
    boxes = [c.getchannel('A').point(lambda v: 255 if v >= 80 else 0).getbbox() for c in cells]
    if not all(boxes):
        raise ValueError('Missing animation frame')
    box = (min(b[0] for b in boxes), min(b[1] for b in boxes),
           max(b[2] for b in boxes), max(b[3] for b in boxes))
    fw, fh = box[2]-box[0], box[3]-box[1]
    factor = min(1, 384/max(fw, fh))
    dw, dh = max(1, round(fw*factor)), max(1, round(fh*factor))
    sheet = Image.new('RGBA', (dw, dh*4))
    for i, cell in enumerate(cells):
        sheet.paste(cell.crop(box).resize((dw, dh), Image.Resampling.NEAREST), (0, i*dh))
    sheet.save(output, optimize=True)
    return {'frameSize': [dw, dh], 'anchorPx': [0 if anchor == 'left' else dw/2, dh/2],
            'method': 'union alpha>=80 bounds / nearest resize / 4 vertical frames'}


def prepare(root, record, specs):
    prepare_ranged(root, record, specs)
    for mid in ('thunderbolt', 'thunder'):
        folder = root / '招式特效/主角八招' / mid
        receipt = json.loads((folder / '来源.json').read_text())['processing']
        record['assets'][mid] = {
            'output': str((folder / (mid + '-动画.png')).relative_to(root)),
            'outputSHA256': receipt['outputSHA256'],
        }
        if mid == 'thunder':
            specs[mid] = {'mode': 'fall', 'width': 100, 'height': 180, 'reach': 120, 'caster': 25}
        specs[mid].update(zip(('fw', 'fh'), receipt['frameSize']))
        specs[mid].update(zip(('ax', 'ay'), receipt['anchorPx']))


def finish(mid, drawing, runtime):
    finish_ranged(mid, drawing, runtime)
    if mid not in HERO_MOVES:
        return
    runtime.update(HERO_MOVES[mid])
    drawing['hero'] = True
    if mid == 'thunderbolt':
        drawing.update(mode='stream', height=72)
    if mid == 'dragonclaw':
        drawing.update(width=24, height=22)
    if mid == 'irontail':
        drawing.update(width=28, height=18)
    if mid == 'airslash':
        drawing.update(width=30, height=36)
    if mid == 'fireblast':
        drawing.update(width=42, height=50)
