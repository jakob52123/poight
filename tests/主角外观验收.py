"""VH read-only raster metrics and deterministic real-speed combat evidence."""
import base64
import hashlib
import io
import json
import math
import re
import subprocess
import time
from itertools import pairwise

from PIL import Image, ImageDraw, ImageFont

IDS = ['thunderbolt', 'quickattack', 'irontail', 'thunder',
       'flamethrower', 'fireblast', 'dragonclaw', 'airslash']
NAMES = ['十万伏特', '电光一闪', '铁尾', '打雷', '喷射火焰', '大字爆炎', '龙爪', '空气斩']
KINDS = dict(zip(IDS, ['beam', 'rush', 'tail', 'thunder', 'beam', 'projectile', 'claw', 'projectile']))
M4 = 'f64982be201b70212a8a6b3e0ff5fad6618f6cad'
FONT = ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc', 14)


def run(page, root, url, check, *, directions=range(8), evidence=True):
    out = root / '验收记录/主角八招重做'
    shots = out / '截图'
    personal = out / '给本人'
    for d in (shots, personal):
        d.mkdir(parents=True, exist_ok=True)
    record = check

    def check(name, ok, detail=None):
        record(name, ok, detail)
        if not ok:
            print('FAIL:', name, flush=True)

    catalog = page.evaluate('window.__waterTest.catalog()')
    roster = {r['id']: r for r in catalog['roster']}
    profile = page.evaluate('window.__waterTest.snapshot().profile')
    moves = catalog['moves']
    pixels = []
    selection = None
    candidate = (root / '候选试玩.html').read_text()
    bundle, _ = json.JSONDecoder().raw_decode(candidate.split('const DATA = ', 1)[1])
    claw = bundle['moveAnimations']['mapping']['effects']['hero-claw-strike']
    claw_pixels = list(Image.open(root/claw['file']).convert('RGBA').get_flattened_data())
    check('VH claw actual opaque purple/cyan gradient endpoints survive palette brightening',
          claw_pixels.count((123, 92, 255, 255)) >= 8
          and claw_pixels.count((111, 240, 255, 255)) >= 8)
    page.evaluate((root / 'tests/主角动画像素.js').read_text())
    for name in ['游戏数据.py', '体型判定.js', '招式特效/主角打包.py']:
        if not (root / name).exists():
            continue
        # M6b union: game data already includes accepted F1 HP x3 and S1 statuses;
        # body/hero atlas packer retain the V1 byte guards without exceptions.
        revision = 'bc5e66c' if name == '游戏数据.py' else 'd3aedfac76bed3e43d1fd07f8a8ab125594bb061'
        baseline = subprocess.check_output(['git', 'show', f'{revision}:{name}'], cwd=root)
        check('VH unchanged combat/body bytes: '+name, (root/name).read_bytes() == baseline)
    for mid in IDS:
        caster = 25 if mid in IDS[:4] else 6
        scope = page.evaluate('''({mid,caster})=>{
          const uses=window.PoightHeroVisuals.prototype.uses, self={core:{enabled:true}};
          return {owner:uses.call(self,mid,{id:caster}),
            other:uses.call(self,mid,{id:7}), off:uses.call({core:{enabled:false}},mid,{id:caster})};
        }''', {'mid': mid, 'caster': caster})
        check('VH owner-only opt-in and old-mode fallback: '+mid,
              scope['owner'] and not scope['other'] and not scope['off'], scope)
    for source in json.loads((root/'招式动画/原版/VH来源.json').read_text()):
        check('VH original source SHA: '+source['file'],
              hashlib.sha256((root/'招式动画/原版'/source['file']).read_bytes()).hexdigest() == source['sha256'])

    def snap():
        return page.evaluate('window.__waterTest.snapshot()')

    def step(t):
        page.evaluate('(t)=>window.__waterTest.step(t)', t)

    def setup(mid, direction=0, scene='arena-formal'):
        nonlocal selection
        caster = 25 if mid in IDS[:4] else 6
        enemy = 6 if caster == 25 else 25
        if selection != (caster, enemy, scene):
            page.evaluate('(p)=>window.__waterTest.select(p)', {
                **profile, 'player': caster, 'enemy': enemy, 'map': scene,
                'playerMoves': roster[caster]['defaultMoves'], 'enemyMoves': roster[enemy]['defaultMoves'],
            })
            selection = (caster, enemy, scene)
        page.evaluate('window.__waterTest.reset(true)')
        bounds = snap()['environment']['bounds']
        # A1 enlarged the emblem to 440–520 world pixels. Keep the original
        # clay-background contract (not the now-white lower half of that emblem).
        # Natural arena fixture and every luminance/chroma/size threshold stay unchanged.
        cx = (bounds['left'] + bounds['right']) / 2 - (450 if scene == 'arena-formal' else 160)
        cy = (bounds['top'] + bounds['bottom']) / 2 - 20
        a = direction * math.pi / 4
        distance = 22 if moves[mid]['kind'] == 'melee' else 95
        page.evaluate('(d)=>window.__waterTest.arrange(d)', {
            'ai': False, 'player': {'x': cx, 'y': cy, 'a': a},
            'enemy': {'x': cx + math.cos(a)*distance, 'y': cy + math.sin(a)*distance, 'a': a+math.pi},
        })
        step(.2)
        return snap()

    def cast(mid):
        return page.evaluate('(m)=>window.__waterTest.cast("player",m)', mid)

    def ticks(n):
        page.evaluate('''n=>{
          const api=window.__waterTest;
          for(let i=0;i<n;i++)api.step(1/120,false);
          api.step(0);
        }''', n)

    def image(raw):
        return Image.open(io.BytesIO(base64.b64decode(raw.split(',')[1]))).convert('RGB')

    def tile(label, fixed=None):
        # Crop the actual backing canvas BEFORE PNG transport; no alternate move renderer.
        raw = page.locator('#game').evaluate('''(c,fixed)=>{
          const s=window.__waterTest.snapshot(), scale=c.width/s.viewport.width;
          const center=fixed || [(s.player.x+s.enemy.x)/2,(s.player.y+s.enemy.y)/2-45];
          const x=(center[0]-s.camera.x)*scale, y=(center[1]-s.camera.y)*scale;
          const half=(center[2] || 270)/2*scale;
          const left=Math.round(x-half), top=Math.round(y-half);
          const tile=document.createElement('canvas');tile.width=tile.height=360;
          const ctx=tile.getContext('2d');ctx.imageSmoothingEnabled=false;
          ctx.drawImage(c,left,top,Math.round(x+half)-left,Math.round(y+half)-top,0,0,360,360);
          return tile.toDataURL();
        }''', fixed)
        result = Image.new('RGB', (360, 384), '#253039')
        result.paste(image(raw), (0, 24))
        ImageDraw.Draw(result).text((6, 5), label, fill='white', font=FONT)
        return result

    for scene in ['arena-formal', 'arena-natural']:
        for mid in IDS:
            print('Raster:', scene, mid, flush=True)
            for direction in directions:
                tag = f'VH/{scene}/{mid}/{direction}'
                start = setup(mid, direction, scene)
                if mid == IDS[0] and direction == directions[0]:
                    check(scene+' actual rendered variant is A', start['environment']['variant'] == 'A')
                hp = start['enemy']['hp']
                cast(mid)
                hit = page.evaluate('''hp=>{
                  const api=window.__waterTest;
                  for(let i=1;i<240;i++) {
                    api.step(1/120,false);
                    if(api.snapshot().enemy.hp<hp){api.step(0);return i;}
                  }
                  return null;
                }''', hp)
                check(tag+' actual hit found', hit is not None)
                if hit is None:
                    continue
                at_hit = snap()
                events = at_hit['animation']['hero']['events']
                check(tag+' contact clock equals first HP loss (<=1 frame)',
                      bool(events) and events[-1]['id'] == mid
                      and abs(events[-1]['time']-at_hit['animation']['time']) <= 1/120)
                setup(mid, direction, scene)
                page.evaluate('(p)=>Object.assign(window.heroProbe,p)', {
                    'enabled': False, 'suppress': False, 'last': None, 'contact': None,
                    'id': mid, 'kind': KINDS[mid]})
                cast(mid)
                before = mid in ['thunderbolt', 'flamethrower', 'fireblast', 'airslash', 'quickattack']
                ticks(hit-1 if before else hit)
                page.evaluate('window.heroProbe.enabled=true')
                step(0)  # Mirror only the measured frame, not every intermediate render.
                measurement = page.evaluate('window.measureHeroPixels()')
                check(tag+' actual raster captured', measurement is not None)
                if measurement is None:
                    page.evaluate('window.heroProbe.enabled=false')
                    continue
                for key in ['composite', 'background', 'mask']:
                    raw = measurement.pop(key)
                    Image.open(io.BytesIO(base64.b64decode(raw.split(',')[1]))).save(
                        shots / f'{scene}-{mid}-{direction}-{key}.png')
                m = measurement
                h, th = m['sourceHeight'], m['targetHeight']
                check(tag+' opaque body exists (alpha>=250)', m['count'] > 20, m)
                if mid in ['thunderbolt', 'flamethrower']:
                    check(tag+' eight normal sections >= max(10,.30H)',
                          m['minimumBeamWidth'] >= max(10, h*.30), m)
                    check(tag+' continuous core luminance >=230', m['centerLuma'] >= 230, m)
                elif mid == 'fireblast':
                    check(tag+' opaque glyph >= .70H', min(m['width'], m['height']) >= h*.70, m)
                    centers = m['centers']
                    check(tag+' exactly five real opaque flame sprites',
                          len(centers) == 5 and all(c['count'] > 8 for c in centers), centers)
                    if len(centers) == 5:
                        top, left, right, leg_l, leg_r = centers
                        check(tag+' 大 geometry: top, horizontal arms, split lower legs',
                              abs(left['y']-right['y']) < 2 and abs(leg_l['y']-leg_r['y']) < 2
                              and top['y'] < left['y'] < leg_l['y']
                              and left['x'] < leg_l['x'] < top['x'] < leg_r['x'] < right['x']
                              and abs(top['x']-(left['x']+right['x'])/2) < 2, centers)
                        check(tag+' flame centers separated (no fire-wall overlap)', all(
                            math.hypot(a['x']-b['x'], a['y']-b['y']) > max(a['width'], b['width'])*1.08
                            for i, a in enumerate(centers) for b in centers[i+1:]), centers)
                elif mid == 'thunder':
                    check(tag+' bolt >=3H tall and >=.35H wide',
                          m['height'] >= 3*h and m['width'] >= .35*h, m)
                    check(tag+' bolt actually enters visible camera top edge', m['screenTop'] <= 1, m)
                    trunks = [s for s in m['strokes'] if s['color'] == '#ffe529' and len(s['points']) == 9]
                    branches = [s for s in m['strokes'] if s['color'] == '#ffe529' and len(s['points']) == 4]
                    check(tag+' actual draw: 8 descending segments, 3 short branches, .25-.35H trunk',
                          len(trunks) == 1 and len(branches) == 3
                          and .25*h <= trunks[0]['width'] <= .35*h
                          and all(a[1] < b[1] for a, b in pairwise(trunks[0]['points'])), m['strokes'])
                elif mid == 'airslash':
                    check(tag+' opaque crescent normal span >=max(14,.45H)',
                          m['normal'] >= max(14, h*.45), m)
                elif mid == 'dragonclaw':
                    check(tag+' opaque contact scars >=.70 target H',
                          max(m['width'], m['height']) >= th*.70, m)
                else:
                    check(tag+' readable silver/white action >=.30H and >=14px',
                          max(m['width'], m['height']) >= max(14, h*.30), m)
                check(tag+' mean background luminance contrast >=60', m['contrast'] >= 60, m)
                if mid not in ['irontail', 'quickattack']:
                    check(tag+' attribute pixels saturation >=.55, coverage >=.30',
                          m['saturation'] >= .55 and m['colorFraction'] >= .30, m)
                if before:
                    check(tag+' precontact has full HP', snap()['enemy']['hp'] == hp)
                    step(1/120)
                    now = snap()
                    check(tag+' next tick visible contact and HP loss', now['enemy']['hp'] < hp
                          and now['animation']['hero']['bursts'][-1]['age'] == 0)
                contact = page.evaluate('window.heroProbe.contact')
                check(tag+' actual opaque contact raster on damaging frame',
                      contact is not None and contact['count'] > 20
                      and (0 <= contact['age'] <= 1/120 if mid == 'thunder' else contact['age'] == 0)
                      and abs(contact['time']-snap()['animation']['time']) <= 1/120, contact)
                pixels.append({'scene': scene, 'id': mid, 'direction': direction,
                               'variant': start['environment']['variant'], 'contactTick': hit, **m})
                if mid in ['thunder', 'dragonclaw']:
                    stages = []
                    revision_start = snap()['animation']['time']
                    # Real simulation ticks; naturally consume hitstop without changing its duration.
                    # Include BOTH white sweeps and the full ring lifetime.
                    for i in range(42 if mid == 'thunder' else 13):
                        if i:
                            page.evaluate('''end=>{
                              const api=window.__waterTest;
                              while(api.snapshot().animation.time < end-1e-7)api.step(1/120,false);
                              api.step(0);
                            }''', revision_start+i/120)
                        revision = page.evaluate('window.measureHeroRevision()')
                        revision['tick'] = i
                        stages.append(revision)
                        if mid == 'thunder':
                            check(tag+f'/{i} target original-color opaque pixels >=50%',
                                  revision['targetPixels'] > 20 and revision['originalFraction'] >= .50,
                                  revision)
                            if i < 27:  # Opaque ring; final .12s intentionally fades.
                                check(tag+f'/{i} hollow ring diameter <=1.3 target H',
                                      0 < revision['ringDiameter'] <= 1.3*th
                                      and revision['ringCenterPixels'] == 0, revision)
                        else:
                            components = revision['components']
                            expected = min(3, 1 + math.floor((i/120+1e-6)/.04))
                            check(tag+f'/{i} sequential slash connected components = {expected}',
                                  len(components) == expected and all(
                                      c['length'] >= .8*th and c['width'] >= 4 for c in components), revision)
                    if mid == 'thunder':
                        flashes = [s['flashPixels'] > 20 for s in stages]
                        bolts = [s['boltOpaque'] > 20 for s in stages]
                        check(tag+' actual white silhouette raster flashes exactly twice',
                              sum(b and not a for a, b in pairwise([False]+flashes)) == 2, flashes)
                        check(tag+' actual bolt raster bright-dark-bright in first .10s',
                              sum(b and not a for a, b in pairwise([False]+bolts)) == 2
                              and bolts[0] and not any(bolts[13:]), bolts)
                    pixels[-1]['revisionFrames'] = stages
                page.evaluate('window.heroProbe.enabled=false')
                if mid == 'quickattack':
                    state = setup(mid, direction, scene)
                    a = direction * math.pi / 4
                    page.evaluate('(p)=>window.__waterTest.arrange({enemy:p})', {
                        'x': state['player']['x']+math.cos(a)*260,
                        'y': state['player']['y']+math.sin(a)*260})
                    cast(mid)
                    ghosts = page.evaluate('''()=>{
                      const api=window.__waterTest, frames=[];
                      for(let i=0;i<28;i++) {api.step(1/120,false);frames.push(api.snapshot().heroGhosts);}
                      api.step(0);
                      return frames;
                    }''')
                    readable = next((f for f in ghosts if 3 <= len(f) <= 4), [])
                    check(tag+' 3-4 actual history silhouettes, graded alpha, distinct positions',
                          len(readable) >= 3 and all(g['alpha'] > 0 for g in readable)
                          and len({(g['x'], g['y']) for g in readable}) == len(readable)
                          and all(a['alpha'] < b['alpha'] for a, b in pairwise(readable)), readable)
            (out / '像素量化.json').write_text(json.dumps(pixels, ensure_ascii=False, indent=2)+'\n')

    if not evidence:
        return pixels
    # Real M4 code from git, not a renamed fallback mode. Atlases and hero data are unchanged.
    candidate = (root / '候选试玩.html').read_text()
    start = candidate.index('const DATA = ') + len('const DATA = ')
    data, _ = json.JSONDecoder().raw_decode(candidate[start:])
    data.pop('moveAnimations')
    paths = ['世界地图.js', '竞技场.js', '草丛藏身.js', '大地图通行.js', '体型判定.js',
             '生图招式.js', '招式第3批.js', '平衡测试.js', '打击感.js', '瞄准预警.js',
             '战斗界面方案.js', '跳跃.js', '对战.js']
    sources = [subprocess.check_output(['git', 'show', f'{M4}:{p}'], cwd=root).decode() for p in paths]
    script = '\n'.join(sources).replace('__GAME_DATA__', json.dumps(data, ensure_ascii=False).replace('</', '<\\/'))
    html = re.sub(r'<script>.*?</script>', lambda _: '<script>'+script+'</script>', candidate, flags=re.DOTALL)
    (out / 'M4-对照.html').write_text(html.replace('assets/', (root/'assets').as_uri()+'/'))
    (out / 'M4-对照来源.json').write_text(json.dumps({
        'commit': M4, 'runtime': {p: hashlib.sha256(s.encode()).hexdigest() for p, s in zip(paths, sources)},
        'note': 'Exact M4 JS; hero atlases and runtime data unchanged; no anim=old impersonation.',
    }, ensure_ascii=False, indent=2)+'\n')
    overview = Image.new('RGB', (1440, 1536), '#253039')
    comparisons = {}
    for mid, name in zip(IDS, NAMES):
        print('Media:', mid, flush=True)
        decoded_indices = {}
        for direction, heading in [(0, '横向'), (1, '斜向')]:
            s = setup(mid, direction)
            fixed = ((s['player']['x']+s['enemy']['x'])/2, (s['player']['y']+s['enemy']['y'])/2-45)
            if mid == 'thunder':
                # Full vertical camera channel, not the old crop hiding its sky origin.
                span = max(270, s['enemy']['y'] - s['camera']['y'] + 65)
                fixed = (fixed[0], s['camera']['y'] + span/2, span)
            cast(mid)
            frames, hit_index = [], None
            hp = s['enemy']['hp']
            for i in range(41):
                if i:
                    step(.04)
                if snap()['enemy']['hp'] < hp and hit_index is None:
                    hit_index = i
                frames.append(tile(f'{name} · {heading} · {i*.04:.2f}s · 1×', fixed))
            decoded_indices[heading] = hit_index
            path = out / f'{mid}-{heading}-原速.gif'
            frames[0].save(path, save_all=True, append_images=frames[1:], duration=40, loop=0,
                           disposal=2, optimize=False)
            with Image.open(path) as gif:
                check(f'GIF/{mid}/{heading} original 25fps / 1.64s',
                      gif.n_frames == 41 and all((gif.seek(i) or gif.info['duration'] == 40)
                                               for i in range(gif.n_frames)))
            # Four exact simulation moments, not arbitrary best-looking screenshot selection.
            setup(mid, direction)
            cast(mid)
            elapsed_ticks = 0
            windup_ticks = max(0, round(moves[mid]['windup']*.5*120))
            ticks(windup_ticks)
            elapsed_ticks += windup_ticks
            windup = tile(name+' · 前摇', fixed)
            contact_tick = next(p['contactTick'] for p in pixels
                                if p['id'] == mid and p['direction'] == direction
                                and p['scene'] == 'arena-formal')
            ticks(contact_tick-1-elapsed_ticks)
            last = tile(name+' · 接触前1帧', fixed)
            step(1/120)
            elapsed_ticks = contact_tick
            contact = tile(name+' · 首次命中', fixed)
            claw_pause = snap()['feel']['remaining'] if mid == 'dragonclaw' else 0
            step(claw_pause + .09 if mid == 'dragonclaw' else .18)
            after = tile(name+(' · 三爪齐出 +0.09s' if mid == 'dragonclaw' else ' · 命中后'), fixed)
            sheet = Image.new('RGB', (1440, 384), '#253039')
            for j, im in enumerate([windup, last, contact, after]):
                sheet.paste(im, (j*360, 0))
            sheet.save(shots / f'{mid}-{heading}-四时刻.png')
            # Three times the full combat crop; retain bolt tips, all five flames and rush ghosts.
            # This presentation zoom is never used for world-pixel size assertions.
            closeup = after if mid == 'dragonclaw' else contact if mid in ['thunder', 'irontail'] else last
            closeup.crop((0, 24, 360, 384)).resize((1080, 1080), Image.Resampling.NEAREST).save(
                shots / f'{mid}-{heading}-3倍特写.png')
            if direction == 0:
                (personal / f'{name}-横向原速.gif').write_bytes(path.read_bytes())
                compare_ticks = elapsed_ticks-1 if mid not in ['thunder', 'dragonclaw', 'irontail'] else elapsed_ticks
                if mid == 'dragonclaw':
                    # Compare both versions at the third scar's emergence, not only scar #1.
                    setup(mid, direction)
                    cast(mid)
                    compare_ticks = elapsed_ticks + math.ceil(claw_pause*120) + 11
                    ticks(compare_ticks)
                    comparisons[mid] = (tile(name+' · 三爪齐出', fixed), compare_ticks, fixed)
                else:
                    comparisons[mid] = (last if compare_ticks < elapsed_ticks else contact, compare_ticks, fixed)
        decoded = Image.new('RGB', (1440, 768), '#253039')
        for row, heading in enumerate(['横向', '斜向']):
            with Image.open(out / f'{mid}-{heading}-原速.gif') as gif:
                hit_index = decoded_indices[heading]
                indices = [max(0, round(moves[mid]['windup']*.5/.04)),
                           max(0, (hit_index or 1)-2), hit_index or 1,
                           min(40, (hit_index or 1)+(6 if mid == 'dragonclaw' else 4))]
                for col, index in enumerate(indices):
                    gif.seek(index)
                    decoded.paste(gif.convert('RGB'), (col*360, row*384))
        decoded.save(shots / f'{mid}-GIF解码读图.png')
    # One old/new overview for all eight moves, identical tick and placement.
    baseline_url = url+'/?test=1&baseline=VH-M4'
    page.route(baseline_url, lambda route: route.fulfill(status=200, content_type='text/html', body=html))
    page.goto(baseline_url)
    for _ in range(600):
        if page.evaluate('''()=>{try{return window.__waterTest?.snapshot().artReady}catch{return false}}'''):
            break
        time.sleep(.03)
    for i, (mid, name) in enumerate(zip(IDS, NAMES)):
        new, count, fixed = comparisons[mid]
        setup(mid)
        cast(mid)
        ticks(count)
        old = tile(name+' · M4 改前', fixed)
        new = new.copy()
        draw = ImageDraw.Draw(new)
        draw.rectangle((0, 0, 359, 23), fill='#253039')
        draw.text((6, 5), name+' · VH 改后', fill='white', font=FONT)
        x, y = (i % 2)*720, (i//2)*384
        overview.paste(old, (x, y))
        overview.paste(new, (x+360, y))
    overview.save(shots / '八招-M4-vs-VH-总览.png')
    page.goto(url+'/?test=1')
    for _ in range(600):
        if page.evaluate('window.__waterTest?.snapshot().artReady'):
            break
        time.sleep(.03)
    (out / '像素量化.json').write_text(json.dumps(pixels, ensure_ascii=False, indent=2)+'\n')
    return pixels
