"""Headless real combat: eight directions, landmarks, timing, range and collision.
PNG sheets use real simulation draws, never a separate move preview renderer.
VH revision: camera-top lightning, hollow ring/target-color retention, three separate timed claws.
"""
import base64
import hashlib
import io
import json
import math
import os
import runpy
import subprocess
import time
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/主角八招重做'
SHOTS = OUT / '截图'
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get('POIGHT_TEST_URL', 'http://localhost:8877/').rstrip('/')
DEFAULTS = {25: ['thunderbolt', 'quickattack', 'irontail', 'thunder'],
            6: ['flamethrower', 'fireblast', 'dragonclaw', 'airslash']}
checks, errors, samples = [], [], []
pixel_samples = []


def check(name, ok, detail=None):
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})


def ready(page):
    for _ in range(400):
        if page.evaluate('window.__waterTest?.snapshot().artReady'):
            return
        time.sleep(.03)
    raise TimeoutError('art load')


def snap():
    return page.evaluate('window.__waterTest.snapshot()')


def step(t):
    page.evaluate('(t)=>window.__waterTest.step(t)', t)


def arrange(data):
    page.evaluate('(d)=>window.__waterTest.arrange(d)', data)


def reset(mid, direction=0, distance=None):
    page.evaluate('window.__waterTest.reset(true)')
    m = moves[mid]
    distance = distance if distance is not None else (20 if m['kind'] == 'melee' else 85)
    angle = direction * math.pi / 4
    arrange({'ai': False, 'player': {'x': CX, 'y': CY, 'a': angle},
             'enemy': {'x': CX + math.cos(angle)*distance,
                       'y': CY + math.sin(angle)*distance, 'a': angle+math.pi}})
    step(.3)
    return snap()


def cast(mid):
    return page.evaluate('(id)=>window.__waterTest.cast("player",id)', mid)


def frame_tile(label):
    # Same backing pixels and crop; transport the crop instead of encoding the whole map.
    data = page.locator('canvas').first.evaluate('''c=>{
      const s=window.__waterTest.snapshot(), scale=c.width/s.viewport.width;
      const x=((s.player.x+s.enemy.x)/2-Math.round(s.camera.x))*scale;
      const y=((s.player.y+s.enemy.y)/2-Math.round(s.camera.y))*scale;
      const left=Math.round(x-140*scale), top=Math.round(y-195*scale);
      const crop=document.createElement('canvas');
      crop.width=Math.round(x+140*scale)-left;crop.height=Math.round(y+85*scale)-top;
      crop.getContext('2d').drawImage(c,left,top,crop.width,crop.height,0,0,crop.width,crop.height);
      return crop.toDataURL();
    }''')
    image = Image.open(io.BytesIO(base64.b64decode(data.split(',')[1]))).convert('RGB')
    tile = image.resize((280, 280))
    result = Image.new('RGB', (280, 300), '#273239')
    result.paste(tile, (0, 20))
    ImageDraw.Draw(result).text((5, 3), label, fill='white')
    return result


def expected_anchor(state, mid):
    p = state['player']
    entry = roster[p['id']]['moveAnchors'].get(moves[mid]['anchor'])
    if not entry:
        return None
    clip = catalog['art'][str(p['id'])][entry['role']]
    row, f = p['direction'], p['animFrame']
    x, y = entry['points'][row][f]
    dx, dy = clip.get('bodyOffsets', [[[0, 0]]])[row][f] if 'bodyOffsets' in clip else (0, 0)
    return {'x': p['x']+(x-clip['anchorX']-dx)*p['scale'],
            'y': p['y']+14+(y-clip['anchorY']-dy)*p['scale']-p['flightHeight']}


def separation(a, b):
    return math.hypot(a['x']-b['x'], a['y']-b['y'])


try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(URL+'/?test=1')
        ready(page)
        catalog = page.evaluate('window.__waterTest.catalog()')
        roster = {c['id']: c for c in catalog['roster']}
        moves = catalog['moves']
        initial = snap()['profile']
        terrain = catalog['terrains'][0]
        cols, cell = terrain['columns'], terrain['cellSize']
        walk = base64.b64decode(terrain['walkB64'])
        area = next(a for a in terrain['areas'] if a['sourceName'] == 'RustboroCity')
        x, y = next((x, y) for y in range(area['gridY']+4, area['gridY']+area['rows']-4)
                    for x in range(area['gridX']+4, area['gridX']+area['columns']-4)
                    if all(walk[(y+dy)*cols+x+dx] for dy in range(-3, 4) for dx in range(-3, 4)))
        CX, CY = (x+.5)*cell, (y+.5)*cell
        # Compare untouched data to M2, preserving T8 Splash and T9 HP integration.
        baseline = {'__name__': 'baseline'}
        # Trusted local baseline fixture, no network or user-controlled source.
        exec(subprocess.check_output(['git', 'show', '0dd16ae:游戏数据.py'], cwd=ROOT), baseline)  # noqa: S102
        raw_rows = json.loads((ROOT/'素材/角色库/角色库.json').read_text())
        base_roster = {c['id']: c for c in baseline['roster_metadata'](
            [r for r in raw_rows if r['id'] in roster])}
        hero_ids = {mid for ids in DEFAULTS.values() for mid in ids}
        from 招式特效.第2批参数 import RANGED_REVISIONS
        from 游戏数据 import MOVES
        # S1 explicitly replaces all burn and electric slow; all other fields remain exact.
        expected_moves = {mid: {k: v for k, v in m.items()
                               if k != 'burn' and not (k == 'slow' and m['type'] == 13)}
                          for mid, m in baseline['MOVES'].items()}
        check('Other 88 definitions unchanged except authorized R2 revisions/S1 field deletions', all(
            m == expected_moves[mid] for mid, m in MOVES.items()
            if mid not in hero_ids and mid not in RANGED_REVISIONS))
        check('S1 removes all burn and electric slow without legacy fallback', all(
            'burn' not in m and (m['type'] != 13 or 'slow' not in m) for m in MOVES.values()))
        original_ids = set(json.loads((ROOT/'首发50.json').read_text())['ids'])
        check('Other original 48 default loadouts unchanged', original_ids <= roster.keys() and all(
            roster[n]['defaultMoves'] == base_roster[n]['defaultMoves'] for n in original_ids if n not in DEFAULTS))
        # R200b explicitly changes only the added 150 defaults; keep the original48 golden intact.
        from 游戏数据 import roster_metadata
        expected_new = {c['id']: c for c in roster_metadata([r for r in raw_rows if r['id'] in roster])}
        check('New150 defaults match authorized learned-move model', all(
            c['defaultMoves'] == expected_new[n]['defaultMoves'] for n,c in roster.items() if n not in original_ids))
        for n, ids in DEFAULTS.items():
            check(f'{n} exact default four', roster[n]['defaultMoves'] == ids)
            check(f'{n} other legal moves remain selectable', len(set(roster[n]['learnset'])-set(ids)) > 0)
        for mid in hero_ids-{'thunder'}:
            check(mid+' damage/cost retained; global cooldown compression',
                  all(moves[mid][k] == baseline['MOVES'][mid][k] for k in ['damage','cost'])
                  and moves[mid]['cd'] == min(3,max(.45,baseline['MOVES'][mid]['cd']*.4)))
        check('Flamethrower faster than Fire Blast', moves['flamethrower']['speed'] > moves['fireblast']['speed'])
        check('Thunder delay 0.6-0.8 seconds from cast', .6 <= moves['thunder']['windup']+moves['thunder']['delay'] <= .8)
        for n, ids in DEFAULTS.items():
            profile = {**initial, 'player': n, 'enemy': 7, 'map': 'emerald-rustborocity',
                       'playerMoves': ids, 'enemyMoves': roster[7]['defaultMoves']}
            page.evaluate('(p)=>window.__waterTest.select(p)', profile)
            for mid in ids:
                print('Behavior:', mid, flush=True)
                m = moves[mid]
                sheet = Image.new('RGB', (1680, 1200), '#273239')
                for direction in range(8):
                    prefix = f'{mid}/{direction}'
                    left, top = (direction//4)*840, (direction % 4)*300
                    s0 = reset(mid, direction)
                    hp = s0['enemy']['hp']
                    check(prefix+' no pre-cast damage', s0['hits'] == 0)
                    check(prefix+' cast', cast(mid))
                    s = snap()
                    reach = s['player']['attack']['range']
                    body = s['player']['body']['nominalSize']
                    check(prefix+' body-based range <=5 lengths', reach <= 5*body)
                    check(prefix+' cooldown blocks recast', not cast(mid))
                    if mid == 'quickattack':
                        check(prefix+' zero windup', s['player']['attack']['hitTime'] == 0 and s['player']['attack']['emitted'])
                    else:
                        step(m['windup']-.001)
                        check(prefix+' no damage before release', snap()['enemy']['hp'] == hp and not snap()['bullets'])
                    sheet.paste(frame_tile(f'{direction} windup (QA: t=0)'), (left, top))
                    step(.001)
                    s = snap()
                    expected = expected_anchor(s, mid)
                    if m['kind'] in ['shot', 'beam']:
                        b = s['bullets'][0]
                        visual = {'x': b['sx']+b['visualOffsetX'],
                                  'y': b['sy']-16-s['player']['visualLift']+b['visualOffset']}
                        error = separation(visual, expected)
                        check(prefix+' release within 6px of sprite landmark', error <= 6, error)
                    elif mid == 'thunder':
                        e = s['generated']['states'][0]
                        check(prefix+' fixed ground anchor <=6px', separation({'x': e['ex'], 'y': e['ey']}, s0['enemy']) <= 6)
                    else:
                        e = next(e for e in s['generated']['states'] if e['id'] == mid)
                        actual = e.get('drawAnchor') or s['player']['attack']['anchor']
                        check(prefix+' attached within 6px of current sprite frame', separation(actual, expected) <= 6)
                    step(.12 if m['kind'] == 'beam' else .08 if m['kind'] == 'shot' else .04 if m['kind'] == 'rush' else .02)
                    if mid == 'thunder':
                        step(.44)
                        check(prefix+' no damage during warning', snap()['enemy']['hp'] == hp)
                        step(.05)
                    sheet.paste(frame_tile(f'{direction} release'), (left+280, top))
                    if mid == 'quickattack':
                        s = snap()
                        check(prefix+' real displacement and trail', separation(s['player'], s0['player']) > 0 and s['ghosts'] > 0)
                    # Find the actual first damaging simulation frame.
                    page.evaluate('''hp=>{
                      const api=window.__waterTest;
                      for(let i=0;i<150;i++) {
                        if(api.snapshot().enemy.hp<hp)break;
                        api.step(1/120, false);
                      }
                      api.step(0);
                    }''', hp)
                    hit = snap()
                    check(prefix+' actual contact damages', hit['enemy']['hp'] < hp, hit['enemy']['hp'])
                    if mid == 'thunder':
                        step(.12)  # The separate ground-burst frame after the bolt.
                    sheet.paste(frame_tile(f'{direction} hit hp={hit["enemy"]["hp"]:.1f}'), (left+560, top))
                    if m['kind'] == 'melee':
                        for tick in range(3):
                            step(.04)
                            attached = snap()
                            e = next(e for e in attached['generated']['states'] if e['id'] == mid)
                            check(prefix+f' frame-follow {tick}', separation(e['drawAnchor'], expected_anchor(attached, mid)) <= 6)
                    samples.append({'id': mid, 'direction': direction, 'range': reach,
                                    'bodyLength': body, 'hitTime': hit['elapsed']-s0['elapsed']})
                    step(2)
                    check(prefix+' no lingering hitbox/projectile', not snap()['bullets'] and snap()['generated']['active'] == 0)
                    # Miss into open space: track real projectile travel, no endpoint-only assertion.
                    reset(mid, direction, 85)
                    cast(mid)
                    arrange({'enemy': {'x': CX+260, 'y': CY+260}})
                    max_travel = 0
                    travel_frames = page.evaluate('''()=>{
                      const frames=[],api=window.__waterTest;
                      for(let i=0;i<160;i++) {
                        api.step(.01, false);
                        const s=api.snapshot();
                        frames.push({bullets:s.bullets});
                      }
                      api.step(0);
                      return frames;
                    }''')
                    for q in travel_frames:
                        for b in q['bullets']:
                            max_travel = max(max_travel, math.hypot(b['x']-b['sx'], b['y']-b['sy']))
                            check(prefix+' projectile retains cast direction', abs(b['ux']-math.cos(direction*math.pi/4)) < .001 and abs(b['uy']-math.sin(direction*math.pi/4)) < .001)
                    check(prefix+' measured travel <=5 lengths', max_travel <= 5*body, max_travel)
                    check(prefix+' miss expires', not snap()['bullets'] and snap()['generated']['active'] == 0)
                    if mid == 'thunder':
                        check(prefix+' dodge before lightning prevents damage', snap()['enemy']['hp'] == hp)
                    # Test actual world-bound removal on all eight projectile headings.
                    if m['kind'] in ['shot', 'beam']:
                        reset(mid, direction)
                        q = snap()
                        ux, uy = math.cos(direction*math.pi/4), math.sin(direction*math.pi/4)
                        page.evaluate('(v)=>window.__waterTest.injectWater(v)', {
                            'owner': 'player', 'move': mid, 'ux': ux, 'uy': uy,
                            'x': q['world']['width']-25.1 if ux > .1 else 25.1 if ux < -.1 else CX,
                            'y': q['world']['height']-30.1 if uy > .1 else 45.1 if uy < -.1 else CY,
                            'range': reach, 'speed': m['speed']})
                        step(.02)
                        check(prefix+' boundary consumes projectile', not snap()['bullets'])
                sheet.save(SHOTS/(mid+'-八方向.png'))
                # Wall lies between actor and target; anchored/zone moves must not damage across it.
                for direction in range(8):
                    ux = round(math.cos(direction*math.pi/4))
                    uy = round(math.sin(direction*math.pi/4))
                    wx, wy = next((x, y) for y in range(3, terrain['rows']-3)
                                  for x in range(3, cols-3)
                                  if not walk[y*cols+x]
                                  and walk[(y-uy)*cols+x-ux]
                                  and walk[(y-2*uy)*cols+x-2*ux]
                                  and walk[(y+uy)*cols+x+ux])
                    reset(mid, direction)
                    arrange({'player': {'x': (wx+.5-.8*ux)*cell, 'y': (wy+.5-.8*uy)*cell},
                             'enemy': {'x': (wx+.5+.8*ux)*cell, 'y': (wy+.5+.8*uy)*cell}})
                    wall_start = snap()
                    check(f'{mid}/{direction} wall test cast', cast(mid))
                    step(m['windup']+.15)
                    if m['kind'] in ['beam', 'shot']:
                        check(f'{mid}/{direction} wall consumes before range expiry', not snap()['bullets'])
                    if mid == 'fireblast':
                        check(f'{mid}/{direction} wall creates five-way visual burst (no damage)',
                              any(e['id'] == mid and e['wall'] for e in snap()['animation']['hero']['events']))
                    step(2)
                    q = snap()
                    check(f'{mid}/{direction} wall prevents damage and expires effect',
                          q['enemy']['hp'] == wall_start['enemy']['hp']
                          and not q['bullets'] and not q['generated']['active'])
                    if mid == 'quickattack':
                        progress = ((q['player']['x']-wall_start['player']['x'])*ux
                                    + (q['player']['y']-wall_start['player']['y'])*uy)
                        check(f'{mid}/{direction} swept rush does not cross wall', progress < cell)
                if mid == 'thunder':
                    reset(mid, distance=220)
                    check('Thunder casts beyond body-scaled range with clamped landing', cast(mid))
                    s = snap()
                    point = s['player']['attack']['targetPoint']
                    dx, dy = point['x']-s['player']['x'], point['y']-s['player']['y']
                    check('Thunder out-of-range landing keeps original maximum range',
                          abs(math.hypot(dx, dy)-s['player']['attack']['range']) < 1)
                    check('Thunder out-of-range landing faces opponent', abs(math.atan2(dy, dx)) < .0873)
        pixel_samples = runpy.run_path(str(ROOT / 'tests/主角外观验收.py'))['run'](
            page, ROOT, URL, check)
        for mid in ['thunder', 'dragonclaw']:
            check(mid+' revised raster covers both A arenas and all eight headings',
                  len([p for p in pixel_samples if p['id'] == mid and p.get('revisionFrames')]) == 16)
        # Three required responsive screenshots, same real battle and assets.
        page.evaluate('(p)=>window.__waterTest.select(p)', {
            **initial, 'player': 25, 'enemy': 6, 'playerMoves': DEFAULTS[25],
            'enemyMoves': DEFAULTS[6], 'map': 'emerald-rustborocity'})
        for w, h in [(1440, 900), (390, 844), (844, 390)]:
            page.set_viewport_size({'width': w, 'height': h})
            reset('thunderbolt')
            step(2)  # Let the real camera settle after responsive resizing.
            cast('thunderbolt')
            step(.52)
            page.screenshot(path=str(SHOTS/f'实战-{w}x{h}.png'))
        check('No JS errors', not errors, errors)
        browser.close()
finally:
    report = {'passed': sum(c['ok'] for c in checks), 'failed': sum(not c['ok'] for c in checks),
              'jsErrors': len(errors), 'errors': errors, 'checks': checks, 'samples': samples,
              'pixelSamples': pixel_samples,
              'candidateSHA256': hashlib.sha256((ROOT/'候选试玩.html').read_bytes()).hexdigest(),
              'limitations': ['Boundary injection covers traveling projectiles; melee/zone have no traveling entity.',
                              'Automated landmark agreement does not replace anatomical visual review.']}
    (OUT/'浏览器验收.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ['passed', 'failed', 'jsErrors']}, ensure_ascii=False))
    if report['failed'] or errors:
        raise SystemExit(1)
