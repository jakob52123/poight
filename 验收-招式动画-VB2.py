"""VB2: 19 x eight directions, authoritative HP clock, native raster, 1x evidence."""
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

from 招式特效.第3批参数 import CASTERS as R3_CASTERS

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/招式动画-VB2'
SHOTS = OUT / '截图'
FILMS = OUT / '给本人'
for folder in (SHOTS, FILMS):
    folder.mkdir(parents=True, exist_ok=True)
IDS = [
    'aquajet', 'flamecharge', 'tackle', 'machpunch', 'bodyslam', 'doubleedge',
    'waterfall', 'flamewheel', 'spark', 'wildcharge', 'rollout', 'zenheadbutt',
    'shadowsneak', 'phantomforce', 'bravebird', 'closecombat', 'rapidspin', 'aquatail', 'bonerush',
]
if os.environ.get('VB2_ONLY'):
    IDS = os.environ['VB2_ONLY'].split()
CASTERS = {**R3_CASTERS, 'closecombat': 68, 'rapidspin': 7, 'aquatail': 130, 'bonerush': 448}
URL = os.environ.get('POIGHT_TEST_URL', 'http://localhost:8875/').rstrip('/')
font_paths = [Path('/System/Library/Fonts/STHeiti Medium.ttc'),
              Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')]
font_path = next((p for p in font_paths if p.exists()), None)
FONT = ImageFont.truetype(str(font_path), 12) if font_path else ImageFont.load_default()
checks, errors, samples, pixel_samples, traces = [], [], [], [], {}
failure = None
reuse_film = False
film_cursor = 0
cached_frames = []
candidate_sha = hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest()
cache_file = OUT / '证据SHA.json'
evidence_cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}


def cached_gif(mid):
    if evidence_cache.get('candidateSHA256') != candidate_sha:
        return False
    paths = [FILMS / f'{mid}-横向-原速.gif', SHOTS / f'{mid}-四时刻-GIF解码.png']
    return all(p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() ==
               evidence_cache.get('files', {}).get(str(p.relative_to(OUT))) for p in paths)


def check(name, ok, detail=None):
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
    if not ok:
        print('FAIL ' + name + ' ' + json.dumps(detail, ensure_ascii=False), flush=True)


def snap():
    return page.evaluate('window.__waterTest.snapshot()')


def step(t):
    page.evaluate('(v)=>window.__waterTest.step(v.t,v.render)', {'t': t, 'render': not reuse_film})


def ready():
    for _ in range(600):
        if page.evaluate('''()=>{try{return window.__waterTest?.snapshot().artReady}catch{return false}}'''):
            return
        time.sleep(.03)
    raise TimeoutError('candidate assets')


def select(mid, scene='arena-formal'):
    c = CASTERS[mid]
    page.evaluate('(p)=>window.__waterTest.select(p)', {
        **profile, 'player': c, 'enemy': 7, 'map': scene,
        'playerMoves': roster[c]['defaultMoves'], 'enemyMoves': roster[7]['defaultMoves'],
    })
    ready()


def reset(mid, direction=0, distance=None):
    page.evaluate('window.__waterTest.reset(true)')
    s = snap()
    bounds = s['environment']['bounds']
    x = (bounds['left'] + bounds['right']) / 2
    y = (bounds['top'] + bounds['bottom']) / 2 - 95
    a = direction * math.pi / 4
    if distance is None and moves[mid].get('limb'):
        distance = page.evaluate('''({mid,a})=>{
          const api=window.__waterTest,s=api.snapshot(),c=api.catalog(),B=window.PoightBodies,
            p={...s.player,a,char:c.roster.find(q=>q.id===s.player.id)},
            e={...s.enemy,char:c.roster.find(q=>q.id===s.enemy.id)},m=c.moves[mid];
          return B.meleeRange(e,Math.min(m.range,p.char.body.nominalSize*m.rangeBodies),
            Math.cos(a),Math.sin(a),p)-1;
        }''', {'mid': mid, 'a': a})
    distance = 65 if distance is None else distance
    page.evaluate('(v)=>window.__waterTest.arrange(v)', {
        'ai': False, 'player': {'x': x, 'y': y, 'a': a},
        'enemy': {'x': x + math.cos(a) * distance, 'y': y + math.sin(a) * distance},
    })
    page.evaluate('(id)=>window.__waterTest.equip("player",[id])', mid)
    step(.1)
    page.evaluate('window.vb2Draws=[]')
    return snap()


def cast(mid):
    return page.evaluate('(id)=>window.__waterTest.cast("player",id)', mid)


def expected(s, mid, r):
    """Independent landmark/frame/scale/lift + existing R1/R3 pose transform."""
    p, m = s['player'], moves[mid]
    entries = roster[p['id']]['moveAnchors']
    part = m.get('anchor')
    entry = entries.get('r3-' + str(part), entries.get(part)) if m.get('r3') else entries.get(part)
    if entry is None:
        return {'x': p['x'], 'y': p['y'] + 14 - p['body']['visibleSize'][1] / 2 - p['flightHeight']}
    clip = catalog['art'][str(p['id'])][entry['role']]
    row, frame = r['row'], r['frame']
    px, py = entry['points'][row][frame]
    ox, oy = clip.get('bodyOffsets', [[[0, 0]] * clip['frames']] * 8)[row][frame]
    if m.get('limb'):
        dx, dy = entries['r1-body']['poseOffsets'][row][frame]
        ox, oy = ox + dx, oy + dy
    point = {'x': p['x'] + (px - clip['anchorX'] - ox) * p['scale'],
             'y': p['y'] + 14 + (py - clip['anchorY'] - oy) * p['scale'] - p['flightHeight']}
    if not m.get('r3'):
        return point
    attack = p['attack']
    active = attack['emitted']
    t = attack['age'] - attack['hitTime'] if active else attack['age'] / attack['hitTime']
    progress = min(1, t / (attack['range'] / m['rushSpeed'])) if active else t
    side = 1 if math.cos(attack['aim']) >= 0 else -1
    angle, lift, squash = 0, 0, 1
    if mid in ['flamewheel', 'rollout']:
        angle = t * 14 * side if active else -progress * .35 * side
    elif mid == 'bodyslam':
        angle = (math.sin(progress * math.pi) if active else -progress * .22) * side
        lift = math.sin(progress * math.pi) * 26 if active else math.sin(progress * math.pi / 2) * 12
        squash = 1 - .1 * math.sin(progress * math.pi) if active else 1
    elif mid == 'waterfall':
        lift = math.sin(progress * math.pi) * 13 if active else progress * 3
    elif mid == 'shadowsneak':
        squash = .72 if active else 1 - progress * .28
    elif mid in ['tackle', 'doubleedge', 'zenheadbutt', 'machpunch']:
        angle = (.14 if active else -progress * (.22 if mid == 'doubleedge' else .12)) * side
    cx, cy = p['x'], p['y'] - p['body']['nominalSize'] * .38
    dx, dy = point['x'] - cx, point['y'] - cy
    return {'x': cx + dx * math.cos(angle) - dy * squash * math.sin(angle),
            'y': cy + dx * math.sin(angle) + dy * squash * math.cos(angle) - lift}


def tile(label, size=300):
    global film_cursor
    if reuse_film:
        result = cached_frames[film_cursor].copy()
        film_cursor += 1
        return result
    s = snap()
    raw = page.locator('#game').evaluate('(c)=>c.toDataURL("image/png")')
    image = Image.open(io.BytesIO(base64.b64decode(raw.split(',')[1]))).convert('RGB')
    scale = image.width / s['viewport']['width']
    x = ((s['player']['x'] + s['enemy']['x']) / 2 - round(s['camera']['x'])) * scale
    y = ((s['player']['y'] + s['enemy']['y']) / 2 - 25 - round(s['camera']['y'])) * scale
    half = 115 * scale
    if s['player']['id'] == 130:
        # Gyarados's flying attack pose and tail reach cannot fit the small-caster crop.
        # Use the same body-derived frame in old/new, never crop off the head or tail arc.
        actors = [s['player'], s['enemy']]
        x0 = min(p['x'] - p['body']['nominalSize']*.85 - p['body']['visibleSize'][1]*.65
                 for p in actors)
        x1 = max(p['x'] + p['body']['nominalSize']*.85 + p['body']['visibleSize'][1]*.65
                 for p in actors)
        y0 = min(p['y'] - p['body']['nominalSize'] - p['flightHeight'] - 40 for p in actors)
        y1 = max(p['y'] + max(35, p['body']['visibleSize'][1]*.75) for p in actors)
        span = max(230, x1-x0, y1-y0)
        x = ((x0+x1)/2 - round(s['camera']['x'])) * scale
        y = ((y0+y1)/2 - round(s['camera']['y'])) * scale
        half = span * scale / 2
    crop = image.crop((round(x-half), round(y-half), round(x+half), round(y+half)))
    result = Image.new('RGB', (size, size + 24), '#20313c')
    result.paste(crop.resize((size, size), Image.Resampling.NEAREST), (0, 24))
    ImageDraw.Draw(result).text((5, 5), label, fill='white', font=FONT)
    return result


def instrument():
    page.evaluate((ROOT / 'tests/VB2像素.js').read_text())
    page.evaluate('''()=>{
      window.vb2Draws=[];
      const draw=window.PoightVB2.emblem;
      window.PoightVB2.emblem=function(ctx,e,p,api,...rest){
        window.vb2Draws.push({id:e.id,x:p.x,y:p.y,time:api.animations.time});
        window.vb2Draws=window.vb2Draws.slice(-500);return draw.call(this,ctx,e,p,api,...rest);
      };
      const burst=window.PoightMoveAnimations.prototype.drawBurst;
      window.PoightMoveAnimations.prototype.drawBurst=function(ctx,b,...rest){
        window.vb2Draws.push({id:b.id,x:b.x,y:b.y,time:this.time,ring:true});
        return burst.call(this,ctx,b,...rest);
      };
    }''')


def actual_trace(mid):
    reset(mid)
    cast(mid)
    return page.evaluate('''()=>{
      const api=window.__waterTest,out=[];
      for(let i=0;i<180;i++){
        api.step(1/120,false);const s=api.snapshot();
        out.push([s.player.x,s.player.y,s.player.hp,s.player.stamina,s.enemy.x,s.enemy.y,
          s.enemy.hp,s.hits,s.taken,s.player.attack?.emitted||false,s.player.cool]);
      }
      api.step(0);return out;
    }''')


try:
    guard_file = ROOT / 'tests/VB2保护图集.json'
    guards = json.loads(guard_file.read_text())
    record = json.loads((ROOT / '招式特效/生图重做/实景预览/构建记录.json').read_text())['assets']
    for g in guards:
        mid = g['id']
        path = (ROOT / '招式特效/主角八招' / mid / (mid + '-动画.png')
                if mid in ['thunderbolt', 'thunder'] else ROOT / record[mid]['output'])
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        check(mid + ' protected SHA unchanged', actual == g['sha256'])
        g['actualSHA256'] = actual
    (OUT / '保护图集.json').write_text(json.dumps(guards, ensure_ascii=False, indent=2) + '\n')
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 900, 'height': 600})
        # test=1 advances/draws through the real step API; avoid redundant idle RAF repaint.
        page.add_init_script('window.requestAnimationFrame=()=>0')
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(URL + '/?test=1')
        ready()
        catalog = page.evaluate('window.__waterTest.catalog()')
        moves, roster = catalog['moves'], {r['id']: r for r in catalog['roster']}
        profile = snap()['profile']
        instrument()
        overview = Image.new('RGB', (600, len(IDS) * 324), '#20313c')
        after_tiles = {}
        for mid in IDS:
            print('CHECK', mid, flush=True)
            select(mid)
            m = moves[mid]
            sheet = Image.new('RGB', (1200, 648), '#20313c')
            for direction in range(8):
                tag = f'{mid}/{direction}'
                initial = reset(mid, direction)
                hp = initial['enemy']['hp']
                check(tag + ' actual cast', cast(mid))
                check(tag + ' cooldown blocks recast', not cast(mid))
                step(m['windup'] - .001)
                check(tag + ' no windup damage', snap()['enemy']['hp'] == hp)
                page.evaluate('(mid)=>Object.assign(window.vb2Probe,{enabled:true,mid,star:null,actor:null})', mid)
                before_release = snap()
                step(.001)
                release = snap()['animation']['releases'][-1]
                ex = expected(snap(), mid, release['anchor'])
                err = math.hypot(release['x'] - ex['x'], release['y'] - ex['y'])
                check(tag + ' independent appearance anchor <=6px', err <= 6, err)
                release_draws = page.evaluate('window.vb2Draws')
                check(tag + ' production emblem actually drawn at release anchor <=6px',
                      any(d['id'] == mid and d['time'] == release['time'] and
                          math.hypot(d['x']-ex['x'], d['y']-ex['y']) <= 6 for d in release_draws))
                body = page.evaluate('window.measureVB2()')
                check(tag + ' real caster raster retained>=50% at release',
                      body['bodyCount'] > 20 and body['bodyRetained'] >= .5,
                      {'bodyCount': body['bodyCount'], 'bodyRetained': body['bodyRetained']})
                page.evaluate('window.vb2Probe.enabled=false')
                result = page.evaluate('''({hp,before})=>{
                  const api=window.__waterTest;let previous=api.snapshot();
                  // H1 melee may hit on release itself; retain the real pre-release frame.
                  if(previous.enemy.hp<hp)return {hit:previous,previous:before,ticks:0};
                  for(let i=0;i<180;i++){
                    api.step(1/120,false);const s=api.snapshot();
                    if(s.enemy.hp<hp){api.step(0);return {hit:api.snapshot(),previous,ticks:i+1};}previous=s;
                  }return {hit:null,previous};
                }''', {'hp': hp, 'before': before_release})
                hit = result['hit']
                check(tag + ' real contact loses HP', hit is not None)
                if not hit:
                    continue
                b = hit['animation']['bursts'][-1]
                draws = page.evaluate('window.vb2Draws')
                matching = [d for d in draws if d['id'] == mid and d['time'] == b['time']
                            and math.hypot(d['x']-b['x'], d['y']-b['y']) <= 6]
                check(tag + ' visible contact <=6px same HP tick (<=1 frame)', bool(matching)
                      and b['age'] == 0 and abs(b['time']-hit['animation']['time']) < 1e-8)
                check(tag + ' previous frame full HP', result['previous']['enemy']['hp'] == hp)
                check(tag + ' hit burst and hitstop', bool(hit['animation']['bursts']) and hit['feel']['remaining'] > 0)
                check(tag + ' damage star floor >=0.8H', b['size'] >= .8 * hit['enemy']['body']['visibleSize'][1])
                sheet.paste(tile(f'{mid} / {direction} / 接触'),
                            ((direction % 4)*300, (direction // 4)*324))
                samples.append({'id': mid, 'direction': direction, 'anchorError': err,
                                'damage': hp-hit['enemy']['hp'], 'burst': b,
                                'contactSeconds': hit['elapsed']-initial['elapsed']})
                step(2)
                check(tag + ' effects expire', not snap()['generated']['states'] and not snap()['animation']['bursts'])
            sheet.save(SHOTS / f'{mid}-八方向.png')
            # The native damage gate must continue rejecting remote, protected and airborne targets.
            initial = reset(mid, distance=300)
            cast(mid)
            step(2)
            check(mid + ' range gate no remote HP loss', snap()['enemy']['hp'] == initial['enemy']['hp'])
            reset(mid)
            page.evaluate('window.__waterTest.dash("enemy",1,0)')
            result = page.evaluate('(id)=>window.__waterTest.injectMoveHit("enemy",id)', mid)
            check(mid + ' protected target damage gate unchanged', not result and not snap()['animation']['bursts'])
            if not m.get('hitsAirborne', True):
                reset(mid)
                page.evaluate('window.__waterTest.jump("enemy")')
                step(.08)
                result = page.evaluate('(id)=>window.__waterTest.injectMoveHit("enemy",id)', mid)
                check(mid + ' airborne damage gate unchanged', not result and not snap()['animation']['bursts'])
            # Exact-byte candidate evidence can be reused; live 25fps HP clocks are still replayed.
            reuse_film = cached_gif(mid)
            cached_frames, film_cursor = [], 0
            if reuse_film:
                with Image.open(FILMS / f'{mid}-横向-原速.gif') as cached:
                    for frame in range(cached.n_frames):
                        cached.seek(frame)
                        cached_frames.extend([cached.convert('RGB').copy()] *
                                             (cached.info['duration'] // 40))
                check(mid + ' cached evidence tied to exact candidate bytes', len(cached_frames) == 38)
            reset(mid)
            cast(mid)
            film, states = [], []
            for tick in range(38):
                film.append(tile(f'{m["name"]} {tick*.04:.2f}s / 1x'))
                states.append(snap())
                step(.04)
            hit_index = next((i for i, s in enumerate(states) if s['animation']['bursts']), None)
            check(mid + ' GIF records actual contact', hit_index is not None)
            release_index = next(i for i, s in enumerate(states) if s['generated']['states'])
            after_hit = 16 if mid == 'phantomforce' else 4
            indices = [max(0, release_index - 2), (release_index + (hit_index or release_index)) // 2,
                       hit_index or release_index, min(37, (hit_index or release_index) + after_hit)]
            gif_path = FILMS / f'{mid}-横向-原速.gif'
            palette_source = Image.new('RGB', (600, 648))
            for col, index in enumerate(indices):
                palette_source.paste(film[index], ((col % 2)*300, (col // 2)*324))
            palette = palette_source.quantize(colors=256)
            encoded = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in film]
            if not reuse_film:
                encoded[0].save(gif_path, save_all=True, append_images=encoded[1:],
                                duration=40, loop=0, optimize=False)
            keyframes = Image.new('RGB', (1200, 324), '#20313c')
            with Image.open(gif_path) as gif:
                total = 0
                for i in range(gif.n_frames):
                    gif.seek(i)
                    total += gif.info['duration']
                for col, i in enumerate(indices):
                    gif.seek(i)
                    keyframes.paste(gif.convert('RGB'), (col*300, 0))
                check(mid + ' GIF 1x duration 1520ms', total == 1520)
            if not reuse_film:
                keyframes.save(SHOTS / f'{mid}-四时刻-GIF解码.png')
            reuse_film = False
            instant = m['windup'] + .06
            reset(mid)
            cast(mid)
            step(instant)
            after_tiles[mid] = tile(f'改后 {m["name"]} / {instant:.3f}s')
            traces[mid] = actual_trace(mid)
        # Native pixels at the first HP-loss tick, including H1 release-tick contacts.
        for scene in ['arena-formal', 'arena-natural']:
            for mid in IDS:
                select(mid, scene)
                initial = reset(mid)
                cast(mid)
                ticks = page.evaluate('''hp=>{
                  const api=window.__waterTest;for(let i=1;i<=240;i++){
                    api.step(1/120,false);if(api.snapshot().enemy.hp<hp)return i;
                  }return null;
                }''', initial['enemy']['hp'])
                tag = f'pixels/{scene}/{mid}'
                check(tag + ' actual hit located', ticks is not None)
                if ticks is None:
                    continue
                reset(mid)
                page.evaluate('(mid)=>Object.assign(window.vb2Probe,{enabled:true,mid,star:null})', mid)
                cast(mid)
                page.evaluate('(n)=>{for(let i=0;i<n;i++)window.__waterTest.step(1/120,false);window.__waterTest.step(0)}', ticks)
                px = page.evaluate('window.measureVB2()')
                for key in ['composite', 'background', 'mask']:
                    raw = px.pop(key)
                    Image.open(io.BytesIO(base64.b64decode(raw.split(',')[1]))).save(
                        SHOTS / f'像素-{scene}-{mid}-{key}.png')
                px.pop('starMask')
                check(tag + ' hit frame HP loss / emitted symbol', px['hp'] < initial['enemy']['hp']
                      and not px['charging'] and px['count'] > 20, px)
                # No shots or beams in VB2: measure occupied opaque symbol pixels, not canvas boxes.
                check(tag + ' actual opaque symbol >=max(14,0.30H)',
                      min(px['opaqueWidth'], px['opaqueHeight']) >= max(14, px['height']*.30), px)
                check(tag + ' S>=0.55 / colored area>=30%', px['saturation'] >= .55 and px['colorFraction'] >= .30, px)
                check(tag + ' positive mean luma above background>=60', px['contrast'] >= 60, px)
                check(tag + ' original posed caster pixels retained>=50%',
                      px['bodyCount'] > 20 and px['bodyRetained'] >= .5, px)
                impact = page.evaluate('window.measureVB2()')
                star = impact['star']
                target_h = snap()['enemy']['body']['visibleSize'][1]
                check(tag + ' same tick actual hollow ring opaque extent>=0.8H', star is not None and
                      min(star['opaqueWidth'], star['opaqueHeight']) >= .8*target_h, star)
                raw = impact['starMask']
                if raw:
                    Image.open(io.BytesIO(base64.b64decode(raw.split(',')[1]))).save(
                        SHOTS / f'像素-{scene}-{mid}-star.png')
                pixel_samples.append({'scene': scene, 'id': mid, **px, 'impactStar': star})
                page.evaluate('window.vb2Probe.enabled=false')
                # Also check windup and the moving shell, not just the contact frame.
                for phase, instant in [('charge', moves[mid]['windup'] * .7),
                                       ('release', moves[mid]['windup'] + .015)]:
                    reset(mid)
                    page.evaluate('(mid)=>Object.assign(window.vb2Probe,{enabled:true,mid,star:null,actor:null})', mid)
                    cast(mid)
                    step(instant)
                    coat = page.evaluate('window.measureVB2()')
                    for key in ['composite', 'background', 'mask', 'starMask']:
                        coat.pop(key)
                    check(tag + '/' + phase + ' positive coat luma>=background+60',
                          coat['contrast'] >= 60, coat)
                    check(tag + '/' + phase + ' original caster pixels retained>=50%',
                          coat['bodyCount'] > 20 and coat['bodyRetained'] >= .5, coat)
                    page.evaluate('window.vb2Probe.enabled=false')
        # Same candidate, same scene/characters/time. anim=old is the required M4 route.
        page.goto(URL + '/?test=1&anim=old')
        ready()
        for row, mid in enumerate(IDS):
            select(mid)
            reset(mid)
            cast(mid)
            instant = moves[mid]['windup'] + .06
            step(instant)
            before = tile(f'改前 anim=old {moves[mid]["name"]} / {instant:.3f}s')
            overview.paste(before, (0, row*324))
            overview.paste(after_tiles[mid], (300, row*324))
            check(mid + ' old route no VB2 release', not snap()['animation']['releases'])
            check(mid + ' 180-tick physics trace identical old/new', actual_trace(mid) == traces[mid])
        overview.save(SHOTS / '19招-改前-vs-改后.png')
        page.goto(URL + '/?test=1')
        ready()
        # Viewport evidence and no network fallback.
        for w, h in [(1440, 900), (390, 844), (844, 390)]:
            page.set_viewport_size({'width': w, 'height': h})
            page.wait_for_timeout(80)
            select('bravebird')
            reset('bravebird', 1)
            cast('bravebird')
            step(moves['bravebird']['windup'] + .08)
            page.screenshot(path=str(SHOTS / f'实战-{w}x{h}.png'))
        offline = browser.new_context(offline=True)
        page = offline.new_page()
        page.add_init_script('window.requestAnimationFrame=()=>0')
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto((ROOT / '候选试玩.html').as_uri() + '?test=1')
        ready()
        for mid in IDS:
            select(mid)
            initial = reset(mid)
            cast(mid)
            step(1.3)
            check(mid + ' offline real combat HP loss', snap()['enemy']['hp'] < initial['enemy']['hp'])
        check('zero JS errors', not errors, errors)
        browser.close()
except (Exception, KeyboardInterrupt) as exc:  # noqa: BLE001 - incomplete runs are never green
    failure = f'{type(exc).__name__}: {exc}'
finally:
    report = {'candidateSHA256': candidate_sha, 'passed': sum(c['ok'] for c in checks),
              'failed': sum(not c['ok'] for c in checks) + bool(failure),
              'jsErrors': len(errors), 'errors': errors, 'failure': failure,
              'checks': checks, 'samples': samples, 'pixelSamples': pixel_samples}
    (OUT / '浏览器验收.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    (OUT / '物理AB轨迹.json').write_text(json.dumps(traces, ensure_ascii=False) + '\n')
    if (not report['failed'] and not errors and len(IDS) == 19 and
            len(samples) == 152 and len(pixel_samples) == 38):
        evidence = [*FILMS.glob('*-原速.gif'), *SHOTS.glob('*-四时刻-GIF解码.png')]
        cache_file.write_text(json.dumps({'candidateSHA256': candidate_sha,
            'files': {str(p.relative_to(OUT)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in evidence}}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['passed', 'failed', 'jsErrors']}, ensure_ascii=False))
    if report['failed'] or errors:
        raise SystemExit(1)
