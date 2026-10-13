"""Actual candidate combat checks. Test-only equip bypass is for renderer coverage, not learnset proof."""
from pathlib import Path
import os,json,math,time,base64,hashlib
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'验收记录/生图实战';OUT.mkdir(exist_ok=True)
URL=os.environ.get('POIGHT_TEST_URL','http://localhost:8792/').rstrip('/');checks=[];errors=[];external=[];coverage=[]
def check(n,v,d=None):checks.append({'name':n,'ok':bool(v),'detail':d});assert v,(n,d)
def snapshot(p):return p.evaluate('window.__waterTest.snapshot()')
def arrange(p,d):p.evaluate('(x)=>window.__waterTest.arrange(x)',d)
def step(p,n):p.evaluate('(x)=>window.__waterTest.step(x)',n)
def ready(p):
 for _ in range(400):
  if p.evaluate('window.__waterTest?.snapshot().artReady'):return
  time.sleep(.03)
 raise TimeoutError('candidate load')
def reset(p,mid,distance=95,angle=0,low=False):
 p.evaluate('window.__waterTest.reset(true)');arrange(p,{'ai':False,'player':{'x':CX,'y':CY,**({'hp':55} if low else {})},'enemy':{'x':CX+math.cos(angle)*distance,'y':CY+math.sin(angle)*distance}})
 p.evaluate('(ids)=>window.__waterTest.equip("player",ids)',[mid]+[s for s in moves if s!=mid][:3])
 step(p,.3)
try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True);p=browser.new_page(viewport={'width':1440,'height':900});p.on('pageerror',lambda e:errors.append(str(e)));p.on('request',lambda r:external.append(r.url) if r.url.startswith(('http','https')) and not r.url.startswith(URL) else None);p.goto(URL+'/?test=1');ready(p)
  catalog=p.evaluate('window.__waterTest.catalog()');moves=catalog['moves'];t=catalog['terrains'][0];cols=t['columns'];walk=base64.b64decode(t['walkB64']);cell=t['cellSize'];area=next(a for a in t['areas'] if a['sourceName']=='RustboroCity');center=None
  for y in range(area['gridY']+2,area['gridY']+area['rows']-2):
   for x in range(area['gridX']+2,area['gridX']+area['columns']-2):
    if all(walk[(y+dy)*cols+x+dx] for dx in range(-2,3) for dy in range(-2,3)):center=(x,y);break
   if center:break
  assert center;CX,CY=(center[0]+.5)*cell,(center[1]+.5)*cell
  spec=json.loads((ROOT/'招式特效/实战绘制.json').read_text())['moves'];spec['thunder']={'caster':25};ids=sorted(set(spec)&set(moves));check('57 runtime entries including thunder; do not invent aerialace',len(ids)==57 and 'aerialace' not in moves);check('authorized roster /121 moves including harmless Splash',len(catalog['roster'])==len(json.loads((ROOT/'首发200.json').read_text())['ids']) and len(moves)==121);check('All104 hashed images loaded before play',snapshot(p)['generated']['loaded']==104)
  default={**snapshot(p)['profile'],'map':'emerald-rustborocity'};roster={c['id']:c for c in catalog['roster']}
  for mid in ids:
   caster=spec[mid]['caster'];prof={**default,'player':caster,'playerMoves':roster[caster]['defaultMoves']};check(mid+' caster loads',p.evaluate('(v)=>window.__waterTest.select(v)',prof))
   m=moves[mid];distance=42 if m['kind'] in ('melee','spin') else 55 if mid=='earthquake' else 95
   for direction in range(8):
    reset(p,mid,distance,direction*math.pi/4,mid=='recover');check(mid+f' dir{direction} actual cast',p.evaluate('(id)=>window.__waterTest.cast("player",id)',mid));step(p,m['windup']+.025);s=snapshot(p);check(mid+f' dir{direction} raster actually drawn',mid in s['generated']['drawn'],s['generated']);check(mid+f' dir{direction} finite state',all(math.isfinite(s[a][k]) for a in ['player','enemy'] for k in ['x','y','hp']));
    if direction==0:
     step(p,.09);p.screenshot(path=str(OUT/(mid+'-实战.png')))
    step(p,2);coverage.append({'id':mid,'direction':direction,'hits':snapshot(p)['hits']})
  p.evaluate('(v)=>window.__waterTest.select(v)',default)
  for mid in ['watergun','solarbeam','hyperbeam']:
   reset(p,mid,125);hp=snapshot(p)['enemy']['hp'];p.evaluate('(id)=>window.__waterTest.cast("player",id)',mid);step(p,moves[mid]['windup']+.01);s=snapshot(p);check(mid+' no emission-time damage before visible front',s['enemy']['hp']==hp and len(s['bullets'])==1,s['bullets']);step(p,.85);s=snapshot(p);check(mid+' real damage on front arrival',s['enemy']['hp']<hp and s['hits']==1,{'hp':s['enemy']['hp'],'hits':s['hits']});step(p,1);check(mid+' once per cast',snapshot(p)['hits']==1)
  reset(p,'fireblast',115);p.evaluate('window.__waterTest.cast("player","fireblast")');step(p,moves['fireblast']['windup']+.025);a=snapshot(p)['bullets'][0];arrange(p,{'enemy':{'x':CX+115,'y':CY+65}});step(p,.1);b=snapshot(p)['bullets'][0];check('FireBlast travels forward without homing',b['x']>a['x'] and b['ux']==a['ux'] and b['uy']==a['uy']);arrange(p,{'enemy':{'x':CX+115,'y':CY}});step(p,.7);s=snapshot(p);check('FireBlast consumed on actual opponent contact',s['hits']==1 and not any(b['move']=='fireblast' for b in s['bullets']),s['hits'])
  # Source collision blocks real generated projectiles, not a separate preview collision.
  block=None
  for y in range(2,t['rows']-2):
   for x in range(2,cols-2):
    i=y*cols+x
    if not walk[i] and walk[i-1] and walk[i-2] and walk[i+1]:block=(x,y);break
   if block:break
  assert block;bx,by=block;arr={'ai':False,'player':{'x':(bx-1.5)*cell,'y':(by+.5)*cell},'enemy':{'x':(bx+1.5)*cell,'y':(by+.5)*cell}}
  for mid in ['watergun','solarbeam','fireblast']:
   reset(p,mid);arrange(p,arr);hp=snapshot(p)['enemy']['hp'];p.evaluate('(v)=>window.__waterTest.cast("player",v)',mid);step(p,2);s=snapshot(p);check(mid+' wall consumes generated shot without damage',s['enemy']['hp']==hp and not s['bullets'])
  lane=next(i for i in range(cols*2,len(walk)-cols*2) if i%cols>5 and i%cols<cols-5 and all(walk[i+dy*cols+dx] for dy in [-1,0,1] for dx in range(-4,5)));ax,ay=(lane%cols+.5)*cell,(lane//cols+.5)*cell
  reset(p,'agility');arrange(p,{'ai':False,'player':{'x':ax,'y':ay},'enemy':{'x':ax+95,'y':ay}});p.evaluate('window.__waterTest.cast("player","agility")');step(p,.28);s=snapshot(p);check('Agility is actual fast swept displacement in clear lane',math.hypot(s['player']['x']-ax,s['player']['y']-ay)>140,s['player']['x']-ax)
  reset(p,'surf');p.evaluate('window.__waterTest.cast("player","surf")');step(p,.65);s=snapshot(p);check('Surf moves rider with wave',s['player']['x']>CX+25 and any(e['mode']=='ride' for e in s['generated']['states']))
  reset(p,'stoneedge');p.evaluate('window.__waterTest.cast("player","stoneedge")');step(p,.55);p.keyboard.press('Escape');before=snapshot(p);step(p,.5);after=snapshot(p);check('Pause freezes generated effects',before['generated']['states']==after['generated']['states']);p.keyboard.press('Escape');p.evaluate('window.__waterTest.reset(true)');s=snapshot(p);check('Reset clears all effects and bullets',s['generated']['active']==0 and not s['bullets'])
  reset(p,'stoneedge');p.evaluate('window.__waterTest.cast("player","stoneedge")');step(p,.55);p.evaluate('(v)=>window.__waterTest.select(v)',{**default,'map':'emerald-mauvillecity'});s=snapshot(p);check('Map change clears old effects',s['generated']['active']==0 and not s['bullets'] and s['environment']['terrain']['grassTriggered']==0)
  p.evaluate('window.__waterTest.reset(true)');step(p,12);check('AI still closes distance and casts after range changes',snapshot(p)['ai']['casts']>0,snapshot(p)['ai'])
  for path in ['/生图招式.js','/招式特效/实战绘制.json','/招式特效/生图重做/首批/水枪/result.png']:
   check('HTTP private source denied '+path,p.request.get(URL+path).status==404)
  offline=browser.new_page();offline.on('pageerror',lambda e:errors.append(str(e)));offline.goto((ROOT/'候选试玩.html').as_uri()+'?test=1');ready(offline);check('Offline all104 atlases loaded',snapshot(offline)['generated']['loaded']==104);check('No browser errors / external requests',not errors and not external,{'errors':errors,'external':external});browser.close()
finally:
 report={'candidateSHA256':hashlib.sha256((ROOT/'候选试玩.html').read_bytes()).hexdigest(),'passed':sum(x['ok'] for x in checks),'checks':checks,'coverage':coverage,'errors':errors,'external':external,'notProven':['Not human approval, anatomy in all directions, learned moves legality, jump/high collision, new balance formulas or all57 art revisions.','Test equip deliberately bypasses learnset for renderer coverage.']};(OUT/'浏览器验收.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':report['passed'],'errors':errors,'coverage':len(coverage)},ensure_ascii=False))
