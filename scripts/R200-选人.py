"""Real desktop keyboard, standard-gamepad API, and touch selection to slot 200."""
import hashlib
import json
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'验收记录/R200'
ids=json.loads((ROOT/'首发200.json').read_text())['ids']
errors=[];records=[]
URL=os.environ['POIGHT_TEST_URL'].rstrip('/')

def poll(p,expr):
    for _ in range(600):
        if p.evaluate(expr):return
        p.wait_for_timeout(30)
    raise TimeoutError(expr)

with sync_playwright() as pw:
    b=pw.chromium.launch(headless=True)
    for width,height in [(1440,900),(844,390),(667,375)]:
        context=b.new_context(viewport={'width':width,'height':height},has_touch=width!=1440)
        p=context.new_page();p.on('pageerror',lambda e:errors.append(str(e)))
        p.add_init_script('''window.r200Pad={connected:true,axes:[0,0],buttons:Array.from({length:16},()=>({pressed:false,value:0}))};
          Object.defineProperty(navigator,'getGamepads',{value:()=>[window.r200Pad]});''')
        response=p.goto(URL+'/?observe=1')
        candidate_sha=hashlib.sha256(response.body()).hexdigest()
        assert candidate_sha==hashlib.sha256((ROOT/'候选试玩.html').read_bytes()).hexdigest()
        poll(p,'()=>document.querySelectorAll(".mon").length===200 && [...document.querySelectorAll("#playerPortrait,#enemyPortrait")].every(e=>e.dataset.frame)')
        order=p.locator('.mon').evaluate_all('(a)=>a.map(e=>Number(e.dataset.id))');assert order==ids
        p.screenshot(path=str(OUT/f'选人-{width}x{height}.png'))
        if width==1440:
            p.evaluate('()=>{window.r200Random=Math.random;Math.random=()=>.999999999;}')
            p.locator('#randomEnemy').click()
            assert p.locator('.mon').last.get_attribute('data-enemy')=='true'
            p.evaluate('()=>{Math.random=window.r200Random;delete window.r200Random;}')
            records.append({'input':'CPU random upper boundary','selected':ids[-1]})
            p.locator('.mon').first.focus()
            for _ in range(20):p.keyboard.press('ArrowDown')
            for _ in range(9):p.keyboard.press('ArrowRight')
            p.keyboard.press('Enter')
            assert p.locator('.mon').last.get_attribute('aria-pressed')=='true'
            records.append({'input':'keyboard','selected':ids[-1]})
            # Reset through actual pointer selection, then hold gamepad down/right.
            p.locator('.mon').first.click()
            p.evaluate('()=>window.r200Pad.buttons[13].pressed=true')
            p.wait_for_timeout(3100)
            p.evaluate('()=>{window.r200Pad.buttons[13].pressed=false;window.r200Pad.buttons[15].pressed=true;}')
            p.wait_for_timeout(1800)
            p.evaluate('()=>{window.r200Pad.buttons[15].pressed=false;window.r200Pad.buttons[0].pressed=true;}')
            p.wait_for_timeout(100)
            p.evaluate('()=>window.r200Pad.buttons[0].pressed=false')
            assert p.locator('.mon').last.get_attribute('aria-pressed')=='true'
            records.append({'input':'gamepad API (synthetic standard pad)','selected':ids[-1]})
        else:
            # Dispatch touch drags (no programmatic scrollTop), then actual tap.
            session=context.new_cdp_session(p)
            rect=p.locator('#roster').bounding_box();x=rect['x']+rect['width']/2
            for _ in range(35):
                bottom=rect['y']+rect['height']-10;top=rect['y']+10
                session.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':bottom}]})
                for j in range(1,5):
                    session.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x,'y':bottom+(top-bottom)*j/4}]})
                session.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
            p.locator('.mon').last.tap()
            assert p.locator('.mon').last.get_attribute('aria-pressed')=='true'
            records.append({'input':f'touch {width}x{height}','selected':ids[-1]})
        poll(p,'()=>document.querySelector("#playerPortrait").dataset.id===document.querySelector(".mon:last-child").dataset.id && document.querySelector("#playerPortrait").dataset.frame!==undefined')
        p.screenshot(path=str(OUT/f'选中第200-{width}x{height}.png'))
        context.close()
    b.close()
assert not errors
report={'candidateSHA256':candidate_sha,'passed':len(records),'failed':0,'jsErrors':len(errors),'records':records}
(OUT/'选人验收.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False))
