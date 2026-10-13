"""200 Chromium randomized rounds plus one real WebKit round; no forced track or mocked RNG.
Each fighter is player once, every round verifies real media time progression (or
original AudioContext output), then terminates through the real victory update.
Full 20-second combat / four emitted moves are independently covered by R200 smoke.
"""
import collections
import hashlib
import json
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'验收记录/M10/第二段'
ids=json.loads((ROOT/'首发200.json').read_text())['ids']
errors=[];records=[]
def wait(p,fn,seconds=8):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  v=p.evaluate(fn)
  if v:return v
  p.wait_for_timeout(25)
 raise TimeoutError(fn)
with sync_playwright() as pw:
 for engine in ['chromium','webkit']:
  b=getattr(pw,engine).launch(headless=True)
  p=b.new_page(viewport={'width':1280,'height':800})
  p.on('pageerror',lambda e:errors.append(str(e)))
  response=p.goto(os.environ['POIGHT_TEST_URL'].rstrip('/')+'/?test=1&lazy=1&music=random')
  sha=hashlib.sha256(response.body()).hexdigest()
  wait(p,'()=>__waterTest?.snapshot().artReady',30)
  for i,ident in enumerate(ids if engine=='chromium' else ids[:1]):
   p.evaluate('''async ([id,enemy])=>{const t=__waterTest,roster=t.catalog().roster;await t.select({player:id,enemy,tier:'great',map:'arena-formal',playerMoves:roster.find(c=>c.id===id).defaultMoves,enemyMoves:roster.find(c=>c.id===enemy).defaultMoves});t.arrange({ai:false});}''',[ident,ids[(i+1)%len(ids)]])
   p.keyboard.press('ArrowRight')
   state=wait(p,'()=>{const m=__waterTest.snapshot().music;return (m.bgm==="orig" ? m.audible>0 : m.media?.running) && m;}')
   if state['bgm']=='orig':
    start=state['audioTime']
    wait(p,f'()=>{{const m=__waterTest.snapshot().music;return m.audible>0 && m.audioTime>{start+.08};}}')
   else:
    start=state['media']['currentTime']
    wait(p,f'()=>__waterTest.snapshot().music.media?.currentTime>{start+.08}')
   final=p.evaluate('()=>__waterTest.snapshot().music')
   records.append(dict(browser=engine,fighter=ident,bgm=state['bgm'],playing=True,start=start,end=final.get('media',{}).get('currentTime') if state['bgm']!='orig' else final['audioTime']))
   p.evaluate('()=>{__waterTest.arrange({enemy:{hp:0}});__waterTest.step(.02);}')
   if (i+1)%20==0:print(engine,'played',i+1,flush=True)
  b.close()
counts={e:dict(collections.Counter(r['bgm'] for r in records if r['browser']==e)) for e in ['chromium','webkit']}
repeats={e:sum(a['bgm']==b['bgm'] for a,b in zip([r for r in records if r['browser']==e],[r for r in records if r['browser']==e][1:])) for e in counts}
passed=sum(r['playing'] for r in records)
report=dict(candidateSHA256=sha,passed=passed,failed=201-passed,jsErrors=len(errors),errors=errors,counts=counts,repeats=repeats,records=records)
(OUT/'200局随机音乐.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='records'},ensure_ascii=False))
assert len(records)==201 and len(counts['chromium'])==9 and sum(counts['webkit'].values())==1 and not errors and not any(repeats.values())
