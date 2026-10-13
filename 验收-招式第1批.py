"""R1 real-combat eight-direction tests, independent landmark transform and 1x sheets."""
import base64
import hashlib
import io
import json
import math
import os
import time
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

from 招式特效.第1批打包 import MOVES as R1

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'验收记录/招式第1批'
SHOTS = OUT/'截图'
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get('POIGHT_TEST_URL', 'http://localhost:8851/').rstrip('/')
CASTERS = dict(zip(R1, [3, 143, 68, 68, 68, 94, 21, 123, 197, 130, 212, 143,
                       143, 143, 7, 6, 6, 470, 25, 68, 448, 68, 68, 448, 94, 94, 21, 700]))
VB1 = {'vinewhip', 'scratch', 'brickbreak', 'karatechop', 'lick', 'wingattack', 'metalclaw',
       'headbutt', 'return', 'firepunch', 'absorb', 'leafblade', 'thunderpunch', 'icepunch',
       'drainpunch', 'reversal', 'crosschop', 'poisonjab', 'shadowpunch', 'peck', 'drainingkiss'}
checks, errors, samples = [], [], []


def check(name, ok, detail=None):
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})


def ready(page):
    for _ in range(400):
        if page.evaluate('window.__waterTest?.snapshot().artReady'):
            return
        time.sleep(.03)
    raise TimeoutError('art load')


def snapshot():
    return page.evaluate('window.__waterTest.snapshot()')


def step(t):
    page.evaluate('(t)=>window.__waterTest.step(t)', t)


def arrange(value):
    page.evaluate('(v)=>window.__waterTest.arrange(v)', value)


def reset(mid, direction=0, distance=None):
    page.evaluate('window.__waterTest.reset(true)')
    angle = direction*math.pi/4
    arrange({'ai': False, 'player': {'x': CX, 'y': CY, 'a': angle, 'hp': 60},
             'enemy': {'x': CX+20*math.cos(angle), 'y': CY+20*math.sin(angle), 'a': angle+math.pi}})
    if distance is None:
        distance = page.evaluate('''(id)=>{
          const a=window.__waterTest,s=a.snapshot(),c=a.catalog(),B=window.PoightBodies;
          const p={...s.player,char:c.roster.find(q=>q.id===s.player.id)};
          const t={...s.enemy,char:c.roster.find(q=>q.id===s.enemy.id)},m=c.moves[id];
          return B.meleeRange(t,Math.min(m.range,p.char.body.nominalSize*m.rangeBodies),
            Math.cos(p.a),Math.sin(p.a),p)-1;
        }''', mid)
    arrange({'enemy': {'x': CX+math.cos(angle)*distance, 'y': CY+math.sin(angle)*distance}})
    page.evaluate('(ids)=>window.__waterTest.equip("player",ids)',
                  [mid]+[x for x in moves if x != mid][:3])
    step(.3)
    return snapshot()


def cast(mid):
    return page.evaluate('(id)=>window.__waterTest.cast("player",id)', mid)


def expected(state, mid):
    if moves[mid].get('fangs'):
        p = state['enemy']
        return {'x': p['x'], 'y': p['y']+14-p['body']['visibleSize'][1]/2-p['flightHeight']}
    p = state['player']
    part = moves[mid]['anchor']
    if mid == 'closecombat' and p['attack'] and p['attack']['emitted']:
        age = next(e['age'] for e in state['generated']['states'] if e['id'] == mid)
        part = 'r1-foot' if age >= .24 else 'r1-hand2' if age >= .12 else part
    entry = roster[p['id']]['moveAnchors'][part]
    clip = catalog['art'][str(p['id'])][entry['role']]
    row, frame = p['direction'], p['animFrame']
    x, y = entry['points'][row][frame]
    dx, dy = clip.get('bodyOffsets', [[[0, 0]]])[row][frame] if 'bodyOffsets' in clip else (0, 0)
    px, py = roster[p['id']]['moveAnchors']['r1-body']['poseOffsets'][row][frame]
    dx, dy = dx+px, dy+py
    return {'x': p['x']+(x-clip['anchorX']-dx)*p['scale'],
            'y': p['y']+14+(y-clip['anchorY']-dy)*p['scale']-p['flightHeight']}


def distance(a, b):
    return math.hypot(a['x']-b['x'], a['y']-b['y'])


def tile(label):
    s = snapshot()
    data = page.locator('canvas').first.evaluate('(c)=>c.toDataURL("image/png")')
    image = Image.open(io.BytesIO(base64.b64decode(data.split(',')[1]))).convert('RGB')
    scale = image.width/s['viewport']['width']
    actors = [s['player'], s['enemy']]
    x0 = min(p['x']-p['body']['nominalSize']*.65-20 for p in actors)
    x1 = max(p['x']+p['body']['nominalSize']*.65+20 for p in actors)
    y0 = min(p['y']-p['body']['nominalSize']-p['flightHeight']-40 for p in actors)
    y1 = max(p['y']+35 for p in actors)
    span = max(180, x1-x0, y1-y0)
    cx = ((x0+x1)/2-round(s['camera']['x']))*scale
    cy = ((y0+y1)/2-round(s['camera']['y']))*scale
    half = span*scale/2
    view = image.crop((round(cx-half), round(cy-half), round(cx+half), round(cy+half))).resize(
        (240, 240), Image.Resampling.NEAREST)
    result = Image.new('RGB', (240, 260), '#273239')
    result.paste(view, (0, 20))
    ImageDraw.Draw(result).text((4, 3), label, fill='white')
    return result


try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(URL+'/?test=1')
        ready(page)
        catalog = page.evaluate('window.__waterTest.catalog()')
        moves = catalog['moves']
        roster = {c['id']: c for c in catalog['roster']}
        profile = snapshot()['profile']
        terrain = catalog['terrains'][0]
        cols, cell = terrain['columns'], terrain['cellSize']
        walk = base64.b64decode(terrain['walkB64'])
        area = next(a for a in terrain['areas'] if a['sourceName'] == 'RustboroCity')
        x, y = next((x, y) for y in range(area['gridY']+4, area['gridY']+area['rows']-4)
                    for x in range(area['gridX']+4, area['gridX']+area['columns']-4)
                    if all(walk[(y+dy)*cols+x+dx] for dy in range(-3, 4) for dx in range(-3, 4)))
        CX, CY = (x+.5)*cell, (y+.5)*cell
        # Real loaded candidate data; check economic data against T5's archived source.
        baseline = json.loads((ROOT/'协作/R1/T5数值基线.json').read_text())
        for mid, caster in CASTERS.items():
            m = moves[mid]
            check(mid+' damage/cost retained; global cooldown compression',
                  all(m[k] == baseline[mid][k] for k in ['damage','cost'])
                  and m['cd'] == min(3,max(.45,baseline[mid]['cd']*.4)))
            page.evaluate('(p)=>window.__waterTest.select(p)',
                          {**profile, 'player': caster, 'enemy': 7, 'map': 'emerald-rustborocity',
                           'playerMoves': roster[caster]['defaultMoves'], 'enemyMoves': roster[7]['defaultMoves']})
            sheet = Image.new('RGB', (1440, 1040), '#273239')
            for direction in range(8):
                name = f'{mid}/{direction}'
                s0 = reset(mid, direction)
                hp = s0['enemy']['hp']
                check(name+' pre-cast no damage', s0['hits'] == 0)
                check(name+' actual cast', cast(mid))
                reach = snapshot()['player']['attack']['range']
                budget = min(m['range'], s0['player']['body']['nominalSize']*m['rangeBodies'])
                check(name+' range capped by shared budget', reach <= budget, {'range': reach, 'budget': budget})
                check(name+' cooldown blocks recast', not cast(mid))
                step(m['windup']-.001)
                s = snapshot()
                check(name+' no windup damage', s['enemy']['hp'] == hp and s['hits'] == 0)
                if mid in VB1:
                    check(name+' VB1 no symbol before real contact', not s['animation']['bursts'])
                left, top = (direction//4)*720, (direction % 4)*260
                sheet.paste(tile(f'{direction} windup'), (left, top))
                step(.001)
                s = snapshot()
                e = next((e for e in s['generated']['states'] if e['id'] == mid), None)
                check(name+' release contact never precedes visible full front',
                      e is not None and e['front'] >= reach-1e-6 and
                      (s['enemy']['hp'] == hp or e['contacted']))
                check(name+' live anchored state', e is not None)
                if e:
                    if mid in VB1:
                        # H1 contactDelay=0: release can already be the real contact tick.
                        check(name+' VB1 symbol iff real contact on release',
                              bool(s['animation']['bursts']) == bool(e['contacted']))
                    else:
                        error = distance(e['drawAnchor'], expected(s, mid))
                        check(name+(' release target-body center <=6px' if m.get('fangs') else ' release landmark <=6px'), error <= 6, error)
                    check(name+' release front is finite and full range', math.isfinite(e['front']) and abs(e['front']-reach)<1e-6)
                step(.075)
                sheet.paste(tile(f'{direction} release'), (left+240, top))
                check(name+' zero-delay visible contact damages by 75ms', snapshot()['enemy']['hp'] < hp)
                for _ in range(60):
                    step(1/120)
                    s = snapshot()
                    if s['enemy']['hp'] < hp:
                        break
                check(name+' actual contact loses HP', s['enemy']['hp'] < hp, s['enemy']['hp'])
                e = next((e for e in s['generated']['states'] if e['id'] == mid), None)
                if e:
                    check(name+' damage not ahead of visible front', e['front'] >= reach-1e-6 and e['contacted'], e)
                sheet.paste(tile(f'{direction} hit HP={s["enemy"]["hp"]:.1f}'), (left+480, top))
                for tick in range(3):
                    step(.025)
                    s = snapshot()
                    e = next((e for e in s['generated']['states'] if e['id'] == mid), None)
                    if mid in VB1:
                        bursts = s['animation']['bursts']
                        contact = s['animation']['contacts'][-1]
                        # M8 routes lick to the continuous mouth-anchored P6 tongue, not VB1.
                        # Its real hit still creates the same timed/contact-keyed hollow burst.
                        owner = bool(bursts) and bursts[-1]['id'] == mid and (
                            (not bursts[-1].get('vb1') and bursts[-1]['key'].startswith('core-impact-'))
                            if mid == 'lick' else bursts[-1].get('vb1'))
                        label = 'P6 tongue contact ring' if mid == 'lick' else 'VB1 symbol'
                        check(name+f' {label} stays at actual hit point {tick}',
                              e is not None and owner and
                              distance(bursts[-1], contact) <= 6 and bursts[-1]['age'] <= .26)
                    else:
                        check(name+(f' target-body-follow {tick}' if m.get('fangs') else f' frame-follow {tick}'),
                              e is not None and distance(e['drawAnchor'], expected(s, mid)) <= 6)
                samples.append({'id': mid, 'direction': direction, 'range': reach, 'budget': budget,
                                'hitTime': s['elapsed']-s0['elapsed']})
                step(2)
                check(name+' no lingering state', not snapshot()['bullets'] and snapshot()['generated']['active'] == 0)
                # No homing/remote damage: distant target and once-per-cast cleanup.
                s0 = reset(mid, direction, 160)
                cast(mid)
                step(2)
                s = snapshot()
                check(name+' distant target not damaged', s['enemy']['hp'] == s0['enemy']['hp'])
                check(name+' no remote entity/out-of-bounds state', not s['bullets'] and not s['generated']['active'])
                # Real raster-map solid boundary in each heading, never a mocked clearLine.
                ux, uy = round(math.cos(direction*math.pi/4)), round(math.sin(direction*math.pi/4))
                wx, wy = next((x, y) for y in range(3, terrain['rows']-3) for x in range(3, cols-3)
                              if not walk[y*cols+x] and walk[(y-uy)*cols+x-ux]
                              and walk[(y-2*uy)*cols+x-2*ux] and walk[(y+uy)*cols+x+ux])
                reset(mid, direction)
                arrange({'player': {'x': (wx+.5-.8*ux)*cell, 'y': (wy+.5-.8*uy)*cell},
                         'enemy': {'x': (wx+.5+.8*ux)*cell, 'y': (wy+.5+.8*uy)*cell}})
                s0 = snapshot()
                check(name+' wall cast', cast(mid))
                step(m['windup']+.12)
                check(name+' solid-boundary contact consumes effect', snapshot()['generated']['active'] == 0)
                step(2)
                check(name+' wall prevents damage', snapshot()['enemy']['hp'] == s0['enemy']['hp'])
                # Like the existing projectile boundary injection, exercise the REAL
                # attached-state emitter just outside each outer world boundary.
                reset(mid, direction)
                q = snapshot()
                px = q['world']['width']+1 if ux > 0 else -1 if ux < 0 else CX
                py = q['world']['height']+1 if uy > 0 else -1 if uy < 0 else CY
                page.evaluate('(v)=>window.__waterTest.injectLimbBoundary(v)',
                              {'move': mid, 'aim': direction*math.pi/4, 'x': px, 'y': py})
                check(name+' boundary probe uses real emitter', snapshot()['generated']['active'] == 1)
                step(1/120)
                check(name+' outer world boundary consumes attached state', snapshot()['generated']['active'] == 0)
            sheet.save(SHOTS/(mid+'-八方向.png'))
            # Additional 1x 30fps sequence (right/down), with no time multiplier.
            frames = []
            for direction in [0, 2]:
                reset(mid, direction)
                cast(mid)
                seq = []
                for tick in range(27):
                    seq.append(tile(f'{mid}/{direction} t={tick/30:.3f}s 1x'))
                    step(1/30)
                frames.append(seq)
            film = [Image.new('RGB', (480, 260), '#273239') for _ in range(27)]
            for tick, image in enumerate(film):
                image.paste(frames[0][tick], (0, 0))
                image.paste(frames[1][tick], (240, 0))
            film[0].save(SHOTS/(mid+'-原速.gif'), save_all=True, append_images=film[1:], duration=33, loop=0)
        for w, h in [(1440, 900), (390, 844), (844, 390)]:
            page.set_viewport_size({'width': w, 'height': h})
            reset('drainingkiss')
            step(2)
            cast('drainingkiss')
            step(.46)
            page.screenshot(path=str(SHOTS/f'实战-{w}x{h}.png'))
        check('No JS errors', not errors, errors)
        browser.close()
finally:
    report = {'passed': sum(c['ok'] for c in checks), 'failed': sum(not c['ok'] for c in checks),
              'jsErrors': len(errors), 'errors': errors, 'checks': checks, 'samples': samples,
              'candidateSHA256': hashlib.sha256((ROOT/'候选试玩.html').read_bytes()).hexdigest(),
              'limitations': ['R1 attacks are body-attached, not traveling projectiles; actual casts test solid boundaries; test-only real-emitter injection tests out-of-world cleanup.',
                              'Landmark transforms do not replace visual anatomy approval; generic landmarks on non-audit species are approximations.']}
    (OUT/'浏览器验收.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ['passed', 'failed', 'jsErrors']}))
    if report['failed'] or errors:
        raise SystemExit(1)
