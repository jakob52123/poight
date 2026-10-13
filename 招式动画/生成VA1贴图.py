"""Reproducible VA1 pixel sprites. Emerald contours + explicitly authored later-gen symbols."""
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

BASE = Path(__file__).resolve().parent
IDS = ['waterpulse', 'energyball', 'thundershock', 'rockthrow', 'mudshot', 'shadowball',
       'confusion', 'dragonpulse', 'sludgebomb', 'moonblast', 'brine', 'scald', 'seedbomb',
       'electroball', 'iceshard', 'aurasphere', 'focusblast', 'powergem', 'venoshock',
       'storedpower', 'darkpulse']


def generate(reference):
    out = BASE / 'VA1素材'
    original = out / '原版'
    original.mkdir(parents=True, exist_ok=True)
    names = ['shadow_ball__ANIM_TAG_SHADOW_BALL.png', 'gold_ring__ANIM_TAG_BLUE_RING_2.png',
             'rocks__ANIM_TAG_ROCKS.png', 'water_orb__ANIM_TAG_BROWN_ORB.png',
             'poison_bubble__ANIM_TAG_POISON_BUBBLE.png', 'spark_0__ANIM_TAG_SPARK.png']
    provenance = []
    for name in names:
        raw = (reference / name).read_bytes()
        (original / name).write_bytes(raw)
        provenance.append({'file': name, 'sha256': hashlib.sha256(raw).hexdigest(),
                           'source': 'ref-moves/还原贴图/' + name})

    def emerald(name, box, colors):
        src = Image.open(original / name).convert('RGBA').crop(box)
        src.putdata([(*colors[min(len(colors)-1, (r+g+b)*len(colors)//766)], a)
                     for r, g, b, a in src.get_flattened_data()])
        return src.resize((32, 32), Image.Resampling.NEAREST)

    for mid in IDS:
        im = Image.new('RGBA', (32, 32))
        d = ImageDraw.Draw(im)
        if mid in ['shadowball', 'energyball', 'aurasphere']:
            ramp = {'shadowball': [(27, 0, 66), (46, 2, 111), (72, 8, 160)],
                    'energyball': [(186, 255, 0), (202, 255, 8), (214, 255, 16)],
                    'aurasphere': [(3, 28, 154), (10, 48, 210), (38, 76, 246)]}[mid]
            im = emerald(names[0], (0, 0, 32, 32), ramp)
            d = ImageDraw.Draw(im)
            if mid == 'shadowball':
                # Bright violet crescent surrounds, rather than replaces, the dark purple core.
                d.arc((1, 1, 30, 30), 195, 345, fill='#dc75ff', width=2)
                d.arc((4, 4, 27, 27), 205, 275, fill='#f6dfff', width=1)
            if mid == 'aurasphere':
                d.arc((5, 5, 26, 26), 40, 205, fill='#31a4ff', width=2)
                d.arc((9, 9, 22, 22), 215, 365, fill='#9ff7ff', width=2)
        elif mid == 'rockthrow':
            im = emerald(names[2], (0, 0, 32, 32),
                         [(48, 14, 0), (75, 25, 0), (104, 40, 0), (137, 62, 7)])
        elif mid in ['mudshot', 'brine', 'scald', 'sludgebomb', 'venoshock']:
            color = {'mudshot': '#682900', 'brine': '#60ffff', 'scald': '#60ffff',
                     'sludgebomb': '#640096', 'venoshock': '#640075'}[mid]
            if mid in ['sludgebomb', 'venoshock']:
                im = emerald(names[4], (0, 0, 16, 16),
                             [(64, 0, 87), (91, 0, 116), (120, 4, 146)])
            else:
                im = emerald(names[3], (0, 0, 16, 16),
                             [(60, 18, 0), (81, 29, 0), (104, 41, 0)] if mid == 'mudshot'
                             else [(90, 255, 255), (96, 255, 255), (100, 255, 255)])
            d = ImageDraw.Draw(im)
            if mid == 'brine':
                d.rectangle((10, 6, 12, 8), fill='#f3ffff')
                d.rectangle((18, 11, 20, 13), fill='#f3ffff')
                d.rectangle((8, 18, 10, 20), fill='#f3ffff')
            elif mid == 'venoshock':
                d.polygon([(1, 9), (15, 3), (31, 15), (16, 28), (3, 23)], fill=color)
                d.line([(7, 13), (21, 12), (26, 16)], fill='#c51bec', width=2)
            else:
                d.rectangle((9, 7, 11, 8), fill='#ab70da' if mid == 'sludgebomb' else '#bc6230'
                            if mid == 'mudshot' else '#f0ffff')
        elif mid in ['waterpulse', 'dragonpulse', 'darkpulse', 'storedpower', 'confusion']:
            color = {'waterpulse': '#60ffff', 'dragonpulse': '#6205a4', 'darkpulse': '#250346',
                     'storedpower': '#a70460', 'confusion': '#970358'}[mid]
            for inset in [1, 6, 11]:
                d.ellipse((inset, inset, 31-inset, 31-inset), outline=color,
                          width=3 if mid != 'confusion' else 2)
            if mid == 'confusion':
                d.arc((1, 7, 30, 24), 20, 200, fill='#e71892', width=2)
                d.arc((6, 1, 25, 30), 180, 355, fill='#b20969', width=3)
            if mid == 'storedpower':
                d.ellipse((12, 12, 19, 19), fill='#f03d9c')
                for x, y in [(4, 4), (25, 5), (3, 24), (24, 24)]:
                    d.rectangle((x, y, x+2, y+2), fill='#ffca20')
        elif mid in ['electroball', 'focusblast']:
            d.ellipse((1, 1, 30, 30), fill='#f9ed08', outline='#ffee08', width=3)
            d.arc((5, 5, 26, 26), 20, 175, fill='#ffffba', width=2)
            if mid == 'electroball':
                d.polygon([(17, 3), (8, 17), (16, 16), (11, 29), (25, 13), (17, 14)],
                          fill='#fffdf0')
                d.line([(1, 8), (5, 10), (1, 15)], fill='#ffff20', width=2)
            else:
                d.ellipse((10, 10, 21, 21), fill='#ffffc2')
                d.arc((2, 2, 29, 29), 210, 320, fill='#ffbc05', width=2)
        elif mid == 'thundershock':
            # One broad jagged bolt; not a round electric orb or a replacement beam.
            d.polygon([(2, 10), (14, 3), (12, 11), (28, 7), (24, 17), (31, 21),
                       (15, 29), (18, 20), (1, 25), (7, 15)], fill='#fff20b')
            d.line([(3, 15), (15, 10), (12, 20), (27, 16)], fill='#ffffcd', width=2)
        elif mid == 'moonblast':
            d.ellipse((1, 1, 30, 30), fill='#690031', outline='#940054', width=2)
            d.ellipse((9, 6, 24, 24), fill='#fff4ff')
            d.ellipse((13, 4, 27, 22), fill='#690031')
            d.rectangle((6, 24, 8, 26), fill='#ffb3ea')
        elif mid == 'seedbomb':
            # Authored seed, with a dark husk seam and two tiny sprouting leaves.
            d.ellipse((3, 4, 28, 30), fill='#143300', outline='#081e00', width=2)
            d.line([(15, 6), (11, 13), (13, 21), (18, 29)], fill='#744006', width=3)
            d.polygon([(15, 8), (4, 5), (2, 0), (10, 0)], fill='#286300')
            d.polygon([(16, 7), (19, 0), (29, 1), (26, 6)], fill='#428500')
            d.line([(20, 10), (23, 15)], fill='#64830c', width=2)
        elif mid == 'iceshard':
            d.polygon([(0, 16), (12, 1), (24, 3), (31, 16), (22, 28), (10, 31)], fill='#2efaff')
            d.polygon([(3, 16), (13, 3), (16, 16), (11, 28)], fill='#a4ffff')
            d.line([(16, 16), (25, 5)], fill='#f1ffff', width=2)
            d.line([(16, 16), (23, 26)], fill='#09c9ff', width=2)
        elif mid == 'powergem':
            d.polygon([(6, 2), (25, 2), (31, 13), (16, 31), (0, 13)], fill='#fff409')
            d.line([(1, 13), (30, 13)], fill='#ffffa2', width=2)
            d.line([(7, 3), (11, 13), (16, 29), (21, 13), (24, 3)], fill='#ffe006', width=2)
            d.polygon([(11, 4), (20, 4), (18, 11)], fill='#ffffbf')
        im.save(out / (mid + '.png'))
    steam = Image.new('RGBA', (32, 32))
    d = ImageDraw.Draw(steam)
    for box in [(2, 14, 21, 29), (10, 6, 28, 26), (6, 1, 21, 19)]:
        d.ellipse(box, fill='#f2fbff')
    steam.save(out / 'steam.png')
    (out / '来源.json').write_text(json.dumps({
        'license': 'AGPL-3.0-or-later; Emerald decomp assets see root NOTICE.md',
        'originals': provenance,
        'authoredSymbols': ['moonblast', 'seedbomb', 'powergem', 'iceshard', 'electroball',
                            'focusblast', 'confusion', 'storedpower', 'dragonpulse', 'darkpulse'],
        'note': 'Later-gen suggestions are adaptations, NOT obtained same-name Emerald animations.',
        'sprites': {mid: hashlib.sha256((out / (mid+'.png')).read_bytes()).hexdigest()
                    for mid in [*IDS, 'steam']},
    }, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    import sys
    generate(Path(sys.argv[1]))
