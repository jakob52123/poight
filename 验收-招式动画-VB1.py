"""VB1: 21 actual moves x eight directions, 120Hz contact and real Canvas raster evidence."""
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

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/招式动画-VB1'
SHOTS = OUT / '截图'
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get('POIGHT_TEST_URL', 'http://localhost:8874/').rstrip('/')
IDS = ['vinewhip', 'scratch', 'brickbreak', 'karatechop', 'lick', 'wingattack', 'metalclaw',
       'headbutt', 'return', 'firepunch', 'absorb', 'leafblade', 'thunderpunch', 'icepunch',
       'drainpunch', 'reversal', 'crosschop', 'poisonjab', 'shadowpunch', 'peck', 'drainingkiss']
CASTERS = dict(zip(IDS, [3, 143, 68, 68, 94, 21, 212, 143, 143, 6, 3, 470,
                         25, 68, 448, 68, 68, 448, 94, 21, 700]))
DRAINS = {'absorb', 'drainpunch', 'drainingkiss'}
checks, errors, samples, pixels = [], [], [], []
failure = None


def check(name, ok, detail=None):
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
    if not ok:
        print('FAIL ' + name + ' ' + json.dumps(detail, ensure_ascii=False), flush=True)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ready(p):
    for _ in range(600):
        if p.evaluate('''()=>{try{return window.__waterTest?.snapshot().artReady}
            catch{return false}}'''):
            return
        time.sleep(.03)
    raise TimeoutError('candidate loading')


def snap():
    return page.evaluate('window.vb1Snapshot()')


def step(t):
    page.evaluate('(t)=>window.__waterTest.step(t)', t)


def select(mid, scene='arena-formal'):
    page.evaluate('(p)=>window.__waterTest.select(p)', {
        **profile, 'map': scene, 'player': CASTERS[mid], 'enemy': 7,
        'playerMoves': roster[CASTERS[mid]]['defaultMoves'], 'enemyMoves': roster[7]['defaultMoves'],
    })


def reset(mid, direction=0, distance=None):
    page.evaluate('window.__waterTest.reset(true)')
    s = snap()
    bounds = s['environment']['bounds']
    # A1 enlarged the emblem under the old clay fixture; sample clay again.
    formal = page.evaluate('__waterTest.snapshot().environment.id === "arena-formal"')
    x = (bounds['left'] + bounds['right']) / 2 - (450 if formal else 0)
    y = (bounds['top'] + bounds['bottom']) / 2 - 95
    a = direction * math.pi / 4
    page.evaluate('(p)=>window.__waterTest.arrange(p)', {
        'ai': False, 'player': {'x': x, 'y': y, 'a': a, 'hp': s['player']['maxHP'] * .5},
        'enemy': {'x': x + 20 * math.cos(a), 'y': y + 20 * math.sin(a)},
    })
    if distance is None:
        distance = page.evaluate('''id=>{
          const api=window.__waterTest,s=api.snapshot(),c=api.catalog(),m=c.moves[id];
          const p={...s.player,char:c.roster.find(r=>r.id===s.player.id)},
            e={...s.enemy,char:c.roster.find(r=>r.id===s.enemy.id)},
            range=Math.min(m.range,p.char.body.nominalSize*(m.rangeBodies||5));
          return window.PoightBodies.meleeRange(e,range,Math.cos(p.a),Math.sin(p.a),p)-4;
        }''', mid)
    page.evaluate('(p)=>window.__waterTest.arrange(p)', {
        'enemy': {'x': x + distance * math.cos(a), 'y': y + distance * math.sin(a)},
    })
    page.evaluate('(id)=>window.__waterTest.equip("player",[id])', mid)
    step(.2)
    page.evaluate('''()=>{if(window.vb1Probe){
      window.vb1Probe.enabled=false;window.vb1Probe.last=null;window.vb1Probe.star=null;
      window.vb1Probe.records=[];window.vb1Probe.pose=[];window.vb1Probe.flows=[];}}''')
    return snap()


def cast(mid):
    return page.evaluate('(id)=>window.__waterTest.cast("player",id)', mid)


def hit(hp):
    return page.evaluate('''hp=>{
      const api=window.__waterTest;let previous=window.vb1Snapshot();
      for(let tick=1;tick<240;tick++){
        api.step(1/120);const s=window.vb1Snapshot();
        if(s.enemy.hp<hp)return {tick,previous,state:s};previous=s;
      }return {tick:null,previous,state:window.vb1Snapshot()};
    }''', hp)


def tile(label, size=280):
    raw = page.evaluate('''()=>{
      const game=document.querySelector('#game'),s=window.__waterTest.snapshot(),
        scale=game.width/s.viewport.width,
        x=((s.player.x+s.enemy.x)/2-s.camera.x)*scale,
        y=((s.player.y+s.enemy.y)/2-16-s.camera.y)*scale,half=100*scale,
        c=document.createElement('canvas');c.width=280;c.height=280;
      const ctx=c.getContext('2d');ctx.imageSmoothingEnabled=false;
      ctx.drawImage(game,Math.round(x-half),Math.round(y-half),Math.round(half*2),
        Math.round(half*2),0,0,280,280);return c.toDataURL();
    }''')
    im = Image.open(io.BytesIO(base64.b64decode(raw.split(',')[1]))).convert('RGB')
    result = Image.new('RGB', (size, size+24), '#223540')
    result.paste(im.resize((size, size), Image.Resampling.NEAREST), (0, 24))
    ImageDraw.Draw(result).text((5, 6), label, fill='white')
    return result


try:
    guards = json.loads((ROOT / '验收记录/招式第3批/受保护图集.json').read_text())
    record = json.loads((ROOT / '招式特效/生图重做/实景预览/构建记录.json').read_text())['assets']
    protection = []
    for mid in ['thunderbolt', 'quickattack', 'irontail', 'thunder', 'flamethrower',
                'fireblast', 'dragonclaw', 'airslash', 'stoneedge']:
        path = (ROOT / '招式特效/主角八招' / mid / (mid+'-动画.png')
                if mid in ['thunderbolt', 'thunder'] else ROOT / record[mid]['output'])
        expected = next(r['sha256'] for r in guards if r['id'] == mid)
        check(mid+' protected SHA', sha(path) == expected)
        protection.append({'id': mid, 'sha256': sha(path), 'baseline': expected})
    (OUT / '保护图集.json').write_text(json.dumps(protection, ensure_ascii=False, indent=2)+'\n')
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(URL+'/?test=1')
        ready(page)
        catalog = page.evaluate('window.__waterTest.catalog()')
        roster = {r['id']: r for r in catalog['roster']}
        moves = catalog['moves']
        compact = '''()=>{window.vb1Snapshot=()=>{
          const s=window.__waterTest.snapshot(),pet=p=>({
            x:p.x,y:p.y,a:p.a,hp:p.hp,maxHP:p.maxHP,body:p.body,flightHeight:p.flightHeight});
          return {player:pet(s.player),enemy:pet(s.enemy),profile:s.profile,
            environment:{bounds:s.environment.bounds},elapsed:s.elapsed,
            animation:s.animation,feel:s.feel};
        }}'''
        page.evaluate(compact)
        profile = snap()['profile']
        page.evaluate((ROOT / 'tests/招式动画VB1像素.js').read_text())
        old_page = browser.new_page(viewport={'width': 1440, 'height': 900})
        old_page.on('pageerror', lambda e: errors.append(str(e)))
        old_page.goto(URL+'/?test=1&anim=old')
        ready(old_page)
        old_page.evaluate(compact)
        before_after = Image.new('RGB', (560, len(IDS)*304), '#223540')
        timings = {}
        for mid in IDS:
            print('CHECK', mid, flush=True)
            select(mid)
            directions = Image.new('RGB', (1120, 608), '#223540')
            m = moves[mid]
            for direction in range(8):
                tag = f'{mid}/{direction}'
                initial = reset(mid, direction)
                hp = initial['enemy']['hp']
                check(tag+' actual cast', cast(mid))
                check(tag+' cooldown blocks recast', not cast(mid))
                step(max(0, m['windup']-.001))
                check(tag+' no windup damage/symbol', snap()['enemy']['hp'] == hp and
                      not snap()['animation']['bursts'])
                result = hit(hp)
                state = result['state']
                check(tag+' actual contact damage', state['enemy']['hp'] < hp)
                if state['enemy']['hp'] >= hp:
                    continue
                b = state['animation']['bursts'][-1]
                check(tag+' previous tick no HP loss', result['previous']['enemy']['hp'] == hp)
                check(tag+' same-tick contact/burst/damage', b['age'] == 0 and
                      abs(b['time']-state['animation']['time']) < 1e-8 and state['feel']['remaining'] > 0)
                # Independent current target-body contact calculation used by the unchanged damage API.
                p, e = result['previous']['player'], result['previous']['enemy']
                length = 1
                reach = 1 / math.hypot(math.cos(p['a'])/e['body']['hurt']['rx'],
                                      math.sin(p['a'])/e['body']['hurt']['ry'])
                point = {'x': e['x']-math.cos(p['a'])/length*reach*.6,
                         'y': e['y']+14-e['body']['visibleSize'][1]/2-e['flightHeight']-
                         math.sin(p['a'])/length*reach*.6}
                gap = math.hypot(b['x']-point['x'], b['y']-point['y'])
                check(tag+' independent hit point <=6px', gap <= 6, gap)
                observed = page.evaluate('window.vb1Probe.records')
                check(tag+' real symbol drawn exactly at contact <=6px', any(
                    r['id'] == mid and r['age'] == 0 and
                    math.hypot(r['x']-b['x'], r['y']-b['y']) <= 6 for r in observed))
                poses = page.evaluate('window.vb1Probe.pose')
                check(tag+' Showdown pose <=0.5H', poses and all(
                    math.hypot(r['x'], r['y']) <= r['height']/2+1e-6 for r in poses), poses[-1:] )
                directions.paste(tile(tag+' actual impact'), ((direction%4)*280, (direction//4)*304))
                if direction == 0:
                    timings[mid] = state['elapsed']-initial['elapsed']
                check(tag+' successful drain only', bool(state['animation']['meleeReturns']) == (mid in DRAINS))
                if mid in DRAINS:
                    r = state['animation']['meleeReturns'][-1]
                    check(tag+' return starts at target', math.hypot(r['x']-b['x'], r['y']-b['y']) <= 6)
                    check(tag+' return points to caster', math.hypot(r['vb1']['root']['x']-p['x'],
                          r['vb1']['root']['y']-(p['y']+14-p['body']['visibleSize'][1]/2-p['flightHeight'])) <= 6)
                step(state['feel']['remaining'] + .15)
                if mid in DRAINS:
                    flows = page.evaluate('window.vb1Probe.flows')
                    root = b['vb1']['root']
                    initial_gap = math.hypot(b['x']-root['x'], b['y']-root['y'])
                    check(tag+' actual return particles approach caster', len(flows) >= 6 and
                          all(math.hypot(f['x']-root['x'], f['y']-root['y']) < initial_gap
                              for f in flows[-6:]), flows[-6:])
                poses = page.evaluate('window.vb1Probe.pose')
                later = [r for r in poses if r['age'] >= r['impact']+.12-1e-8]
                check(tag+' returns to zero in 120ms', later and all(
                    math.hypot(r['x'], r['y']) < 1e-6 for r in later), later[-1:])
                samples.append({'id': mid, 'direction': direction, 'gap': gap, 'burst': b,
                                'damage': hp-state['enemy']['hp'], 'hitSeconds': state['elapsed']-initial['elapsed']})
                step(1)
                check(tag+' no lingering animation/pose instance', not snap()['animation']['bursts'] and
                      not snap()['animation']['meleeReturns'] and
                      page.evaluate('window.vb1Probe.poseInstances') == 0)
            directions.save(SHOTS / (mid+'-八方向.png'))
            # Both mandatory actual maps, real raster at first damaging 120Hz frame.
            for scene in ['arena-formal', 'arena-natural']:
                select(mid, scene)
                initial = reset(mid)
                page.evaluate('window.vb1Probe.enabled=true')
                cast(mid)
                contact = hit(initial['enemy']['hp'])
                state = contact['state']
                if not state['animation']['bursts']:
                    check(scene+'/'+mid+' pixel contact exists', False)
                    continue
                if mid == 'lick':
                    # P6b authorizes the uncut continuous tongue one 120Hz tick before contact.
                    # Preserve the REAL contact ring/clock; only the tongue raster is pre-contact.
                    page.evaluate('''b=>{window.vb1LickContact={b,star:window.vb1Probe.star};}''',
                                  state['animation']['bursts'][-1])
                    reset(mid)
                    page.evaluate('window.vb1Probe.enabled=true')
                    cast(mid)
                    page.evaluate('''n=>{for(let i=0;i<n;i++)window.__waterTest.step(1/120);
                      window.__waterTest.step(0);
                      window.vb1Probe.last={...window.vb1Probe.tongue,b:window.vb1LickContact.b};
                      window.vb1Probe.star=window.vb1LickContact.star;}''', contact['tick']-1)
                    check(scene+'/lick sample is exactly one tick before actual contact',
                          snap()['enemy']['hp'] == initial['enemy']['hp'] and contact['tick'] > 1)
                px = page.evaluate('window.measureVB1Pixels()')
                for key in ['composite', 'background', 'mask', 'starMask']:
                    raw = px.pop(key)
                    (SHOTS / f'像素-{scene}-{mid}-{key}.png').write_bytes(
                        base64.b64decode(raw.split(',')[1]))
                tag = scene+'/'+mid
                check(tag+' opaque recognizable symbol >=0.6H', px['count'] > 20 and
                      px['diameter'] >= px['height']*.6, px)
                check(tag+' opaque impact >=0.8H', px['star']['count'] > 20 and
                      px['star']['diameter'] >= px['height']*.8, px['star'])
                check(tag+' saturated main body >=0.55', px['saturation'] >= .55 and
                      px['colorFraction'] >= .30, px)
                check(tag+' actual background mean contrast >=60', px['contrast'] >= 60, px)
                if mid in DRAINS:
                    step(state['feel']['remaining'] + .18)
                    flow_pixels = page.evaluate('window.measureVB1Flow()')
                    minimum = max(14, state['player']['body']['visibleSize'][1]*.30)
                    check(tag+' actual opaque green return >=max(14,0.30H)', len(flow_pixels) == 6 and
                          all(f['count'] > 20 and f['diameter'] >= minimum and f['greenFraction'] >= .90
                              for f in flow_pixels), flow_pixels)
                    px['flowPixels'] = flow_pixels
                pixels.append({'scene': scene, **px})
            select(mid)
            reset(mid, distance=250)
            cast(mid)
            step(2)
            check(mid+' range gate/no fake impact', snap()['enemy']['hp'] == snap()['enemy']['maxHP'] and
                  not snap()['animation']['contacts'] and not snap()['animation']['meleeReturns'])
            reset(mid)
            cast(mid)
            page.keyboard.press('Escape')
            frozen = snap()['animation']
            step(.2)
            check(mid+' manual pause freezes animation', snap()['animation'] == frozen)
            page.keyboard.press('Escape')
            initial = reset(mid)
            cast(mid)
            check(mid+' actual dash cancels windup', page.evaluate(
                'window.__waterTest.dash("player",1,0)'))
            step(1)
            check(mid+' cancellation has no damage/symbol/pose', snap()['enemy']['hp'] == initial['enemy']['hp'] and
                  not snap()['animation']['contacts'] and
                  page.evaluate('window.vb1Probe.poseInstances') == 0)
            # All GIFs at 25fps original speed, including real hitstop; decode the delivered GIF.
            reset(mid)
            cast(mid)
            captured = page.evaluate('''()=>{
              const api=window.__waterTest,game=document.querySelector('#game'),frames=[];
              const canvas=document.createElement('canvas');canvas.width=280;canvas.height=280;
              const ctx=canvas.getContext('2d');ctx.imageSmoothingEnabled=false;
              for(let i=0;i<32;i++){
                const s=api.snapshot(),scale=game.width/s.viewport.width,
                  x=((s.player.x+s.enemy.x)/2-s.camera.x)*scale,
                  y=((s.player.y+s.enemy.y)/2-16-s.camera.y)*scale,half=100*scale;
                ctx.drawImage(game,Math.round(x-half),Math.round(y-half),Math.round(half*2),
                  Math.round(half*2),0,0,280,280);
                frames.push({raw:canvas.toDataURL(),contact:!!s.animation.bursts.length});
                api.step(.04);
              }return frames;
            }''')
            film = []
            for tick, frame in enumerate(captured):
                im = Image.open(io.BytesIO(base64.b64decode(frame['raw'].split(',')[1]))).convert('RGB')
                tile_image = Image.new('RGB', (280, 304), '#223540')
                tile_image.paste(im, (0, 24))
                ImageDraw.Draw(tile_image).text((5, 6), f'{mid} / {tick*.04:.2f}s / 1x', fill='white')
                film.append(tile_image)
            path = SHOTS / (mid+'-横向-原速.gif')
            film[0].save(path, save_all=True, append_images=film[1:], duration=40, loop=0)
            contact = next((i for i, frame in enumerate(captured) if frame['contact']), None)
            check(mid+' GIF actual impact captured', contact is not None)
            indices = [max(0, (contact or 0)-3), max(0, (contact or 0)-1),
                       contact or 0, min(31, (contact or 0)+5)]
            sheet = Image.new('RGB', (1120, 304), '#223540')
            with Image.open(path) as gif:
                duration = 0
                for i in range(gif.n_frames):
                    gif.seek(i)
                    duration += gif.info['duration']
                for col, index in enumerate(indices):
                    gif.seek(index)
                    sheet.paste(gif.convert('RGB'), (col*280, 0))
            check(mid+' original GIF duration 1280ms', duration == 1280)
            sheet.save(SHOTS / (mid+'-四时刻-GIF解码.png'))
            instant = (contact or 0)*.04
            reset(mid)
            cast(mid)
            step(instant)
            after = tile(f'VB1 new / {mid} / {instant:.3f}s')
            current = page
            page = old_page
            select(mid)
            reset(mid)
            cast(mid)
            step(instant)
            before = tile(f'M4 old / {mid} / {instant:.3f}s')
            before_after.paste(before, (0, IDS.index(mid)*304))
            before_after.paste(after, (280, IDS.index(mid)*304))
            check(mid+' anim=old disables VB1', not snap()['animation']['enabled'] and
                  not snap()['animation']['meleeReturns'])
            page = current
            (OUT / '进行中.json').write_text(json.dumps({'checks': checks, 'pixels': pixels,
                                                        'errors': errors}, ensure_ascii=False, indent=2))
        before_after.save(SHOTS / '21招-M4-vs-VB1-并排总览.png')
        for w, h in [(1440, 900), (390, 844), (844, 390)]:
            page.set_viewport_size({'width': w, 'height': h})
            page.wait_for_timeout(80)
            select('firepunch')
            initial = reset('firepunch')
            cast('firepunch')
            hit(initial['enemy']['hp'])
            page.screenshot(path=str(SHOTS / f'实战-{w}x{h}.png'))
        browser.close()
except Exception as exc:  # noqa: BLE001 - Never turn incomplete evidence into a green report.
    failure = f'{type(exc).__name__}: {exc}'
finally:
    report = {'candidateSHA256': sha(ROOT / '候选试玩.html'),
              'passed': sum(c['ok'] for c in checks),
              'failed': sum(not c['ok'] for c in checks)+bool(failure),
              'jsErrors': len(errors), 'errors': errors, 'failure': failure,
              'checks': checks, 'samples': samples, 'pixelSamples': pixels}
    (OUT / '浏览器验收.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ['passed', 'failed', 'jsErrors']}, ensure_ascii=False))
    if report['failed'] or errors:
        raise SystemExit(1)
