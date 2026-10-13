"""Reproducible local Emerald silhouettes; sources are restored indexed palettes, not gray PNGs."""
import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
DEST = Path(__file__).resolve().parent
REF = DEST / '原版' if (DEST / '原版').is_dir() else ROOT.parent / 'ref-moves/还原贴图'
# Tight crops preserve Emerald silhouettes; FX1 palettes stay luminous on dirt/grass.
SPECS = {
    'bubble': ('bubble__ANIM_TAG_BUBBLE', (0, 0, 16, 16), '#4fc3ff'),
    'flame': ('small_ember__ANIM_TAG_SMALL_EMBER', (0, 32, 32, 64), '#ffb22e'),
    'leaf': ('leaf__ANIM_TAG_LEAF', (0, 0, 16, 16), '#8aff45'),
    'razor': ('razor_leaf__ANIM_TAG_RAZOR_LEAF', (0, 0, 32, 16), '#8aff45'),
    'gust': ('gust__ANIM_TAG_GUST', (0, 0, 32, 64), '#70dcff'),
    'needle': ('needle__ANIM_TAG_NEEDLE', (0, 0, 16, 16), '#b45cf0'),
    'star': ('yellow_star__ANIM_TAG_YELLOW_STAR', (0, 0, 32, 32), '#ffff24'),
    'triangle': ('tri_attack_triangle__ANIM_TAG_TRI_ATTACK_TRIANGLE', (0, 0, 64, 64), None),
    'crescent': ('air_wave_2__ANIM_TAG_AIR_WAVE_2', (0, 0, 32, 16), '#7020ff'),
    'ice': ('ice_crystals_0__ANIM_TAG_ICE_CRYSTALS', (0, 0, 16, 16), '#65ffff'),
    'spikes': ('ice_spikes__ANIM_TAG_ICE_SPIKES', (0, 32, 8, 48), '#31e8ff'),
    'orb': ('orbs__ANIM_TAG_ORBS', (0, 32, 16, 48), '#ffec45'),
    'water': ('water_orb__ANIM_TAG_WATER_ORB', (0, 0, 16, 16), '#4fc3ff'),
    'ring': ('gold_ring__ANIM_TAG_GOLD_RING', (0, 0, 16, 32), '#ffff24'),
    'red': ('glowy_red_orb__ANIM_TAG_GLOWY_RED_ORB', (0, 0, 8, 8), '#ff8787'),
    'green': ('glowy_red_orb__ANIM_TAG_GLOWY_GREEN_ORB', (0, 0, 8, 8), '#5dff24'),
    'sap': ('orbs__ANIM_TAG_ORBS', (0, 32, 16, 48), '#70ff24'),
    'silver': ('orbs__ANIM_TAG_ORBS', (0, 32, 16, 48), '#73edff'),
    'heal': ('blue_star__ANIM_TAG_BLUE_STAR', (0, 64, 32, 96), None),
    'breath': ('small_ember__ANIM_TAG_SMALL_EMBER', (0, 32, 32, 64), '#ffea39'),
    'dragon-flare': ('small_ember__ANIM_TAG_SMALL_EMBER', (0, 32, 32, 64), '#ff8c39'),
    'electric': ('lightning__ANIM_TAG_LIGHTNING', (0, 32, 32, 64), None),
    'poison': ('poison_bubble__ANIM_TAG_POISON_BUBBLE', (0, 0, 16, 16), '#b45cf0'),
}


def fire_texture(size):
    """GBA-sized tongues, bright yellow core and orange rim (no dark ramp)."""
    im = Image.new('RGBA', size)
    draw = ImageDraw.Draw(im)
    w, h = size
    draw.polygon([(w*.5, 0), (w*.66, h*.35), (w*.88, h*.18),
                  (w-1, h*.72), (w*.72, h-1), (w*.22, h-1),
                  (0, h*.70), (w*.25, h*.38)], fill='#ffb22e')
    draw.polygon([(w*.5, h*.19), (w*.6, h*.50), (w*.8, h*.40),
                  (w*.83, h*.77), (w*.6, h-2), (w*.3, h-2),
                  (w*.15, h*.69)], fill='#ffb22e')
    draw.polygon([(w*.48, h*.45), (w*.65, h*.74), (w*.55, h-2),
                  (w*.3, h-2), (w*.27, h*.78)], fill='#fff2a8')
    # White-hot glints occupy the broad inner facet; the colored rim still reads orange.
    # This is necessary on bright grass: yellow/orange alone have insufficient luma gap.
    inner = im.getchannel('A').filter(ImageFilter.MinFilter(3))
    shine = Image.new('RGBA', size, '#fffefa')
    shine.putalpha(inner)
    im.alpha_composite(shine)
    draw = ImageDraw.Draw(im)
    draw.line((w*.42, h*.65, w*.42, h*.92), fill='#ffe14f', width=8)
    draw.line((w*.45, h*.70, w*.45, h*.91), fill='#fff2a8', width=2)
    draw.line((w*.5, 0, w*.5, 2), fill='#ff6a1f', width=1)
    draw.line((w-2, h*.70, w*.75, h*.93), fill='#ff6a1f', width=1)
    return im


def luminous(im, color, key):
    """Keep the restored alpha silhouette; colored contour plus a broad white facet."""
    rgb = tuple(int(color[n:n+2], 16) for n in (1, 3, 5)) if color else None
    data = list(im.get_flattened_data())
    points = [(x, y) for y in range(im.height) for x in range(im.width)
              if data[y*im.width+x][3]]
    edge = im.getchannel('A').filter(ImageFilter.MinFilter(3))
    # Contour first, then upper-left specular ordering; deterministic, no random textures.
    points.sort(key=lambda p: (edge.getpixel(p), p[0]+p[1], p[1]))
    if key in {'star', 'triangle'}:
        fraction = .48  # Thin contours need extra colored facets at <=10px raster size.
    else:
        fraction = .31 if key in {'bubble', 'water', 'red', 'silver'} else .36
    colored = set(points[:round(len(points)*fraction)])
    result = []
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, alpha = data[y*im.width+x]
            if key == 'crescent':
                # Neon violet with a tiny pink glint, not the former dark red.
                shade = (255, 140, 245) if (x, y) == points[-1] else rgb
            elif (x, y) not in colored:
                shade = (255, 255, 255)
            elif rgb:
                shade = rgb
            elif key == 'triangle':
                shade = [(255, 218, 57), (138, 255, 69), (69, 255, 255)][
                    max(range(3), key=lambda i: (r, g, b)[i])]
            else:
                shade = (255, 225, 79) if key == 'electric' else (101, 255, 255)
            result.append((*shade, alpha))
    im.putdata(result)
    return im


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--priority', action='store_true')
    args = parser.parse_args()
    mapping, provenance = {}, []
    for key, (name, box, color) in SPECS.items():
        if args.priority and key not in {'flame', 'needle', 'poison'}:
            continue
        path = REF / (name + '.png')
        raw = path.read_bytes()
        original = Image.open(path).convert('RGBA')
        im = original.crop(box)
        im = im.crop(im.getbbox())
        if key not in {'flame', 'needle', 'poison'}:
            im = luminous(im, color, key)
        if key == 'flame':
            im = fire_texture((24, 34))
        if key == 'needle':
            im = Image.new('RGBA', (6, 32))
            draw = ImageDraw.Draw(im)
            draw.polygon([(3, 0), (5, 5), (5, 29), (2, 31), (0, 5)], fill='#ffffff')
            # The fine purple inset sits inside a white contour, not a thick purple rod.
            draw.line((2, 7, 2, 21), fill='#b45cf0', width=1)
            draw.point((2, 8), fill='#ff8cf5')
        if key == 'poison':
            alpha = im.getchannel('A')
            draw = ImageDraw.Draw(im)
            draw.ellipse((0, 0, im.width-1, im.height-1), fill='#b45cf0')
            draw.ellipse((1, 1, im.width-2, im.height-2), fill='#ff8cf5')
            draw.line((2, 2, 3, 2), fill='#ffffff', width=1)
            im.putalpha(alpha)
        name_out = key + '.png'
        im.save(DEST / name_out)
        mapping['va2-' + key] = {'source': name_out, 'width': im.width, 'height': im.height}
        provenance.append({'key': key, 'restoredSource': path.name,
                           'sourceSHA256': hashlib.sha256(raw).hexdigest(), 'frame': box,
                           'outputSHA256': hashlib.sha256((DEST / name_out).read_bytes()).hexdigest(),
                           'palette': color,
                           'note': 'FX1 luminous palette; H-scaled contour; immutable source alpha'})
    # Mapping/provenance receipts are immutable inputs; the packer reads PNG dimensions.
    return mapping, provenance


if __name__ == '__main__':
    main()
