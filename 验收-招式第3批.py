"""R3: real headless combat, 28 x 8 directions, no slow motion or preview renderer."""
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

from 招式特效.第3批参数 import ALL, CASTERS
from 招式特效.第3批参数 import MOVES as PATCH
from 游戏数据 import MOVES as SOURCE_MOVES

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/招式第3批'
SHOTS = OUT / '截图'
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get('POIGHT_TEST_URL', 'http://localhost:8853/').rstrip('/')
checks, errors, samples = [], [], []


def check(name, ok, detail=None):
    checks.append({'name':name, 'ok':bool(ok), 'detail':detail})


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snap():
    return page.evaluate('window.__waterTest.snapshot()')


def step(t):
    page.evaluate('(t)=>window.__waterTest.step(t)', t)


def arrange(data):
    page.evaluate('(d)=>window.__waterTest.arrange(d)', data)


def cast(mid):
    return page.evaluate('(id)=>window.__waterTest.cast("player",id)', mid)


def reset(mid, direction=0, distance=95):
    page.evaluate('window.__waterTest.reset(true)')
    a = direction * math.pi / 4
    arrange({'ai': False, 'player': {'x': CX, 'y': CY, 'a': a, 'hp': 60},
             'enemy': {'x': CX+math.cos(a)*distance, 'y': CY+math.sin(a)*distance}})
    page.evaluate('(ids)=>window.__waterTest.equip("player",ids)', [mid]+[id for id in moves if id!=mid][:3])
    step(.3)
    return snap()


def tile(label):
    s = snap()
    data = page.locator('canvas').first.evaluate('(c)=>c.toDataURL("image/png")')
    image = Image.open(io.BytesIO(base64.b64decode(data.split(',')[1]))).convert('RGB')
    scale = image.width/s['viewport']['width']
    x = (s['player']['x']-round(s['camera']['x']))*scale
    y = (s['player']['y']-round(s['camera']['y']))*scale
    crop = image.crop((round(x-125*scale), round(y-170*scale),
                       round(x+155*scale), round(y+110*scale))).resize((280,280))
    result = Image.new('RGB',(280,300),'#273239')
    result.paste(crop,(0,20))
    ImageDraw.Draw(result).text((5,3),label,fill='white')
    return result


def expected(s, mid):
    p = s['player']
    entries = roster[p['id']].get('moveAnchors', {})
    part = moves[mid].get('anchor')
    entry = entries.get('r3-' + part, entries.get(part)) if part else None
    if not entry:
        return None
    clip = catalog['art'][str(p['id'])][entry['role']]
    row, frame = p['direction'], p['animFrame']
    x, y = entry['points'][row][frame]
    dx, dy = clip.get('bodyOffsets', [[[0,0]]*clip['frames']]*8)[row][frame]
    point = {'x':p['x']+(x-clip['anchorX']-dx)*p['scale'],
             'y':p['y']+14+(y-clip['anchorY']-dy)*p['scale']-p['flightHeight']}
    if mid not in PATCH or moves[mid]['kind'] != 'rush':
        return point
    # Independent implementation of R3-only native-body transform.
    a = p['attack']
    active = a['emitted']
    t = a['age']-a['hitTime'] if active else a['age']/max(.001,a['hitTime'])
    progress = min(1,t/(a['range']/moves[mid]['rushSpeed'])) if active else t
    side = 1 if math.cos(a['aim'])>=0 else -1
    angle, lift, squash = 0,0,1
    if mid in ['flamewheel','rollout']:
        angle = t*14*side if active else -progress*.35*side
    elif mid == 'bodyslam':
        angle = (math.sin(progress*math.pi) if active else -progress*.22)*side
        lift = math.sin(progress*math.pi)*26 if active else math.sin(progress*math.pi/2)*12
        squash = 1-.1*math.sin(progress*math.pi) if active else 1
    elif mid == 'waterfall':
        lift = math.sin(progress*math.pi)*13 if active else progress*3
    elif mid == 'shadowsneak':
        squash = .72 if active else 1-progress*.28
    elif mid in ['tackle','doubleedge','zenheadbutt','machpunch']:
        angle = (.14 if active else -progress*(.22 if mid=='doubleedge' else .12))*side
    cx,cy = p['x'],p['y']-p['body']['nominalSize']*.38
    dx,dy = point['x']-cx,point['y']-cy
    return {'x':cx+dx*math.cos(angle)-dy*squash*math.sin(angle),
            'y':cy+dx*math.sin(angle)+dy*squash*math.cos(angle)-lift}


def distance(a,b):
    return math.hypot(a['x']-b['x'],a['y']-b['y'])


try:
    baseline = Path(os.environ.get('POIGHT_T5_BASELINE', ROOT.parent / 'T5'))
    record = json.loads((ROOT/'招式特效/生图重做/实景预览/构建记录.json').read_text())['assets']
    guards = []
    for mid in ['thunderbolt','quickattack','irontail','thunder','flamethrower','fireblast','dragonclaw','airslash','stoneedge']:
        relative = (Path('招式特效/主角八招')/mid/(mid+'-动画.png') if mid in ['thunderbolt','thunder']
                    else Path(record[mid]['output']))
        row = {'id':mid,'sha256':sha(ROOT/relative),'t5SHA256':sha(baseline/relative)}
        guards.append(row)
        check(mid+' protected atlas matches T5',row['sha256']==row['t5SHA256'],row)
    (OUT/'受保护图集.json').write_text(json.dumps(guards,ensure_ascii=False,indent=2)+'\n')
    print('Protected atlas SHA256:')
    for row in guards:
        print(row['id'],row['sha256'],'== T5',row['sha256']==row['t5SHA256'])
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width':1440,'height':900})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(URL+'/?test=1')
        for _ in range(400):
            if page.evaluate('window.__waterTest?.snapshot().artReady'):
                break
            time.sleep(.03)
        catalog = page.evaluate('window.__waterTest.catalog()')
        roster = {r['id']:r for r in catalog['roster']}
        moves = catalog['moves']
        initial = snap()['profile']
        for mid in ALL:
            source = SOURCE_MOVES[mid]
            cd = source['cd'] if source['kind'] in ['heal','buff','splash'] else min(3,max(.45,source['cd']*.4))
            check(mid+' damage/cost retained; global cooldown compression',
                  all(moves[mid][key]==source[key] for key in ['damage','cost']) and moves[mid]['cd']==cd)
        for mid in ['wildcharge','phantomforce']:
            old=json.loads((baseline/'招式特效/实战打包记录.json').read_text())['timingAndRangeOverrides'][mid]
            expected_runtime = {**old}
            if 'windup' in old:
                expected_runtime['windup'] = 0 if old['windup']==0 else min(.35,max(.05,old['windup']*.5))
            if 'recovery' in old:
                expected_runtime['recovery'] = old['recovery']*.6
            check(mid+' retained runtime unchanged except H1 timing',
                  all(moves[mid][key]==value for key,value in expected_runtime.items()))
        terrain = catalog['terrains'][0]
        cols,cell = terrain['columns'],terrain['cellSize']
        walk = base64.b64decode(terrain['walkB64'])
        area = next(a for a in terrain['areas'] if a['sourceName']=='RustboroCity')
        x,y = next((x,y) for y in range(area['gridY']+4,area['gridY']+area['rows']-4)
                   for x in range(area['gridX']+4,area['gridX']+area['columns']-4)
                   if all(walk[(y+dy)*cols+x+dx] for dy in range(-3,4) for dx in range(-3,4)))
        CX,CY = (x+.5)*cell,(y+.5)*cell
        for mid in ALL:
            print('CHECK',mid,flush=True)
            caster = CASTERS[mid]
            page.evaluate('(p)=>window.__waterTest.select(p)',
                          {**initial,'player':caster,'enemy':7,'map':'emerald-rustborocity',
                           'playerMoves':roster[caster]['defaultMoves'],'enemyMoves':roster[7]['defaultMoves']})
            m = moves[mid]
            sheet = Image.new('RGB',(1680,1200),'#273239')
            for direction in range(8):
                prefix = f'{mid}/{direction}'
                start = reset(mid,direction,20 if m['kind']=='melee' else 70 if mid=='machpunch' else 95)
                hp = start['enemy']['hp']
                check(prefix+' pre-cast no damage',start['hits']==0)
                check(prefix+' cast',cast(mid))
                s = snap()
                reach = s['player']['attack']['range']
                body = s['player']['body']['nominalSize']
                budget = min(m['range'],body*m.get('rangeBodies',5))
                check(prefix+' range <= budget <=5 bodies',reach<=budget+1e-6 and reach<=body*5,reach)
                check(prefix+' cooldown blocks recast',not cast(mid))
                step(m['windup']-.001)
                check(prefix+' no damage before release',snap()['enemy']['hp']==hp and not snap()['bullets'])
                left,top = (direction//4)*840,(direction%4)*300
                sheet.paste(tile(prefix+' windup'),(left,top))
                step(.001)
                s = snap()
                point = expected(s,mid)
                if point:
                    actual = (s['bullets'][0]['originAnchor'] if s['bullets'] else
                              s['player']['attack']['anchor'])
                    check(prefix+' emission within 6px of sprite landmark',actual is not None and distance(point,actual)<=6,
                          distance(point,actual) if actual else None)
                else:
                    check(prefix+' retained move has no new anchor',mid in ['wildcharge','phantomforce'])
                if m['kind']=='beam':
                    a = direction*math.pi/4
                    ux,uy = math.cos(a),math.sin(a)
                    def body_reach(p, ux=ux, uy=uy):
                        h = p['body']['hurt']
                        return 1/math.hypot(ux/h['rx'],uy/h['ry'])
                    window = (95-body_reach(s['player'])-body_reach(s['enemy'])-m['radius'])/m['speed']
                    step(max(.015,min(.16,window*.55)))
                else:
                    step(.07)
                sheet.paste(tile(prefix+' release'),(left+280,top))
                result = page.evaluate('''(data)=>{
                    const api=window.__waterTest;
                    let premature=false;
                    for(let tick=0;tick<240 && api.snapshot().enemy.hp>=data.hp;tick++) {
                        api.step(1/120,data.surf);
                        if(data.surf) {
                            const s=api.snapshot(),e=s.generated.states.find(e=>e.id==='surf');
                            if(e?.visibleFront) {
                                const ux=Math.cos(data.aim),uy=Math.sin(data.aim),h=s.enemy.body.hurt;
                                const edge=1/Math.hypot(ux/h.rx,uy/h.ry);
                                const ahead=(s.enemy.x-e.visibleFront.x)*ux+(s.enemy.y-e.visibleFront.y)*uy;
                                if(ahead>edge && s.enemy.hp<data.hp) premature=true;
                            }
                        }
                    }
                    api.step(0);
                    return {state:api.snapshot(),premature};
                }''',{'hp':hp,'surf':mid=='surf','aim':direction*math.pi/4})
                hit = result['state']
                if mid=='surf':
                    check(prefix+' no damage before visible wave front',not result['premature'])
                check(prefix+' actual contact damages',hit['enemy']['hp']<hp,hit['enemy']['hp'])
                if mid in ['absorb','gigadrain']:
                    step(.12)
                sheet.paste(tile(prefix+' hit'+(' / return +.12s' if mid in ['absorb','gigadrain'] else '')),
                            (left+560,top))
                if mid in ['absorb','gigadrain']:
                    if mid == 'absorb':
                        check(prefix+' contact-only VB1 green return flow',
                              any(e['id'] == mid and e['vb1']['drain']
                                  for e in hit['animation']['meleeReturns']))
                    else:
                        check(prefix+' contact-only return flow',
                              any(e['mode']=='r3return' for e in hit['generated']['states']) or
                              any(b['id']==mid and b.get('va2Root') and b['age']==0
                                  for b in hit['animation']['bursts']))
                samples.append({'id':mid,'direction':direction,'range':reach,'budget':budget,
                                'hitSeconds':hit['elapsed']-start['elapsed'],'damage':hp-hit['enemy']['hp']})
                step(2)
                check(prefix+' effect expires',not snap()['bullets'] and not snap()['generated']['active'])
                reset(mid,direction)
                cast(mid)
                arrange({'enemy':{'x':CX+260,'y':CY+260}})
                maximum = page.evaluate('''(data)=>{
                    const api=window.__waterTest,start=api.snapshot().player;
                    let maximum=0;
                    for(let tick=0;tick<220;tick++) {
                        api.step(.01,false);
                        const s=api.snapshot();
                        if(data.rush) maximum=Math.max(maximum,Math.hypot(s.player.x-start.x,s.player.y-start.y));
                        for(const b of s.bullets)
                            maximum=Math.max(maximum,Math.hypot(b.x-b.sx,b.y-b.sy));
                    }
                    api.step(0);
                    return maximum;
                }''',{'rush':m['kind']=='rush'})
                check(prefix+' measured travel <= budget',maximum<=budget+.1,maximum)
                check(prefix+' miss expires',not snap()['bullets'] and not snap()['generated']['active'])
                if m['kind'] in ['shot','beam']:
                    reset(mid,direction)
                    ux,uy = math.cos(direction*math.pi/4),math.sin(direction*math.pi/4)
                    world = snap()['world']
                    page.evaluate('(v)=>window.__waterTest.injectWater(v)',
                                  {'owner':'player','move':mid,'ux':ux,'uy':uy,
                                   'x':world['width']-25.1 if ux>.1 else 25.1 if ux<-.1 else CX,
                                   'y':world['height']-30.1 if uy>.1 else 45.1 if uy<-.1 else CY,
                                   'range':reach,'speed':m['speed']})
                    step(.02)
                    check(prefix+' boundary consumes projectile',not snap()['bullets'])
            sheet.save(SHOTS/(mid+'-八方向.png'))
            for direction in range(8):
                ux,uy = round(math.cos(direction*math.pi/4)),round(math.sin(direction*math.pi/4))
                wx,wy = next((x,y) for y in range(3,terrain['rows']-3) for x in range(3,cols-3)
                             if not walk[y*cols+x] and walk[(y-uy)*cols+x-ux]
                             and walk[(y-2*uy)*cols+x-2*ux] and walk[(y+uy)*cols+x+ux])
                reset(mid,direction)
                arrange({'player':{'x':(wx+.5-.8*ux)*cell,'y':(wy+.5-.8*uy)*cell},
                         'enemy':{'x':(wx+.5+.8*ux)*cell,'y':(wy+.5+.8*uy)*cell}})
                hp = snap()['enemy']['hp']
                check(f'{mid}/{direction} wall cast',cast(mid))
                step(3)
                s = snap()
                check(f'{mid}/{direction} wall blocks damage and effect expires',
                      s['enemy']['hp']==hp and not s['bullets'] and not s['generated']['active'])
        # This batch has no radial nova/target-zone after Surf's already-existing ride route.
        check('Batch uses no invisible instantaneous area damage',all(moves[mid]['kind'] not in ['nova','zone'] for mid in ALL))
        page.evaluate('(p)=>window.__waterTest.select(p)',
                      {**initial,'player':9,'enemy':7,'map':'emerald-rustborocity',
                       'playerMoves':roster[9]['defaultMoves'],'enemyMoves':roster[7]['defaultMoves']})
        for w,h in [(1440,900),(390,844),(844,390)]:
            page.set_viewport_size({'width':w,'height':h})
            page.wait_for_timeout(80)
            page.evaluate('window.dispatchEvent(new Event("resize"))')
            reset('flashcannon')
            step(2)
            cast('flashcannon')
            step(.65)
            q=snap()
            check(f'{w}x{h} real battle visible',
                  0<=q['player']['x']-q['camera']['x']<=q['viewport']['width']
                  and 0<=q['player']['y']-q['camera']['y']<=q['viewport']['height'])
            page.screenshot(path=str(SHOTS/f'实战-{w}x{h}.png'))
        check('No JS errors',not errors,errors)
        browser.close()
except Exception as exc:
    check('Harness completed without exception', False, str(exc))
    raise
finally:
    report = {'passed':sum(c['ok'] for c in checks),'failed':sum(not c['ok'] for c in checks),
              'jsErrors':len(errors),'errors':errors,'checks':checks,'samples':samples,
              'candidateSHA256':sha(ROOT/'候选试玩.html'),
              'limitations':['One canonical caster per move; equip bypass is renderer coverage, not learnset validation.',
                             'Native-body poses are image transforms, not newly redrawn character art.',
                             'Protected retained rushes use their unmodified T5 attachment behavior.']}
    (OUT/'浏览器验收.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['passed','failed','jsErrors']},ensure_ascii=False))
    if report['failed'] or errors:
        raise SystemExit(1)
