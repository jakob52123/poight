from pathlib import Path
from playwright.sync_api import sync_playwright
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import quote
import json,hashlib,gzip,time
ROOT=Path(__file__).resolve().parent;BASE='http://localhost:8792/';checks=[];details={}
def check(name,ok,data=None):
    checks.append({'name':name,'passed':bool(ok),'details':data})
    if not ok:raise AssertionError(name+': '+repr(data))
def wait(page,expr,timeout=10):
    # Playwright旧版wait_for_function在后续轮询里eval字符串，会被正式CSP拦住。
    # 在测试侧用CDP逐次读取表达式，不放宽游戏的unsafe-eval策略。
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if page.evaluate('()=>('+expr+')'):return
        page.wait_for_timeout(35)
    raise TimeoutError(expr)
def save():(ROOT/'健壮性验收.json').write_text(json.dumps({'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks,'details':details,'candidateSHA256':hashlib.sha256((ROOT/'候选试玩.html').read_bytes()).hexdigest()},ensure_ascii=False,indent=2)+'\n')
try:
    request=Request(BASE,headers={'Accept-Encoding':'gzip'})
    with urlopen(request) as r:body=r.read();headers=dict(r.headers)
    decoded=gzip.decompress(body);expected=hashlib.sha256((ROOT/'候选试玩.html').read_bytes()).hexdigest()
    check('HTTP压缩后的页面解码SHA与构建一致',hashlib.sha256(decoded).hexdigest()==expected)
    check('HTTP确实gzip而不是空口压缩',headers.get('Content-Encoding')=='gzip' and len(body)<len(decoded)*.3,{'compressed':len(body),'original':len(decoded)})
    check('页面带不外联/不嵌框/无写保护头',"connect-src 'none'" in headers.get('Content-Security-Policy','') and headers.get('X-Frame-Options')=='DENY' and headers.get('X-Content-Type-Options')=='nosniff')
    for path in ['素材/','素材/用户绿宝石包/压缩包检查.json','说明.md','对战.js','发布清单.json','../AGENTS.md','%2e%2e/AGENTS.md','assets/../index.html','assets/','assets/%2e%2e/说明.md']:
        try:
            with urlopen(BASE+quote(path,safe='/%')) as r:status=r.status
        except HTTPError as e:status=e.code
        check('不暴露源码/目录/穿越：'+path,status==404,status)
    try:
        with urlopen(Request(BASE,data=b'{}',headers={'Content-Type':'application/json'},method='POST')) as r:status=r.status
    except HTTPError as e:status=e.code
    check('没有写接口',status==405)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        for asset in ['0007-Idle-','ground-']:
            context=browser.new_context(viewport={'width':1280,'height':800});page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            pattern='**/assets/'+asset+'*.png';page.route(pattern,lambda route:route.abort())
            page.goto(BASE+'?test=1',wait_until='load');wait(page,'document.querySelector("#setup").open&&document.querySelector("#setupMessage").classList.contains("error")')
            check('缺素材可见报错：'+asset,'assets' in page.locator('#setupMessage').inner_text() and not page.locator('#startBattle').is_disabled())
            page.unroute(pattern);page.locator('#startBattle').click();wait(page,'__waterTest.snapshot().phase==="playing"&&__waterTest.snapshot().artReady')
            check('恢复文件后可重试：'+asset,not errors,errors);context.close()
        context=browser.new_context(viewport={'width':1280,'height':800});page=context.new_page()
        page.add_init_script('''(()=>{const d=Object.getOwnPropertyDescriptor(HTMLImageElement.prototype,'src');Object.defineProperty(HTMLImageElement.prototype,'src',{...d,set(v){if(String(v).includes('/0025-'))setTimeout(()=>d.set.call(this,v),500);else d.set.call(this,v)}})})();''')
        page.goto(BASE+'?observe=1',wait_until='load');wait(page,'document.querySelector("#setup").open');page.locator('#startBattle').click();page.locator('#setupButton').click();page.locator('#search').fill('皮卡丘');page.locator('.mon').click();page.locator('#startBattle').click();page.locator('#closeSetup').click();page.wait_for_timeout(750)
        s=page.evaluate('__waterTest.snapshot()');check('取消迟到加载不覆盖当前角色/战局',s['player']['id']==7 and s['profile']['player']==7 and s['phase']=='paused',{'id':s['player']['id'],'phase':s['phase']});context.close()
        context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page();requests=[];page.on('request',lambda r:requests.append(r.url));page.goto(BASE+'?observe=1',wait_until='load');wait(page,'document.querySelector("#setup").open');page.wait_for_timeout(250)
        before=len(requests);payload=page.evaluate('()=>[...performance.getEntriesByType("navigation"),...performance.getEntriesByType("resource")].reduce((s,e)=>s+(e.encodedBodySize||0),0)');page.locator('#startBattle').click();page.keyboard.down('s');page.wait_for_timeout(3000);page.keyboard.up('s');after=len(requests)
        details['initialLoad']={'requests':before,'wireBodyBytes':payload,'requestsAfter3SecCombat':after};check('启动只请求当前两只动作，不载入全图鉴动画',before<=18,details['initialLoad']);check('战斗不追加任何模型/网络请求',before==after,details['initialLoad']);context.close();browser.close()
    save();print(json.dumps({'passed':len(checks),'details':details},ensure_ascii=False,indent=2))
except Exception:save();raise
