"""VA1: 21 physical shots x 8 directions; real precontact rasters on both A arenas."""
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
OUT = ROOT / '验收记录/招式动画-VA1'
SHOTS = OUT / '截图'
GIFS = OUT / '原速GIF'
for folder in [SHOTS, GIFS]:
    folder.mkdir(parents=True, exist_ok=True)
URL = os.environ.get('POIGHT_TEST_URL', 'http://localhost:8872/').rstrip('/')
CASTERS = {'waterpulse': 9, 'energyball': 3, 'thundershock': 25, 'rockthrow': 448,
           'mudshot': 1, 'shadowball': 94, 'confusion': 65, 'dragonpulse': 149,
           'sludgebomb': 94, 'moonblast': 282, 'brine': 9, 'scald': 54, 'seedbomb': 3,
           'electroball': 25, 'iceshard': 471, 'aurasphere': 448, 'focusblast': 448,
           'powergem': 95, 'venoshock': 94, 'storedpower': 196, 'darkpulse': 197}
font_path = Path('/System/Library/Fonts/STHeiti Medium.ttc')
FONT = ImageFont.truetype(str(font_path), 12) if font_path.exists() else ImageFont.load_default()
checks, errors, pixels, samples, traces, hit_ticks = [], [], [], [], {}, {}
failure = None
CAPTURE = os.environ.get('POIGHT_VA1_CAPTURE') == '1'
CAPTURE_ONLY = os.environ.get('POIGHT_VA1_CAPTURE_ONLY') == '1'
PIXELS_ONLY = os.environ.get('POIGHT_VA1_PIXELS_ONLY') == '1'


def visual_hash():
    paths = [ROOT / name for name in ['招式动画/VA1飞行弹.js', '招式动画接入.js',
             '对战.js', '生图招式.js', '游戏数据.py', '招式动画/VA1打包.py',
             '招式动画/招式动画.json']]
    paths += sorted((ROOT / '招式动画/VA1素材').glob('*.png'))
    h = hashlib.sha256((ROOT / '候选试玩.html').read_bytes())
    h.update(json.dumps(CASTERS, sort_keys=True).encode())
    for path in paths:
        h.update(path.read_bytes())
    return h.hexdigest()


def check(name, ok, detail=None):
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
    if not ok:
        print('FAIL ' + name + ' ' + json.dumps(detail, ensure_ascii=False), flush=True)


def ready(p):
    for _ in range(int(os.environ.get('POIGHT_READY_POLLS', '600'))):
        if p.evaluate('()=>window.__waterTest?.snapshot().artReady'):
            return
        time.sleep(.03)
    raise TimeoutError('loading candidate')


def snap():
    return page.evaluate('window.__waterTest.snapshot()')


def step(t):
    page.evaluate('(t)=>window.__waterTest.step(t)', t)


def select(mid, scene='arena-formal'):
    caster = CASTERS[mid]
    page.evaluate('(p)=>window.__waterTest.select(p)', {
        **profile, 'map': scene, 'player': caster, 'enemy': 7,
        'playerMoves': roster[caster]['defaultMoves'], 'enemyMoves': roster[7]['defaultMoves'],
    })


def scene_id(state):
    return state['environment']['id']


def reset(mid, direction=0, distance=105, offset=0):
    page.evaluate('window.va1Draws=[];window.__waterTest.reset(true)')
    s = snap()
    bounds = s['environment']['bounds']
    # A1's enlarged center emblem is not the red-clay background fixture.
    clay_offset = 450 if offset and scene_id(s) == 'arena-formal' else 45
    x = (bounds['left'] + bounds['right']) / 2 - clay_offset
    y = (bounds['top'] + bounds['bottom']) / 2 + offset
    angle = direction * math.pi / 4
    page.evaluate('(v)=>window.__waterTest.arrange(v)', {
        'ai': False, 'player': {'x': x, 'y': y, 'a': angle},
        'enemy': {'x': x + math.cos(angle) * distance, 'y': y + math.sin(angle) * distance},
    })
    page.evaluate('(id)=>window.__waterTest.equip("player",[id])', mid)
    step(.1)
    return snap()


def cast(mid):
    return page.evaluate('(id)=>window.__waterTest.cast("player",id)', mid)


def tile(label, size=320):
    s = snap()
    data = page.locator('#game').evaluate('''(c,s)=>{
      const scale=c.width/s.viewport.width,
        x=((s.player.x+s.enemy.x)/2-s.camera.x)*scale,
        y=((s.player.y+s.enemy.y)/2-20-s.camera.y)*scale,half=125*scale;
      const crop=document.createElement('canvas');crop.width=Math.round(half*2);crop.height=crop.width;
      crop.getContext('2d').drawImage(c,Math.round(x-half),Math.round(y-half),crop.width,crop.height,
        0,0,crop.width,crop.height);return crop.toDataURL();
    }''', s)
    im = Image.open(io.BytesIO(base64.b64decode(data.split(',')[1]))).convert('RGB')
    result = Image.new('RGB', (size, size+24), '#223540')
    result.paste(im.resize((size, size), Image.Resampling.NEAREST), (0, 24))
    ImageDraw.Draw(result).text((5, 5), label, font=FONT, fill='white')
    return result


def hit_trace(mid, hp):
    return page.evaluate('''({mid,hp})=>{
      const api=window.__waterTest;let previous=api.snapshot(),release=null,releaseDraw=null,
        hit=null,hitTick=null,trajectory=[];
      for(let tick=0;tick<360;tick++){
        api.step(1/120,false);let s=api.snapshot();
        if(!release && s.bullets.length) {
          api.step(0);s=api.snapshot();release=s;
          releaseDraw=(window.va1Draws||[]).filter(d=>d.key==='va1-'+mid &&
            d.time===s.animation.time).sort((a,b)=>b.size-a.size)[0]||null;
        }
        if(s.bullets.length) trajectory.push(s.bullets.map(b=>({x:b.x,y:b.y,ux:b.ux,uy:b.uy,
          speed:b.speed,range:b.range,radius:b.radius,age:b.age})));
        if(s.enemy.hp<hp){api.step(0);hit=api.snapshot();hitTick=tick+1;break;}previous=s;
      }
      return {previous,release,releaseDraw,hit,hitTick,trajectory};
    }''', {'mid': mid, 'hp': hp})


def save_image(raw, path):
    Image.open(io.BytesIO(base64.b64decode(raw.split(',')[1]))).save(path)


try:
    guards = json.loads((ROOT / '验收记录/招式第3批/受保护图集.json').read_text())
    for guard in guards:
        path = ROOT / guard['path'] if 'path' in guard else None
        if path is None:
            record = json.loads((ROOT / '招式特效/生图重做/实景预览/构建记录.json').read_text())['assets']
            mid = guard['id']
            path = (ROOT / '招式特效/主角八招' / mid / (mid+'-动画.png') if mid in
                    ['thunderbolt', 'thunder'] else ROOT / record[mid]['output'])
        check(guard['id'] + ' protected SHA unchanged',
              hashlib.sha256(path.read_bytes()).hexdigest() == guard['sha256'])
    (OUT / '保护图集.json').write_text(json.dumps(guards, ensure_ascii=False, indent=2)+'\n')
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 800, 'height': 600})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(URL + '/?test=1')
        ready(page)
        catalog = page.evaluate('window.__waterTest.catalog()')
        roster = {r['id']: r for r in catalog['roster']}
        profile = snap()['profile']
        check('VA1 whitelist exactly the 21 contracted IDs',
              set(page.evaluate('Object.keys(window.PoightVA1Shots)')) == set(CASTERS))
        for mid, caster in CASTERS.items():
            check(mid+' caster can actually equip this move in the game', mid in roster[caster]['learnset'])
        page.evaluate('''()=>{
          window.va1Draws=[];
          const p=window.PoightMoveAnimations.prototype,sprite=p.sprite,draw=p.drawBurst;
          p.sprite=function(ctx,key,x,y,size,...args){
            window.va1Draws.push({key,x,y,size,time:this.time});
            window.va1Draws=window.va1Draws.slice(-300);
            return sprite.call(this,ctx,key,x,y,size,...args);
          };
          p.drawBurst=function(ctx,b,...args){
            const {key}=b,{x,y,diameter:size}=this.ringGeometry(ctx,b);
            const record={key,x:b.x,y:b.y,ringX:x,ringY:y,size,time:this.time,ring:true};
            {
              const m=ctx.getTransform(),scale=Math.hypot(m.a,m.b),side=Math.ceil(size*scale*1.5)+12;
              const c=window.va1ImpactCanvas ||= document.createElement('canvas');
              c.width=ctx.canvas.width;c.height=ctx.canvas.height;
              const cx=m.a*x+m.c*y+m.e,cy=m.b*x+m.d*y+m.f,cc=c.getContext('2d');
              cc.setTransform(m);
              this.clipContactCenters(cc);
              draw.call(this,cc,b,...args);
              const left=Math.max(0,Math.floor(cx-side/2)),top=Math.max(0,Math.floor(cy-side/2)),
                w=Math.min(side,c.width-left),h=Math.min(side,c.height-top),
                d=cc.getImageData(left,top,w,h).data;
              let lx=Infinity,hx=-Infinity,ly=Infinity,hy=-Infinity,count=0;
              for(let py=0;py<h;py++)for(let px=0;px<w;px++){
                if(d[(py*w+px)*4+3]<250)continue;
                lx=Math.min(lx,px);hx=Math.max(hx,px);ly=Math.min(ly,py);hy=Math.max(hy,py);count++;
              }
              record.opaqueDiameter=Math.max(hx-lx+1,hy-ly+1)/scale;record.opaqueCount=count;
            }
            window.va1Draws.push(record);window.va1Draws=window.va1Draws.slice(-300);
            return draw.call(this,ctx,b,...args);
          };
        }''')
        old_page = browser.new_page(viewport={'width': 800, 'height': 600})
        old_page.on('pageerror', lambda e: errors.append(str(e)))
        old_page.goto(URL + '/?test=1&anim=old')
        ready(old_page)
        compare = Image.new('RGB', (640, 344*len(CASTERS)), '#223540')
        for row, mid in enumerate([] if PIXELS_ONLY else CASTERS):
            print('CHECK', mid, flush=True)
            select(mid)
            directions = Image.new('RGB', (1280, 688), '#223540')
            for direction in ([] if CAPTURE_ONLY else range(8)):
                tag = f'{mid}/{direction}'
                initial = reset(mid, direction)
                hp = initial['enemy']['hp']
                check(tag+' cast', cast(mid))
                check(tag+' cooldown remains', not cast(mid))
                result = hit_trace(mid, hp)
                release, hit = result['release'], result['hit']
                check(tag+' real physics hits', hit is not None)
                check(tag+' no release-time damage', release is not None and release['enemy']['hp'] == hp)
                if hit is None or release is None:
                    continue
                r = release['animation']['releases'][-1]
                root = r['anchor']
                actor = release['player']
                entries = roster[actor['id']]['moveAnchors']
                m = catalog['moves'][mid]
                part = m.get('anchor')
                # heroMove only resolves missing base landmarks for batch2 moves.
                if m.get('batch2') and part not in entries:
                    part = next((k for k in ['mouth', 'palms', 'head', 'cheek', 'plant', 'wing']
                                 if k in entries), None)
                if part and m.get('r3') and 'r3-' + part in entries:
                    part = 'r3-' + part
                # Unregistered M4 shots use V1's r3-mouth fallback, not the older mouth table.
                if not part or part not in entries:
                    part = 'r3-mouth' if 'r3-mouth' in entries else 'mouth'
                entry = entries[part]
                clip = catalog['art'][str(actor['id'])][entry['role']]
                pt = entry['points'][root['row']][root['frame']]
                offsets = clip.get('bodyOffsets')
                off = offsets[root['row']][root['frame']] if offsets else [0, 0]
                expected = [actor['x']+(pt[0]-clip['anchorX']-off[0])*actor['scale'],
                            actor['y']+14+(pt[1]-clip['anchorY']-off[1])*actor['scale']-actor['flightHeight']]
                error = math.hypot(r['x']-expected[0], r['y']-expected[1])
                check(tag+' independent release anchor <=6px', error <= 6, error)
                first_draw = result['releaseDraw']
                check(tag+' actual first opaque head <=6px from release', first_draw is not None and
                      math.hypot(first_draw['x']-r['x'], first_draw['y']-r['y']) <= 6, first_draw)
                b = hit['animation']['bursts'][-1]
                ribbon = hit['animation']['ribbons'][-1]
                check(tag+' previous 120Hz tick no HP loss', result['previous']['enemy']['hp'] == hp)
                check(tag+' visible contact and damage same tick', ribbon['age'] == 0 and b['age'] == 0 and
                      b['time'] == hit['animation']['time'] and hit['feel']['remaining'] > 0)
                check(tag+' appearance exactly at collision <=6px',
                      math.hypot(ribbon['front']['x']-b['x'], ribbon['front']['y']-b['y']) <= 6)
                draws = page.evaluate('window.va1Draws')
                check(tag+' actual P6 hollow ring on hit', any(d.get('ring') and d['key'] == b['key'] and
                      d['time'] == b['time'] and math.hypot(d['x']-b['x'], d['y']-b['y']) < .01 for d in draws))
                check(tag+' target 0.8H+ impact', b['size'] >= hit['enemy']['body']['visibleSize'][1]*.8)
                stars = [d for d in draws if d.get('ring') and d['key'] == b['key'] and d['time'] == b['time'] and
                         math.hypot(d['x']-b['x'], d['y']-b['y']) < .01]
                check(tag+' actual opaque impact diameter >= target 0.8H',
                      any(d.get('opaqueCount', 0) > 20 and d.get('opaqueDiameter', 0) >=
                          hit['enemy']['body']['visibleSize'][1]*.8 for d in stars), stars)
                samples.append({'id': mid, 'direction': direction, 'releaseError': error,
                                'damage': hp-hit['enemy']['hp'], 'contact': b})
                if direction == 0:
                    traces[mid] = result['trajectory']
                    hit_ticks[mid] = result['hitTick']
                if CAPTURE:
                    directions.paste(tile(tag+' actual hit'), (direction%4*320, direction//4*344))
                step(1)
                check(tag+' presentation expires', not snap()['animation']['ribbons'] and
                      not snap()['animation']['bursts'])
            if CAPTURE and not CAPTURE_ONLY:
                directions.save(SHOTS / (mid+'-八方向.png'))
            if not CAPTURE:
                current = page
                page = old_page
                select(mid)
                initial = reset(mid)
                cast(mid)
                old = hit_trace(mid, initial['enemy']['hp'])
                check(mid+' old/new identical physical trajectory', old['trajectory'] == traces[mid])
                page = current
                (OUT / '检查中间结果.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2))
                continue
            # 25fps / 40ms, genuine wall-clock including hitstop, no slowdown.
            reset(mid)
            cast(mid)
            film, states = [], []
            for frame in range(45):
                film.append(tile(f'{mid} {frame*.04:.2f}s 1x'))
                states.append(snap())
                step(.04)
            gif = GIFS / (mid+'-横向-原速.gif')
            palette_samples = Image.new('RGB', (64*len(film), 64))
            for i, frame in enumerate(film):
                palette_samples.paste(frame.resize((64, 64)), (i*64, 0))
            palette = palette_samples.quantize(colors=256)
            encoded = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in film]
            encoded[0].save(gif, save_all=True, append_images=encoded[1:], duration=40, loop=0,
                            optimize=False)
            release = next(i for i, s in enumerate(states) if s['bullets'])
            contact = next(i for i, s in enumerate(states) if s['animation']['bursts'])
            check(mid+' GIF actual hit', contact > release)
            indices = [max(0, release-2), (release+contact)//2, contact, min(44, contact+5)]
            sheet = Image.new('RGB', (1280, 344), '#223540')
            with Image.open(gif) as decoded:
                duration = 0
                for f in range(decoded.n_frames):
                    decoded.seek(f)
                    duration += decoded.info['duration']
                check(mid+' GIF 1x 1800ms', duration == 1800)
                for col, index in enumerate(indices):
                    decoded.seek(index)
                    sheet.paste(decoded.convert('RGB'), (col*320, 0))
            sheet.save(SHOTS / (mid+'-四时刻-GIF解码.png'))
            instant = indices[1] * .04
            reset(mid)
            cast(mid)
            step(instant)
            after = tile(f'{mid} 改后 {instant:.2f}s')
            current = page
            page = old_page
            select(mid)
            reset(mid)
            cast(mid)
            step(instant)
            before = tile(f'{mid} M4 anim=old {instant:.2f}s')
            compare.paste(before, (0, row*344))
            compare.paste(after, (320, row*344))
            pair = Image.new('RGB', (640, 344))
            pair.paste(before, (0, 0)); pair.paste(after, (320, 0))
            pair.save(SHOTS / (mid+'-M4-vs-VA1.png'))
            if not CAPTURE_ONLY:
                initial = reset(mid)
                cast(mid)
                old = hit_trace(mid, initial['enemy']['hp'])
                check(mid+' old/new identical physical trajectory', old['trajectory'] == traces[mid])
            page = current
            (OUT / '检查中间结果.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2))
        if CAPTURE:
            compare.save(SHOTS / '整批-M4-vs-VA1.png')
            evidence_files = [*GIFS.glob('*.gif'), *SHOTS.glob('*-四时刻-GIF解码.png'),
                              *SHOTS.glob('*-M4-vs-VA1.png'), SHOTS / '整批-M4-vs-VA1.png']
            (OUT / '影像指纹.json').write_text(json.dumps({'visualSHA256': visual_hash(),
                'files': {str(p.relative_to(OUT)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in evidence_files}}, ensure_ascii=False, indent=2)+'\n')
        if not CAPTURE_ONLY and not PIXELS_ONLY:
            evidence = json.loads((OUT / '影像指纹.json').read_text())
            check('movie evidence belongs to current visual sources', evidence['visualSHA256'] == visual_hash())
            for relative, digest in evidence['files'].items():
                check('movie evidence SHA '+relative, hashlib.sha256((OUT / relative).read_bytes()).hexdigest() == digest)
        page.evaluate((ROOT / 'tests/VA1像素.js').read_text())
        for scene in ([] if CAPTURE_ONLY else ['arena-formal', 'arena-natural']):
            for mid in CASTERS:
                print('PIXELS', scene, mid, flush=True)
                select(mid, scene)
                initial = reset(mid, offset=-95)
                cast(mid)
                ticks = page.evaluate('''hp=>{
                  const api=window.__waterTest;
                  for(let i=1;i<=360;i++){api.step(1/120,false);if(api.snapshot().enemy.hp<hp)return i;}
                  return null;
                }''', initial['enemy']['hp'])
                check(f'{scene}/{mid} real hit', ticks is not None)
                if ticks is None:
                    continue
                reset(mid, offset=-95)
                page.evaluate('window.va1Probe.enabled=true')
                cast(mid)
                page.evaluate('''(n)=>{for(let i=0;i<n;i++)window.__waterTest.step(1/120,false);
                  window.__waterTest.step(0)}''', ticks-1)
                pix = page.evaluate('window.measureVA1()')
                for key in ['composite', 'background', 'mask', 'head']:
                    save_image(pix.pop(key), SHOTS / f'像素-{scene}-{mid}-{key}.png')
                tag = f'{scene}/{mid}'
                floor = max(14, pix['height']*(.4 if catalog['moves'][mid]['damage'] >= 21 else .3))
                check(tag+' actual opaque central chord size', pix['diameter'] >= floor and
                      pix['count'] > 30 and pix['sliceCount'] > 2, {'minimum': floor, **pix})
                check(tag+' main saturation >=.55', pix['saturation'] >= .55 and pix['colorFraction'] >= .3, pix)
                check(tag+' same mask mean brightness difference >=60', pix['contrast'] >= 60, pix)
                check(tag+' real precontact full HP', snap()['enemy']['hp'] == initial['enemy']['hp'])
                step(1/120)
                check(tag+' next 120Hz tick damage + visible burst', snap()['enemy']['hp'] <
                      initial['enemy']['hp'] and snap()['animation']['bursts'][-1]['age'] == 0)
                pixels.append({'scene': scene, **pix})
                (OUT / '像素中间结果.json').write_text(json.dumps(pixels, ensure_ascii=False, indent=2))
                page.evaluate('window.va1Probe.enabled=false')
        # Boundary behavior tested via real cast, not damage injection.
        for mid in ([] if CAPTURE_ONLY or PIXELS_ONLY else CASTERS):
            select(mid)
            reset(mid, distance=350)
            cast(mid)
            step(4)
            check(mid+' outside range no hit or burst', snap()['hits'] == 0 and not snap()['animation']['bursts'])
            reset(mid, distance=65)
            page.evaluate('window.__waterTest.equip("enemy",["protect"]);window.__waterTest.cast("enemy","protect")')
            cast(mid)
            step(2)
            guarded = snap()
            check(mid+' successful guard damage iff contact burst',
                  bool(guarded['hits']) == bool(guarded['animation']['contacts']))
            current = page
            page = old_page
            select(mid)
            reset(mid, distance=65)
            page.evaluate('window.__waterTest.equip("enemy",["protect"]);window.__waterTest.cast("enemy","protect")')
            cast(mid); step(2)
            check(mid+' 30HP guard and overflow unchanged', snap()['enemy']['hp'] == guarded['enemy']['hp']
                  and snap()['hits'] == guarded['hits'])
            page = current
            initial = reset(mid)
            cast(mid)
            step((hit_ticks[mid]-10)/120)
            check(mid+' actual jump starts before predicted collision',
                  page.evaluate('window.__waterTest.jump("enemy")'))
            step(10/120)
            airborne = snap()
            check(mid+' target really airborne at contact clock', airborne['enemy']['airborne'])
            check(mid+' existing airborne permission enforced at contact',
                  (airborne['enemy']['hp'] < initial['enemy']['hp']) ==
                  (catalog['moves'][mid].get('hitsAirborne') is not False))
            step(2)
            new_hp = snap()['enemy']['hp']
            current = page
            page = old_page
            select(mid)
            reset(mid)
            cast(mid)
            step((hit_ticks[mid]-10)/120)
            page.evaluate('window.__waterTest.jump("enemy")')
            step(10/120+2)
            check(mid+' airborne gate old/new unchanged', snap()['enemy']['hp'] == new_hp)
            page = current
            select(mid, 'arena-natural')
            reset(mid)
            page.evaluate('''()=>window.__waterTest.arrange({ai:false,
              player:{x:230,y:312,a:0},enemy:{x:420,y:312}})''')
            cast(mid)
            step(3)
            check(mid+' rock wall blocks; no fabricated contact', snap()['hits'] == 0 and
                  not snap()['animation']['contacts'])
        for w, h in ([] if CAPTURE_ONLY else [(1440, 900), (390, 844), (844, 390)]):
            page.set_viewport_size({'width': w, 'height': h})
            page.wait_for_timeout(80)
            select('moonblast')
            reset('moonblast', direction=1)
            cast('moonblast'); step(.6)
            page.screenshot(path=str(SHOTS / f'实战-{w}x{h}.png'))
        offline = browser.new_context(offline=True)
        page = offline.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto((ROOT / '候选试玩.html').as_uri()+'?test=1')
        ready(page)
        for mid in ([] if CAPTURE_ONLY or PIXELS_ONLY else CASTERS):
            select(mid)
            reset(mid)
            cast(mid); step(2)
            check(mid+' file offline hit', snap()['hits'] == 1)
        browser.close()
except (Exception, KeyboardInterrupt) as exc:  # noqa: BLE001 - persist incomplete evidence, never false green
    failure = f'{type(exc).__name__}: {exc}'
finally:
    report = {'passed': sum(c['ok'] for c in checks),
              'failed': sum(not c['ok'] for c in checks)+bool(failure),
              'jsErrors': len(errors), 'errors': errors, 'failure': failure,
              'checks': checks, 'samples': samples, 'pixels': pixels,
              'candidateSHA256': hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest(),
              'mode': 'evidence-only' if CAPTURE_ONLY else 'pixels-only' if PIXELS_ONLY else 'full-combat'}
    report_name = '影像验收.json' if CAPTURE_ONLY else '像素调试.json' if PIXELS_ONLY else '浏览器验收.json'
    (OUT / report_name).write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ['passed', 'failed', 'jsErrors']}, ensure_ascii=False))
    if report['failed'] or errors:
        raise SystemExit(1)
