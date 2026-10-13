"""All authorized species: actual load/move/cast and six-role browser pixel probes."""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument('--url', default=os.environ.get('POIGHT_TEST_URL', 'http://localhost:8988/'))
ap.add_argument('--tag', default='R200')
a = ap.parse_args()
OUT = ROOT / '验收记录/R200'
OUT.mkdir(parents=True, exist_ok=True)
rows, errors = [], []
start = time.monotonic()
tested_sha = None


def save():
    report = dict(testedHTMLSHA256=tested_sha, tested=len(rows), passed=sum(r['passed'] for r in rows),
                  failed=sum(not r['passed'] for r in rows), jsErrors=len(errors), errors=errors,
                  rows=rows, seconds=round(time.monotonic()-start, 2))
    (OUT / f'逐精灵验收-{a.tag}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    return report


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width':1280,'height':800})
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        response = page.goto(a.url.rstrip('/')+'/?test=1&lazy=1', wait_until='load')
        tested_sha = hashlib.sha256(response.body()).hexdigest()
        for _ in range(600):
            if page.evaluate('()=>window.__waterTest?.snapshot().artReady'): break
            page.wait_for_timeout(50)
        else: raise TimeoutError('artReady')
        roster = page.evaluate('()=>__waterTest.catalog().roster')
        assert [c['id'] for c in roster] == json.loads((ROOT/'首发200.json').read_text())['ids']
        for c in roster:
            result = page.evaluate('''async c => {
              const t=__waterTest, cat=t.catalog(), other=cat.roster.find(c=>c.id===7);
              const loaded=await t.select({player:c.id,enemy:7,playerMoves:c.defaultMoves,
                enemyMoves:other.defaultMoves,tier:'great',map:'arena-formal'});
              const spawn=t.snapshot();
              const free=p=>t.freeAt(p.x,p.y,p.body.moveRadius,p.onBridge);
              const spawnFree=free(spawn.player)&&free(spawn.enemy);
              t.arrange({ai:false,player:{x:700,y:700,a:0},enemy:{x:800,y:700,a:Math.PI}});
              const pixels=t.assetProbe(), before=t.snapshot().player;
              dispatchEvent(new KeyboardEvent('keydown',{code:'KeyS',bubbles:true}));
              t.step(.3);
              dispatchEvent(new KeyboardEvent('keyup',{code:'KeyS',bubbles:true}));
              const walking=t.snapshot().player.anim==='walk', delta=t.snapshot().player.y-before.y;
              const id=c.defaultMoves[0], m=cat.moves[id];
              let damage=0,cast=false,hitDistance=null;
              // Existing contact-attached melee and muzzle offsets have different
              // reach. Keep the damage assertion, probe actual legal distances.
              for (const distance of [16,28,40,64,96,128]) {
                t.reset(true);t.arrange({ai:false,player:{x:700,y:700,a:0},enemy:{x:700+distance,y:700,a:Math.PI}});
                const hp=t.snapshot().enemy.hp;
                cast=t.cast('player',id);t.step(Math.max(2,m.windup+(m.delay||0)+1));
                damage=hp-t.snapshot().enemy.hp;
                if(damage>0 || c.id===129){hitDistance=distance;break;}
              }
              const s=t.snapshot();
              return {id:c.id,name:c.name,loaded,spawnFree,moved:delta>0,
                measuredWalk:delta/.3,expectedWalk:c.speed,walking,cast,damage,hitDistance,
                pixelSamples:pixels.length,allSamplesVisible:pixels.every(p=>p.visible>0&&p.sizeOK),
                cachedCharacters:s.cachedCharacters.length,correctSpecies:s.player.id===c.id};
            }''', c)
            result['passed'] = all(result[k] for k in ('loaded','spawnFree','moved','walking','cast','allSamplesVisible','correctSpecies')) and abs(result['measuredWalk']-result['expectedWalk']) < .1 and result['cachedCharacters'] <= 6 and (result['damage'] == 0 if c['id'] == 129 else result['damage'] > 0)
            rows.append(result)
            if len(rows)%20 == 0: save(); print('verified', len(rows), '/', len(roster), flush=True)
        report=save()
        print(json.dumps({k:report[k] for k in ('tested','passed','failed','jsErrors','seconds')}, ensure_ascii=False))
        assert report['passed']==len(roster) and not errors
    except Exception:
        save(); page.screenshot(path=str(OUT/f'逐精灵-失败-{a.tag}.png')); raise
    finally:
        browser.close()
