"""200 fighters: 100 live-engine 20s AI matches + every default slot actually emitted.
No coarse physics ticks; simulation uses production 120Hz. Test-only HP x100
prevents early KOs so every fighter receives the entire 20-second exercise.
"""
import hashlib
import json
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'验收记录/R200'
OUT.mkdir(parents=True,exist_ok=True)
ids=json.loads((ROOT/'首发200.json').read_text())['ids']
checks,errors,games,casts=[],[],[],[]
started=time.monotonic()
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1280,'height':800})
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('response',lambda r: errors.append(f'HTTP {r.status} {r.url}') if r.status>=400 else None)
    response=page.goto(os.environ['POIGHT_TEST_URL'].rstrip('/')+'/?test=1&lazy=1')
    sha=hashlib.sha256(response.body()).hexdigest()
    for _ in range(600):
        if page.evaluate('()=>__waterTest?.snapshot().artReady'):break
        page.wait_for_timeout(50)
    else:raise TimeoutError('artReady')
    for index in range(0,len(ids),2):
        record=page.evaluate('''async ([a,b,index])=>{
          const t=__waterTest,cat=t.catalog(),lookup=new Map(cat.roster.map(c=>[c.id,c]));
          const loaded=await t.select({player:a,enemy:b,playerMoves:lookup.get(a).defaultMoves,
            enemyMoves:lookup.get(b).defaultMoves,tier:'great',map:'arena-formal'});
          const spawn=t.snapshot(),free=p=>t.freeAt(p.x,p.y,p.body.moveRadius,p.onBridge);
          const spawnFree=free(spawn.player)&&free(spawn.enemy),casts=[];
          for(const [side,id] of [['player',a],['enemy',b]]){
            for(const mid of lookup.get(id).defaultMoves){
              t.reset(true);t.arrange({ai:false,player:{x:700,y:700,a:0,hp:50},enemy:{x:770,y:700,a:Math.PI,hp:50}});
              const before=t.snapshot()[side],m=cat.moves[mid],accepted=t.cast(side,mid);
              let emitted=false;
              for(let i=0;i<480;i++){
                t.step(1/120,false);const p=t.snapshot()[side];
                emitted ||= !!p.attack?.emitted || p.shield>before.shield ||
                  p.splashes>before.splashes || p.shots>before.shots || p.punches>before.punches ||
                  p.hp>before.hp || Object.keys(p.buffs).some(k=>p.buffs[k]>before.buffs[k]);
              }
              t.step(0,true);
              casts.push({id,side,move:mid,accepted,emitted});
            }
          }
          const ai=t.simulate({seed:20000+index,tier:'great',playerTier:'great',maxSeconds:20,hpMultiplier:100});
          const end=t.snapshot();
          return {loaded,spawnFree,casts,ai,endFree:free(end.player)&&free(end.enemy),
            enemyDecisions:end.ai.decisions,playerDecisions:end.balance.playerDecisions};
        }''',[ids[index],ids[index+1],index])
        games.append({k:v for k,v in record.items() if k!='casts'})
        casts.extend(record['casts'])
        checks.append(record['loaded'] and record['spawnFree'] and record['endFree'] and record['ai']['ticks']==2400 and record['playerDecisions']>0 and record['enemyDecisions']>0)
        if (index+2)%20==0: print('smoked',index+2,'/',len(ids),flush=True)
    report=dict(candidateSHA256=sha,tested=len(ids),games=len(games),secondsPerMatch=20,
                passed=sum(checks)*2,failed=(len(checks)-sum(checks))*2,
                defaultCasts=len(casts),emitted=sum(c['accepted'] and c['emitted'] for c in casts),
                castFailures=[c for c in casts if not(c['accepted'] and c['emitted'])],
                jsErrors=len(errors),errors=errors,records=games,casts=casts,
                wallSeconds=round(time.monotonic()-started,2))
    (OUT/'冒烟.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['records','casts']},ensure_ascii=False))
    browser.close()
    assert report['failed']==0 and not errors and not report['castFailures']
