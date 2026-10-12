"""Reproducible local Emerald silhouettes; sources are restored indexed palettes, not gray PNGs."""
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
DEST = Path(__file__).resolve().parent
REF = DEST / '原版' if (DEST / '原版').is_dir() else ROOT.parent / 'ref-moves/还原贴图'
# Tight crop is measured, not transparent nominal canvas. Needle deliberately thickened.
SPECS = {
    'bubble': ('bubble__ANIM_TAG_BUBBLE', (0, 0, 16, 16), '#093b9d'),
    'flame': ('small_ember__ANIM_TAG_SMALL_EMBER', (0, 32, 32, 64), '#981701'),
    'leaf': ('leaf__ANIM_TAG_LEAF', (0, 0, 16, 16), '#03280b'),
    'razor': ('razor_leaf__ANIM_TAG_RAZOR_LEAF', (0, 0, 32, 16), '#06451a'),
    'gust': ('gust__ANIM_TAG_GUST', (0, 0, 32, 64), '#063b70'),
    'needle': ('needle__ANIM_TAG_NEEDLE', (0, 0, 16, 16), '#601378'),
    'star': ('yellow_star__ANIM_TAG_YELLOW_STAR', (0, 0, 32, 32), '#ffff24'),
    'triangle': ('tri_attack_triangle__ANIM_TAG_TRI_ATTACK_TRIANGLE', (0, 0, 64, 64), None),
    'crescent': ('air_wave_2__ANIM_TAG_AIR_WAVE_2', (0, 0, 32, 16), '#900749'),
    'ice': ('ice_crystals_0__ANIM_TAG_ICE_CRYSTALS', (0, 0, 16, 16), '#65ffff'),
    'spikes': ('ice_spikes__ANIM_TAG_ICE_SPIKES', (0, 32, 8, 48), '#31e8ff'),
    'orb': ('orbs__ANIM_TAG_ORBS', (0, 32, 16, 48), '#ffec45'),
    'water': ('water_orb__ANIM_TAG_WATER_ORB', (0, 0, 16, 16), '#65ffff'),
    'ring': ('gold_ring__ANIM_TAG_GOLD_RING', (0, 0, 16, 32), '#ffff24'),
    'red': ('glowy_red_orb__ANIM_TAG_GLOWY_RED_ORB', (0, 0, 8, 8), '#ff7272'),
    'green': ('glowy_red_orb__ANIM_TAG_GLOWY_GREEN_ORB', (0, 0, 8, 8), '#5dff24'),
    'sap': ('orbs__ANIM_TAG_ORBS', (0, 32, 16, 48), '#70ff24'),
    'silver': ('orbs__ANIM_TAG_ORBS', (0, 32, 16, 48), '#39ddff'),
    'heal': ('blue_star__ANIM_TAG_BLUE_STAR', (0, 64, 32, 96), None),
    'breath': ('small_ember__ANIM_TAG_SMALL_EMBER', (0, 32, 32, 64), '#ffea39'),
    'dragon-flare': ('small_ember__ANIM_TAG_SMALL_EMBER', (0, 32, 32, 64), '#ff8c39'),
    'electric': ('lightning__ANIM_TAG_LIGHTNING', (0, 32, 32, 64), None),
    'poison': ('poison_bubble__ANIM_TAG_POISON_BUBBLE', (0, 0, 16, 16), '#601378'),
}


def main():
    mapping, provenance = {}, []
    for key, (name, box, color) in SPECS.items():
        path = REF / (name + '.png')
        raw = path.read_bytes()
        original = Image.open(path).convert('RGBA')
        (DEST / '原版').mkdir(exist_ok=True)
        (DEST / '原版' / path.name).write_bytes(raw)
        im = original.crop(box)
        im = im.crop(im.getbbox())
        if color:
            rgb = tuple(int(color[n:n+2], 16) for n in (1, 3, 5))
            # A narrow white specular patch, all other colors use a saturated ramp.
            im.putdata([(*(round(c * (.78 + .22 * max(r, g, b)/255)) for c in rgb), a)
                        for r, g, b, a in im.get_flattened_data()])
            if key in {'bubble', 'star'}:
                x, y = im.width//3, im.height//4
                if im.getpixel((x, y))[3]:
                    im.putpixel((x, y), (255, 255, 255, 255))
        if key == 'ice':
            # A white facet, not a white whole crystal: keep >30% high-chroma ice body.
            alpha = im.getchannel('A')
            draw = ImageDraw.Draw(im)
            w, h = im.size
            draw.polygon([(w*.38, 1), (w*.73, 3), (w*.73, h-2), (w*.38, h-4)],
                         fill='#f8ffff')
            im.putalpha(alpha)
        if key == 'needle':
            # Keep a long shaft, add a readable pointed tip rather than a fat rectangle.
            im = Image.new('RGBA', (8, 24))
            draw = ImageDraw.Draw(im)
            draw.polygon([(4, 0), (7, 7), (7, 19), (5, 23), (2, 23), (0, 19), (0, 7)],
                         fill='#601378')
            draw.line((3, 7, 3, 19), fill='#c347eb', width=1)
        if key == 'triangle':
            # Keep original RGB vertex coding but darken lines for dirt/grass contrast.
            im.putdata([(round(r*.36), round(g*.36), round(b*.36), a)
                        for r, g, b, a in im.get_flattened_data()])
        name_out = key + '.png'
        im.save(DEST / name_out)
        mapping['va2-' + key] = {'source': name_out, 'width': im.width, 'height': im.height}
        provenance.append({'key': key, 'restoredSource': path.name,
                           'sourceSHA256': hashlib.sha256(raw).hexdigest(), 'frame': box,
                           'outputSHA256': hashlib.sha256((DEST / name_out).read_bytes()).hexdigest(),
                           'palette': color, 'note': 'tight alpha crop; needle width adapted for readability'})
    (DEST / '贴图映射.json').write_text(json.dumps(mapping, ensure_ascii=False, indent=2)+'\n')
    (DEST / '来源.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    main()
