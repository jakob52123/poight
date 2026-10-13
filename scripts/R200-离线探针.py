"""All 200 selected offline under file:// with no HTTP requests or browser errors."""
import hashlib
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'验收记录/R200'
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    p = b.new_page()
    errors=[];external=[]
    p.on('pageerror',lambda e:errors.append(str(e)))
    p.on('request',lambda r:external.append(r.url) if r.url.startswith(('http:','https:')) else None)
    p.goto((ROOT/'候选试玩.html').as_uri()+'?test=1&lazy=1')
    for _ in range(600):
        if p.evaluate('()=>window.__waterTest?.snapshot().artReady'):break
        p.wait_for_timeout(50)
    else:raise TimeoutError('file:// artReady')
    result=p.evaluate('''async()=>{
      const t=__waterTest,roster=t.catalog().roster,other=roster.find(c=>c.id===7),rows=[];
      for(const c of roster){
        const loaded=await t.select({player:c.id,enemy:7,playerMoves:c.defaultMoves,
          enemyMoves:other.defaultMoves,tier:'great',map:'arena-formal'});
        t.arrange({ai:false});t.step(.05);
        rows.push({id:c.id,loaded,ready:t.snapshot().artReady,correct:t.snapshot().player.id===c.id});
      }
      return rows;
    }''')
    report=dict(candidateSHA256=hashlib.sha256((ROOT/'候选试玩.html').read_bytes()).hexdigest(),
                tested=len(result),passed=sum(r['loaded'] and r['ready'] and r['correct'] for r in result),
                jsErrors=len(errors),errors=errors,externalRequests=external)
    (OUT/'离线.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))
    b.close()
    assert report['passed']==len(json.loads((ROOT/'首发200.json').read_text())['ids']) and not errors and not external
