"""B1: four moves x eight real headings, Emerald pixels, closure-time damage and evidence."""
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

from 招式特效.咬类打包 import FANGS

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'验收记录/咬类招式'
SHOTS = OUT/'截图'
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get('POIGHT_TEST_URL', 'http://localhost:8867/').rstrip('/')
checks, errors, samples = [], [], []
CASTERS = {'bite': 197, 'crunch': 130, 'firefang': 6, 'bugbite': 123}


def check(name, ok, detail=None):
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})


def snap():
    return page.evaluate('window.__waterTest.snapshot()')


def step(seconds):
    page.evaluate('(t)=>window.__waterTest.step(t)', max(0, seconds))


def arrange(value):
    page.evaluate('(v)=>window.__waterTest.arrange(v)', value)


def state(mid):
    return next((e for e in snap()['generated']['states'] if e['id'] == mid), None)


def reset(mid, heading=0, miss=False):
    page.evaluate('window.__waterTest.reset(true)')
    a = heading*math.pi/4
    arrange({'ai': False, 'player': {'x': CX, 'y': CY, 'a': a},
             'enemy': {'x': CX+20*math.cos(a), 'y': CY+20*math.sin(a), 'a': a+math.pi}})
    distance = 160 if miss else page.evaluate('''(id)=>{
        const s=window.__waterTest.snapshot(),c=window.__waterTest.catalog();
        const p={...s.player,char:c.roster.find(q=>q.id===s.player.id)};
        const t={...s.enemy,char:c.roster.find(q=>q.id===s.enemy.id)},m=c.moves[id];
        return window.PoightBodies.meleeRange(t,Math.min(m.range,p.char.body.nominalSize*m.rangeBodies),
          Math.cos(p.a),Math.sin(p.a),p)-3;
    }''', mid)
    arrange({'enemy': {'x': CX+distance*math.cos(a), 'y': CY+distance*math.sin(a)}})
    page.evaluate('(ids)=>window.__waterTest.equip("player",ids)',
                  [mid]+[x for x in catalog['moves'] if x != mid][:3])
    step(.3)
    return snap()


def cast(mid):
    return page.evaluate('(id)=>window.__waterTest.cast("player",id)', mid)


def seek(mid, age):
    pause = max(snap()['generated']['fangPause'], snap()['feel']['remaining'])
    if pause:
        step(pause)
    e = state(mid)
    if e and age > e['age']:
        step(age-e['age'])
    return state(mid)


def tile(label, close=False):
    s = snap()
    data = page.locator('canvas').first.evaluate('(c)=>c.toDataURL("image/png")')
    image = Image.open(io.BytesIO(base64.b64decode(data.split(',')[1]))).convert('RGB')
    e = next((e for e in s['generated']['states'] if e['mode'] == 'fangs'), None)
    p = s['enemy']
    cx = e['x'] if e else p['x']
    cy = e['y'] if e else p['y']+14-p['body']['visibleSize'][1]/2
    ratio = image.width/s['viewport']['width']
    cx, cy = (cx-round(s['camera']['x']))*ratio, (cy-round(s['camera']['y']))*ratio
    span = 128 if close else 160
    half = span*ratio/2
    image = image.crop((round(cx-half), round(cy-half), round(cx+half), round(cy+half)))
    size = 384 if close else 200
    image = image.resize((size, size), Image.Resampling.NEAREST)
    result = Image.new('RGB', (size, size+20), '#273239')
    result.paste(image, (0, 20))
    ImageDraw.Draw(result).text((4, 4), label, fill='white')
    return result


def center(p):
    return {'x': p['x'], 'y': p['y']+14-p['body']['visibleSize'][1]/2-p['flightHeight']}


try:
    receipt = json.loads((ROOT/'素材/原版战斗动画/来源.json').read_text())
    for asset in receipt['assets']:
        check('download SHA '+asset['file'],
              hashlib.sha256((ROOT/'素材/原版战斗动画'/asset['file']).read_bytes()).hexdigest() == asset['sha256'])
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(URL+'/?test=1')
        for _ in range(600):
            if page.evaluate('window.__waterTest?.snapshot().artReady'):
                break
            time.sleep(.03)
        catalog = page.evaluate('window.__waterTest.catalog()')
        roster = {c['id']: c for c in catalog['roster']}
        terrain = catalog['terrains'][0]
        walk = base64.b64decode(terrain['walkB64'])
        cols, cell = terrain['columns'], terrain['cellSize']
        area = next(q for q in terrain['areas'] if q['sourceName'] == 'RustboroCity')
        x, y = next((x, y) for y in range(area['gridY']+4, area['gridY']+area['rows']-4)
                    for x in range(area['gridX']+4, area['gridX']+area['columns']-4)
                    if all(walk[(y+dy)*cols+x+dx] for dy in range(-3, 4) for dx in range(-3, 4)))
        CX, CY = (x+.5)*cell, (y+.5)*cell
        baseline = json.loads((ROOT/'协作/R1/T5数值基线.json').read_text())
        # Observe the real renderer, do not replace it or provide mocked artwork.
        page.evaluate('''()=>{
          window.fangDraws=[];window.fangPixels={};
          const original=window.PoightGeneratedMoves.prototype.stamp;
          window.PoightGeneratedMoves.prototype.stamp=function(...args){
            const [ctx,id,x,y,width,height,age,angle]=args;
            if(this.data[id]?.runtime?.fangs){
              window.fangDraws.push({id,x,y,width,height,angle});
              window.fangDraws=window.fangDraws.slice(-16);
              if(!window.fangPixels[id]){
                const c=document.createElement('canvas');c.width=c.height=64;
                c.getContext('2d').drawImage(this.images.get(id),0,0,64,64,0,0,64,64);
                window.fangPixels[id]=c.toDataURL('image/png');
              }
            }
            return original.apply(this,args);
          };
        }''')
        for mid, caster in CASTERS.items():
            m = catalog['moves'][mid]
            check(mid+' unchanged damage/CD/SP/range',
                  all(m[k] == baseline[mid][k] for k in ['damage', 'cost']) and m['cd'] == min(3, max(.45, baseline[mid]['cd']*.4)) and m['range'] == 42 and m['rangeBodies'] == 1.5)
            check(mid+' first close <=.22', m['contactDelay'] <= .22)
            page.evaluate('(p)=>window.__waterTest.select(p)',
                          {**snap()['profile'], 'player': caster, 'enemy': 7, 'map': 'emerald-rustborocity',
                           'playerMoves': roster[caster]['defaultMoves'], 'enemyMoves': roster[7]['defaultMoves']})
            sheet = Image.new('RGB', (800, 1760), '#273239')
            for direction in range(8):
                label = f'{mid}/{direction}'
                s0 = reset(mid, direction)
                hp = s0['enemy']['hp']
                check(label+' actual cast', cast(mid))
                check(label+' cooldown prevents recast', not cast(mid))
                check(label+' windup no damage', snap()['enemy']['hp'] == hp)
                e = state(mid)
                check(label+' target state no mouth purple', e is not None and e['mode'] == 'fangs')
                reach = snap()['player']['attack']['range']
                for frame, age in enumerate([-m['windup'], -m['windup']*.66, -m['windup']*.33, 0], 1):
                    e = seek(mid, age)
                    s = snap()
                    check(label+f' keyframe{frame} HP', (s['enemy']['hp'] == hp) if frame < 4 else (s['enemy']['hp'] < hp), s['enemy']['hp'])
                    c = center(s['enemy'])
                    check(label+f' keyframe{frame} center', math.hypot(e['x']-c['x'], e['y']-c['y']) <= e['bodyWidth']/2)
                    check(label+f' keyframe{frame} tooth/body width', 1 <= e['width']/e['bodyWidth'] <= 1.3)
                    samples.append({'id': mid, 'direction': direction, 'frame': frame, 'age': e['age'],
                                    'center': [e['x'], e['y']], 'jaws': e['jaws'], 'hp': s['enemy']['hp']})
                    if frame == 1:
                        opened = e['jaws']
                    if frame == 3:
                        partial = e['jaws']
                    if frame == 4:
                        first_loss = hp-s['enemy']['hp']
                        check(label+' release tick closes and damages', len(e['closures']) == 1 and e['closures'][0]['age'] == 0)
                        check(label+' contact hitstop', s['generated']['fangPause'] > 0)
                        check(label+' closed jaws meet', math.hypot(e['jaws'][0]['x']-e['jaws'][1]['x'], e['jaws'][0]['y']-e['jaws'][1]['y']) < .01)
                    if frame != 3:
                        column = {1: 0, 2: 1, 4: 2}[frame]
                        sheet.paste(tile(f'{direction} keyframe {frame} t={e["age"]:.3f}'), (column*200, direction*220))
                seek(mid, .04)
                sheet.paste(tile(f'{direction} impact'), (600, direction*220))
                dx = partial[0]['x']-opened[0]['x']
                dy = partial[0]['y']-opened[0]['y']
                check(label+' first jaw inward direction', dy > 0 and (dx > 0 if mid == 'crunch' else abs(dx) < 1e-6), [dx, dy])
                check(label+' lower jaw inward direction', partial[1]['y'] < opened[1]['y'] and
                      (partial[1]['x'] < opened[1]['x'] if mid == 'crunch' else abs(partial[1]['x']-opened[1]['x']) < 1e-6))
                if mid == 'crunch':
                    # Actual renderer's localized background operation, on a blank reference canvas.
                    local = page.evaluate('''(e)=>{
                      const c=document.createElement('canvas');c.width=c.height=256;
                      const g=c.getContext('2d');g.fillStyle='#ffffff';g.fillRect(0,0,256,256);
                      const q={...e,x:128,y:128,radius:60};
                      window.PoightFangs.draw(null,g,q,'below');
                      const center=[...g.getImageData(128,128,1,1).data],edge=[...g.getImageData(2,2,1,1).data];
                      g.fillStyle='#ffffff';g.fillRect(0,0,256,256);
                      window.PoightFangs.draw(null,g,{...q,age:.6,dimAge:.6},'below');
                      return {center,edge,end:[...g.getImageData(128,128,1,1).data]};
                    }''', state(mid))
                    check(label+' local dim only and restores by .6', local['center'][0] < 255 and
                          local['edge'] == [255, 255, 255, 255] and local['end'] == [255, 255, 255, 255])
                    seek(mid, .06)
                    second_open = state(mid)['jaws']
                    seek(mid, .10)
                    second_partial = state(mid)['jaws']
                    check(label+' second opposite diagonal', second_partial[0]['x'] < second_open[0]['x'] and second_partial[0]['y'] > second_open[0]['y'])
                    seek(mid, .125)
                    e = state(mid)
                    check(label+' second bite at +.12 within 120Hz tick', abs(e['closures'][1]['age']-.12) <= 1/120)
                    check(label+' exactly two closures and two HP losses', len(e['closures']) == 2 and len(e['contacts']) == 2 and snap()['hits'] == 2)
                    mult = math.prod(catalog['efficacy'][str(m['type'])].get(str(t), 1) for t in roster[7]['types'])
                    total = math.floor(m['damage']*mult*(1.1 if m['type'] in roster[caster]['types'] else 1)+.5)
                    check(label+' split total equals original +/-1', abs(hp-snap()['enemy']['hp']-total) <= 1, [hp-snap()['enemy']['hp'], total])
                    check(label+' each bite exactly half normal damage', first_loss == total/2 and
                          hp-snap()['enemy']['hp']-first_loss == total/2)
                step(1)
                check(label+' no lingering state', snap()['generated']['active'] == 0)
                reset(mid, direction, miss=True)
                cast(mid)
                step(m['windup'])
                e, s = state(mid), snap()
                p = s['player']
                origin = center(p)
                a = p['attack']['aim']
                expected = [origin['x']+math.cos(a)*reach, origin['y']+math.sin(a)*reach]
                check(label+' miss center at budget end +/-6', not e['targeted'] and math.hypot(e['x']-expected[0], e['y']-expected[1]) <= 6, expected)
                seek(mid, 0)
                check(label+' visible miss closes with no damage', len(state(mid)['closures']) == 1 and snap()['enemy']['hp'] == snap()['enemy']['maxHP'])
                step(1)
                check(label+' miss never remote-damages', snap()['enemy']['hp'] == snap()['enemy']['maxHP'] and snap()['hits'] == 0)
            sheet.save(SHOTS/f'{mid}-八方向四时刻.png')
            # Inspect the actual loaded image used by stamp against original pixels.
            pixels = page.evaluate('(id)=>window.fangPixels[id]', mid)
            actual = Image.open(io.BytesIO(base64.b64decode(pixels.split(',')[1]))).convert('RGBA')
            original = Image.open(ROOT/'素材/原版战斗动画/sharp_teeth.png')
            recolor = {'fire': {1: (92, 24, 16), 2: (172, 48, 24), 3: (244, 104, 40), 4: (255, 220, 132)},
                       'bug': {1: (20, 52, 24), 2: (48, 104, 44), 3: (112, 180, 72), 4: (220, 255, 156)}}
            expected = Image.new('RGBA', original.size)
            expected.putdata([(0, 0, 0, 0) if index == 0 else
                              (*recolor.get(FANGS[mid], {}).get(index, color[:3]), 255)
                              for index, color in zip(original.getdata(), original.convert('RGBA').getdata())])
            check(mid+' real renderer source pixels match original/recolor', actual.tobytes() == expected.tobytes())
            atlas = Image.open(ROOT/f'招式特效/第1批/原版牙齿/{mid}-动画.png').convert('RGBA')
            check(mid+' all four packed frames preserve original pixels',
                  all(atlas.crop((0, i*64, 64, (i+1)*64)).tobytes() == expected.tobytes() for i in range(4)))
            strip = Image.new('RGB', (1920, 404), '#273239')
            reset(mid)
            cast(mid)
            for index, age in enumerate([-m['windup'], -m['windup']*.66, -m['windup']*.33, 0, .125 if mid == 'crunch' else .08]):
                seek(mid, age)
                strip.paste(tile(f'{mid} t={age:.3f} 3x', close=True), (index*384, 0))
            strip.save(SHOTS/f'{mid}-3倍五帧特写.png')
            reset(mid)
            cast(mid)
            film = []
            for tick in range(34):
                film.append(tile(f'{mid} real t={tick/30:.3f}s 1x'))
                step(1/30)
            film[0].save(SHOTS/f'{mid}-原速.gif', save_all=True, append_images=film[1:],
                         duration=[30, 30, 40]*11+[30], loop=0)
            with Image.open(SHOTS/f'{mid}-原速.gif') as gif:
                duration = 0
                for frame in range(gif.n_frames):
                    gif.seek(frame)
                    duration += gif.info['duration']
                check(mid+' GIF centisecond durations preserve 1x speed', abs(duration-34/30*1000) <= 10)
            # Real dash cancellation must still clear an attached attack.
            reset(mid)
            cast(mid)
            step(m['windup']*.5)
            page.evaluate('window.__waterTest.dash("player",1,0)')
            step(1)
            check(mid+' dash cancel no damage/no state', snap()['enemy']['hp'] == snap()['enemy']['maxHP'] and snap()['generated']['active'] == 0)
        for w, h in [(1440, 900), (390, 844), (844, 390)]:
            page.set_viewport_size({'width': w, 'height': h})
            page.wait_for_timeout(100)
            reset('bugbite')
            step(1)
            cast('bugbite')
            step(catalog['moves']['bugbite']['windup']+.08)
            s = snap()
            c = center(s['enemy'])
            check(f'viewport {w}x{h} target and teeth on-screen',
                  0 < c['x']-s['camera']['x'] < s['viewport']['width'] and
                  0 < c['y']-s['camera']['y'] < s['viewport']['height'])
            page.screenshot(path=str(SHOTS/f'实战-{w}x{h}.png'))
        offline = browser.new_page()
        offline.on('pageerror', lambda e: errors.append(str(e)))
        offline.goto((ROOT/'候选试玩.html').as_uri()+'?test=1')
        for _ in range(600):
            if offline.evaluate('window.__waterTest?.snapshot().artReady'):
                break
            time.sleep(.03)
        check('offline all104 loaded including M4 and new teeth/impact', offline.evaluate('window.__waterTest.snapshot().generated.loaded') == 104)
        check('No JS errors', not errors, errors)
        browser.close()
finally:
    report = {'passed': sum(c['ok'] for c in checks), 'failed': sum(not c['ok'] for c in checks),
              'jsErrors': len(errors), 'errors': errors, 'checks': checks, 'samples': samples,
              'candidateSHA256': hashlib.sha256((ROOT/'候选试玩.html').read_bytes()).hexdigest(),
              'keyframeDefinition': '1=windup appearance; 2=34% windup; 3=67% windup; 4=release tick closure; crunch second +.12s. Simulation 120Hz; GIF30fps 1x.',
              'bodyDefinition': 'native visibleSize calibrated silhouette width and height; center includes +14 and flight lift'}
    (OUT/'浏览器验收.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ['passed', 'failed', 'jsErrors']}))
    if report['failed'] or errors:
        raise SystemExit(1)
