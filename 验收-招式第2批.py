"""224 real casts: anatomical origins, budget, timing, damage and terrain.
Capture raster-only real combat, with 1.0x clips (30fps; no slow motion).
"""
import base64
import hashlib
import io
import json
import math
import os
import subprocess
import time
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

from 招式特效.第2批参数 import PRESERVED, RANGED_REVISIONS

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/招式第2批'
SHOTS = OUT / '截图'
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get('POIGHT_TEST_URL', 'http://localhost:8852/').rstrip('/')
CASTERS = {mid: r['caster'] for mid, r in RANGED_REVISIONS.items()} | PRESERVED
ORDER = ['bubble', 'waterpulse', 'ember', 'razorleaf', 'energyball', 'thundershock',
         'icywind', 'rockthrow', 'mudshot', 'shadowball', 'confusion', 'gust',
         'dragonpulse', 'sludgebomb', 'swift', 'moonblast', 'triattack', 'brine',
         'scald', 'leafstorm', 'seedbomb', 'electroball', 'iceshard', 'aurasphere',
         'focusblast', 'venoshock', 'storedpower', 'darkpulse']
if os.environ.get('POIGHT_TEST_IDS'):
    ORDER = os.environ['POIGHT_TEST_IDS'].split(',')
checks, errors, samples = [], [], []


def check(name, ok, detail=None):
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})


def ready(page):
    for _ in range(500):
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


def reset(mid, direction=0, distance=100):
    page.evaluate('window.__waterTest.reset(true)')
    angle = direction * math.pi / 4
    arrange({'ai': False, 'player': {'x': CX, 'y': CY, 'a': angle},
             'enemy': {'x': CX + math.cos(angle)*distance,
                       'y': CY + math.sin(angle)*distance, 'a': angle+math.pi}})
    page.evaluate('(ids)=>window.__waterTest.equip("player",ids)',
                  [mid, 'protect', 'tackle', 'watergun'])
    step(.3)
    return snap()


def cast(mid):
    return page.evaluate('(id)=>window.__waterTest.cast("player",id)', mid)


def tile(label, size=240):
    s = snap()
    # Crop existing canvas pixels BEFORE PNG encoding, rather than transporting
    # a full 1440px canvas for every tiny GIF frame. No separate FX renderer.
    data = page.locator('canvas').first.evaluate('''(c,v)=>{
        const scale=c.width/v.width, out=document.createElement('canvas');
        out.width=out.height=v.size;
        const g=out.getContext('2d'); g.imageSmoothingEnabled=false;
        g.drawImage(c,Math.round((v.cx-120)*scale),Math.round((v.cy-120)*scale),
                    Math.round(240*scale),Math.round(240*scale),0,0,v.size,v.size);
        return out.toDataURL('image/png');
    }''', {'width':s['viewport']['width'],'size':size,
           'cx':(s['player']['x']+s['enemy']['x'])/2-round(s['camera']['x']),
           'cy':(s['player']['y']+s['enemy']['y'])/2-round(s['camera']['y'])-25})
    image = Image.open(io.BytesIO(base64.b64decode(data.split(',')[1]))).convert('RGB')
    result = Image.new('RGB', (size,size+20), '#273239')
    result.paste(image,(0,20))
    ImageDraw.Draw(result).text((4,3),label,fill='white')
    return result


def expected_anchor(s, mid):
    p = s['player']
    key = moves[mid].get('anchor')
    entry = roster[p['id']].get('moveAnchors', {}).get(key)
    if not entry:
        return None
    clip = catalog['art'][str(p['id'])][entry['role']]
    x, y = entry['points'][p['direction']][p['animFrame']]
    dx, dy = clip.get('bodyOffsets', [])[p['direction']][p['animFrame']] if 'bodyOffsets' in clip else (0,0)
    return {'x': p['x']+(x-clip['anchorX']-dx)*p['scale'],
            'y': p['y']+14+(y-clip['anchorY']-dy)*p['scale']-p['flightHeight']}


def gap(a, b):
    return math.hypot(a['x']-b['x'],a['y']-b['y'])


try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width':1440,'height':900})
        page.on('pageerror',lambda e: errors.append(str(e)))
        page.goto(URL+'/?test=1')
        ready(page)
        catalog = page.evaluate('window.__waterTest.catalog()')
        roster = {c['id']:c for c in catalog['roster']}
        moves = catalog['moves']
        profile = snap()['profile']
        terrain = catalog['terrains'][0]
        cols, cell = terrain['columns'], terrain['cellSize']
        walk = base64.b64decode(terrain['walkB64'])
        area = next(a for a in terrain['areas'] if a['sourceName']=='RustboroCity')
        x,y = next((x,y) for y in range(area['gridY']+4,area['gridY']+area['rows']-4)
                   for x in range(area['gridX']+4,area['gridX']+area['columns']-4)
                   if all(walk[(y+dy)*cols+x+dx] for dy in range(-3,4) for dx in range(-3,4)))
        CX,CY = (x+.5)*cell,(y+.5)*cell
        baseline = {'__name__':'baseline','__file__':str(ROOT/'游戏数据.py')}
        exec(subprocess.check_output(['git','show','928b570:游戏数据.py'],cwd=ROOT),baseline)  # noqa: S102
        from 游戏数据 import MOVES
        t5_overrides = json.loads((ROOT/'协作/R2/T5基线.json').read_text())['runtimeOverrides']
        expected_moves = {mid: {k: v for k, v in m.items()
                               if k != 'burn' and not (k == 'slow' and m['type'] == 13)}
                          for mid, m in baseline['MOVES'].items()}
        t5_runtime = {mid: expected_moves[mid] | t5_overrides.get(mid,{}) for mid in PRESERVED}
        # Independently read the checked-in source table: do not copy actual runtime probabilities.
        import csv
        with (ROOT/'招式状态表.tsv').open() as source:
            for row in csv.DictReader(source, delimiter='\t'):
                if row['id'] in t5_runtime:
                    t5_runtime[row['id']].setdefault('statuses', []).append({
                        'id': row['状态'], 'chance': float(row['概率']), 'line': int(row['来源行'])})
        check('Other 95 T5 source definitions unchanged except S1 field deletions',all(
            MOVES[mid]==m for mid,m in expected_moves.items() if mid not in RANGED_REVISIONS))
        check('All 120 T5 damage/cooldown/stamina unchanged',all(
            all(MOVES[mid][k]==m[k] for k in ('damage','cd','cost'))
            for mid,m in baseline['MOVES'].items()))
        for mid in PRESERVED:
            old = t5_runtime[mid]
            expected = {**old, 'hitsAirborne': moves[mid]['hitsAirborne'],
                        'windup': 0 if old['windup']==0 else min(.35,max(.05,old['windup']*.5)),
                        'recovery': old['recovery']*.6,
                        'cd': old['cd'] if old['kind'] in ['heal','buff','splash'] else min(3,max(.45,old['cd']*.4))}
            check(mid+' exact T5 runtime with J1, H1 timing and S1 source-table statuses',
                  moves[mid]==expected)
        for mid in ORDER:
            caster = CASTERS[mid]
            # No immunities against any of this batch's damage types.
            page.evaluate('(p)=>window.__waterTest.select(p)', {
                **profile, 'player':caster,'enemy':7,'map':'emerald-rustborocity',
                'playerMoves':roster[caster]['defaultMoves'],'enemyMoves':roster[7]['defaultMoves']})
            m = moves[mid]
            sheet = Image.new('RGB',(1440,1040),'#273239')
            for direction in range(8):
                prefix = f'{mid}/{direction}'
                left,top = (direction//4)*720,(direction%4)*260
                initial = reset(mid,direction)
                hp = initial['enemy']['hp']
                check(prefix+' no pre-cast damage',initial['hits']==0)
                check(prefix+' cast',cast(mid))
                s = snap()
                reach = s['player']['attack']['range']
                body = s['player']['body']['nominalSize']
                budget = min(m['range'],body*m.get('rangeBodies',5))
                check(prefix+' range <= budget and <=5 bodies',reach<=budget and reach<=5*body,reach)
                check(prefix+' cooldown blocks recast',not cast(mid))
                step(m['windup']-.001)
                s = snap()
                check(prefix+' no damage or projectile before release',s['enemy']['hp']==hp and not s['bullets'])
                sheet.paste(tile(f'{direction} windup t={m["windup"]-.001:.3f}'),(left,top))
                anchor = expected_anchor(s,mid)
                if anchor:
                    check(prefix+' charge tracks current frame <=6px',gap(s['player']['attack']['anchor'],anchor)<=6)
                step(.001)
                s = snap()
                check(prefix+' real projectile emitted',bool(s['bullets']))
                if s['bullets'] and anchor:
                    anchor = expected_anchor(s,mid)
                    for b in s['bullets']:
                        visual = {'x':b['sx']+(b['visualOffsetX'] or 0),
                                  'y':b['sy']-16-s['player']['visualLift']+(b['visualOffset'] or 0)}
                        check(prefix+' release at landmark <=6px',gap(visual,anchor)<=6,gap(visual,anchor))
                if mid=='triattack':
                    check(prefix+' separate fire/electric/ice variants',sorted(b['variant'] for b in s['bullets'])==[0,1,2])
                # Never advance past first contact for the release picture.
                flight = max(.05, (gap(s['bullets'][0], s['enemy'])
                                   - s['enemy']['body']['nominalSize']/2 - m['radius']) / m['speed'] * .45) if s['bullets'] else .05
                step(flight)
                sheet.paste(tile(f'{direction} release'),(left+240,top))
                hit = page.evaluate('''(hp)=>{
                    const api=window.__waterTest;
                    for(let i=0;i<360 && api.snapshot().enemy.hp>=hp;i++) api.step(1/120);
                    return api.snapshot();
                }''',hp)
                check(prefix+' actual contact damages',hit['enemy']['hp']<hp,hit['enemy']['hp'])
                check(prefix+' one hit group (fan cannot multiply damage)',hit['hits']==1,hit['hits'])
                sheet.paste(tile(f'{direction} hit hp={hit["enemy"]["hp"]:.1f}'),(left+480,top))
                samples.append({'id':mid,'direction':direction,'range':reach,'budget':budget,
                                'bodyLength':body,'firstHitSeconds':hit['elapsed']-initial['elapsed']})
                step(4)
                check(prefix+' contact effects expire',not snap()['bullets'] and not snap()['generated']['active'])
                # Miss: bound the COMPLETE traveled path, not just final position.
                reset(mid,direction)
                cast(mid)
                arrange({'enemy':{'x':CX+300,'y':CY+300}})
                step(m['windup'])
                paths, prev, returned = {},{},False
                max_displacement = 0
                flight_frames = page.evaluate('''()=>{
                    const api=window.__waterTest, frames=[];
                    for(let i=0;i<320;i++) {
                        const s=api.snapshot(); frames.push({bullets:s.bullets});
                        if(!s.bullets.length) break;
                        api.step(.01);
                    }
                    return frames;
                }''')
                for q in flight_frames:
                    for b in q['bullets']:
                        bid=b['id']
                        origin={'x':b['sx'],'y':b['sy']}
                        old=prev.get(bid)
                        paths[bid]=paths.get(bid,0)+gap(b,old or origin)
                        prev[bid]=b
                        returned |= bool(b['returned'])
                        max_displacement=max(max_displacement,gap(b,origin))
                        if not m.get('returning') and old:
                            # Fan headings are fixed at release; no target steering.
                            check(prefix+' projectile retains released direction',
                                  b['ux']==old['ux'] and b['uy']==old['uy'])
                check(prefix+' total measured path <= budget',all(d<=budget+.01 for d in paths.values()),max(paths.values(),default=0))
                check(prefix+' displacement <= budget',max_displacement<=budget+.01,max_displacement)
                check(prefix+' miss expires and causes no damage',not snap()['bullets'] and snap()['enemy']['hp']==hp)
                if mid=='razorleaf':
                    check(prefix+' missed leaf returns without homing',returned)
                # World-bound removal in each heading.
                reset(mid,direction)
                q=snap()
                ux,uy=math.cos(direction*math.pi/4),math.sin(direction*math.pi/4)
                page.evaluate('(v)=>window.__waterTest.injectWater(v)',{
                    'owner':'player','move':mid,'ux':ux,'uy':uy,
                    'x':q['world']['width']-25.1 if ux>.1 else 25.1 if ux<-.1 else CX,
                    'y':q['world']['height']-30.1 if uy>.1 else 45.1 if uy<-.1 else CY,
                    'range':reach,'speed':m['speed']})
                step(.02)
                check(prefix+' world bound consumes',not snap()['bullets'])
                # A real solid cell separates the actor and target.
                ux,uy=round(ux),round(uy)
                wx,wy=next((x,y) for y in range(3,terrain['rows']-3) for x in range(3,cols-3)
                           if not walk[y*cols+x] and walk[(y-uy)*cols+x-ux]
                           and walk[(y-2*uy)*cols+x-2*ux] and walk[(y+uy)*cols+x+ux])
                reset(mid,direction)
                arrange({'player':{'x':(wx+.5-.8*ux)*cell,'y':(wy+.5-.8*uy)*cell},
                         'enemy':{'x':(wx+.5+.8*ux)*cell,'y':(wy+.5+.8*uy)*cell}})
                wall=snap()
                check(prefix+' wall cast',cast(mid))
                step(m['windup']+.65)
                check(prefix+' wall consumes before range expiry',not snap()['bullets'])
                step(4)
                check(prefix+' no damage through wall',snap()['enemy']['hp']==wall['enemy']['hp'])
            sheet.save(SHOTS/(mid+'-八方向.png'))
            # Normal-speed evidence for each move: fixed 1/30 simulation interval.
            reset(mid,0)
            cast(mid)
            frames=[]
            for f in range(72):
                step(1/30)
                frames.append(tile(f'{mid} 1.0x t={(f+1)/30:.2f}',size=240))
            frames[0].save(SHOTS/(mid+'-原速.gif'),save_all=True,append_images=frames[1:],
                           duration=[30 if i%3 != 2 else 40 for i in range(len(frames))],loop=0)
            print(mid+' eight directions complete',flush=True)
        check('No zone/nova in R2: wavefront damage never uses instantaneous area',all(
            moves[mid]['kind'] in ('shot','fan') for mid in ORDER))
        for w,h in [(1440,900),(390,844),(844,390)]:
            page.set_viewport_size({'width':w,'height':h})
            reset('darkpulse')
            step(2)
            cast('darkpulse')
            step(.65)
            page.screenshot(path=str(SHOTS/f'实战-{w}x{h}.png'))
        check('No JS errors',not errors,errors)
        browser.close()
finally:
    report={'passed':sum(c['ok'] for c in checks),'failed':sum(not c['ok'] for c in checks),
            'jsErrors':len(errors),'errors':errors,'checks':checks,'samples':samples,
            'candidateSHA256':hashlib.sha256((ROOT/'候选试玩.html').read_bytes()).hexdigest(),
            'limitations':['Primary anatomical coverage uses 16 casters; not a human playtest.',
                           'No zone/nova in this batch; no invented area-damage test.',
                           '1.0x GIF uses 30fps fixed simulation, not slowed animation.']}
    (OUT/'浏览器验收.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['passed','failed','jsErrors']},ensure_ascii=False))
    if report['failed'] or errors:
        raise SystemExit(1)
