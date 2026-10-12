"""Offline animation assets; only visual data, never combat overrides."""
import hashlib
import json
import math
from io import BytesIO
from pathlib import Path

from PIL import Image

from 招式动画 import VA2素材

from .VB1素材 import build as build_vb1


def build(root, output, types):
    base = root / '招式动画'
    mapping = json.loads((base / '特效映射.json').read_text())
    for effect in mapping['effects'].values():
        source = Path(effect['file'])
        path = base / 'V1p素材' / source.name if source.parts[0] == '素材' else root / source
        raw = path.read_bytes()
        effect['file'] = output('animation-' + hashlib.sha256(raw).hexdigest()[:16] + path.suffix, raw)
    sources = {
        'core-water': ('small_bubbles__ANIM_TAG_SMALL_BUBBLES.png', [0, 0, 16, 16]),
        'core-drop': ('small_bubbles__ANIM_TAG_SMALL_BUBBLES.png', [0, 16, 16, 16]),
        'core-splash': ('water_impact__ANIM_TAG_WATER_IMPACT.png', [0, 0, 32, 32]),
        'core-ice': ('ice_crystals_0__ANIM_TAG_ICE_CRYSTALS.png', [0, 0, 16, 16]),
        'core-shard': ('ice_crystals_1__ANIM_TAG_ICE_CRYSTALS.png', [0, 0, 8, 16]),
        'core-dust': ('flying_dirt__ANIM_TAG_FLYING_DIRT.png', [0, 0, 32, 16]),
    }
    for key, (name, frame) in sources.items():
        original = Image.open(base / '原版' / name).convert('RGBA')
        if key in {'core-water', 'core-drop', 'core-splash', 'core-ice', 'core-shard'}:
            # Emerald's restored bubble palette is lavender. Keep its pixel silhouette,
            # but use explicit high-chroma water/ice ramps (the source stays untouched).
            ice = key in {'core-ice', 'core-shard'}
            ramp = ([(50, 239, 255), (65, 248, 255), (100, 255, 255), (242, 255, 255)]
                    if ice else [(6, 35, 155), (12, 50, 202), (14, 65, 230), (60, 140, 255)])
            original.putdata([(*ramp[0 if g < 140 else 1 if g < 185 else 2 if g < 240 else 3], a)
                              for r, g, b, a in original.get_flattened_data()])
            if key == 'core-water':
                # Small white specular highlight; not a pale translucent bubble.
                for x, y in [(5, 3), (6, 3), (5, 4), (6, 4)]:
                    original.putpixel((x, y), (245, 255, 255, 255))
        if key == 'core-dust':
            original.putdata([(93, 50, 15, a) if g < 180 else (120, 63, 18, a)
                              for r, g, b, a in original.get_flattened_data()])
        buf = BytesIO()
        original.save(buf, format='PNG')
        raw = buf.getvalue()
        mapping['effects'][key] = {
            'file': output('animation-' + hashlib.sha256(raw).hexdigest()[:16] + '.png', raw),
            'width': frame[2], 'height': frame[3], 'frames': [frame],
        }
    # VH: retain source bytes; tightly crop actual silhouettes, not transparent canvas bounds.
    hero_sources = {
        'spark0': ('spark_0__ANIM_TAG_SPARK.png', (0, 0, 8, 64)),
        'spark1': ('spark_1__ANIM_TAG_SPARK.png', (0, 0, 16, 64)),
        'orb': ('shock_3__ANIM_TAG_SHOCK_3.png', (0, 64, 32, 96)),
        'flame-rim': ('small_ember__ANIM_TAG_SMALL_EMBER.png', (0, 64, 32, 96)),
        'flame0': ('small_ember__ANIM_TAG_SMALL_EMBER.png', (0, 64, 32, 96)),
        'flame1': ('small_ember__ANIM_TAG_SMALL_EMBER.png', (0, 96, 32, 128)),
        'claw-purple': ('claw_slash__ANIM_TAG_CLAW_SLASH.png', (0, 96, 32, 128)),
        'claw-cyan': ('claw_slash__ANIM_TAG_CLAW_SLASH.png', (0, 96, 32, 128)),
        'claw-strike': ('claw_slash__ANIM_TAG_CLAW_SLASH.png', (0, 128, 32, 160)),
        'wind': ('air_wave_2__ANIM_TAG_AIR_WAVE_2.png', (0, 0, 32, 16)),
        'lightning': ('lightning__ANIM_TAG_LIGHTNING.png', (0, 32, 32, 64)),
    }
    for key, (name, box) in hero_sources.items():
        im = Image.open(base / '原版' / name).convert('RGBA').crop(box)
        im = im.crop(im.getbbox())
        pixels = []
        for r, g, b, a in im.get_flattened_data():
            if key == 'flame-rim':
                rgb = (r, g, b)  # Original orange-red fire fringe, translucent beneath the hot body.
            elif key.startswith('claw'):
                rgb = ((245, 255, 255) if g > 140 else
                       (174, 65, 255) if key.endswith('purple') and r > 150 and g < 80
                       else (105, 255, 255))
            elif key == 'wind':
                rgb = (250, 255, 255) if r > 180 else (105, 255, 255)
            elif key == 'orb':
                rgb = (255, 255, 240) if r > 220 and g > 220 else (255, 223, 20)
            elif key.startswith('flame'):
                rgb = (255, 252, 217) if g > 210 else (255, 255, 32) if g > 80 else (255, 220, 12)
            else:
                rgb = (255, 255, 245) if r > 240 and g > 240 else (255, 231, 25)
            pixels.append((*rgb, a))
        if key == 'claw-strike':
            # Final Emerald slash silhouette, not the earlier flame-tipped smear.
            pixels = []
            interior = [x+y for y in range(im.height) for x in range(im.width)
                        if im.getpixel((x, y))[3] and im.getpixel((x, y))[1] <= 80]
            lo_axis, hi_axis = min(interior), max(interior)
            for y in range(im.height):
                for x in range(im.width):
                    r, g, b, a = im.getpixel((x, y))
                    # Preserve a truly purple heel, then graduate quickly into the bright cyan blade.
                    # Normalize to actual colored pixels, not invisible canvas endpoints.
                    axis = (x + y - lo_axis) / (hi_axis - lo_axis)
                    t = max(0, min(1, (axis - .15) / .15))
                    rgb = ((250, 255, 255) if g > 80 else tuple(round(lo + (hi-lo)*t)
                           for lo, hi in zip((123, 92, 255), (111, 240, 255))))
                    if g <= 80:
                        rgb = (rgb[0] - round(20 * math.sin(math.pi * t)), *rgb[1:])
                    pixels.append((*rgb, a))
        im.putdata(pixels)
        buf = BytesIO()
        im.save(buf, format='PNG')
        raw = buf.getvalue()
        mapping['effects']['hero-' + key] = {
            'file': output('animation-hero-' + hashlib.sha256(raw).hexdigest()[:16] + '.png', raw),
            'width': im.width, 'height': im.height,
        }
    VA2素材.build(base, mapping, output)
    VA2素材.sources(root, output)
    impact = Image.open(base / '原版/impact__ANIM_TAG_IMPACT.png').convert('RGBA')
    for tid, t in {**types, -1: ('test', '#ffffff')}.items():
        color = t[1].lstrip('#')
        rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        tinted = impact.copy()
        # Retain Emerald's white core and pixel contour, color only the rim.
        tinted.putdata([(255, 255, 255, a) if r >= 250 and g >= 250 else
                        (*(round(c * (.6 + .4 * g / 255)) for c in rgb), a)
                        for r, g, b, a in impact.get_flattened_data()])
        buf = BytesIO()
        tinted.save(buf, format='PNG')
        raw = buf.getvalue()
        mapping['effects']['core-impact-' + str(tid)] = {
            'file': output('animation-impact-' + hashlib.sha256(raw).hexdigest()[:16] + '.png', raw),
            'width': 32, 'height': 32,
        }
    build_vb1(root, output, mapping)
    notices = {}
    for name in ['NOTICE.md', 'LICENSE-AGPL-3.0', 'vendor/showdown/NOTICE.md', 'vendor/showdown/LICENSE']:
        raw = (root / name).read_bytes()
        notices[name] = output('animation-legal-' + hashlib.sha256(raw).hexdigest()[:16] + '.txt', raw)
    # Editable corresponding source accompanies every portable build, no remote source link required.
    for name in ['招式动画引擎.js', '招式动画接入.js', '主角招式外观.js', '招式动画/招式动画.json',
                 '招式动画/特效映射.json', '招式动画/打包.py', '招式动画/接入指南.md',
                 '招式动画/主角八招接入.md', '招式动画/原版/VH来源.json',
                 '招式动画近身VB1.js', '招式动画/VB1素材.py', '招式动画/VB1原版/来源.json',
                 '招式动画/VB1接入.md']:
        raw = (root / name).read_bytes()
        output('animation-source-' + hashlib.sha256(raw).hexdigest()[:16] + '.txt', raw)
    return {'data': json.loads((base / '招式动画.json').read_text()),
            'mapping': mapping, 'notices': notices}


def runtime(root):
    source = (root / '招式动画引擎.js').read_text().replace('export ', '')
    return ('(() => {\n' + source + '\nwindow.PoightAnimationEngine = MoveAnimationEngine;\n'
            '})();\n' + (root / '招式动画接入.js').read_text() + '\n'
            + (root / '主角招式外观.js').read_text() + '\n'
            + (root / '招式动画近身VB1.js').read_text())
