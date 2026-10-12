"""All121 real move outcomes on source-grid clear terrain after body changes.
Deliberate test-only equip bypass, not proof of learnset legality/competitive balance.
Old365 suite assumes deleted FireRed coordinates; it is not relabeled as this test.
"""
from pathlib import Path
import json,hashlib,base64,time,os
from playwright.sync_api import sync_playwright
from 招式特效.第1批打包 import MOVES as R1
P=Path(__file__).resolve().parent;O=P/'验收记录/体型与移速';O.mkdir(exist_ok=True)
URL=os.environ.get('POIGHT_TEST_URL','http://localhost:8792/');checks=[];errors=[];outcomes=[]
def check(n,v,d=None):checks.append({'name':n,'ok':bool(v),'detail':d});assert v,(n,d)
try:
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True);p=b.new_page(viewport={'width':1280,'height':800});p.on('pageerror',lambda e:errors.append(str(e)));p.goto(URL+'?test=1')
  deadline=time.monotonic()+45
  while not p.evaluate('window.__waterTest?.snapshot().artReady'):
   assert time.monotonic()<deadline,p.locator('#setupMessage').inner_text();time.sleep(.05)
  def snap():return p.evaluate('window.__waterTest.snapshot()')
  c=p.evaluate('window.__waterTest.catalog()');t=c['terrains'][0];w=base64.b64decode(t['walkB64']);n=t['columns'];area=next(q for q in t['areas'] if q['sourceName']=='RustboroCity');at=next((x,y) for y in range(area['gridY']+3,area['gridY']+area['rows']-3) for x in range(area['gridX']+4,area['gridX']+area['columns']-4) if all(w[(y+dy)*n+x+dx] for dy in range(-2,3) for dx in range(-4,5)));x,y=(at[0]+.5)*48,(at[1]+.5)*48
  squirtle=next(q for q in c['roster'] if q['id']==7);profile={**snap()['profile'],'player':7,'enemy':7,'map':'emerald-rustborocity','playerMoves':squirtle['defaultMoves'],'enemyMoves':squirtle['defaultMoves']};p.evaluate('(v)=>window.__waterTest.select(v)',profile)
  for mid,m in c['moves'].items():
   p.evaluate('window.__waterTest.reset(true)');p.evaluate('(v)=>window.__waterTest.arrange(v)',{'ai':False,'player':{'x':x,'y':y,'hp':60},'enemy':{'x':x+(20 if mid in R1 or mid=='absorb' else 24 if mid in ('irontail','dragonclaw') else 34),'y':y}})
   ids=[mid]+[i for i in ['watergun','brickbreak','protect','agility'] if i!=mid][:3];p.evaluate('(v)=>window.__waterTest.equip("player",v)',ids);ok=p.evaluate('(v)=>window.__waterTest.cast("player",v)',mid);s=snap();check(mid+' cast and cost',ok and s['player']['spent']==m['cost']);check(mid+' independent CD starts',abs(s['player']['cool'][mid]-m['cd'])<1e-6)
   support=m['kind'] in ['guard','heal','buff'];p.evaluate('(v)=>window.__waterTest.step(v)',m['windup']+.03 if support else max(3,m['windup']+m.get('delay',0)+.5));s=snap()
   if m['kind']=='guard':effect=s['player']['shield']==m['damage']
   elif m['kind']=='heal':effect=s['player']['hp']>60
   elif m['kind']=='buff':effect=s['player']['buffs'][m['boost']]>0
   elif m['kind']=='splash':effect=s['enemy']['hp']==s['enemy']['maxHP'] and s['player']['splashes']==1 and s['hits']==0
   else:effect=s['enemy']['hp']<s['enemy']['maxHP']
   q={'id':mid,'kind':m['kind'],'playerHP':s['player']['hp'],'enemyHP':s['enemy']['hp'],'damage':s['enemy']['maxHP']-s['enemy']['hp'],'active':s['player']['attack']};outcomes.append(q);check(mid+' actual effect',effect,q)
  fairness=[]
  for tier in c['tiers']:
   p.evaluate('(v)=>window.__waterTest.select(v)',{**profile,'tier':tier['id']});p.evaluate('window.__waterTest.reset(true)');p.evaluate('(v)=>window.__waterTest.arrange(v)',{'ai':False,'player':{'x':x,'y':y},'enemy':{'x':x+95,'y':y}});p.evaluate('window.__waterTest.cast("player","watergun")');p.evaluate('window.__waterTest.step(1)');s=snap();fairness.append([s['player']['maxHP'],s['enemy']['maxHP'],s['player']['speed'],s['enemy']['speed'],s['player']['body']['hurt'],s['enemy']['body']['hurt'],s['enemy']['hp'],s['player']['spent']])
  check('Four tiers same HP/speed/hurtshape/cost/damage',all(q==fairness[0] for q in fairness));check('No JS errors',not errors,errors);b.close()
finally:
 r={'candidateSHA256':hashlib.sha256((P/'候选试玩.html').read_bytes()).hexdigest(),'passed':sum(q['ok'] for q in checks),'checks':checks,'outcomes':outcomes,'errors':errors,'scope':'121 actual effect checks +121 cost +121 independent cooldown +tier/stat parity; not old365, legality, performance, audio or win-rate balancing'};(O/'121招机制回归.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':r['passed'],'outcomes':len(outcomes),'errors':errors},ensure_ascii=False))
