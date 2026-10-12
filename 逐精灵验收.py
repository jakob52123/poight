"""每一只在浏览器里实际切入、移动、攻击；六类动作读回像素，非只看文件数。"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,time,hashlib,argparse
ROOT=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--url',default='http://localhost:8792/');ap.add_argument('--tag',default='候选');a=ap.parse_args()
rows=[];errors=[];start=time.monotonic();tested_sha=None

def save():
    out={'url':a.url,'testedHTMLSHA256':tested_sha,'tested':len(rows),'passed':sum(r.get('passed',False) for r in rows),'rows':rows,'errors':errors,'seconds':round(time.monotonic()-start,2),'scope':'全部角色真实加载后走路/攻击；每种动作抽首中末帧和南北行浏览器绘制读回像素。全帧边界和SHA另外由构建器逐帧核验。'}
    (ROOT/f'逐精灵验收-{a.tag}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')

with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='chrome',headless=True);context=browser.new_context(viewport={'width':1280,'height':800});page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    try:
        resp=page.goto(a.url+'?test=1',wait_until='load');tested_sha=hashlib.sha256(resp.body()).hexdigest();page.wait_for_function('__waterTest.snapshot().artReady',timeout=30000)
        roster=page.evaluate('()=>__waterTest.catalog().roster');assert len(roster)==json.loads((ROOT/'构建核验-完整版.json').read_text())['roster']
        for c in roster:
            result=page.evaluate('''async c=>{const t=__waterTest,r=t.catalog().roster.find(r=>r.id===7);const loaded=await t.select({player:c.id,enemy:7,playerMoves:c.defaultMoves,enemyMoves:r.defaultMoves,tier:'great'});t.arrange({ai:false,player:{x:215,y:280},enemy:{x:280,y:280}});const pixels=t.assetProbe();dispatchEvent(new KeyboardEvent('keydown',{code:'KeyS',bubbles:true}));t.step(.16);dispatchEvent(new KeyboardEvent('keyup',{code:'KeyS',bubbles:true}));const moved=t.snapshot().player.y>300;const walking=t.snapshot().player.anim==='walk';t.arrange({player:{x:215,y:280},enemy:{x:280,y:280}});const id=c.defaultMoves[0],m=t.catalog().moves[id],cast=t.cast('player',id);t.step(m.windup+(m.delay||0)+.3);const s=t.snapshot();return {id:c.id,name:c.name,loaded,moved,walking,cast,damage:100-s.enemy.hp,pixelSamples:pixels.length,allSamplesVisible:pixels.every(p=>p.visible>0&&p.sizeOK),cachedCharacters:s.cachedCharacters.length,correctSpecies:s.player.id===c.id};}''',c)
            result['passed']=all([result[k] for k in ['loaded','moved','walking','cast','allSamplesVisible','correctSpecies']]) and result['damage']>0 and result['cachedCharacters']<=6
            rows.append(result)
            if not result['passed']:raise AssertionError(result)
            if len(rows)%100==0:save();print('verified',len(rows),'/',len(roster),flush=True)
        assert len(rows)==len(roster) and not errors
        save();print(json.dumps({'tested':len(rows),'passed':sum(x['passed'] for x in rows),'seconds':round(time.monotonic()-start,2),'errors':errors},ensure_ascii=False))
    except Exception:
        save();page.screenshot(path=str(ROOT/f'逐精灵-失败-{a.tag}.png'));raise
    finally:browser.close()
