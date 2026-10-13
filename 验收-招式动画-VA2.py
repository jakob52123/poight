"""VA2: 19 real casts x 8 directions; exact contact clock, raster thresholds, 1x films."""
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
OUT = ROOT / '验收记录/招式动画-VA2'
SHOTS = OUT / '截图'
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get('POIGHT_TEST_URL', 'http://localhost:8873/').rstrip('/')
CASTERS = dict(zip([
    'bubble', 'ember', 'razorleaf', 'icywind', 'gust', 'poisonsting', 'swift', 'triattack',
    'leafstorm', 'psychocut', 'hydropump', 'solarbeam', 'psybeam', 'dragonbreath', 'hyperbeam',
    'signalbeam', 'gigadrain', 'freezedry', 'flashcannon',
], [7, 4, 3, 471, 21, 123, 133, 21, 3, 196, 9, 3, 196, 149, 143, 123, 3, 471, 9]))
FONT = ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc', 12)
checks, errors, pixels, samples = [], [], [], []
failure = None


def check(name, ok, detail=None):
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
    if not ok:
        print('FAIL ' + name + ' ' + json.dumps(detail, ensure_ascii=False), flush=True)
    if not ok:
        print('FAIL', name, str(detail)[:250], flush=True)


def ready(p):
    for _ in range(600):
        if p.evaluate('''()=>{try{return !!window.__waterTest?.snapshot().artReady}
                             catch{return false}}'''):
            return
        time.sleep(.03)
    raise TimeoutError('candidate load')


def snap():
    return page.evaluate('window.__waterTest.snapshot()')


def step(t):
    page.evaluate('(t)=>window.__waterTest.step(t)', t)


def select(mid, scene='arena-formal'):
    cid = CASTERS[mid]
    page.evaluate('(p)=>window.__waterTest.select(p)', {
        **profile, 'player': cid, 'enemy': 143, 'map': scene,
        'playerMoves': roster[cid]['defaultMoves'], 'enemyMoves': roster[143]['defaultMoves'],
    })


def reset(mid, direction=0, distance=100):
    page.evaluate('window.__waterTest.reset(true)')
    state = snap()
    b = state['environment']['bounds']
    # Same clay-background fixture correction as V1/VB1 for A1's enlarged emblem.
    offset = 450 if state['environment']['id'] == 'arena-formal' else 0
    x, y = (b['left'] + b['right']) / 2 - offset, (b['top'] + b['bottom']) / 2 - 95
    a = direction * math.pi / 4
    page.evaluate('(v)=>window.__waterTest.arrange(v)', {
        'ai': False, 'player': {'x': x, 'y': y, 'a': a},
        'enemy': {'x': x + math.cos(a)*distance, 'y': y + math.sin(a)*distance},
    })
    page.evaluate('(id)=>window.__waterTest.equip("player",[id])', mid)
    step(.1)
    return snap()


def cast(mid):
    return page.evaluate('(id)=>window.__waterTest.cast("player",id)', mid)


def tile(label, size=300):
    raw = page.evaluate('window.va2TilePNG()')
    im = Image.open(io.BytesIO(base64.b64decode(raw.split(',')[1]))).convert('RGB')
    out = Image.new('RGB', (size, size+24), '#223540')
    out.paste(im.resize((size, size), Image.Resampling.NEAREST), (0, 24))
    ImageDraw.Draw(out).text((5, 5), label, font=FONT, fill='white')
    return out


def hit_ticks(hp):
    return page.evaluate('''hp=>{
      const api=window.__waterTest;
      for(let n=1;n<=420;n++){api.step(1/120);if(api.snapshot().enemy.hp<hp)return n;}
      return null;
    }''', hp)


def audit_contact(mid, direction):
    initial = reset(mid, direction)
    hp = initial['enemy']['hp']
    tag = f'{mid}/{direction}'
    check(tag+' cast succeeds', cast(mid))
    check(tag+' cooldown blocks recast', not cast(mid))
    m = snap()['player']['attack']['move'] if 'move' in snap()['player']['attack'] else catalog['moves'][mid]
    step(m['windup']-.001)
    check(tag+' no windup damage', snap()['enemy']['hp'] == hp)
    step(.001)
    release = snap()
    r = release['animation']['releases'][-1]
    p = release['player']
    root = r['anchor']
    entries = roster[p['id']]['moveAnchors']
    # Independently name the intended body landmark; do not accept any nearby landmark.
    parts = {'razorleaf':'plant', 'leafstorm':'plant', 'gust':'wing', 'psychocut':'head',
             'psybeam':'head', 'signalbeam':'head', 'solarbeam':'flower',
             'gigadrain':'flower', 'flashcannon':'cannon'}
    part = parts.get(mid, 'mouth')
    key = None
    if m.get('batch2'):
        key = m.get('anchor') if m.get('anchor') in entries else next(
            (key for key in ['mouth', 'palms', 'head', 'cheek', 'plant', 'wing'] if key in entries),
            None)
    if key is None:
        key = next(key for key in ['r3-'+part, part, 'r3-mouth', 'mouth'] if key in entries)
    entry = entries[key]
    clip = catalog['art'][str(p['id'])][entry['role']]
    x, y = entry['points'][root['row']][root['frame']]
    ox, oy = clip.get('bodyOffsets', [[[0, 0]]*clip['frames']]*8)[root['row']][root['frame']]
    expected = (p['x']+(x-clip['anchorX']-ox)*p['scale'],
                p['y']+14+(y-clip['anchorY']-oy)*p['scale']-p['flightHeight'])
    gap = math.hypot(root['x']-expected[0], root['y']-expected[1])
    check(tag+' independent frame landmark <=6px', gap <= 6, gap)
    check(tag+' fan roots identical', len({(r['x'],r['y']) for r in release['animation']['releases']}) == 1)
    result = page.evaluate('''hp=>{
      const api=window.__waterTest;let previous=api.snapshot();
      for(let n=0;n<420;n++) {
        api.step(1/120);const s=api.snapshot();
        if(s.enemy.hp<hp)return {previous,hit:s};previous=s;
      }
      return {previous,hit:null};
    }''', hp)
    hit = result['hit']
    check(tag+' physical collision hits', hit is not None)
    if not hit:
        return
    burst = hit['animation']['bursts'][-1]
    ribbon = min(hit['animation']['ribbons'], key=lambda r: math.hypot(
        r['front']['x']-burst['x'], r['front']['y']-burst['y']))
    check(tag+' HP contact and burst same tick <=1frame', result['previous']['enemy']['hp'] == hp
          and burst['age'] == 0 and abs(burst['time']-hit['animation']['time']) < 1e-8)
    check(tag+' visible head on hit point <=6px', ribbon['age'] == 0 and math.hypot(
        ribbon['front']['x']-burst['x'], ribbon['front']['y']-burst['y']) <= 6)
    check(tag+' impact >=0.8 target H', burst['size'] >= hit['enemy']['body']['visibleSize'][1]*.8)
    check(tag+' actual hollow contact ring drawn', page.evaluate('''b=>window.va2Draws.some(
      d=>d.key===b.key&&Math.hypot(d.x-b.x,d.y-b.y)<.01&&d.time===b.time)''', burst))
    samples.append({'id': mid, 'direction': direction, 'gap': gap,
                    'damage': hp-hit['enemy']['hp'], 'contact': burst, 'ribbon': ribbon})
    return tile(f'{mid} / {direction} / contact')


def raster(mid, scene):
    print('RASTER', scene, mid, flush=True)
    select(mid, scene)
    initial = reset(mid)
    cast(mid)
    ticks = hit_ticks(initial['enemy']['hp'])
    check(f'{scene}/{mid} actual HP loss found', ticks is not None)
    if ticks is None:
        return
    reset(mid)
    page.evaluate('window.va2PixelProbe.enabled=false;window.va2PixelProbe.entries=[]')
    cast(mid)
    # Only mirror the last frame, avoiding retention of earlier positions.
    page.evaluate('(n)=>{for(let i=0;i<n;i++)window.__waterTest.step(1/120)}', ticks-2)
    page.evaluate('window.va2PixelProbe.entries=[];window.va2PixelProbe.enabled=true;window.__waterTest.step(1/120)')
    print('MEASURE', mid, ticks, flush=True)
    result = page.evaluate('window.measureVA2Pixels()')
    for key in ['composite', 'background', 'mask']:
        raw = result.pop(key)
        Image.open(io.BytesIO(base64.b64decode(raw.split(',')[1]))).save(
            SHOTS / f'像素-{scene}-{mid}-{key}.png')
    tag = f'{scene}/{mid}'
    check(tag+' actual opaque pixels', result['count'] >= (4 if mid == 'poisonsting' else 20), result)
    check(tag+' precontact full HP', result['hp'] == initial['enemy']['hp'])
    check(tag+' actual opaque leading edge never ahead of head',
          result['frontOverrun'] <= result['pixelSize'], result['frontOverrun'])
    beam = mid in list(CASTERS)[10:]
    if beam:
        ratio = .4 if mid in ['hydropump', 'solarbeam', 'hyperbeam'] else .25
        check(tag+' 8sections minimum opaque width', result['minimumBeamWidth'] >= max(10, result['height']*ratio), result)
        check(tag+' core luma >=230', result['centerLuma'] >= 230, result)
    elif mid == 'poisonsting':
        h, pixel = result['height'], result['pixelSize']
        check(tag+' needle length .30-.40H, width <=.08H',
              .30*h-pixel <= result['opaqueLength'] <= .40*h+pixel
              and result['opaqueDiameter'] <= .08*h+pixel, result)
    else:
        h, pixel = result['height'], result['pixelSize']
        check(tag+' small projectile maximum extent .25-.45H',
              .25*h-pixel <= result['maxDimension'] <= .45*h+pixel, result)
    # FX1's <=.08H needle has a white contour; preserve S>=.55, not the old fat-rod fill.
    minimum_color = .10 if mid == 'poisonsting' else .30
    check(tag+f' nonwhite attribute pixels S>=.55 and >={minimum_color:.0%}',
          result['saturation'] >= .55 and result['colorFraction'] >= minimum_color, result)
    check(tag+' same-mask background luma difference >=60', result['contrast'] >= 60, result)
    step(1/120)
    check(tag+' next tick contact and HP', snap()['enemy']['hp'] < initial['enemy']['hp']
          and snap()['animation']['bursts'][-1]['age'] == 0)
    pixels.append({'scene':scene, **result})
    page.evaluate('window.va2PixelProbe.enabled=false')


try:
    guards = json.loads((ROOT / '验收记录/招式第3批/受保护图集.json').read_text())
    record = json.loads((ROOT / '招式特效/生图重做/实景预览/构建记录.json').read_text())['assets']
    for g in guards:
        mid = g['id']
        path = ROOT / (str(Path('招式特效/主角八招') / mid / (mid+'-动画.png'))
                       if mid in ['thunderbolt','thunder'] else record[mid]['output'])
        check(mid+' protected atlas SHA unchanged', hashlib.sha256(path.read_bytes()).hexdigest() == g['sha256'])
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width':1440,'height':900})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(URL+'/?test=1')
        ready(page)
        catalog = page.evaluate('window.__waterTest.catalog()')
        roster = {r['id']:r for r in catalog['roster']}
        profile = snap()['profile']
        page.evaluate((ROOT/'tests/招式动画-VA2像素.js').read_text())
        crop_function = '''()=>{
          window.va2TilePNG=()=>{
            const s=window.__waterTest.snapshot(),game=document.querySelector('#game'),
              scale=game.width/s.viewport.width,
              x=((s.player.x+s.enemy.x)/2-s.camera.x)*scale,
              y=((s.player.y+s.enemy.y)/2-16-s.camera.y)*scale,r=90*scale;
            const c=document.createElement('canvas');c.width=300;c.height=300;
            const ctx=c.getContext('2d');ctx.imageSmoothingEnabled=false;
            ctx.drawImage(game,Math.round(x-r),Math.round(y-r),Math.round(r*2),Math.round(r*2),0,0,300,300);
            return c.toDataURL();
          };
        }'''
        page.evaluate(crop_function)
        old_page = browser.new_page(viewport={'width':1440,'height':900})
        old_page.on('pageerror',lambda e:errors.append(str(e)))
        old_page.goto(URL+'/?test=1&anim=old');ready(old_page)
        old_page.evaluate(crop_function)
        page.evaluate('''()=>{
          // P6 replaced the solid star texture with drawBurst's hollow contact ring.
          // Observe the real dispatch, preserving contact identity/coordinates/tick checks.
          window.va2Draws=[];const proto=window.PoightMoveAnimations.prototype,draw=proto.drawBurst;
          proto.drawBurst=function(ctx,b,...rest){
            window.va2Draws.push({key:b.key,x:b.x,y:b.y,size:b.size,time:this.time});
            window.va2Draws=window.va2Draws.slice(-1500);
            return draw.call(this,ctx,b,...rest);
          };
        }''')
        overview = Image.new('RGB',(600,324*len(CASTERS)),'#223540')
        for row, mid in enumerate(CASTERS):
            print('CHECK', mid, flush=True)
            select(mid)
            directions = Image.new('RGB',(1200,648),'#223540')
            for direction in range(8):
                im = audit_contact(mid, direction)
                if im:
                    directions.paste(im, ((direction%4)*300,(direction//4)*324))
            directions.save(SHOTS/f'{mid}-八方向.png')
            # Original wall-clock 25fps recording, including real hitstop.
            reset(mid)
            cast(mid)
            film = []
            captured = page.evaluate('''()=>{
              const result=[],api=window.__waterTest;
              for(let n=0;n<55;n++){
                const s=api.snapshot();result.push({png:window.va2TilePNG(),
                  bullets:s.bullets.length,contact:s.animation.bursts.length});api.step(.04);
              }return result;
            }''')
            for n, frame in enumerate(captured):
                im = Image.open(io.BytesIO(base64.b64decode(frame['png'].split(',')[1]))).convert('RGB')
                out = Image.new('RGB',(300,324),'#223540');out.paste(im,(0,24))
                ImageDraw.Draw(out).text((5,5),f'{mid} / {n*.04:.2f}s / 1x',font=FONT,fill='white')
                film.append(out)
            path = SHOTS/f'{mid}-横向-原速.gif'
            film[0].save(path,save_all=True,append_images=film[1:],duration=40,loop=0)
            contact = next((n for n,s in enumerate(captured) if s['contact']),None)
            check(mid+' film includes actual contact', contact is not None)
            release = next(n for n,s in enumerate(captured) if s['bullets'])
            indices = [max(0,release-2),(release+(contact or release))//2,
                       contact or release,min(54,(contact or release)+4)]
            sheet = Image.new('RGB',(1200,324),'#223540')
            with Image.open(path) as gif:
                duration = 0
                for n in range(gif.n_frames):
                    gif.seek(n);duration += gif.info['duration']
                check(mid+' GIF 1x 2200ms',duration==2200)
                for col,index in enumerate(indices):
                    gif.seek(index);sheet.paste(gif.convert('RGB'),(col*300,0))
            sheet.save(SHOTS/f'{mid}-四时刻-GIF解码.png')
            instant = (release + max(release, (contact or release)-1))//2*.04
            reset(mid);cast(mid);step(instant)
            after = tile(f'VA2 / {mid} / {instant:.2f}s')
            current = page
            page = old_page
            select(mid);reset(mid);cast(mid);step(instant)
            before = tile(f'M4 anim=old / {mid} / {instant:.2f}s')
            check(mid+' old mode disabled',not snap()['animation']['enabled'])
            page=current
            overview.paste(before,(0,row*324));overview.paste(after,(300,row*324))
            # Range and invulnerability are behavior assertions, not visual snapshots.
            reset(mid,distance=700);cast(mid);step(4)
            check(mid+' no out-of-range damage',snap()['enemy']['hp']==snap()['enemy']['maxHP'])
            reset(mid)
            rejected = page.evaluate('''id=>{
              const api=window.__waterTest;api.dash('enemy',1,0);
              return !api.injectMoveHit('enemy',id);
            }''',mid)
            check(mid+' real dash immunity rejects direct damage', rejected and
                  snap()['enemy']['hp']==snap()['enemy']['maxHP'] and not snap()['animation']['bursts'])
        overview.save(SHOTS/'整批-M4-vs-VA2.png')
        for scene in ['arena-formal','arena-natural']:
            for mid in CASTERS:
                raster(mid,scene)
        for w,h in [(1440,900),(390,844),(844,390)]:
            page.set_viewport_size({'width':w,'height':h});page.wait_for_timeout(100)
            select('solarbeam');reset('solarbeam');cast('solarbeam');step(.95)
            page.screenshot(path=str(SHOTS/f'实战-{w}x{h}.png'))
        offline = browser.new_context(offline=True)
        page = offline.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto((ROOT/'候选试玩.html').as_uri()+'?test=1');ready(page)
        for mid in CASTERS:
            select(mid);reset(mid);cast(mid);step(2)
            check(mid+' offline real hit',snap()['hits']>0)
        check('0 JS errors',not errors,errors)
        browser.close()
except Exception as exc:  # noqa: BLE001 - Never report incomplete checks as green.
    failure = f'{type(exc).__name__}: {exc}'
finally:
    report = {'passed':sum(c['ok'] for c in checks),'failed':sum(not c['ok'] for c in checks)+bool(failure),
              'jsErrors':len(errors),'failure':failure,'errors':errors,'checks':checks,
              'samples':samples,'pixelSamples':pixels}
    (OUT/'浏览器验收.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['passed','failed','jsErrors','failure']},ensure_ascii=False))
    if report['failed'] or errors:
        raise SystemExit(1)
