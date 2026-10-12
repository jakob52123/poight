"""Append R1 landmarks to T5's SINGLE sprite/frame table (source pixels unchanged).
Reviewed species overrides are fractions of each actual pose alpha bounds.
Other species use nearest opaque pixel, explicitly an anatomical approximation.
"""
import json

from PIL import Image

MOUTH = [(.5, .36), (.20, .32), (.10, .30), (.25, .19),
         (.5, .18), (.75, .19), (.90, .30), (.80, .32)]
HAND = [(.20, .62), (.25, .58), (.18, .65), (.18, .56),
        (.80, .57), (.82, .56), (.82, .65), (.75, .58)]
TAIL = [(.80, .77), (.90, .65), (.89, .63), (.83, .67),
        (.50, .90), (.17, .67), (.11, .63), (.10, .65)]
WING = [(.87, .48), (.88, .58), (.53, .70), (.20, .65),
        (.13, .45), (.80, .65), (.47, .70), (.12, .58)]
# Values checked on the 8-row Attack sheets, not idle silhouettes.
OVERRIDES = {
    143: {'r1-hand': [(.13, .50), (.16, .51), (.40, .58), (.16, .51),
                      (.16, .55), (.84, .51), (.60, .58), (.84, .51)]},
    448: {'r1-hand': [(.16, .53), (.20, .54), (.25, .61), (.17, .55),
                      (.82, .54), (.83, .55), (.75, .61), (.80, .54)]},
    68: {'r1-hand': [(.13, .53), (.18, .57), (.25, .58), (.15, .52),
                     (.85, .52), (.85, .52), (.75, .58), (.82, .57)]},
    3: {'r1-vine': [(.5, .45)]*8},
    7: {'r1-tail': TAIL},
    94: {'r1-mouth': [(.50, .62), (.15, .56), (.16, .49), (.16, .40),
                      (.50, .18), (.84, .40), (.84, .49), (.85, .56)]},
    21: {'r1-mouth': [(.50, .45), (.13, .48), (.08, .38), (.17, .36),
                      (.50, .22), (.83, .36), (.92, .38), (.87, .48)]},
    130: {'r1-mouth': [(.50, .65), (.20, .60), (.08, .43), (.14, .36),
                       (.50, .18), (.86, .36), (.92, .43), (.80, .60)]},
    470: {'r1-leaf': [(.10, .22), (.11, .29), (.14, .30), (.23, .18),
                      (.50, .20), (.77, .18), (.86, .30), (.89, .29)]},
}


def extend(result, rows, root):
    selected = set(json.loads((root/'首发50.json').read_text())['ids'])
    fractions = {'r1-hand': HAND, 'r1-hand2': [(1-u, v) for u, v in HAND],
                 'r1-mouth': MOUTH, 'r1-head': [(u, max(.12, v-.14)) for u, v in MOUTH],
                 'r1-tail': TAIL, 'r1-wing': WING, 'r1-vine': [(.5, .30)]*8,
                 'r1-leaf': HAND, 'r1-body': [(.5, .5)]*8,
                 'r1-foot': [(.5, .85)]*8}
    for row in rows:
        n = row['id']
        if n not in selected:
            continue
        clip = row['art']['melee']
        im = Image.open(root/'素材/角色库'/clip['file']).convert('RGBA')
        w, h = clip['frameWidth'], clip['frameHeight']
        entries = result.setdefault(n, {})
        pose_offsets = []
        for direction in range(8):
            boxes = [im.crop((f*w, direction*h, (f+1)*w, (direction+1)*h)).getbbox()
                     for f in range(clip['frames'])]
            base_x, base_y = (boxes[0][0]+boxes[0][2])/2, boxes[0][3]
            pose_offsets.append([[round((b[0]+b[2])/2-base_x, 2), b[3]-base_y] for b in boxes])
        for part, fractions_by_row in fractions.items():
            points = []
            for direction in range(8):
                poses = []
                for frame in range(clip['frames']):
                    tile = im.crop((frame*w, direction*h, (frame+1)*w, (direction+1)*h))
                    x0, y0, x1, y1 = tile.getbbox()
                    u, v = OVERRIDES.get(n, {}).get(part, fractions_by_row)[direction]
                    if n == 68 and frame >= 8 and part.startswith('r1-hand'):
                        # This source turns its back through the final spinning poses.
                        u = .12 if direction in (0, 1, 2, 7) else .88
                        v = .38
                    x, y = x0+(x1-x0)*u, y0+(y1-y0)*v
                    if n == 130 and part == 'r1-mouth' and direction in (0, 1, 2, 6, 7):
                        # Mouth interior is orange/red; tiny brow-red must NOT win.
                        warm = [(xx, yy) for yy in range(h) for xx in range(w)
                                if (c := tile.getpixel((xx, yy)))[3] and c[0] > 190
                                and c[0] > c[1]*1.45 and c[0] > c[2]*2]
                        if warm:
                            x, y = min(warm, key=lambda p: (p[0]-x)**2+(p[1]-y)**2)
                    if part != 'r1-body':
                        pixels = [(xx, yy) for yy in range(h) for xx in range(w)
                                  if tile.getpixel((xx, yy))[3] > 128]
                        x, y = min(pixels, key=lambda p: (p[0]-x)**2+(p[1]-y)**2)
                    poses.append([round(x, 2), round(y, 2)])
                points.append(poses)
            entries[part] = {'role': 'melee', 'points': points,
                             'occludedRows': [3, 4, 5] if n == 130 and part == 'r1-mouth' else []}
        entries['r1-body']['poseOffsets'] = pose_offsets
        if n == 6:
            # Reuse the already calibrated claw/palm poses, including its late turn.
            entries['r1-hand'] = {**entries['claw'], 'occludedRows': []}
