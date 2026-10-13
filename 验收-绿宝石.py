"""Focused integration tests for original-map candidate; not an aesthetic acceptance."""
from pathlib import Path
from urllib.parse import urlsplit
import hashlib,json,time,base64,math,os
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'验收记录/绿宝石';OUT.mkdir(parents=True,exist_ok=True)
URL=os.environ.get('POIGHT_TEST_URL','http://localhost:8792/').rstrip('/')
checks=[];errors=[];external=[]
def check(name,ok,detail=None):
 checks.append({'name':name,'ok':bool(ok),'detail':detail});assert ok,(name,detail)
def wait(page,expr,seconds=20):
 start=time.monotonic()
 while time.monotonic()-start<seconds:
  if page.evaluate(expr):return
  time.sleep(.05)
 raise AssertionError('timeout: '+expr)
def snap(page):return page.evaluate('window.__waterTest.snapshot()')
def arrange(page,data):page.evaluate('(v)=>window.__waterTest.arrange(v)',data)
def step(page,t):page.evaluate('(v)=>window.__waterTest.step(v)',t)
try:
 source=json.loads((ROOT/'素材/绿宝石场景/来源核验.json').read_text());check('518 original map records decoded',source['decodedMaps']==source['totalMaps']==518)
 catalog=json.loads((ROOT/'素材/绿宝石场景/场景目录.json').read_text());t=catalog['terrains'][0];s=t['cellSize'];cols=t['columns'];walk=base64.b64decode(t['walkB64']);check('49-map chunked region',len(t['areas'])==49 and len(t['chunks'])==219)
 check('No media API or ROM',source['paidAPICalls']==0 and not source['romRead'])
 frozen=json.loads((ROOT/'验收记录/绿宝石-接入前/收据.json').read_text())['files']
 for n in ['index.html','发布清单.json']:check('Formal file unchanged: '+n,hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==frozen[n])
 formal=json.loads((ROOT/'发布清单.json').read_text());bad=[p for p,r in formal['assets'].items() if not (ROOT/p).is_file() or hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=r['sha256']]
 before_manifest=json.loads((ROOT/'验收记录/绿宝石-接入前/候选发布清单.json').read_text())
 known_credit_mismatch=bad==['assets/鸣谢.txt'] and hashlib.sha256((ROOT/'assets/鸣谢.txt').read_bytes()).hexdigest()==before_manifest['assets']['assets/鸣谢.txt']['sha256']
 check('No new formal asset changes; pre-existing fixed-credit mismatch recorded',not bad or known_credit_mismatch,{'existingMismatches':bad,'matchedPreEmeraldCandidateReceipt':known_credit_mismatch,'notRepairedHere':True})
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True);context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:external.append(r.url) if urlsplit(r.url).scheme in ('http','https') and urlsplit(r.url).hostname not in ('localhost','localhost') else None)
  page.goto(URL+'/?test=1',wait_until='load');wait(page,'window.__waterTest?.snapshot().artReady');check('Exact authorized roster/moves121 preserved',snap(page)['rosterCount']==len(json.loads((ROOT/'首发200.json').read_text())['ids']) and snap(page)['moveCount']==121)
  cat=page.evaluate('window.__waterTest.catalog()');cat['scenes']=[s for s in cat['scenes'] if s.get('type')!='arena'];base={**snap(page)['profile'],'map':'emerald-littleroottown'};check('Sixteen original town start presets including independent Sootopolis',len(cat['scenes'])==16)
  for scene in cat['scenes']:
   ok=page.evaluate('(p)=>window.__waterTest.select(p)',{**base,'map':scene['id']});check('Atomic town entry '+scene['name'],ok)
   page.evaluate('window.__waterTest.reset(true)');arrange(page,{'ai':False});a=snap(page)
   check('Spawn and world '+scene['name'],a['environment']['id']==scene['id'] and a['world']==scene['world'])
   for side in ['player','enemy']:
    p=a[side];check('Walkable spawn '+scene['name']+'/'+side,page.evaluate('(p)=>window.__waterTest.freeAt(p.x,p.y)',p))
   path=page.evaluate('(v)=>window.__waterTest.findPath(v.player.x,v.player.y,v.enemy.x,v.enemy.y)',a);check('Reachable enemy '+scene['name'],len(path)>0,len(path))
   check('Visible chunks not full-world canvas '+scene['name'],a['environment']['terrain']['lastDrawChunks']<=9 and not a['environment']['terrain']['fullWorldCanvas'],a['environment']['terrain'])
   step(page,.01);page.screenshot(path=str(OUT/(scene['name']+'-对战.png')))
  # Sootopolis is independent; explicitly restore main-world terrain before walking its seams.
  page.evaluate('(p)=>window.__waterTest.select(p)',base)
  # Actual keyboard movement across source connection cells; resources/time must not reset.
  for seam in t['seams']:
   pairs=seam['walkablePairs']
   if not pairs:continue
   x,y,nx,ny=pairs[len(pairs)//2];px,py=(x+.5)*s,(y+.5)*s
   page.evaluate('window.__waterTest.reset(true)');arrange(page,{'ai':False,'player':{'x':px,'y':py,'hp':57,'stamina':61}});before=snap(page);check('Seam starts on source '+seam['from'],before['environment']['area']==seam['from'])
   key='d' if nx>x else 'a' if nx<x else 's' if ny>y else 'w';travel=.24*216/before['player']['speed'];page.keyboard.down(key);step(page,travel);page.keyboard.up(key);after=snap(page)
   check('Walk seam '+seam['from']+' -> '+seam['to'],after['environment']['area']==seam['to'],{'xy':[after['player']['x'],after['player']['y']],'wanted':seam['to'],'actual':after['environment']['area']})
   check('Seam retains HP and time',after['player']['hp']==57 and abs(after['elapsed']-travel)<1e-7)
  # Solid collision selected directly from original collision grid, away from missing-map borders.
  area=next(a for a in t['areas'] if a['id']=='MAP_LITTLEROOT_TOWN');pair=None
  for y in range(area['gridY']+2,area['gridY']+area['rows']-2):
   for x in range(area['gridX']+2,area['gridX']+area['columns']-2):
    if walk[y*cols+x] and not walk[(y-1)*cols+x]:pair=(x,y);break
   if pair:break
  x,y=pair;px,py=(x+.5)*s,(y+.5)*s;edge=y*s
  page.evaluate('window.__waterTest.reset(true)');arrange(page,{'ai':False,'player':{'x':px,'y':py}});page.keyboard.down('w');step(page,1);page.keyboard.up('w');a=snap(page);check('Original solid tile blocks walking',a['player']['y']>=edge+a['player'].get('body',{}).get('moveRadius',18)-1e-6,a['player']['y'])
  arrange(page,{'player':{'x':px,'y':py,'stamina':100}});page.evaluate("window.__waterTest.dash('player',0,-1)");step(page,.3);check('Original tile blocks dash sweep',snap(page)['player']['y']>=edge+snap(page)['player'].get('body',{}).get('moveRadius',18)-1e-6)
  check('Original tile blocks attack ray',not page.evaluate('(v)=>window.__waterTest.clearLine(v.x,v.y,v.x,v.y-48,3)',{'x':px,'y':py}))
  page.evaluate('(v)=>window.__waterTest.injectWater(v)',{'owner':'player','x':px,'y':py,'ux':0,'uy':-1,'speed':550});step(page,.2);check('Projectile consumed at wall',len(snap(page)['bullets'])==0)
  # T7: base had no explicit water-block assertion. Add capability-aware water checks;
  # keep every solid-tile walking/dash/ray/projectile assertion above unchanged.
  water=base64.b64decode(t['waterB64']);behaviors=base64.b64decode(t['behaviorB64']);raw_collision=base64.b64decode(t['collisionB64'])
  at=next(i for i,v in enumerate(water) if v);wet={'x':(at%cols+.5)*s,'y':(at//cols+.5)*s}
  check('Open water allows actual body occupancy',page.evaluate('(v)=>window.__waterTest.freeAt(v.x,v.y,20)',wet))
  rules=t['traversalRules']
  check('Water mask follows explicit free-exploration policy without changing original collision',all(not v or (rules.get(str(behaviors[i]),{}).get('mode')=='water' and (raw_collision[i]==0 or rules[str(behaviors[i])].get('overrideCollision'))) for i,v in enumerate(water)))
  check('Authorized waterfalls swimmable and named bridges walkable; unknown bridges blocked',all((water[i] and not walk[i]) if b==19 else (walk[i] and not water[i]) if str(b) in rules else (not water[i] and not walk[i]) for i,b in enumerate(behaviors) if b==19 or 0x70<=b<=0x7f))
  # Real combat still hits; AI actively walks on source collision rather than a background-only scene.
  first=cat['scenes'][0];page.evaluate('(p)=>window.__waterTest.select(p)',{**base,'map':first['id']});page.evaluate('window.__waterTest.reset(true)');arrange(page,{'ai':False});a=snap(page);check('Default firing line',page.evaluate('(v)=>window.__waterTest.clearLine(v.player.x,v.player.y,v.enemy.x,v.enemy.y,7)',a))
  # Generated Water Gun deliberately changed from650 to140 world-pixel range.
  dx,dy=a['enemy']['x']-a['player']['x'],a['enemy']['y']-a['player']['y'];length=math.hypot(dx,dy);point={'x':a['player']['x']+dx/length*110,'y':a['player']['y']+dy/length*110};check('Short-range combat target walkable',page.evaluate('(p)=>window.__waterTest.freeAt(p.x,p.y)',point));arrange(page,{'ai':False,'enemy':point});a=snap(page)
  hp=a['enemy']['hp'];page.evaluate("window.__waterTest.cast('player','watergun')");step(page,1.3);check('Combat damage inside revised short range on original map',snap(page)['enemy']['hp']<hp)
  page.evaluate('window.__waterTest.reset(true)');a=snap(page);step(page,1.4);b=snap(page);check('Actual AI moves',math.hypot(a['enemy']['x']-b['enemy']['x'],a['enemy']['y']-b['enemy']['y'])>10);check('AI remains walkable with actual footprint',page.evaluate('(p)=>window.__waterTest.freeAt(p.x,p.y,p.body?.moveRadius??18)',b['enemy']))
  # Cancel must keep current fight.
  page.locator('#battleMenuButton').click();page.locator('#sceneButton').click();wait(page,"document.getElementById('scenePicker').open");before=snap(page);page.locator('#sceneCards [data-scene="arena-formal"]').click();page.locator('#cancelScene').click();after=snap(page);check('Cancel preserves fight/map',after['environment']['id']==before['environment']['id'] and after['player']['hp']==before['player']['hp'])
  for width,height in [(1920,1080),(844,390),(390,844)]:
   page.set_viewport_size({'width':width,'height':height});page.locator('#battleMenuButton').click();page.locator('#sceneButton').click();page.screenshot(path=str(OUT/f'起点选择-{width}x{height}.png'));box=page.locator('#applyScene').bounding_box();page.locator('#applyScene').scroll_into_view_if_needed();box=page.locator('#applyScene').bounding_box();check(f'Controls reachable {width}x{height}',box and box['y']>=0 and box['y']+box['height']<=height+1);page.locator('#cancelScene').click()
  page.set_viewport_size({'width':1440,'height':900})
  # Actual allowlist, including newly content-hashed credits.
  for path in ['/世界地图.js','/素材/绿宝石场景/原始/pokeemerald/README.md','/.git/config','/首发50.json','/首发200.json']:
   check('Private path blocked '+path,page.request.get(URL+path).status==404)
  href=page.locator('.credits a').get_attribute('href');check('Credits available',page.request.get(URL+'/'+href).status==200)
  # Offline without a server, preserving separate page scope.
  offline=context.new_page();offline.on('pageerror',lambda e:errors.append(str(e)));offline.goto((ROOT/'候选试玩.html').as_uri()+'?test=1');wait(offline,'window.__waterTest?.snapshot().artReady');offline.evaluate('(p)=>window.__waterTest.select(p)',base);check('file:// offline local chunks loaded without whole-world preload',0<snap(offline)['environment']['terrain']['textures']<82 and snap(offline)['environment']['terrain']['visibleMissing']==0)
  check('No browser errors',not errors,errors);check('No runtime external requests',not external,external)
  context.close();browser.close()
except Exception as e:
 error=repr(e);print(error);raise
finally:
 report={'state':'technical_checks_passed_visual_review_pending' if checks and all(c['ok'] for c in checks) and 'error' not in globals() else 'failed','candidateSHA256':hashlib.sha256((ROOT/'候选试玩.html').read_bytes()).hexdigest(),'checks':checks,'passed':sum(c['ok'] for c in checks),'errors':errors,'external':external,'failure':globals().get('error'),'notVerified':['Human aesthetics/feel','All518 playable maps','Story/NPC/all other interiors; swim/dive/contracted warps covered by 大地图通行 suite','60FPS/audio/balance','Jump and human acceptance of generated effect anatomy/timing']}
 (OUT/'浏览器验收.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['checks']},ensure_ascii=False,indent=2))
