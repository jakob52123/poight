"""Extend T5's existing table, never replace its protected per-frame landmarks."""
import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '协作/R3/锚点'
OUT.mkdir(parents=True, exist_ok=True)
rows = json.loads((ROOT / '素材/角色库/角色库.json').read_text())
selected = set(json.loads((ROOT / '首发50.json').read_text())['ids']) if isinstance(
    json.loads((ROOT / '首发50.json').read_text()), dict) else set(json.loads((ROOT / '首发50.json').read_text()))
result = json.loads((ROOT / '招式特效/主角锚点.json').read_text())
# Facing rows: down, down-left, left, up-left, up, up-right, right, down-right.
mouth = [(.50,.37),(.24,.32),(.14,.30),(.25,.21),(.50,.19),(.75,.21),(.86,.30),(.76,.32)]
head = [(.50,.25),(.30,.23),(.24,.23),(.32,.19),(.50,.16),(.68,.19),(.76,.23),(.70,.23)]
hand = [(.28,.54),(.18,.52),(.18,.52),(.23,.46),(.26,.43),(.77,.46),(.82,.52),(.82,.52)]
review_ids = {3, 4, 6, 7, 9, 25, 65, 68, 94, 95, 123, 143, 146, 149, 471}
for row in rows:
    n = row['id']
    if n not in selected:
        continue
    entries = result.setdefault(str(n), {})
    chart = Image.new('RGB', (8*140, 7*130), '#28383f')
    for index, (part, role) in enumerate([('mouth','shoot'), ('head','shoot'), ('cannon','shoot'),
                                        ('flower','shoot'), ('r3body','melee'),
                                        ('headMelee','melee'), ('hand','melee'), ('foot','melee'),
                                        ('mouthMelee','melee')]):
        # T5 landmarks are shared unchanged. All R3 additions are namespaced so
        # R2's independent mouth/head/hand coordinates cannot overwrite them.
        if str(n) == '6' and part == 'mouth':
            continue
        key = 'r3-' + part
        clip = row['art'][role]
        im = Image.open(ROOT / '素材/角色库' / clip['file']).convert('RGBA')
        w, h = clip['frameWidth'], clip['frameHeight']
        points = []
        for direction in range(8):
            poses = []
            for f in range(clip['frames']):
                tile = im.crop((f*w, direction*h, (f+1)*w, (direction+1)*h))
                bb = tile.getchannel('A').getbbox()
                x0, y0, x1, y1 = bb
                u, v = (.5, .53) if part == 'r3body' else (.5, .97) if part == 'foot' else (
                    head[direction] if part in ['head','headMelee','flower'] else
                    hand[direction] if part == 'hand' else mouth[direction])
                if n == 7 and part == 'mouth':
                    u, v = [(.5,.48),(.20,.43),(.10,.38),(.24,.27),(.50,.26),(.76,.27),(.90,.38),(.80,.43)][direction]
                if n == 143 and part == 'mouth':
                    u, v = [(.5,.29),(.25,.29),(.14,.28),(.28,.19),(.5,.16),(.72,.19),(.86,.28),(.75,.29)][direction]
                x, y = x0+(x1-x0)*u, y0+(y1-y0)*v
                if n == 3 and part == 'flower':
                    pixels = [(x,y) for y in range(y0,y1) for x in range(x0,x1)
                              if (c := tile.getpixel((x,y)))[3] and c[0]>145 and c[1]<125 and c[2]<125]
                    if pixels:
                        x, y = sum(p[0] for p in pixels)/len(pixels), sum(p[1] for p in pixels)/len(pixels)
                if n == 9 and part == 'cannon':
                    pixels = [(x,y) for y in range(y0,y0+max(1,(y1-y0)//2)) for x in range(x0,x1)
                              if (c := tile.getpixel((x,y)))[3] and min(c[:3])>105 and max(c[:3])-min(c[:3])<45]
                    if pixels:
                        x, y = max(pixels, key=lambda q: (q[0]-(x0+x1)/2)*(1 if direction>=4 else -1))
                poses.append([round(x,2), round(y,2)])
            points.append(poses)
            if n in review_ids and part in ['mouth','cannon','flower','hand','r3body','headMelee','foot']:
                # Inspection annotations only; never embedded in runtime artwork.
                f = min(3, clip['frames']-1)
                tile = im.crop((f*w, direction*h, (f+1)*w, (direction+1)*h))
                zoom = 2
                dest = (direction*140+5, min(index,6)*130+18)
                chart.paste(tile.resize((w*zoom,h*zoom), Image.Resampling.NEAREST), dest,
                            tile.resize((w*zoom,h*zoom), Image.Resampling.NEAREST))
                x,y = points[-1][f]
                g = ImageDraw.Draw(chart)
                g.ellipse((dest[0]+x*zoom-2,dest[1]+y*zoom-2,dest[0]+x*zoom+2,dest[1]+y*zoom+2), fill='red')
                g.text((direction*140+5,min(index,6)*130), f'{part} row{direction}', fill='white')
        entries[key] = {'role': role, 'points': points, 'occludedRows': []}
    if n in review_ids:
        chart.save(OUT / f'{n}-定位.png')
# Same one-entry-per-line layout as the shared T5/R1/R2 generator.
lines = ['{']
for ni, (n, entries) in enumerate(result.items()):
    lines.append(f'  "{n}": {{')
    for pi, (part, entry) in enumerate(entries.items()):
        suffix = ',' if pi + 1 < len(entries) else ''
        lines.append(f'    "{part}": ' + json.dumps(entry, ensure_ascii=False, separators=(',', ':')) + suffix)
    lines.append('  }'+(',' if ni < len(result)-1 else ''))
lines.append('}')
(ROOT / '招式特效/主角锚点.json').write_text('\n'.join(lines)+'\n')
print('Existing T5 table extended:', len(result), 'characters')
