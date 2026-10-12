"""R1-only raster slots and backward-compatible runtime overrides.
The source MOVES damage/CD/cost and all eight hero slots remain untouched.
"""
import hashlib
import json

# anchor, display size, windup: range is min(42px, 1.5 nominal lengths).
MOVES = {
    'vinewhip': ('r1-vine', (44, 25), .34),
    'scratch': ('r1-hand', (19, 18), .28),
    'brickbreak': ('r1-hand', (16, 25), .34),
    'closecombat': ('r1-hand', (21, 19), .36),
    'karatechop': ('r1-hand', (16, 24), .32),
    'lick': ('r1-mouth', (24, 10), .32),
    'wingattack': ('r1-wing', (18, 10), .32),
    'bugbite': ('r1-mouth', (15, 13), .30),
    'bite': ('r1-mouth', (16, 14), .30),
    'crunch': ('r1-mouth', (21, 20), .36),
    'metalclaw': ('r1-hand', (18, 16), .30),
    'headbutt': ('r1-head', (15, 13), .34),
    'return': ('r1-hand', (18, 16), .32),
    'rapidspin': ('r1-body', (38, 25), .32),
    'aquatail': ('r1-tail', (22, 14), .36),
    'firepunch': ('r1-hand', (15, 16), .34),
    'firefang': ('r1-mouth', (16, 14), .32),
    'leafblade': ('r1-leaf', (25, 14), .34),
    'thunderpunch': ('r1-hand', (14, 15), .32),
    'icepunch': ('r1-hand', (17, 17), .34),
    'drainpunch': ('r1-hand', (16, 17), .34),
    'reversal': ('r1-hand', (20, 18), .38),
    'crosschop': ('r1-hand', (20, 20), .38),
    'bonerush': ('r1-hand', (34, 25), .44),
    'poisonjab': ('r1-hand', (16, 12), .32),
    'shadowpunch': ('r1-hand', (17, 17), .34),
    'peck': ('r1-mouth', (9, 7), .28),
    'drainingkiss': ('r1-mouth', (12, 12), .34),
}


def prepare(root, record, specs):
    """Add generated additions to the existing atlas packer; fail closed if absent."""
    for mid in MOVES:
        receipt_path = root/'招式特效/第1批'/mid/'来源.json'
        if not receipt_path.exists():
            if mid not in specs:
                raise FileNotFoundError(f'R1 artwork not ready: {mid}')
            continue  # existing raster is reused, never regenerated gratuitously
        receipt = json.loads(receipt_path.read_text())['processing']
        path = root/'招式特效/第1批'/mid/(mid+'-动画.png')
        assert hashlib.sha256(path.read_bytes()).hexdigest() == receipt['outputSHA256']
        record['assets'][mid] = {'output': str(path.relative_to(root)),
                                 'outputSHA256': receipt['outputSHA256']}
        specs[mid] = {'mode': 'melee', 'width': 20, 'height': 20, 'reach': 42,
                      'caster': receipt['caster'], 'fw': receipt['frameSize'][0],
                      'fh': receipt['frameSize'][1], 'ax': receipt['anchorPx'][0],
                      'ay': receipt['anchorPx'][1]}


def finish(mid, drawing, runtime):
    if mid not in MOVES:
        return
    anchor, size, windup = MOVES[mid]
    drawing.update(width=size[0], height=size[1], limb=True)
    runtime.update(kind='spin' if mid == 'rapidspin' else 'melee', limb=True,
                   anchor=anchor, range=42, rangeBodies=1.5, windup=windup,
                   recovery=.48 if mid in ('closecombat', 'rapidspin', 'bonerush') else .38,
                   contactDelay=.10, contactWindow=.22)
    if mid in ('vinewhip', 'leafblade', 'bonerush', 'lick', 'aquatail'):
        drawing['attachSource'] = True
    if mid == 'bonerush':
        # Grip at the actual proximal bone end of EACH source pose, not canvas-left.
        drawing['frameAnchors'] = [[62, 220], [43, 228], [59, 84], [43, 98]]
    if mid == 'vinewhip':
        drawing['frameAnchors'] = [[55, 125], [55, 120], [55, 120], [55, 128]]
