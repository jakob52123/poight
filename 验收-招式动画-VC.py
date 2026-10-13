"""VC: actual eight-direction combat, native raster, original-speed GIFs and old-mode comparison."""
import base64
import hashlib
import io
import json
import math
import os
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/招式动画-VC'
SHOTS = OUT / '截图'
SHOTS.mkdir(parents=True, exist_ok=True)
IDS = ['surf', 'dazzlinggleam', 'boomburst', 'explosion', 'waterspout', 'heatwave',
       'discharge', 'bulldoze', 'blizzard', 'rockslide', 'hex', 'psychic', 'inferno',
       'iciclecrash', 'earthpower', 'poisongas', 'dracometeor', 'synthesis', 'recover',
       'rest', 'aquaring', 'agility', 'focusenergy', 'protect']
SUPPORT = {'synthesis', 'recover', 'rest', 'aquaring', 'agility', 'focusenergy', 'protect'}
SHOTS_IDS = {'blizzard', 'poisongas'}
URL = os.environ.get('POIGHT_TEST_URL', 'http://localhost:8876/').rstrip('/')
FONT = ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc', 12)
checks, errors, samples, pixels = [], [], [], []
failure = None
selected_scenes = {}
record_signature = hashlib.sha256(b''.join((ROOT / p).read_bytes() for p in
                                         ['招式动画VC.js', '招式动画/VC打包.py'])).hexdigest()
record_path = OUT / '录制缓存.json'
record_cache = json.loads(record_path.read_text()) if record_path.exists() else {}


def check(name, ok, detail=None):
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
    if not ok:
        print('FAIL ' + name + ' ' + json.dumps(detail, ensure_ascii=False), flush=True)
    if not ok:
        print('FAIL', name, detail, flush=True)


def ready(p):
    for _ in range(600):
        if p.evaluate('''()=>{try{return window.__waterTest?.snapshot().artReady}
                             catch{return false}}'''):
            return
        time.sleep(.03)
    raise TimeoutError('loading')


def snap():
    return page.evaluate('window.__waterTest.snapshot()')


def step(t):
    page.evaluate('(t)=>window.__waterTest.step(t)', t)


def reset(mid, direction=0, scene='arena-formal', distance=65):
    if selected_scenes.get(page) != scene:
        page.evaluate('(p)=>window.__waterTest.select(p)', {
            **profile, 'map': scene, 'player': 9, 'enemy': 7,
            'playerMoves': roster[9]['defaultMoves'], 'enemyMoves': roster[7]['defaultMoves'],
        })
        selected_scenes[page] = scene
    page.evaluate('window.__waterTest.reset(true)')
    s = snap()
    bounds = s['environment']['bounds']
    # Sample actual clay, outside A1's enlarged center emblem.
    x = (bounds['left'] + bounds['right']) / 2 - (450 if scene == 'arena-formal' else 0)
    y = (bounds['top'] + bounds['bottom']) / 2 - 95
    a = direction * math.pi / 4
    page.evaluate('(v)=>window.__waterTest.arrange(v)', {
        'ai': False, 'player': {'x': x, 'y': y, 'a': a, 'hp': s['player']['maxHP'] - 40},
        'enemy': {'x': x + math.cos(a) * distance, 'y': y + math.sin(a) * distance},
    })
    page.evaluate('(id)=>window.__waterTest.equip("player",[id])', mid)
    step(.1)
    return snap()


def cast(mid):
    return page.evaluate('(id)=>window.__waterTest.cast("player",id)', mid)


def tile(label, size=280):
    data = page.locator('#game').evaluate('''(c,size)=>{
      const s=window.__waterTest.snapshot(),scale=c.width/s.viewport.width,
        x=((s.player.x+s.enemy.x)/2-s.camera.x)*scale,
        y=((s.player.y+s.enemy.y)/2-20-s.camera.y)*scale,
        half=150*scale,t=document.createElement('canvas');
      t.width=size;t.height=size;const ctx=t.getContext('2d');ctx.imageSmoothingEnabled=false;
      ctx.drawImage(c,Math.round(x-half),Math.round(y-half),Math.round(half*2),
        Math.round(half*2),0,0,size,size);return t.toDataURL();
    }''', size)
    im = Image.open(io.BytesIO(base64.b64decode(data.split(',')[1]))).convert('RGB')
    result = Image.new('RGB', (size, size + 24), '#223540')
    result.paste(im, (0, 24))
    ImageDraw.Draw(result).text((5, 4), label, fill='white', font=FONT)
    return result


def first_event(mid, initial):
    return page.evaluate('''({id,initial})=>{
      const api=window.__waterTest;let previous=api.snapshot();
      for(let tick=1;tick<=480;tick++){
        api.step(1/120,false);const s=api.snapshot();
        const event=s.enemy.hp<initial.enemy.hp ||
          (['synthesis','recover','rest','aquaring'].includes(id) && s.player.hp>initial.player.hp) ||
          (['agility','focusenergy','protect'].includes(id) && s.generated.states.some(e=>e.id===id));
        if(event){api.step(0);return {tick,hit:api.snapshot(),previous}}previous=s;
      }return {tick:null,hit:null,previous};
    }''', {'id': mid, 'initial': initial})


def comparison_time(mid, move):
    if mid in SHOTS_IDS:
        delay = .025
    elif mid in SUPPORT:
        delay = .06 if mid == 'agility' else .3
    elif move['kind'] == 'nova':
        delay = .27
    elif move['kind'] == 'zone':
        delay = (max(.4, 65/170) if mid == 'earthpower' else
                 max(.65, move.get('delay', .75))) + .025
    else:
        delay = .18
    return move['windup'] + delay


def capture_comparison(mid, instant, old_page):
    global page
    reset(mid)
    cast(mid)
    step(instant)
    after = tile('NEW ' + mid + f' {instant:.3f}s')
    current = page
    try:
        page = old_page
        reset(mid)
        cast(mid)
        step(instant)
        before = tile('OLD ' + mid + f' {instant:.3f}s')
    finally:
        page = current
    before.save(SHOTS / f'{mid}-old.png')
    after.save(SHOTS / f'{mid}-new.png')


def pixel_case(mid, scene):
    initial = reset(mid, scene=scene)
    cast(mid)
    found = first_event(mid, initial)
    if not found['hit']:
        check(mid + scene + ' pixel actual event exists', False)
        return
    ticks = found['tick']
    reset(mid, scene=scene)
    page.evaluate('window.vcProbe.enabled=false;window.vcProbe.last=null')
    cast(mid)
    # Support has no attack contact: measure one real rendered tick after release.
    count = ticks + 2 if mid in SUPPORT else ticks if mid in {'hex', 'psychic'} else max(1, ticks - 1)
    page.evaluate('(n)=>window.__waterTest.step(n/120,false)', count)
    page.evaluate('window.vcProbe.enabled=true;window.__waterTest.step(0)')
    measurement = page.evaluate('window.measureVCPixels()')
    for key in ['composite', 'background', 'mask']:
        data = measurement.pop(key)
        Image.open(io.BytesIO(base64.b64decode(data.split(',')[1]))).save(
            SHOTS / f'像素-{scene}-{mid}-{key}.png')
    tag = f'{mid}/{scene}'
    check(tag + ' actual opaque body raster', measurement['count'] > 20, measurement)
    check(tag + ' S>=.55 and attribute coverage>=30%', measurement['saturation'] >= .55 and
          measurement['colorFraction'] >= .3, measurement)
    check(tag + ' actual same-position mean luma delta>=60', measurement['contrast'] >= 60, measurement)
    height = snap()['player']['body']['visibleSize'][1]
    if mid in SHOTS_IDS:
        check(tag + ' individual opaque projectile diameter>=max(14,.30H)',
              measurement['opaqueSpriteDiameter'] >= max(14, height * .3), measurement)
    else:
        check(tag + ' recognizable opaque symbol extent>=.30H',
              max(measurement['width'], measurement['height']) >= max(14, height * .3), measurement)
    if measurement['method'] == 'drawNova':
        state = next(e for e in snap()['generated']['states'] if e['id'] == mid)
        check(tag + ' physical radius in actual opaque wave raster',
              measurement['radialMin'] <= state['radius'] <= measurement['radialMax'])
    pixels.append({'scene': scene, **measurement})
    page.evaluate('window.vcProbe.enabled=false')


try:
    baseline = json.loads((ROOT / '验收记录/招式第3批/受保护图集.json').read_text())
    record = json.loads((ROOT / '招式特效/生图重做/实景预览/构建记录.json').read_text())['assets']
    guards = []
    for mid in ['thunderbolt', 'quickattack', 'irontail', 'thunder', 'flamethrower',
                'fireblast', 'dragonclaw', 'airslash', 'stoneedge']:
        path = (ROOT / '招式特效/主角八招' / mid / (mid + '-动画.png') if mid in
                ['thunderbolt', 'thunder'] else ROOT / record[mid]['output'])
        value = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = next(r['sha256'] for r in baseline if r['id'] == mid)
        check(mid + ' protected atlas SHA unchanged', value == expected)
        guards.append({'id': mid, 'sha256': value, 'baseline': expected})
    (OUT / '保护图集.json').write_text(json.dumps(guards, ensure_ascii=False, indent=2) + '\n')
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1000, 'height': 700})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(URL + '/?test=1')
        ready(page)
        catalog = page.evaluate('window.__waterTest.catalog()')
        roster = {r['id']: r for r in catalog['roster']}
        profile = snap()['profile']
        page.evaluate((ROOT / 'tests/招式动画VC像素.js').read_text())
        old = browser.new_page(viewport={'width': 1000, 'height': 700})
        old.on('pageerror', lambda e: errors.append(str(e)))
        old.goto(URL + '/?test=1&anim=old')
        ready(old)
        check('old/new move physics catalog identical', catalog['moves'] ==
              old.evaluate('window.__waterTest.catalog().moves'))
        compare = Image.new('RGB', (560, len(IDS) * 304), '#223540')
        for row, mid in enumerate(IDS):
            print('CHECK', mid, flush=True)
            m = catalog['moves'][mid]
            directions = Image.new('RGB', (1120, 608), '#223540')
            for direction in range(8):
                tag = f'{mid}/{direction}'
                initial = reset(mid, direction)
                check(tag + ' cast', cast(mid))
                check(tag + ' cooldown unchanged', not cast(mid))
                step(m['windup'] - .001)
                check(tag + ' no damage/heal before release', snap()['enemy']['hp'] ==
                      initial['enemy']['hp'] and snap()['player']['hp'] == initial['player']['hp'])
                result = first_event(mid, initial)
                hit, previous = result['hit'], result['previous']
                check(tag + ' actual combat event', hit is not None)
                if hit is None:
                    continue
                if mid in SHOTS_IDS:
                    r = hit['animation']['releases'][-1]
                    p = hit['player']
                    entries = roster[p['id']]['moveAnchors']
                    entry = entries.get('r3-mouth', entries.get('mouth'))
                    clip = catalog['art'][str(p['id'])][entry['role']]
                    root = r['anchor']
                    point = entry['points'][root['row']][root['frame']]
                    offset = clip.get('bodyOffsets', [[[0, 0]] * clip['frames']] * 8)[root['row']][root['frame']]
                    # Source actor has not moved for either projectile.
                    expected = [p['x'] + (point[0]-clip['anchorX']-offset[0])*p['scale'],
                                p['y']+14+(point[1]-clip['anchorY']-offset[1])*p['scale']-p['flightHeight']]
                    check(tag + ' independent source mouth within6px', math.hypot(
                        r['x']-expected[0], r['y']-expected[1]) <= 6)
                else:
                    e = next(e for e in hit['generated']['states'] if e['id'] == mid)
                    if m['kind'] == 'nova':
                        check(tag + ' caster origin within6px', math.hypot(
                            e['x']-initial['player']['x'], e['y']-initial['player']['y']) <= 6)
                    elif m['kind'] == 'zone':
                        check(tag + ' symbol at actual landing within6px', math.hypot(
                            e['drawAnchor']['x']-e['ex'], e['drawAnchor']['y']-e['ey']) <= 6)
                    elif mid in SUPPORT and e.get('drawAnchor'):
                        check(tag + ' symbol centered on caster within6px', math.hypot(
                            e['drawAnchor']['x']-hit['player']['x'], e['drawAnchor']['y'] -
                            (hit['player']['y']+14-hit['player']['body']['visibleSize'][1]/2-
                             hit['player']['flightHeight'])) <= 6)
                    else:
                        check(tag + ' surf release at native foot anchor', e.get('drawAnchor') is not None)
                if mid not in SUPPORT:
                    b = hit['animation']['bursts'][-1]
                    check(tag + ' HP change and impact same simulation tick', b['age'] == 0 and
                          abs(b['time']-hit['animation']['time']) < 1e-8)
                    check(tag + ' previous tick no damage', previous['enemy']['hp'] == initial['enemy']['hp'])
                    raster = page.evaluate('window.vcContactRaster')
                    check(tag + ' actual opaque impact raster >=.8 target height',
                          min(raster['width'], raster['height']) >=
                          .8*hit['enemy']['body']['visibleSize'][1], raster)
                    check(tag + ' actual contact star rendered at contact this tick',
                          raster['key'] == b['key'] and abs(raster['time'] - b['time']) < 1e-8 and
                          math.hypot(raster['x']-b['x'], raster['y']-b['y']) <= 6)
                    if m['kind'] == 'nova':
                        prior = next(e for e in previous['generated']['states'] if e['id'] == mid)
                        check(tag + ' visible wave crossing within1frame', prior['radius'] <
                              e['targetDistance'] <= e['contactRadius'])
                    elif m['kind'] == 'zone':
                        prior = next(e for e in previous['generated']['states'] if e['id'] == mid)
                        check(tag + ' falling/visible pulse lands within1frame', not prior['landed'] and
                              e['landed'] and e['age'] - (e['life']-.35) <= 1/120+.00001)
                    elif mid in SHOTS_IDS:
                        ribbon = hit['animation']['ribbons'][-1]
                        check(tag + ' visible projectile ends on actual contact within6px',
                              math.hypot(ribbon['front']['x']-b['x'], ribbon['front']['y']-b['y']) <= 6)
                    else:
                        def surf_gap(state):
                            p, target = state['player'], state['enemy']
                            row_p = round((p['a'] - math.pi/2) / (math.pi/4)) % 8
                            row_t = round((target['a'] - math.pi/2) / (math.pi/4)) % 8
                            rx, ry = p['body']['hurtByDirection'][row_p]
                            ux, uy = math.cos(p['a']), math.sin(p['a'])
                            pad = 1/math.hypot(-uy/rx, ux/ry) + 4
                            tx, ty = target['body']['hurtByDirection'][row_t]
                            visual_reach = 1/math.hypot(ux/(tx+pad), uy/(ty+pad)) - 1/math.hypot(ux/tx, uy/ty)
                            return math.hypot((p['x']-target['x'])/(tx+pad),
                                              (p['y']-target['y'])/(ty+pad)), visual_reach
                        prior_gap, _ = surf_gap(previous)
                        hit_gap, pad = surf_gap(hit)
                        check(tag + ' surf visible lip advances into unchanged segment within1frame',
                              prior_gap > 1 and hit_gap <= 1 and abs(math.hypot(
                                  e['visibleFront']['x']-hit['player']['x'],
                                  e['visibleFront']['y']-hit['player']['y'])-pad) < .01,
                              {'priorGap': prior_gap, 'hitGap': hit_gap, 'pad': pad})
                else:
                    check(tag + ' support never fabricates enemy impact', not hit['animation']['bursts'] and
                          hit['enemy']['hp'] == initial['enemy']['hp'])
                samples.append({'id': mid, 'direction': direction, 'tick': result['tick'],
                                'damage': initial['enemy']['hp']-hit['enemy']['hp']})
                directions.paste(tile(tag + ' actual event'), ((direction % 4)*280, (direction // 4)*304))
                step(2)
                check(tag + ' no residual visual state', not snap()['generated']['states'] and
                      not snap()['animation']['ribbons'] and not snap()['animation']['bursts'])
            directions.save(SHOTS / f'{mid}-八方向.png')
            if mid not in SUPPORT:
                # Zone reach includes its landing radius and the target body extent.
                distance = max(500, m['range'] + m.get('radius', 0) + 100)
                initial = reset(mid, distance=distance)
                cast(mid)
                step(3)
                check(mid + ' out of range cannot damage', snap()['enemy']['hp'] == initial['enemy']['hp'])
            print('COMBAT DONE', mid, time.strftime('%H:%M:%S'), flush=True)
            instant = comparison_time(mid, m)
            cache = record_cache.get(mid, {})
            valid_cache = cache.get('signature') == record_signature and all(
                (SHOTS / name).exists() and hashlib.sha256((SHOTS / name).read_bytes()).hexdigest() == value
                for name, value in cache.get('files', {}).items()) and bool(cache.get('files'))
            if not valid_cache:
                # 25fps at 1x, including genuine hitstop; recording cache never skips combat checks.
                reset(mid)
                cast(mid)
                film, states = [], []
                for frame in range(48):
                    film.append(tile(f'{mid} {frame*.04:.2f}s 1x'))
                    states.append(snap())
                    step(.04)
                film[0].save(SHOTS / f'{mid}-横向-原速.gif', save_all=True,
                             append_images=film[1:], duration=40, loop=0)
                contact = next((i for i, s in enumerate(states) if s['animation']['bursts'] or
                                (mid in SUPPORT and s['generated']['states'])), 20)
                release = next((i for i, s in enumerate(states) if s['bullets'] or s['generated']['states']), contact)
                indices = [max(0, release-2), (release+contact)//2, contact, min(47, contact+5)]
                sheet = Image.new('RGB', (1120, 304), '#223540')
                for col, index in enumerate(indices):
                    sheet.paste(film[index], (col*280, 0))
                sheet.save(SHOTS / f'{mid}-四时刻.png')
                with Image.open(SHOTS / f'{mid}-横向-原速.gif') as gif:
                    decoded = Image.new('RGB', (1120, 304), '#223540')
                    for col, index in enumerate(indices):
                        gif.seek(index)
                        decoded.paste(gif.convert('RGB'), (col*280, 0))
                    decoded.save(SHOTS / f'{mid}-GIF读图.png')
                capture_comparison(mid, instant, old)
                paths = [f'{mid}-{suffix}' for suffix in ['横向-原速.gif', '四时刻.png', 'GIF读图.png', 'old.png', 'new.png']]
                record_cache[mid] = {'signature': record_signature, 'comparisonTime': instant, 'files': {
                    name: hashlib.sha256((SHOTS / name).read_bytes()).hexdigest() for name in paths}}
                record_path.write_text(json.dumps(record_cache, ensure_ascii=False, indent=2) + '\n')
            if record_cache[mid].get('comparisonTime') != instant:
                capture_comparison(mid, instant, old)
                record_cache[mid]['comparisonTime'] = instant
                for name in [f'{mid}-old.png', f'{mid}-new.png']:
                    record_cache[mid]['files'][name] = hashlib.sha256((SHOTS / name).read_bytes()).hexdigest()
                record_path.write_text(json.dumps(record_cache, ensure_ascii=False, indent=2) + '\n')
            with Image.open(SHOTS / f'{mid}-横向-原速.gif') as gif:
                duration = 0
                for f in range(gif.n_frames):
                    gif.seek(f)
                    duration += gif.info['duration']
                check(mid + ' GIF original speed', duration == 1920)
            compare.paste(Image.open(SHOTS / f'{mid}-old.png'), (0, row*304))
            compare.paste(Image.open(SHOTS / f'{mid}-new.png'), (280, row*304))
            print('RECORD DONE', mid, time.strftime('%H:%M:%S'), flush=True)
            for scene in ['arena-formal', 'arena-natural']:
                pixel_case(mid, scene)
        compare.save(SHOTS / 'VC-M4-old-vs-new-24招.png')
        # Audit actual opacity/size of all successful impact textures in a real draw.
        for w, h in [(1440, 900), (390, 844), (844, 390)]:
            page.set_viewport_size({'width': w, 'height': h})
            page.wait_for_timeout(80)
            reset('discharge')
            cast('discharge')
            step(catalog['moves']['discharge']['windup'] + .2)
            page.screenshot(path=str(SHOTS / f'实战-{w}x{h}.png'))
        check('zero JavaScript errors', not errors, errors)
        browser.close()
except Exception as exc:  # noqa: BLE001
    failure = f'{type(exc).__name__}: {exc}'
    print(failure, flush=True)
finally:
    report = {'passed': sum(c['ok'] for c in checks),
              'failed': sum(not c['ok'] for c in checks) + bool(failure),
              'jsErrors': len(errors), 'errors': errors, 'failure': failure,
              'checks': checks, 'samples': samples, 'pixelSamples': pixels}
    (OUT / '浏览器验收.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['passed', 'failed', 'jsErrors']}, ensure_ascii=False))
    if report['failed'] or errors:
        raise SystemExit(1)
