from pathlib import Path
from playwright.sync_api import sync_playwright
import json,time,argparse
ROOT=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--headed',action='store_true');ap.add_argument('--url',default='http://localhost:8792/');a=ap.parse_args();result={'mode':'headed' if a.headed else 'headless','runs':[]}
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=not a.headed,args=['--window-position=-2800,-1800'] if a.headed else [])
    info=browser.new_browser_cdp_session().send('SystemInfo.getInfo');result['gpu']={k:info['gpu'].get(k) for k in ['devices','featureStatus']};result['renderer']=info['gpu'].get('auxAttributes',{}).get('glRenderer')
    page=browser.new_page(viewport={'width':1440,'height':900})
    for mode in ['blank','canvasBaseline','gameMenu','game']:
        if mode=='blank':page.goto('about:blank');page.set_content('<html><body style="background:#73cda4"></body></html>')
        elif mode=='canvasBaseline':page.set_content('<canvas id="c" width="960" height="600" style="width:100vw;height:100vh"></canvas><script>let c=document.querySelector("canvas").getContext("2d");function f(){c.fillStyle="#73cda4";c.fillRect(0,0,960,600);requestAnimationFrame(f)}f();</script>')
        elif mode=='gameMenu':page.goto(a.url+'?observe=1',wait_until='load');page.wait_for_function('document.querySelector("#setup").open')
        elif mode=='game':page.locator('#startBattle').click();page.keyboard.down('s')
        page.wait_for_timeout(250)
        measurement=page.evaluate('''()=>new Promise(resolve=>{const start=performance.now();let last=start,frames=0,times=[];function tick(t){frames++;times.push(t-last);last=t;if(t-start>=3000){times.sort((a,b)=>a-b);resolve({wallMs:t-start,frames,fps:frames*1000/(t-start),frameP95Ms:times[Math.floor(times.length*.95)],visibility:document.visibilityState,focus:document.hasFocus(),game:window.__waterTest?.snapshot().timing});}else requestAnimationFrame(tick)}requestAnimationFrame(tick)})''')
        result['runs'].append({'name':mode,**measurement})
    page.keyboard.up('s');browser.close()
(ROOT/('性能复验-'+result['mode']+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
