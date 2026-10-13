"""VB1 only: Emerald alpha contours, tightly cropped and high-chroma indexed ramps."""
import hashlib
from io import BytesIO

from PIL import Image

# Source frame indices are from Emerald's sprite templates, not sheet bounding boxes.
SOURCES = {
    'star': ('impact__ANIM_TAG_IMPACT', (0, 0, 32, 32)),
    'fist': ('hands_and_feet__ANIM_TAG_HANDS_AND_FEET', (0, 0, 32, 32)),
    'palm': ('hands_and_feet__ANIM_TAG_HANDS_AND_FEET', (0, 96, 32, 128)),
    'whip': ('slam_hit__ANIM_TAG_WHIP_HIT', (0, 32, 32, 64)),
    'scratch': ('scratch__ANIM_TAG_SCRATCH', (0, 96, 32, 128)),
    'claw': ('claw_slash__ANIM_TAG_CLAW_SLASH', (0, 128, 32, 160)),
    'tongue': ('lick__ANIM_TAG_LICK', (0, 128, 16, 160)),
    'gust': ('gust__ANIM_TAG_GUST', (0, 0, 32, 64)),
    'cross': ('cross_impact__ANIM_TAG_CROSS_IMPACT', (0, 0, 32, 32)),
    'leaf': ('leaf__ANIM_TAG_LEAF', (0, 32, 16, 48)),
    'ember': ('small_ember__ANIM_TAG_SMALL_EMBER', (0, 64, 32, 96)),
    'bolt': ('lightning__ANIM_TAG_LIGHTNING', (0, 32, 32, 96)),
    'orb': ('orbs__ANIM_TAG_ORBS', (0, 32, 16, 48)),
    'heart': ('magenta_heart__ANIM_TAG_PINK_HEART', (0, 0, 16, 16)),
    'blueorb': ('gray_orb__ANIM_TAG_BLUE_ORB', (0, 0, 8, 8)),
    'wall': ('green_light_wall__ANIM_TAG_BLUE_LIGHT_WALL', (0, 0, 32, 64)),
    'shard': ('torn_metal__ANIM_TAG_TORN_METAL', (0, 0, 32, 32)),
}
RAMPS = {
    'gold': [(153, 95, 8), (255, 230, 50), (255, 242, 80)],
    'green': [(160, 255, 85), (175, 255, 90), (185, 255, 100)],
    'fire': [(180, 42, 5), (255, 230, 40), (255, 241, 65)],
    'ice': [(8, 114, 155), (55, 245, 255), (100, 255, 255)],
    'pink': [(70, 0, 27), (108, 0, 46), (145, 8, 70)],
    'poison': [(255, 100, 255), (255, 100, 255), (255, 100, 255)],
    'ghost': [(13, 0, 27), (37, 0, 58), (95, 16, 164)],
    'blue': [(45, 215, 255), (65, 245, 255), (85, 250, 255)],
}
VARIANTS = {
    'fist': ['gold', 'fire', 'ice', 'green', 'ghost'],
    'star': ['gold'], 'palm': ['gold', 'poison'], 'whip': ['green'], 'scratch': ['gold'],
    'claw': ['ice'], 'tongue': ['pink'], 'gust': ['gold'], 'cross': ['gold', 'green'],
    'leaf': ['green'], 'ember': ['fire'], 'bolt': ['gold'], 'orb': ['green', 'poison'],
    'heart': ['pink'], 'blueorb': ['blue'], 'wall': ['green'], 'shard': ['green'],
}


def build(root, output, mapping):
    for shape, colors in VARIANTS.items():
        name, box = SOURCES[shape]
        source = root / '招式动画/VB1原版' / (name + '.png')
        raw_source = source.read_bytes()
        output('animation-vb1-original-' + hashlib.sha256(raw_source).hexdigest()[:16] + '.png', raw_source)
        original = Image.open(source).convert('RGBA').crop(box)
        original = original.crop(original.getbbox())
        for color in colors:
            ramp = RAMPS[color]
            if shape == 'claw':
                ramp = [(60, 225, 255), (80, 245, 255), (110, 255, 255)]
            if shape == 'ember':
                ramp = [(255, 55, 8), (255, 224, 25), (255, 247, 100)]
            if shape == 'star':
                ramp = [(255, 245, 60), (255, 255, 70), (255, 255, 80)]
            tinted = original.copy()
            values = []
            for pixel, (r, g, b, a) in enumerate(original.get_flattened_data()):
                luma = (r + g + b) / 3
                # Hands are filled dark in the original: keep the knuckle ink dark and
                # the face saturated bright. The outside white contour remains a highlight.
                if shape in {'fist', 'palm'}:
                    highlight = ramp[2] if color == 'ghost' else (250, 255, 250)
                    rgb = highlight if luma > 150 else ramp[0] if luma < 55 else ramp[1]
                else:
                    rgb = ramp[0 if luma < 60 else 1 if luma < 210 else 2]
                if color == 'poison' and (pixel % original.width + pixel // original.width) % 4 < 2:
                    rgb = (255, 255, 255)  # white facets on the same Emerald alpha contour
                values.append((*rgb, a))
            tinted.putdata(values)
            if shape == 'star':
                cx, cy = tinted.width // 2, tinted.height // 2
                for x in range(cx - 2, cx + 2):
                    for y in range(cy - 2, cy + 2):
                        if tinted.getpixel((x, y))[3]:
                            tinted.putpixel((x, y), (250, 255, 250, 255))
            buffer = BytesIO()
            tinted.save(buffer, format='PNG')
            raw = buffer.getvalue()
            key = f'vb1-{shape}-{color}'
            mapping['effects'][key] = {
                'file': output('animation-vb1-' + hashlib.sha256(raw).hexdigest()[:16] + '.png', raw),
                'width': tinted.width, 'height': tinted.height,
            }
