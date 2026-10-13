"""VC-only Emerald contours. Original copies never recolored on disk."""
import hashlib
from io import BytesIO

from PIL import Image


def build(root, output, mapping):
    sources = {
        'blast': ('explosion__ANIM_TAG_EXPLOSION', (0, 32, 32, 64), '#9b1808'),
        'rock': ('rocks__ANIM_TAG_ROCKS', (0, 0, 32, 32), '#522600'),
        'cloud': ('mist_cloud__ANIM_TAG_PURPLE_GAS_CLOUD', (0, 0, 32, 32), '#650083'),
        'shield': ('protect__ANIM_TAG_PROTECT', (0, 0, 64, 64), '#002712'),
        'z': ('letter_z__ANIM_TAG_LETTER_Z', (0, 0, 32, 32), '#651083'),
        'energy': ('focus_energy__ANIM_TAG_FOCUS_ENERGY', (0, 32, 16, 64), '#551800'),
        'star': ('blue_star__ANIM_TAG_BLUE_STAR', (0, 32, 32, 64), '#062783'),
        'shine': ('sparkle_1__ANIM_TAG_SPARKLE_2', (0, 0, 32, 32), '#103100'),
        'orb': ('orbs__ANIM_TAG_ORBS', (0, 32, 16, 48), '#203400'),
        'water': ('small_bubbles__ANIM_TAG_SMALL_BUBBLES', (0, 0, 16, 16), '#00efff'),
        'spike': ('ice_spikes__ANIM_TAG_ICE_SPIKES', (0, 32, 8, 64), '#50ffff'),
        'meteor': ('warm_rock__ANIM_TAG_WARM_ROCK', (0, 0, 32, 32), '#7b1e02'),
        'spark': ('spark_0__ANIM_TAG_SPARK', (0, 0, 8, 32), '#ffff16'),
        'flame': ('small_ember__ANIM_TAG_SMALL_EMBER', (0, 0, 32, 32), '#a31a00'),
        'ring': ('gold_ring__ANIM_TAG_GOLD_RING', (0, 0, 16, 32), '#520057'),
    }
    for key, (name, crop, color) in sources.items():
        im = Image.open(root / '招式动画/VC原版' / (name + '.png')).convert('RGBA').crop(crop)
        im = im.crop(im.getbbox())
        rgb = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
        # Keep the original pixel silhouette and two-tone shading; explicit highlights are sparse.
        low = .97 if key in {'spike', 'spark'} else .78
        pixels = list(im.get_flattened_data())
        bright = set()
        if key == 'flame':
            opaque = [i for i, pixel in enumerate(pixels) if pixel[3]]
            # Preserve a small readable yellow-white flame heart, not a flat red silhouette.
            bright = set(sorted(opaque, key=lambda i: pixels[i][1] + pixels[i][2],
                                reverse=True)[:max(1, len(opaque)//16)])
        im.putdata([(*(round(c * (low + (1 - low) * (.2126*r + .7152*g + .0722*b) / 255))
                      for c in rgb), a) if i not in bright else (255, 247, 230, a)
                    for i, (r, g, b, a) in enumerate(pixels)])
        buf = BytesIO()
        im.save(buf, format='PNG')
        raw = buf.getvalue()
        mapping['effects']['vc-' + key] = {
            'file': output('animation-vc-' + hashlib.sha256(raw).hexdigest()[:16] + '.png', raw),
            'width': im.width, 'height': im.height,
        }
    for name in ['招式动画VC.js', '招式动画/VC打包.py', '招式动画/VC原版/来源.json']:
        raw = (root / name).read_bytes()
        output('animation-source-' + hashlib.sha256(raw).hexdigest()[:16] + '.txt', raw)
