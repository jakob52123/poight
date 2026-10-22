"""Two isolated contexts, real touch input and WebSocket relay. No physics mutation."""
import json
import statistics
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
URL = (sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8899').rstrip('/')
OUT = Path('/workspace/poight-shots'); OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(args=['--disable-background-timer-throttling','--disable-renderer-backgrounding'])
    desktop_context = browser.new_context(viewport={'width':1280,'height':800})
    phone_context = browser.new_context(viewport={'width':844,'height':390},is_mobile=True,has_touch=True,
        user_agent='Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/131.0 Mobile Safari/537.36')
    desktop = desktop_context.new_page(); phone = phone_context.new_page(); errors=[]
    desktop.set_default_timeout(10000);phone.set_default_timeout(10000)
    for page in [desktop,phone]: page.on('pageerror',lambda e:errors.append(str(e)))
    desktop.goto(URL+'/?observe=1')
    desktop.locator('#setup[open]').wait_for()
    desktop.locator('#startBattle').click()
    desktop.wait_for_function("() => window.__waterTest.snapshot().phase === 'playing'",timeout=60000)
    desktop.locator('#remotePanel summary').click();desktop.locator('#remoteConnect').click()
    desktop.wait_for_function("() => document.querySelector('#remoteCode').textContent.length===6")
    link = desktop.locator('#remoteLink').get_attribute('href')
    desktop.screenshot(path=str(OUT/'task2-room.png'))
    # Proxy actual network frames, allowing deterministic cable-pull/retry testing.
    channels=[]
    def route(ws):
        server=ws.connect_to_server(); channels.append((ws,server))
    phone.route_web_socket('**/relay',route)
    phone.goto(link)
    phone.wait_for_function("() => document.querySelector('#padStatus').textContent.startsWith('已连接')")
    desktop.wait_for_function("() => document.querySelector('#remoteStatus').textContent === '手柄已连接'")
    phone.screenshot(path=str(OUT/'task2-phone.png'))
    cdp = phone_context.new_cdp_session(phone)
    box=phone.locator('#padStick').bounding_box()
    x,y=box['x']+box['width']/2,box['y']+box['height']/2
    def touch(kind, points):
        cdp.send('Input.dispatchTouchEvent',{'type':kind,'touchPoints':[{'x':a,'y':b,'id':i} for i,a,b in points]})
    start=desktop.evaluate('window.__waterTest.snapshot().player.x')
    touch('touchStart',[(1,x,y)])
    touch('touchMove',[(1,x+box['width']*.32,y)])
    desktop.wait_for_function('(x) => window.__waterTest.snapshot().player.x > x+30', arg=start)
    dash=phone.locator('[data-action="dash"]').bounding_box()
    touch('touchStart',[(1,x+box['width']*.32,y),(2,dash['x']+dash['width']/2,dash['y']+dash['height']/2)])
    desktop.wait_for_function("() => window.poightRemoteLastAction?.action === 'dash'")
    state=desktop.evaluate('window.__waterTest.snapshot()')
    assert state['player']['stamina'] < 100 and state['player']['dashCool'] > 0, state['player']
    touch('touchEnd',[])
    desktop.wait_for_function('() => window.poightInput.inputVector().x === 0')
    desktop.screenshot(path=str(OUT/'task2-moving.png'))
    # Rough action-to-desktop receive upper bound, includes Python/CDP scheduling.
    samples=[]
    print('join/touch/dash PASS', flush=True)
    for _ in range(8):
        previous=desktop.evaluate('window.poightRemoteLastAction?.seq || 0')
        t=time.perf_counter()
        phone.locator('[data-action="start"]').tap()
        desktop.wait_for_function("(n) => window.poightRemoteLastAction?.action === 'start' && window.poightRemoteLastAction.seq > n",arg=previous,polling=5)
        samples.append((time.perf_counter()-t)*1000)
    print('latency samples',samples,flush=True)
    # Disconnect while movement is held, not after an already-neutral release.
    touch('touchStart',[(1,x,y)])
    touch('touchMove',[(1,x-box['width']*.34,y)])
    desktop.wait_for_function('() => window.poightInput.inputVector().x < -.9')
    channels[-1][1].close();channels[-1][0].close()
    desktop.wait_for_function("() => document.querySelector('#remoteStatus').textContent === '手柄已断开'",timeout=5000)
    print('disconnect PASS',flush=True)
    assert desktop.evaluate('window.poightInput.inputVector().x') == 0
    touch('touchEnd',[])
    desktop.screenshot(path=str(OUT/'task2-disconnected.png'),timeout=5000)
    phone.wait_for_function("() => document.querySelector('#padStatus').textContent.startsWith('已连接')",timeout=15000)
    desktop.wait_for_function("() => document.querySelector('#remoteStatus').textContent === '手柄已连接'")
    phone.locator('[data-action="jump"]').tap()
    desktop.wait_for_function("() => window.poightRemoteLastAction?.action === 'jump'")
    desktop.wait_for_function("() => window.__waterTest.snapshot().player.jumping")
    desktop.screenshot(path=str(OUT/'task2-reconnected.png'))
    assert not errors, errors
    report={'result':'PASS','movement_px':round(state['player']['x']-start,1),
        'rough_latency_ms':{'median':round(statistics.median(samples),1),'max':round(max(samples),1),'samples':samples},
        'checks':['join','touch joystick','multi-touch dash','neutral release','disconnect status','held-input disconnect neutralization','automatic backoff reconnect','jump after reconnect']}
    (OUT/'task2-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
    browser.close()
