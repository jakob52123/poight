"""V1 core: actual 120 Hz collisions, native raster evidence, offline portable candidate."""
import base64
import hashlib
import io
import json
import math
import os
import re
import subprocess
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/招式动画核心'
SHOTS = OUT / '截图'
PERSONAL = OUT / '给本人'
for directory in (SHOTS, PERSONAL):
    directory.mkdir(parents=True, exist_ok=True)
URL = os.environ.get('POIGHT_TEST_URL', 'http://localhost:8871/').rstrip('/')
M4 = 'f64982be201b70212a8a6b3e0ff5fad6618f6cad'
CASTERS = {'watergun': 7, 'icebeam': 9, 'earthquake': 95}
checks, errors, samples, requests, responses = [], [], [], [], []
pixel_samples = []
failure = None
font_path = Path('/System/Library/Fonts/STHeiti Medium.ttc')
FONT = ImageFont.truetype(str(font_path), 12) if font_path.exists() else ImageFont.load_default()


def check(name, ok, detail=None):
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ready(p):
    # Current + historical pages decode concurrently under the sprint's shared CPU load.
    # Keep the exact artReady gate; extend only the bounded loading budget (18s -> 120s).
    for _ in range(4000):
        # M4 exposes snapshot before its actors exist; a loading-time probe can throw.
        if p.evaluate('''()=>{
            if (!window.__waterTest) return false;
            try { return window.__waterTest.snapshot().artReady; } catch { return false; }
        }'''):
            return
        time.sleep(.03)
    diagnostics = p.evaluate('''() => {
      let snapshot;
      try { snapshot = window.__waterTest?.snapshot(); } catch (e) { snapshot = String(e); }
      return {url:location.href, snapshot, text:document.body.innerText,
        resources:performance.getEntriesByType('resource').map(r=>({url:r.name, bytes:r.transferSize}))};
    }''')
    (OUT / '加载诊断.json').write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2)+'\n')
    raise TimeoutError('candidate loading')


def snap():
    return page.evaluate('window.__waterTest.snapshot()')


def step(t):
    page.evaluate('(t)=>window.__waterTest.step(t)', t)


def select(mid):
    caster = CASTERS[mid]
    page.evaluate('(p)=>window.__waterTest.select(p)', {
        **profile, 'player': caster, 'enemy': 7,
        'playerMoves': roster[caster]['defaultMoves'], 'enemyMoves': roster[7]['defaultMoves'],
    })
    # Find arena ID by metadata, not a hardcoded assumption.
    if snap()['environment']['type'] != 'arena':
        raise AssertionError('test must use an arena')


def reset(mid, direction=0, distance=None):
    page.evaluate('window.__waterTest.reset(true)')
    s = snap()
    bounds = s['environment']['bounds']
    x = (bounds['left'] + bounds['right']) / 2
    y = (bounds['top'] + bounds['bottom']) / 2
    distance = distance if distance is not None else (55 if mid == 'earthquake' else 100)
    a = direction * math.pi / 4
    page.evaluate('(v)=>window.__waterTest.arrange(v)', {
        'ai': False, 'player': {'x': x, 'y': y, 'a': a},
        'enemy': {'x': x + math.cos(a) * distance, 'y': y + math.sin(a) * distance},
    })
    page.evaluate('(id)=>window.__waterTest.equip("player",[id])', mid)
    step(.1)
    return snap()


def cast(mid):
    return page.evaluate('(id)=>window.__waterTest.cast("player",id)', mid)


def tile(label, size=360):
    s = snap()
    data = page.locator('#game').evaluate('(c)=>c.toDataURL("image/png")')
    image = Image.open(io.BytesIO(base64.b64decode(data.split(',')[1]))).convert('RGB')
    p, e = s['player'], s['enemy']
    scale = image.width / s['viewport']['width']
    x = ((p['x'] + e['x']) / 2 - s['camera']['x']) * scale
    y = ((p['y'] + e['y']) / 2 - 16 - s['camera']['y']) * scale
    half = 135 * scale
    image = image.crop((round(x-half), round(y-half), round(x+half), round(y+half)))
    result = Image.new('RGB', (size, size + 24), '#223540')
    result.paste(image.resize((size, size), Image.Resampling.NEAREST), (0, 24))
    ImageDraw.Draw(result).text((6, 6), label, fill='white', font=FONT)
    return result


def pixel_acceptance():
    """Two real arena backgrounds; capture the last 120Hz frame BEFORE actual HP loss."""
    page.evaluate((ROOT / 'tests/招式动画像素.js').read_text())
    for scene in ['arena-formal', 'arena-natural']:
        profile['map'] = scene
        for mid in CASTERS:
            select(mid)
            initial = reset(mid)
            # A1's 440–520px emblem now covers this old dirt fixture, including
            # its red upper half. Move only formal samples left onto genuine clay;
            # keep all luminance, chroma, geometry and next-tick damage thresholds.
            page.evaluate('''()=>{
              const api=window.__waterTest,s=api.snapshot(),
                dx=s.environment.id==='arena-formal'?450:0;
              api.arrange({ai:false,player:{x:s.player.x-dx,y:s.player.y-95,a:0},
                enemy:{x:s.enemy.x-dx,y:s.enemy.y-95}});
            }''')
            placement = snap()
            cast(mid)
            ticks = page.evaluate('''hp=>{
              const api=window.__waterTest;
              for(let i=1;i<240;i++) {api.step(1/120);if(api.snapshot().enemy.hp<hp)return i;}
              return null;
            }''', initial['enemy']['hp'])
            tag = f'pixels/{scene}/{mid}'
            check(tag + ' actual hit found', ticks is not None)
            if ticks is None:
                continue
            reset(mid)
            page.evaluate('(s)=>window.__waterTest.arrange({ai:false,player:s.player,enemy:s.enemy})', {
                'player': {k: placement['player'][k] for k in ['x', 'y', 'a']},
                'enemy': {k: placement['enemy'][k] for k in ['x', 'y']},
            })
            page.evaluate('window.pixelProbe.enabled=true')
            cast(mid)
            page.evaluate('(n)=>{for(let i=0;i<n;i++)window.__waterTest.step(1/120)}', ticks-1)
            pixels = page.evaluate('window.measureMovePixels()')
            for key in ['composite', 'background', 'mask']:
                raw = pixels.pop(key)
                Image.open(io.BytesIO(base64.b64decode(raw.split(',')[1]))).save(
                    SHOTS / f'像素-{scene}-{mid}-{key}.png')
            check(tag + ' precontact has full HP', pixels['hp'] == initial['enemy']['hp'])
            check(tag + ' opaque raster exists', pixels['count'] > 20, pixels)
            if mid == 'watergun':
                check(tag + ' 5-7 actual bead sprites', 5 <= pixels['beadCount'] <= 7)
                check(tag + ' opaque bead diameter >= max(14,0.30H)',
                      pixels['beadDiameter'] >= max(14, pixels['height'] * .30), pixels)
            elif mid == 'icebeam':
                check(tag + ' opaque beam width >= max(10,0.25H)',
                      pixels['minimumBeamWidth'] >= max(10, pixels['height'] * .25), pixels)
                check(tag + ' visible 230+ luminous core',
                      pixels['brightPixels'] > 20 and pixels['centerLuma'] >= 230, pixels)
            else:
                state = next(e for e in snap()['generated']['states'] if e['mode'] == 'core-nova')
                check(tag + ' opaque ground ring at physical wavefront',
                      pixels['radialMin'] <= state['radius'] <= pixels['radialMax'])
                check(tag + ' next tick wave reaches before damage',
                      state['radius'] < math.hypot(snap()['enemy']['x']-state['x'],
                                                   snap()['enemy']['y']-state['y']))
            check(tag + ' attribute-colored pixels S>=0.55',
                  pixels['saturation'] >= .55 and pixels['colorFraction'] >= .30, pixels)
            check(tag + ' mean luma contrast >=60', pixels['contrast'] >= 60, pixels)
            step(1/120)
            check(tag + ' exactly next tick is visible impact and damage',
                  snap()['enemy']['hp'] < initial['enemy']['hp'] and snap()['animation']['bursts'][-1]['age'] == 0)
            pixel_samples.append({'scene': scene, 'id': mid, **pixels})
            page.evaluate('window.pixelProbe.enabled=false')
    profile['map'] = 'arena-formal'


def serve_html(html):
    # Playwright may supply (route, request); keep a one-argument handler and bind outside the loop.
    return lambda route: route.fulfill(status=200, content_type='text/html', body=html)


def m4_reference():
    """Exact M4 runtime source, identical three-sample combat data; no old-mode impersonation."""
    candidate = (ROOT / '候选试玩.html').read_text()
    start = candidate.index('const DATA = ') + len('const DATA = ')
    data, _ = json.JSONDecoder().raw_decode(candidate[start:])
    data.pop('moveAnimations')
    paths = ['世界地图.js', '竞技场.js', '草丛藏身.js', '大地图通行.js', '体型判定.js',
             '生图招式.js', '招式第3批.js', '平衡测试.js', '打击感.js', '瞄准预警.js',
             '战斗界面方案.js', '跳跃.js', '对战.js']
    sources = [subprocess.check_output(['git', 'show', f'{M4}:{p}'], cwd=ROOT).decode() for p in paths]
    script = '\n'.join(sources).replace('__GAME_DATA__', json.dumps(data, ensure_ascii=False).replace('</', '<\\/'))
    html = re.sub(r'<script>.*?</script>', lambda _: '<script>' + script + '</script>', candidate, flags=re.DOTALL)
    html = html.replace('assets/', (ROOT / 'assets').as_uri() + '/')
    path = OUT / 'M4-对照.html'
    path.write_text(html)
    (OUT / 'M4-对照来源.json').write_text(json.dumps({
        'commit': M4, 'runtimeSources': {p: hashlib.sha256(s.encode()).hexdigest() for p, s in zip(paths, sources)},
        'sampleData': {mid: {'base': data['moves'][mid], 'runtime': data['generatedFx'][mid]['runtime']}
                       for mid in CASTERS},
        'note': 'M4 runtime source from git; current packaged data shared. Sample runtime unchanged; B1 data for other moves not exercised.',
    }, ensure_ascii=False, indent=2) + '\n')
    return path


try:
    record = json.loads((ROOT / '招式特效/生图重做/实景预览/构建记录.json').read_text())['assets']
    guards = []
    for mid in ['thunderbolt', 'quickattack', 'irontail', 'thunder', 'flamethrower',
                'fireblast', 'dragonclaw', 'airslash', 'stoneedge']:
        relative = (Path('招式特效/主角八招') / mid / (mid + '-动画.png')
                    if mid in ['thunderbolt', 'thunder'] else Path(record[mid]['output']))
        before = json.loads((ROOT / '验收记录/招式第3批/受保护图集.json').read_text())
        baseline = next(r['sha256'] for r in before if r['id'] == mid)
        value = sha(ROOT / relative)
        guards.append({'id': mid, 'sha256': value, 'baseline': baseline})
        check(mid + ' protected atlas SHA unchanged', value == baseline)
    (OUT / '保护图集.json').write_text(json.dumps(guards, ensure_ascii=False, indent=2) + '\n')
    manifest = json.loads((ROOT / '候选发布清单.json').read_text())['assets']
    for name, asset in manifest.items():
        check('offline manifest bytes ' + name, (ROOT / name).exists() and sha(ROOT / name) == asset['sha256'])
    check('NOTICE and license in release', sum('animation-legal-' in p for p in manifest) >= 3)
    reference = m4_reference()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('requestfailed', lambda r: requests.append(r.url))
        page.on('response', lambda r: responses.append(r.url) if r.status >= 400 else None)
        page.goto(URL + '/?test=1')
        ready(page)
        catalog = page.evaluate('window.__waterTest.catalog()')
        roster = {r['id']: r for r in catalog['roster']}
        profile = snap()['profile']
        arena = next(s['id'] for s in catalog['scenes'] if s.get('type') == 'arena')
        profile['map'] = arena
        # Observe the actual renderer's original texture dispatch, without replacing its drawing.
        page.evaluate('''()=>{
          window.coreDraws=[];
          const draw=window.PoightMoveAnimations.prototype.sprite;
          window.PoightMoveAnimations.prototype.sprite=function(ctx,key,x,y,size,...rest){
            window.coreDraws.push({key,x,y,size,time:this.time});window.coreDraws=window.coreDraws.slice(-300);
            return draw.call(this,ctx,key,x,y,size,...rest);
          };
        }''')
        for mid in CASTERS:
            print('CHECK', mid, flush=True)
            select(mid)
            m = catalog['moves'][mid]
            directions = Image.new('RGB', (1440, 768), '#223540')
            for direction in range(8):
                tag = f'{mid}/{direction}'
                initial = reset(mid, direction)
                hp = initial['enemy']['hp']
                check(tag + ' cast', cast(mid))
                check(tag + ' cooldown prevents recast', not cast(mid))
                step(m['windup'] - .001)
                check(tag + ' no windup damage', snap()['enemy']['hp'] == hp)
                step(.001)
                release = snap()
                if mid != 'earthquake':
                    r = release['animation']['releases'][-1]
                    p = release['player']
                    root = r['anchor']
                    entries = roster[p['id']]['moveAnchors']
                    entry = entries.get('r3-mouth', entries.get('mouth'))
                    clip = catalog['art'][str(p['id'])][entry['role']]
                    point = entry['points'][root['row']][root['frame']]
                    offset = clip.get('bodyOffsets', [[[0, 0]] * clip['frames']] * 8)[root['row']][root['frame']]
                    expected = [p['x'] + (point[0]-clip['anchorX']-offset[0])*p['scale'],
                                p['y']+14+(point[1]-clip['anchorY']-offset[1])*p['scale']-p['flightHeight']]
                    check(tag + ' independent T5 mouth <=6px', math.hypot(r['x']-expected[0], r['y']-expected[1]) <= 6)
                else:
                    state = next(e for e in release['generated']['states'] if e['mode'] == 'core-nova')
                    check(tag + ' nova origin at caster', math.hypot(state['x']-release['player']['x'],
                                                                   state['y']-release['player']['y']) <= 6)
                result = page.evaluate('''({mid,hp})=>{
                  const api=window.__waterTest;let premature=false,previous=api.snapshot(),hit=null;
                  for(let tick=0;tick<240;tick++){
                    api.step(1/120);const s=api.snapshot();
                    if(mid==='earthquake'){
                      const e=s.generated.states.find(e=>e.id===mid);
                      if(e && e.radius<Math.hypot(s.enemy.x-e.x,s.enemy.y-e.y) && s.enemy.hp<hp)
                        premature=true;
                    }
                    if(s.enemy.hp<hp){hit=s;break;}previous=s;
                  }
                  return {premature,hit,previous};
                }''', {'mid': mid, 'hp': hp})
                hit = result['hit']
                check(tag + ' real collision damages', hit is not None)
                if hit is None:
                    continue
                b = hit['animation']['bursts'][-1]
                check(tag + ' contact same tick as HP and hitstop', b['age'] == 0 and
                      hit['feel']['remaining'] > 0 and abs(b['time']-hit['animation']['time']) < 1e-8)
                check(tag + ' damage-scaled star with 0.8 body floor', abs(b['size'] - hit['enemy']['body']['visibleSize'][1] *
                      max(.8, .6 + .4 * (hp-hit['enemy']['hp']) / 35)) < 1e-8)
                draws = page.evaluate('window.coreDraws')
                check(tag + ' actual contact star drawn', any(d['key'] == b['key'] and
                      math.hypot(d['x']-b['x'], d['y']-b['y']) < .01 and d['time'] == b['time'] for d in draws))
                check(tag + ' previous tick no HP loss', result['previous']['enemy']['hp'] == hp)
                if mid == 'earthquake':
                    e = next(e for e in hit['generated']['states'] if e['id'] == mid)
                    check(tag + ' visible wave must reach center before damage', not result['premature'] and
                          e['contactRadius'] >= e['targetDistance'])
                    prior = next(e for e in result['previous']['generated']['states'] if e['id'] == mid)
                    check(tag + ' wave crossing within one 120Hz frame', prior['radius'] < e['targetDistance'])
                else:
                    r = hit['animation']['ribbons'][-1]
                    check(tag + ' surviving beam/beads terminate exactly on impact', r['age'] == 0 and
                          math.hypot(r['front']['x']-b['x'], r['front']['y']-b['y']) < .01)
                directions.paste(tile(f'{mid} / direction {direction} / impact'),
                                 ((direction % 4) * 360, (direction // 4) * 384))
                if mid == 'icebeam':
                    check(tag + ' frost starts at 0.3s on impact', hit['animation']['frost'] == [.3])
                    step(hit['feel']['remaining'] + .31)
                    check(tag + ' frost expires after 0.3s simulation', not snap()['animation']['frost'])
                samples.append({'id': mid, 'direction': direction, 'damage': hp-hit['enemy']['hp'],
                                'impactSeconds': hit['elapsed']-initial['elapsed'], 'burst': b})
                step(1)
                check(tag + ' all presentation expires', not snap()['animation']['bursts'] and
                      not snap()['animation']['ribbons'] and not snap()['generated']['states'])
            directions.save(SHOTS / f'{mid}-八方向.png')
            # No out-of-range damage; earthquake retains M4's square, not a circle.
            reset(mid, distance=250)
            cast(mid)
            step(2)
            s = snap()
            check(mid + ' range gate unchanged', s['enemy']['hp'] == s['enemy']['maxHP'] and not s['hits'])
            # 25fps real-time capture, including genuine hitstop, never retimed slow motion.
            for direction, name in [(0, '横向'), (2, '纵向'), (1, '斜向')]:
                reset(mid, direction)
                cast(mid)
                film, states = [], []
                for tick in range(38):
                    film.append(tile(f'{mid} / {name} / {tick*.04:.2f}s / 1x'))
                    states.append(snap())
                    step(.04)
                folder = PERSONAL if mid in ['watergun', 'icebeam'] else SHOTS
                path = folder / f'{mid}-{name}-原速.gif'
                film[0].save(path, save_all=True, append_images=film[1:], duration=40, loop=0)
                contact = next((i for i, s in enumerate(states) if s['animation']['bursts']), None)
                check(mid + name + ' recorded real impact', contact is not None)
                release = next(i for i, s in enumerate(states) if s['bullets'] or s['generated']['states'])
                indices = [max(0, release-2), (release+(contact or release))//2,
                           contact or release, min(37, (contact or release)+5)]
                sheet = Image.new('RGB', (1440, 384), '#223540')
                for col, index in enumerate(indices):
                    sheet.paste(film[index], (col*360, 0))
                sheet.save(SHOTS / f'{mid}-{name}-四时刻.png')
                with Image.open(path) as gif:
                    durations = []
                    decoded = Image.new('RGB', (1440, 384), '#223540')
                    for index in range(gif.n_frames):
                        gif.seek(index)
                        durations.append(gif.info['duration'])
                    for col, index in enumerate(indices):
                        gif.seek(index)
                        decoded.paste(gif.convert('RGB'), (col*360, 0))
                    decoded.save(SHOTS / f'{mid}-{name}-GIF解码.png')
                    check(mid + name + ' GIF is 1x', sum(durations) == 1520)
            # Same wall-clock frame, before/after, exact M4 runtime source for the left image.
            instant = m['windup'] + .12
            reset(mid)
            cast(mid)
            step(instant)
            after = tile(f'V1 / {mid} / {instant:.3f}s')
            current_page = page
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.on('pageerror', lambda e: errors.append(str(e)))
            baseline_url = URL + '/?test=1&baseline=M4'
            baseline_html = reference.read_text().replace((ROOT / 'assets').as_uri() + '/', 'assets/')
            page.route(baseline_url, serve_html(baseline_html))
            page.goto(baseline_url)
            ready(page)
            select(mid)
            reset(mid)
            cast(mid)
            step(instant)
            before = tile(f'M4 f64982b / {mid} / {instant:.3f}s')
            compare = Image.new('RGB', (720, 384))
            compare.paste(before, (0, 0))
            compare.paste(after, (360, 0))
            compare.save(SHOTS / f'{mid}-M4-vs-V1.png')
            page.close()
            page = current_page
        pixel_acceptance()
        for mid, m in catalog['moves'].items():
            if m['kind'] != 'nova':
                continue
            reset(mid)
            cast(mid)
            warning = snap()['warnings'][0]
            check(mid + ' nova warning is caster-centered ground ring',
                  warning['shape'] == 'ground-ring' and warning['x'] == snap()['player']['x'] and
                  warning['y'] == snap()['player']['y'])
            style = page.evaluate('''s=>{
              const c=document.createElement('canvas').getContext('2d');let rects=0,style=null;
              const rect=c.rect.bind(c),stroke=c.stroke.bind(c);
              c.rect=(...a)=>{rects++;rect(...a)};
              c.stroke=(...a)=>{style={color:c.strokeStyle,dash:c.getLineDash()};stroke(...a)};
              window.PoightTelegraph.draw(c,s,true,.01);
              return {...style,rects};
            }''', warning)
            check(mid + ' nova warning brown dashed edge never white grid',
                  style['color'] == '#d6af62' and style['dash'] == [7, 5] and style['rects'] == 0)
        # Generic damage entry covers all damaging moves, including the eight protected heroes.
        for mid, m in catalog['moves'].items():
            if m['damage'] <= 0 or m['kind'] in ['heal', 'guard', 'buff', 'splash']:
                continue
            reset('watergun')
            result = page.evaluate('(id)=>window.__waterTest.injectMoveHit("enemy",id)', mid)
            step(0)
            s = snap()
            check(mid + ' common impact iff successful direct damage', bool(s['animation']['bursts']) == bool(result))
        # Merge guard: B1 local dim may advance during hitstop, never during manual pause.
        page.evaluate('(p)=>window.__waterTest.select(p)', {
            **profile, 'player': 197, 'enemy': 7,
            'playerMoves': roster[197]['defaultMoves'], 'enemyMoves': roster[7]['defaultMoves'],
        })
        reset('bite', distance=24)
        cast('bite')
        step(catalog['moves']['bite']['windup'] + .04)
        page.keyboard.press('Escape')
        frozen = snap()
        step(.2)
        paused = snap()
        check('B1 manual pause freezes all jaw state including dimAge', frozen['phase'] == 'paused' and
              paused['generated']['states'] == frozen['generated']['states'])
        check('manual pause freezes core simulation clock', paused['animation']['time'] == frozen['animation']['time'])
        page.keyboard.press('Escape')
        for w, h in [(1440, 900), (390, 844), (844, 390)]:
            page.set_viewport_size({'width': w, 'height': h})
            page.wait_for_timeout(80)
            select('icebeam')
            reset('icebeam', 1)
            cast('icebeam')
            step(catalog['moves']['icebeam']['windup'] + .19)
            page.screenshot(path=str(SHOTS / f'实战-{w}x{h}.png'))
        # Normal live update and render for 60 seconds of match wall-clock, no stat overrides.
        for mode in ['', '&anim=old']:
            print('BATTLE 60s', mode or 'new', flush=True)
            page.goto(URL + '/?test=1' + mode)
            ready(page)
            select('earthquake')
            reset('earthquake')
            cast('earthquake')
            check(('old' if mode else 'new') + ' earthquake warning switch',
                  snap()['warnings'][0]['shape'] == ('grid' if mode else 'ground-ring'))
            page.evaluate('(p)=>window.__waterTest.select(p)', {**profile, 'player': 7, 'enemy': 9,
                          'playerMoves': ['watergun', 'icebeam', 'protect'],
                          'enemyMoves': ['watergun', 'icebeam', 'protect']})
            page.evaluate('window.__waterTest.reset(true);window.__waterTest.autopilot("poke")')
            result = page.evaluate('''()=>{
              let restarts=0,total=0,hits=0;
              for(let frame=0;frame<1800;frame++){
                const api=window.__waterTest;
                if(api.snapshot().phase!=='playing'){
                  hits+=api.snapshot().hits+api.snapshot().taken;
                  api.reset(true);api.autopilot('poke');restarts++;
                }
                api.step(1/30);total+=1/30;
              }
              const s=window.__waterTest.snapshot();
              return {total,restarts,hits:hits+s.hits+s.taken,enabled:s.animation.enabled};
            }''')
            check(('old' if mode else 'new') + ' full 60s real battle/render', result['total'] >= 59.99 and result['hits'] > 0, result)
            check(('old' if mode else 'new') + ' switch state', result['enabled'] == (not mode))
        # A new offline context, with all network denied; every asset comes from the portable folder.
        offline = browser.new_context(offline=True)
        page = offline.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('requestfailed', lambda r: requests.append(r.url))
        page.route('http://**/*', lambda route: route.abort())
        page.route('https://**/*', lambda route: route.abort())
        page.goto((ROOT / '候选试玩.html').as_uri() + '?test=1')
        ready(page)
        check('offline new context all animation images decoded', snap()['animation']['loaded'] > 40)
        check('offline baseline 104 atlases decoded', snap()['generated']['loaded'] == 104)
        for mid in CASTERS:
            select(mid)
            reset(mid)
            cast(mid)
            step(1)
            check(mid + ' offline actual hit', snap()['hits'] == 1)
        check('no network failures / 404 / JS errors', not requests and not responses and not errors,
              {'requests': requests, 'responses': responses, 'errors': errors})
        browser.close()
except Exception as exc:  # noqa: BLE001 - Persist incomplete runs as failures, never false green.
    failure = f'{type(exc).__name__}: {exc}'
finally:
    report = {'candidateSHA256': sha(ROOT / '候选试玩.html'), 'passed': sum(c['ok'] for c in checks),
              'failed': sum(not c['ok'] for c in checks) + bool(failure),
              'failure': failure, 'jsErrors': len(errors), 'errors': errors,
              'checks': checks, 'samples': samples, 'pixelSamples': pixel_samples}
    (OUT / '浏览器验收.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['passed', 'failed', 'jsErrors']}, ensure_ascii=False))
    if report['failed'] or errors:
        raise SystemExit(1)
