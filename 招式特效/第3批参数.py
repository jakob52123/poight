"""R3-only runtime overrides. Damage, cooldown, cost and protected moves untouched."""
MOVES = {}


def move(mid, kind, reach, bodies, windup, anchor, **kw):
    MOVES[mid] = dict(kind=kind, range=reach, rangeBodies=bodies, windup=windup,
                      anchor=anchor, recovery=.28, r3=True, **kw)


move('watergun', 'beam', 140, 4.2, .32, 'mouth', speed=190, radius=3)
move('hydropump', 'beam', 180, 4.5, .45, 'mouth', speed=185, radius=8)
move('solarbeam', 'beam', 180, 4.5, .85, 'flower', speed=350, radius=4)
move('icebeam', 'beam', 170, 4.5, .42, 'mouth', speed=210, radius=4)
move('psybeam', 'beam', 170, 4.5, .4, 'head', speed=180, radius=4)
move('dragonbreath', 'beam', 135, 4, .42, 'mouth', speed=170, radius=7)
move('hyperbeam', 'beam', 190, 4.5, .85, 'mouth', speed=350, radius=7)
move('signalbeam', 'beam', 155, 4.5, .42, 'head', speed=180, radius=3)
move('gigadrain', 'beam', 160, 4.3, .5, 'flower', speed=160, radius=4)
move('freezedry', 'beam', 150, 4.3, .42, 'mouth', speed=170, radius=3)
move('flashcannon', 'beam', 170, 4.5, .48, 'cannon', speed=190, radius=5)
move('absorb', 'melee', 38, .9, .32, 'mouthMelee')
# Rush range measures the actual body's travel, not a detached hitbox.
move('aquajet', 'rush', 120, 3.3, .3, 'r3body', rushSpeed=240)
move('surf', 'rush', 150, 3.3, .42, 'foot', rushSpeed=180)
move('flamecharge', 'rush', 120, 3.3, .36, 'r3body', rushSpeed=230)
move('tackle', 'rush', 75, 1.8, .3, 'r3body', rushSpeed=170)
move('machpunch', 'rush', 60, 1.5, .26, 'hand', rushSpeed=230)
move('bodyslam', 'rush', 75, 1.8, .5, 'r3body', rushSpeed=150)
move('doubleedge', 'rush', 120, 2.8, .46, 'r3body', rushSpeed=240)
move('waterfall', 'rush', 100, 2.8, .36, 'r3body', rushSpeed=200)
move('flamewheel', 'rush', 105, 3, .36, 'r3body', rushSpeed=210)
move('spark', 'rush', 105, 3.2, .32, 'r3body', rushSpeed=250)
move('rollout', 'rush', 120, 2.8, .4, 'r3body', rushSpeed=210)
move('zenheadbutt', 'rush', 100, 2.5, .4, 'headMelee', rushSpeed=210)
move('shadowsneak', 'rush', 115, 3, .4, 'foot', rushSpeed=190)
move('bravebird', 'rush', 145, 3.5, .4, 'r3body', rushSpeed=360)

ALL = list(MOVES) + ['wildcharge', 'phantomforce']
BODY_ONLY = {'tackle', 'machpunch', 'bodyslam', 'doubleedge', 'rollout'}
NEW_ART = {'hyperbeam', 'psybeam', 'freezedry', 'gigadrain', 'absorb',
           'flamecharge', 'waterfall', 'spark', 'zenheadbutt', 'shadowsneak'}
CASTERS = {**dict.fromkeys(['solarbeam', 'gigadrain', 'absorb'], 3),
           **dict.fromkeys(['watergun', 'aquajet', 'waterfall'], 7),
           **dict.fromkeys(['hydropump', 'icebeam', 'surf', 'flashcannon'], 9),
           **dict.fromkeys(['tackle', 'bodyslam', 'doubleedge', 'hyperbeam'], 143),
           'flamecharge': 6, 'flamewheel': 4, 'machpunch': 68, 'psybeam': 65,
           'signalbeam': 123, 'dragonbreath': 149, 'spark': 25, 'wildcharge': 25,
           'freezedry': 471, 'rollout': 95, 'zenheadbutt': 65,
           'shadowsneak': 94, 'phantomforce': 94, 'bravebird': 146}


def prepare(root, record, specs):
    """Extend the existing four-frame atlas pack; never replace unrelated slots."""
    import json
    folder = root / '招式特效/第3批'
    for mid in MOVES:
        receipt = folder / mid / '来源.json'
        if mid in NEW_ART and not receipt.exists():
            raise FileNotFoundError(f'R3 art receipt missing: {receipt}; no geometric fallback')
        if receipt.exists():
            rec = json.loads(receipt.read_text())['processing']
            record['assets'][mid] = {'output': rec['output'], 'outputSHA256': rec['outputSHA256']}
            brief = json.loads((folder / mid / 'brief.json').read_text())
            mode = 'stream' if brief['mode'] == 'stream' else 'melee' if mid == 'absorb' else 'rush'
            specs[mid] = {'id': mid, 'mode': mode, 'width': 40, 'height': 40,
                          'reach': MOVES[mid]['range'], 'caster': CASTERS[mid],
                          'fw': rec['frameSize'][0], 'fh': rec['frameSize'][1],
                          'ax': rec['anchorPx'][0], 'ay': rec['anchorPx'][1]}


def finish(mid, drawing, runtime):
    if mid not in MOVES:
        return
    runtime.update(MOVES[mid])
    drawing['r3'] = True
    if runtime['kind'] == 'beam':
        drawing.update(mode='stream', height={'watergun': 8, 'hydropump': 24,
                       'solarbeam': 14, 'icebeam': 9, 'psybeam': 12, 'dragonbreath': 20,
                       'hyperbeam': 22, 'signalbeam': 10, 'gigadrain': 10,
                       'freezedry': 8, 'flashcannon': 14}[mid])
    if mid == 'flamecharge':
        drawing.update(width=76, height=68)
    if mid == 'spark':
        drawing.update(width=46, height=36)
    if mid == 'waterfall':
        drawing.update(width=44, height=48)
    if mid == 'zenheadbutt':
        drawing.update(width=30, height=28)
    if mid == 'aquajet':
        drawing.update(width=46, height=32)
    if mid == 'bravebird':
        drawing.update(width=58, height=42)
    if mid == 'flamewheel':
        drawing.update(width=44, height=44)
    if mid == 'surf':
        drawing.update(mode='ride', width=94, height=56)
