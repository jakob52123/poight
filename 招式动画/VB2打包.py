"""VB2-only Emerald silhouettes. No combat data overrides."""
import hashlib
from io import BytesIO
from pathlib import Path

from PIL import Image

SOURCES = {
    'fist': ('hands_and_feet__ANIM_TAG_HANDS_AND_FEET.png', (0, 0, 32, 32), '#fff72b'),
    'bird': ('bird__ANIM_TAG_BIRD.png', (0, 0, 64, 64), '#00f0ff'),
    'flame': ('small_ember__ANIM_TAG_SMALL_EMBER.png', (0, 64, 32, 96), '#ffff25'),
    'bone': ('bone__ANIM_TAG_BONE.png', (0, 0, 32, 32), '#ffe72b'),
    'dust': ('mud_sand_0__ANIM_TAG_MUD_SAND.png', (0, 0, 8, 8), '#ffe72b'),
    'rock': ('rocks__ANIM_TAG_ROCKS.png', (0, 0, 32, 32), '#ffe72b'),
    'drop': ('small_bubbles__ANIM_TAG_SMALL_BUBBLES.png', (0, 16, 16, 32), '#20ffff'),
    'splash': ('water_impact__ANIM_TAG_WATER_IMPACT.png', (0, 0, 32, 32), '#20ffff'),
}


def build(root, output, mapping):
    for key, (name, frame, color) in SOURCES.items():
        folder = '原版' if key in {'drop', 'splash'} else 'VB2原版'
        source = root / '招式动画' / folder / name
        image = Image.open(source).convert('RGBA').crop(frame)
        rgb = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
        # Preserve the source silhouette, with white-hot highlights instead of flat dark fill.
        original = list(image.get_flattened_data())
        pixels = []
        for i, (red, green, blue, alpha) in enumerate(original):
            x, y = i % image.width, i // image.width
            # Emerald fist's light finger grooves must remain readable, not zebra stripes.
            highlight = red + green + blue > 420 if key == 'fist' else (x + y) % 4 < 2
            tint = (248, 255, 255) if highlight else rgb
            if key == 'flame':
                edge = any(nx < 0 or ny < 0 or nx >= image.width or ny >= image.height or
                           not original[ny * image.width + nx][3]
                           for nx, ny in [(x-1, y), (x+1, y), (x, y-1), (x, y+1)])
                tint = rgb if edge else (255, 120, 37) if (x + y) % 8 == 0 else tint
            pixels.append((*tint, alpha))
        image.putdata(pixels)
        buf = BytesIO()
        image.save(buf, format='PNG')
        raw = buf.getvalue()
        mapping['effects']['vb2-' + key] = {
            'file': output('animation-vb2-' + hashlib.sha256(raw).hexdigest()[:16] + '.png', raw),
            'width': image.width, 'height': image.height,
        }
    for name in ['招式动画VB2.js', '招式动画/VB2打包.py', '招式动画/VB2原版/来源.json']:
        raw = (root / name).read_bytes()
        output('animation-source-vb2-' + hashlib.sha256(raw).hexdigest()[:16] + '.txt', raw)
    for source in (root / '招式动画/VB2原版').glob('*.png'):
        raw = source.read_bytes()
        output('animation-original-vb2-' + hashlib.sha256(raw).hexdigest()[:16] + '.png', raw)


def runtime(root):
    return (Path(root) / '招式动画VB2.js').read_text()
