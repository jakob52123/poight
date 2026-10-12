"""R2-only overrides: keep damage/cooldown/stamina and all other moves intact."""
# id: caster, anatomical part, display width/height, pixel cap, speed, windup
ROWS = {
    'bubble': (7, 'mouth', 13, 13, 140, 65, .46),
    'waterpulse': (7, 'mouth', 26, 24, 150, 140, .46),
    'ember': (6, 'mouth', 12, 9, 160, 150, .40),
    'razorleaf': (3, 'plant', 26, 18, 180, 150, .46),
    'energyball': (3, 'plant', 26, 26, 180, 140, .55),
    'thundershock': (25, 'cheek', 27, 13, 120, 130, .40),
    'icywind': (471, 'mouth', 32, 18, 160, 120, .46),
    'rockthrow': (68, 'hand', 22, 20, 170, 140, .65),
    'mudshot': (95, 'mouth', 22, 15, 170, 145, .44),
    'confusion': (65, 'head', 26, 22, 170, 140, .48),
    'gust': (21, 'wing', 25, 22, 125, 115, .46),
    'dragonpulse': (149, 'mouth', 30, 24, 180, 145, .52),
    'swift': (143, 'mouth', 15, 15, 175, 160, .44),
    'triattack': (143, 'mouth', 18, 18, 175, 145, .52),
    'brine': (7, 'mouth', 29, 13, 150, 145, .46),
    'scald': (7, 'mouth', 30, 18, 145, 140, .50),
    'leafstorm': (3, 'plant', 34, 26, 180, 130, .60),
    'seedbomb': (3, 'plant', 22, 22, 170, 140, .55),
    'electroball': (25, 'cheek', 23, 23, 128, 125, .52),
    'iceshard': (144, 'mouth', 28, 18, 155, 160, .42),
    'aurasphere': (448, 'palms', 25, 25, 170, 150, .62),
    'focusblast': (68, 'palms', 30, 30, 180, 135, .70),
    'venoshock': (94, 'mouth', 29, 18, 165, 140, .48),
    'storedpower': (65, 'head', 26, 26, 175, 140, .60),
    'darkpulse': (197, 'mouth', 30, 23, 155, 135, .50),
}
PRESERVED = {'shadowball': 94, 'sludgebomb': 94, 'moonblast': 700}
FANS = {'bubble': 3, 'ember': 3, 'icywind': 3, 'gust': 3,
        'swift': 5, 'triattack': 3, 'leafstorm': 5}
RANGED_REVISIONS = {}
for mid, (caster, part, width, height, reach, speed, windup) in ROWS.items():
    runtime = {'kind': 'fan' if mid in FANS else 'shot', 'range': reach,
               'rangeBodies': 4, 'speed': speed, 'windup': windup,
               'recovery': .30, 'anchor': part, 'batch2': True}
    if mid in FANS:
        runtime['count'] = FANS[mid]
    if mid in ('bubble', 'triattack', 'swift'):
        runtime['fanSpread'] = {'bubble': .36, 'triattack': .30, 'swift': .24}[mid]
    if mid in ('rockthrow', 'focusblast', 'aurasphere'):
        runtime['animationRole'] = 'melee'
    if mid == 'razorleaf':
        runtime['returning'] = True
    RANGED_REVISIONS[mid] = {'caster': caster, 'mode': 'shot', 'width': width,
                             'height': height, 'reach': reach, 'runtime': runtime}


def prepare(root, record, specs):
    """Extend the SAME record/specs consumed by the T5 atlas packer."""
    import json

    manifest = json.loads((root / '招式特效/第2批/图集记录.json').read_text())
    for mid, d in RANGED_REVISIONS.items():
        if mid in manifest:
            receipt = manifest[mid]
            record['assets'][mid] = {'output': receipt['output'],
                                     'outputSHA256': receipt['outputSHA256']}
            specs[mid] = {k: v for k, v in d.items() if k != 'runtime'}
            specs[mid].update(receipt['drawing'])


def finish(mid, drawing, runtime):
    if mid not in RANGED_REVISIONS:
        return
    revision = RANGED_REVISIONS[mid]
    runtime.update(revision['runtime'])
    drawing.update(width=revision['width'], height=revision['height'], batch2=True)
