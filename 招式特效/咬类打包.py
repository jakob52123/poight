"""Emerald indexed sprites: preserve indices/geometry, only index 0 becomes transparent."""
import hashlib
import io

from PIL import Image

FANGS = {'bite': 'native', 'crunch': 'native', 'firefang': 'fire', 'bugbite': 'bug'}
PALETTES = {
    'fire': {1: (92, 24, 16), 2: (172, 48, 24), 3: (244, 104, 40), 4: (255, 220, 132)},
    'bug': {1: (20, 52, 24), 2: (48, 104, 44), 3: (112, 180, 72), 4: (220, 255, 156)},
}


def sprite(root, name, palette='native'):
    indexed = Image.open(root/'素材/原版战斗动画'/f'{name}.png')
    image = indexed.convert('RGBA')
    source = list(indexed.getdata())
    colors = list(image.getdata())
    image.putdata([(0, 0, 0, 0) if i == 0 else (*PALETTES.get(palette, {}).get(i, rgb[:3]), 255)
                   for i, rgb in zip(source, colors)])
    return image


def prepare(root, record, specs):
    folder = root/'招式特效/第1批/原版牙齿'
    folder.mkdir(exist_ok=True)
    for mid, palette in FANGS.items():
        image = sprite(root, 'sharp_teeth', palette)
        atlas = Image.new('RGBA', (64, 256))
        for frame in range(4):
            atlas.paste(image, (0, frame*64))
        path = folder/f'{mid}-动画.png'
        atlas.save(path)
        record['assets'][mid] = {'output': str(path.relative_to(root)),
                                 'outputSHA256': hashlib.sha256(path.read_bytes()).hexdigest()}
        specs[mid] = {**specs[mid], 'fw': 64, 'fh': 64, 'ax': 32, 'ay': 32}


def finish(root, mid, drawing, runtime, output):
    if mid not in FANGS:
        return
    buffer = io.BytesIO()
    sprite(root, 'impact').save(buffer, format='PNG')
    raw = buffer.getvalue()
    drawing['fangImpact'] = output('fang-impact-'+hashlib.sha256(raw).hexdigest()[:16]+'.png', raw)
    drawing['fangPalette'] = FANGS[mid]
    # Existing range/CD/cost/damage and the R1 front-lean windup are untouched.
    runtime.update(fangs=True, contactDelay=10/60, recovery=.7 if mid == 'crunch' else .38)
