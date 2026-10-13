"""Body/locomotion candidate tests. Assertions on actual movement/hits, not win-rate proof."""
from pathlib import Path
import os,json,hashlib,time,base64,math
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'验收记录/体型与移速';OUT.mkdir(exist_ok=True)
URL=os.environ.get('POIGHT_TEST_URL','http://localhost:8792').rstrip('/')
checks=[];errors=[];external=[];samples=[];shots=[]
ROSTER_COUNT=len(json.loads((ROOT/'首发200.json').read_text())['ids'])
def check(name,ok,detail=None):
 checks.append({'name':name,'ok':bool(ok),'detail':detail});assert ok,(name,detail)
def snap(p):return p.evaluate('window.__waterTest.snapshot()')
def ready(p):
 for _ in range(400):
  if p.evaluate('window.__waterTest?.snapshot().artReady'):return
  time.sleep(.025)
 raise TimeoutError('art ready')
def reset(p,px=None,py=None,ex=None,ey=None):
 p.evaluate('window.__waterTest.reset(true)');p.evaluate('(v)=>window.__waterTest.arrange(v)',{'ai':False,'player':{'x':CX if px is None else px,'y':CY if py is None else py,'a':0},'enemy':{'x':CX-170 if ex is None else ex,'y':CY if ey is None else ey,'a':0}})
def select(p,a,b=7):
 return p.evaluate('(v)=>window.__waterTest.select(v)',{**default,'player':a,'enemy':b,'playerMoves':roster[a]['defaultMoves'],'enemyMoves':roster[b]['defaultMoves']})
def injected(p,side,offset,inside=True):
 target='player' if side=='enemy' else 'enemy';s=snap(p);x=s[target]['x'];y=s[target]['y'];before=s[target]['hp']
 p.evaluate('(v)=>window.__waterTest.injectWater(v)',{'owner':side,'x':x-85,'y':y+offset,'ux':1,'uy':0,'speed':650,'range':240})
 p.evaluate('window.__waterTest.step(.30)');a=snap(p)
 return before-a[target]['hp']
try:
 old=json.loads((ROOT/'验收记录/体型与移速-修改前/收据.json').read_text())
 for f in ['index.html','发布清单.json']:check('Formal untouched '+f,hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==old['formal'][f])
 # 冲刺 2026-10-11 授权修改源码，范围守卫移除
 prev=json.loads((ROOT/'验收记录/体型与移速-修改前/候选发布清单.json').read_text())['assets'];now=json.loads((ROOT/'候选发布清单.json').read_text())['assets']
 # Explicit authorized atlas replacements; all other previous assets stay exact.
 old_fx=json.loads((ROOT/'招式特效/生图重做/实景预览/构建记录.json').read_text())['assets']
 replaced={'assets/move-fx-e62aec5ac518d2a8.png','assets/move-fx-'+old_fx['drainpunch']['outputSHA256'][:16]+'.png',
           'assets/move-fx-'+old_fx['hyperbeam']['outputSHA256'][:16]+'.png',
           'assets/move-fx-fc3de7f0ce443644.png','assets/move-fx-993358e9b5107657.png','assets/move-fx-1437364f98e30eef.png'}
 replaced.update('assets/move-fx-'+old_fx[mid]['outputSHA256'][:16]+'.png' for mid in ['bugbite','crunch'])
 # R200 authorizes only the combined roster icon sheet and expanded credits.
 r200_repacked={'assets/icons-9a1f8a05f051.png','assets/鸣谢-d2355ec27d7e.txt'}
 retired=json.loads((ROOT/'素材/绿宝石场景/被全图区块替代.json').read_text())['assets']
 check('Exactly 83 registered world repack replacements',len(retired)==83 and all(k in prev and v==prev[k] for k,v in retired.items()))
 check('Previous assets byte-identical except authorized M4 atlases; listed or W2 registered',all((ROOT/k).is_file() and hashlib.sha256((ROOT/k).read_bytes()).hexdigest()==v['sha256'] and ((k in now and now[k]['sha256']==v['sha256']) or (k in retired and retired[k]==v) or k in r200_repacked) for k,v in prev.items() if k not in replaced))
 drain=json.loads((ROOT/'招式特效/第1批/drainpunch/来源.json').read_text())['processing']['outputSHA256']
 check('Authorized DrainPunch replacement matches source receipt',now['assets/move-fx-'+drain[:16]+'.png']['sha256']==drain)
 for mid in ('bubble','razorleaf','darkpulse'):
  sha=json.loads((ROOT/'招式特效/第2批'/mid/'来源.json').read_text())['outputSHA256']
  check('Authorized R2 replacement matches receipt '+mid,now['assets/move-fx-'+sha[:16]+'.png']['sha256']==sha)
 new_hyper=json.loads((ROOT/'招式特效/第3批/hyperbeam/来源.json').read_text())['processing']['outputSHA256']
 check('Authorized HyperBeam replacement matches R3 receipt',now['assets/move-fx-'+new_hyper[:16]+'.png']['sha256']==new_hyper)
 latest=json.loads((ROOT/'招式特效/主角八招/thunderbolt/来源.json').read_text())['processing']['outputSHA256']
 check('Authorized Thunderbolt replacement matches P3b receipt',now['assets/move-fx-'+latest[:16]+'.png']['sha256']==latest)
 mapping=json.loads((ROOT/'数值资料/体型校准/映射记录.json').read_text());source=json.loads((ROOT/'数值资料/体型校准/来源.json').read_text());check('authorized roster archived, validated default-form responses',len(source['species'])==ROSTER_COUNT and not source['errors']);check('authorized roster body mappings',len(mapping['species'])==ROSTER_COUNT)
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True);p=browser.new_page(viewport={'width':1440,'height':960});p.on('pageerror',lambda e:errors.append(str(e)));p.on('request',lambda r:external.append(r.url) if r.url.startswith(('http','https')) and not r.url.startswith(URL) else None);p.goto(URL+'/?test=1');ready(p)
  c=p.evaluate('window.__waterTest.catalog()');roster={m['id']:m for m in c['roster']};default={**snap(p)['profile'],'map':'emerald-rustborocity'}
  check('authorized roster/121/104 with Splash and R1/R2/R3',len(roster)==ROSTER_COUNT and len(c['moves'])==121 and snap(p)['generated']['loaded']==104)
  t=c['terrains'][0];cols=t['columns'];walk=base64.b64decode(t['walkB64']);area=next(a for a in t['areas'] if a['sourceName']=='RustboroCity');lane=None
  for y in range(area['gridY']+3,area['gridY']+area['rows']-3):
   for x in range(area['gridX']+4,area['gridX']+area['columns']-4):
    if all(walk[(y+dy)*cols+x+dx] for dy in range(-2,3) for dx in range(-4,5)):lane=x,y;break
   if lane:break
  assert lane,'9x5 real-map open area';CX,CY=(lane[0]+.5)*48,(lane[1]+.5)*48
  for n,mon in roster.items():
   check(f'{n}: profile loads',select(p,n))
   b=mon['body'];check(f'{n}: source dimensions/speed present',b['heightMeters']>0 and b['weightKg']>0 and 83<=mon['speed']<=120 and len(b['hurtByDirection'])==8)
   reset(p);s=snap(p);p.keyboard.down('KeyD');p.evaluate('window.__waterTest.step(.4)');p.keyboard.up('KeyD');end=snap(p);distance=math.hypot(end['player']['x']-s['player']['x'],end['player']['y']-s['player']['y']);check(f'{n}: real walking matches configured speed',abs(distance-mon['speed']*.4)<.05,{'actual':distance,'speed':mon['speed']})
   reset(p);s=snap(p);p.keyboard.down('KeyD');p.keyboard.down('KeyS');p.evaluate('window.__waterTest.step(.4)');p.keyboard.up('KeyD');p.keyboard.up('KeyS');end=snap(p);diagonal=math.hypot(end['player']['x']-s['player']['x'],end['player']['y']-s['player']['y']);check(f'{n}: diagonal not faster',abs(diagonal-distance)<.05)
   reset(p);check(f'{n}: actual center projectile hits',injected(p,'enemy',0)>0)
   reset(p);ry=snap(p)['player']['body']['hurt']['ry'];edge=ry+c['moves']['watergun']['radius'];check(f'{n}: actual outside-body projectile misses',injected(p,'enemy',edge+2)==0)
   reset(p);check(f'{n}: actual inside-body projectile hits',injected(p,'enemy',edge-2)>0)
   # Analytic geometry and live renderer direction agree for all eight rows; no RNG in body tests.
   geom=p.evaluate('''()=>{const a=window.__waterTest,s=a.snapshot(),B=window.PoightBodies,c=a.catalog().roster.find(q=>q.id===s.player.id);return Array.from({length:8},(_,row)=>{const p={x:0,y:0,a:Math.PI/2+row*Math.PI/4,char:c},b=B.shape(p);return {row,center:Number.isFinite(B.segment(p,-100,0,100,0,3)),miss:!Number.isFinite(B.segment(p,-100,b.ry+5,100,b.ry+5,3)),stable:Array.from({length:10},()=>B.segment(p,-100,b.ry+5,100,b.ry+5,3)).every(x=>x===Infinity),shape:b};});}''')
   check(f'{n}: all8 body directions deterministic hit/miss',all(g['center'] and g['miss'] and g['stable'] for g in geom))
   check(f'{n}: walk/fly animation and body finite',all(math.isfinite(snap(p)['player'][k]) for k in ['x','y','scale','speed','flightHeight']) and b['moveRadius']<=20)
   samples.append({'id':n,'name':mon['name'],'speed':mon['speed'],'distance04s':distance,'diagonal04s':diagonal,'body':b,'geometry':geom})
  for a,b in [(25,143),(133,208),(7,6),(147,148)]:
   select(p,a,b);reset(p,px=CX-60,ex=CX+100);p.evaluate('window.__waterTest.step(.8)');s=snap(p);fn=f'{a:04}-{b:04}-实战体型.png';p.screenshot(path=str(OUT/fn));shots.append({'file':fn,'player':s['player'],'enemy':s['enemy']})
  check('Small species move faster than representative large species',roster[25]['speed']>roster[143]['speed'] and roster[133]['speed']>roster[208]['speed'] and roster[7]['speed']>roster[6]['speed'])
  for n,expected in [(25,False),(143,True)]:
   select(p,n);reset(p);check(f'Identical18px grazing path: {n} hit={expected}',(injected(p,'enemy',18)>0)==expected)
   select(p,7,n);reset(p,px=CX-170,ex=CX);check(f'Same rules on CPU side: {n} hit={expected}',(injected(p,'player',18)>0)==expected)
  # True melee range follows both bodies, while damage/cooldowns remain unchanged.
  reaches={}
  for n in [25,208]:
   select(p,n);reset(p,ex=CX+50)
   r=p.evaluate('''()=>{const a=window.__waterTest,c=a.catalog(),s=a.snapshot(),B=window.PoightBodies,make=k=>({...s[k],char:c.roster.find(q=>q.id===s[k].id)});return B.meleeRange(make('enemy'),c.moves.brickbreak.range,1,0,make('player'));}''');reaches[n]=r
   for offset,expected in [(-1,True),(1,False)]:
    reset(p,ex=CX+r+offset);p.evaluate('window.__waterTest.equip("player",["brickbreak","watergun","protect","agility"])');hp=snap(p)['enemy']['hp'];p.evaluate('window.__waterTest.cast("player","brickbreak")');p.evaluate('(n)=>window.__waterTest.step(n)',c['moves']['brickbreak']['windup']-.001);check(f'{n}: no damage before visible melee contact {offset:+}',snap(p)['enemy']['hp']==hp);p.evaluate('window.__waterTest.step(.10)');check(f'{n}: melee edge {offset:+} actual hit={expected}',(snap(p)['enemy']['hp']<hp)==expected)
  check('Large body has natural melee contact reach, not damage buff',reaches[208]>reaches[25]+20,reaches)
  # Both footprint sizes remain outside source-grid walls after swept dashes.
  wall=next((x,y) for y in range(area['gridY']+2,area['gridY']+area['rows']-2) for x in range(area['gridX']+3,area['gridX']+area['columns']-2) if not walk[y*cols+x] and all(walk[y*cols+x-d] for d in [1,2,3]))
  for n in [25,143,208]:
   select(p,n);reset(p,px=(wall[0]-1.5)*48,py=(wall[1]+.5)*48,ex=CX,ey=CY+60);p.evaluate('window.__waterTest.dash("player",1,0)');p.evaluate('window.__waterTest.step(.3)');s=snap(p);check(f'{n}: swept dash obeys own foot and source wall',s['player']['x']<=wall[0]*48-s['player']['body']['moveRadius']+.05 and p.evaluate('(v)=>window.__waterTest.freeAt(...v)',[s['player']['x'],s['player']['y'],s['player']['body']['moveRadius']]))
  select(p,25,143);reset(p,px=CX-60,ex=CX+100);p.evaluate('window.__waterTest.step(.8)');p.keyboard.press('Escape');before=snap(p);p.evaluate('window.__waterTest.step(1)');check('Pause still freezes positions',snap(p)['player']['x']==before['player']['x']);p.keyboard.press('Escape')
  for width,height in [(1440,960),(390,844),(844,390)]:
   p.set_viewport_size({'width':width,'height':height})
   p.locator('#battleMenuButton').click();p.locator('#setupButton').click()
   compact=not p.locator('#playerBody').is_visible()
   if compact:p.locator('#toggleLoadout').click()
   facts=p.locator('#selectedStats' if compact else '#playerBody')
   narrow_portrait=width<=430 and height>width
   # R200b 补充1裁决：MOB3窄竖屏有意隐藏详情，不改UI；DOM信息与真实配招仍须可用。
   text=facts.text_content() if facts.count()==1 else ''
   check(f'UI body facts {"in DOM" if narrow_portrait else "visible"} via GBA card/configuration {width}x{height}',
         facts.count()==1 and (narrow_portrait or facts.is_visible()) and '0.4 m' in text and '6 kg' in text)
   if narrow_portrait:
    check('Narrow portrait loadout slots and catalog usable',
          p.locator('#moveSlots button').count()==4 and p.locator('#moveChoice0').is_visible() and
          p.locator('#moveCatalog button:enabled').count()>0)
    p.locator('#moveChoice0').click()
    alternative=p.locator('#moveCatalog button:enabled[aria-pressed="false"]').first
    chosen=alternative.get_attribute('data-move');alternative.click()
    check('Narrow portrait real move replacement works',p.locator('#moveChoice0').get_attribute('data-move')==chosen)
    p.locator('#defaultMoves').click()
    check('Narrow portrait recommended loadout restored',
          p.locator('#moveSlots button').evaluate_all('(buttons)=>buttons.map(b=>b.dataset.move)')==roster[25]['defaultMoves'])
   p.screenshot(path=str(OUT/f'选角体型-{width}x{height}.png'))
   check(f'No page horizontal overflow {width}x{height}',p.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
   check(f'Body facts do not overlap title {width}x{height}',p.evaluate('''compact=>{
     if(compact){const d=document.querySelector('#selectedStats').getBoundingClientRect(),
       n=document.querySelector('#selectedName').getBoundingClientRect();
       return d.right<=n.left+.5||d.left>=n.right-.5||d.top>=n.bottom-.5||d.bottom<=n.top+.5;}
     return [...document.querySelectorAll('.fighter-panel')].every(e=>{
       const b=e.querySelector('.fighter-badge').getBoundingClientRect(),n=e.querySelector('strong').getBoundingClientRect(),
       d=e.querySelector('.body-summary').getBoundingClientRect();return b.bottom<=n.top+.5&&n.bottom<=d.top+.5});}''',compact))
   if compact:p.locator('#closeMoves').click()
   p.locator('#closeSetup').click()
  for path in ['/体型数据.py','/体型判定.js','/数值资料/体型校准/原始响应/0025.json']:
   check('Private source denied '+path,p.request.get(URL+path).status==404)
  q=browser.new_page();q.on('pageerror',lambda e:errors.append(str(e)));q.on('request',lambda r:external.append(r.url) if r.url.startswith(('http','https')) else None);q.goto((ROOT/'候选试玩.html').as_uri()+'?test=1');ready(q);check('Offline body profiles and104FX load',len(q.evaluate('window.__waterTest.catalog().roster.filter(c=>c.body)'))==ROSTER_COUNT and snap(q)['generated']['loaded']==104)
  check('No JS errors or external runtime requests',not errors and not external,{'errors':errors,'external':external});browser.close()
finally:
 report={'candidateSHA256':hashlib.sha256((ROOT/'候选试玩.html').read_bytes()).hexdigest(),'passed':sum(x['ok'] for x in checks),'checks':checks,'samples':samples,'screenshots':shots,'errors':errors,'external':external,'notProven':['human feel/visual approval','win-rate parity','all50 pairings balance','exact per-pixel/height/anatomical collision','swimming/diving/world-agent integration'],'controlsUnchanged':['WASD/arrows','JKLI','R','Esc','double-tap dash','Space reserved for unimplemented jump']};(OUT/'浏览器验收.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':report['passed'],'testedSpecies':len(samples),'errors':errors},ensure_ascii=False))
