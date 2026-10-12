from pathlib import Path
import base64,json,time,hashlib,os
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'验收记录/绿宝石草丛';OUT.mkdir(exist_ok=True)
URL=os.environ.get('POIGHT_TEST_URL','http://localhost:8792/');checks=[];errors=[]
def check(n,v,d=None):checks.append({'name':n,'ok':bool(v),'detail':d});assert v,(n,d)
def info(p):return p.evaluate('window.__waterTest.snapshot()')
def terrain(p):return info(p)['environment']['terrain']
def arrange(p,v):p.evaluate('(x)=>window.__waterTest.arrange(x)',v)
def step(p,s):p.evaluate('(x)=>window.__waterTest.step(x)',s)
try:
 data=json.loads((ROOT/'素材/绿宝石场景/场景目录.json').read_text());t=data['terrains'][0];s=t['cellSize'];cols=t['columns'];walk=base64.b64decode(t['walkB64']);beh=base64.b64decode(t['behaviorB64']);area=next(a for a in t['areas'] if a['sourceName']=='Route101');pair=None
 for y in range(area['gridY']+1,area['gridY']+area['rows']-1):
  for x in range(area['gridX']+1,area['gridX']+area['columns']-1):
   i=y*cols+x
   if beh[i]==2 and walk[i] and walk[i-1] and beh[i-1]!=2:pair=(x,y);break
  if pair:break
 assert pair,'grass edge missing'
 x,y=pair;start={'x':(x-.5)*s,'y':(y+.5)*s};check('Native5-frame TallGrass sequence',t['fieldEffects']['tall']['frames']==5 and [x['frame'] for x in t['fieldEffects']['tall']['sequence']]==[1,2,3,4,0]);check('Source palette/hash receipts',len(json.loads((ROOT/'素材/绿宝石场景/丰缘西南/草丛来源.json').read_text())['files'])==5)
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True);p=b.new_page(viewport={'width':1440,'height':900});p.on('pageerror',lambda e:errors.append(str(e)));p.goto(URL+'?test=1')
  for _ in range(200):
   if p.evaluate('window.__waterTest?.snapshot().artReady'):break
   time.sleep(.05)
  p.evaluate('(v)=>window.__waterTest.select(v)',{**info(p)['profile'],'map':'emerald-littleroottown'})
  p.evaluate('window.__waterTest.reset(true)');arrange(p,{'ai':False,'player':start});step(p,.8);check('No false effect on ordinary green ground',terrain(p)['grassTriggered']==0)
  p.keyboard.down('d');step(p,.2);p.keyboard.up('d');a=terrain(p);check('Walking into grass triggers native effect',a['grassTriggered']>0 and a['grassActive']>0,a);p.screenshot(path=str(OUT/'草叶-进入.png'))
  step(p,.18);bstate=terrain(p);check('Native animation advances',a['grassFrames'][0]['frame']!=bstate['grassFrames'][0]['frame']);p.screenshot(path=str(OUT/'草叶-晃动.png'))
  before=bstate['grassTriggered'];step(p,1);state=terrain(p);check('Standing settles, does not repeatedly emit',state['grassTriggered']==before and all(x['frame']==0 for x in state['grassFrames']));p.screenshot(path=str(OUT/'草叶-站立遮脚.png'))
  # Pause freezes time; leaving expires the effect, reset clears all fields.
  p.keyboard.press('Escape');age=terrain(p)['grassFrames'][0]['age'];step(p,.5);check('Pause freezes grass',terrain(p)['grassFrames'][0]['age']==age);p.keyboard.press('Escape')
  p.keyboard.down('a');step(p,.3);p.keyboard.up('a');step(p,1);check('Leaving expires settled grass',terrain(p)['grassActive']==0)
  p.evaluate('window.__waterTest.reset(true)');arrange(p,{'ai':False,'player':start});p.evaluate("window.__waterTest.dash('player',1,0)");step(p,.17);check('Dash also rustles traversed grass',terrain(p)['grassTriggered']>0)
  p.evaluate('window.__waterTest.reset(true)');check('Reset clears grass',terrain(p)['grassTriggered']==0 and terrain(p)['grassActive']==0)
  profile=info(p)['profile'];roster=p.evaluate('window.__waterTest.catalog().roster');char=next(c for c in roster if c['id']==6);p.evaluate('(v)=>window.__waterTest.select(v)',{**profile,'player':6,'playerMoves':char['defaultMoves']});p.evaluate('window.__waterTest.reset(true)');arrange(p,{'ai':False,'player':start});p.keyboard.down('d');step(p,.3);p.keyboard.up('d');check('Flying Charizard does not stomp grass',terrain(p)['grassTriggered']==0)
  check('No browser errors',not errors,errors);b.close()
finally:
 report={'candidateSHA256':hashlib.sha256((ROOT/'候选试玩.html').read_bytes()).hexdigest(),'passed':sum(x['ok'] for x in checks),'checks':checks,'errors':errors,'scope':'Original palette/frames, player walk/dash, standing/leave/pause/reset/airborne. No wild encounter or generated effects.'};(OUT/'验收.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
