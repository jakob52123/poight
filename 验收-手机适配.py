"""MOB audit reused for MOB2. Run ONLY through tools/远程执行.sh, port 8977.
Production UI uses ?observe=1 (read-only snapshot); no test setters.
Portrait selection/VS and real rotation are captured without hiding the barrier.
Safe-area simulation replaces env() in the existing inline CSS, retaining cascade.
OS Safari/WeChat chrome and native gesture menus cannot be certified headlessly.
"""
import argparse
import json
import os
import time
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent.resolve()
OUT = ROOT / os.environ.get('POIGHT_MOB_OUT', '验收记录/MOB')
SHOTS = OUT / '截图'
URL = os.environ['POIGHT_TEST_URL'].rstrip('/')
DEVICES = ['iPhone SE', 'iPhone 13', 'iPhone 15 Pro Max', 'Pixel 7', 'Galaxy S9+', 'iPad Mini']

METRICS = r"""() => {
 const box = r => ({x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom});
 const rendered = e => {const r=e.getBoundingClientRect(); return r.width>0 && r.height>0 &&
   getComputedStyle(e).visibility !== 'hidden' && !e.closest('[hidden]');};
 const key = e => e.id ? '#'+e.id : e.className ? '.'+String(e.className).trim().replaceAll(' ','.') : e.tagName;
 const clip = e => {let r=e.getBoundingClientRect(), a={left:Math.max(0,r.left),top:Math.max(0,r.top),
   right:Math.min(innerWidth,r.right),bottom:Math.min(innerHeight,r.bottom)};
   for(let p=e.parentElement;p;p=p.parentElement){let s=getComputedStyle(p),b=p.getBoundingClientRect();
     if(/hidden|auto|scroll|clip/.test(s.overflowX)){a.left=Math.max(a.left,b.left);a.right=Math.min(a.right,b.right);}
     if(/hidden|auto|scroll|clip/.test(s.overflowY)){a.top=Math.max(a.top,b.top);a.bottom=Math.min(a.bottom,b.bottom);}}
   return {width:Math.max(0,a.right-a.left),height:Math.max(0,a.bottom-a.top)};};
 // S2 is a deliberately denser selector. Unmodified battle/loadout gates stay 12px/44px.
 const s2=document.documentElement.dataset.selection==='S2';
 const minFont=e=>s2&&e.closest('#setup')&&!e.closest('#loadoutPanel')?9:12;
 const minTarget=e=>s2&&e.closest('#typeChoices,.roster-toolbar')?23:
   s2&&innerHeight<=500&&e.matches('.fighter-panel')?32:44;
 const els=[...document.querySelectorAll('button,input,a,summary')].filter(rendered);
 const targets=els.map(e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e),c=clip(e),
   hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
   return {selector:key(e),id:e.dataset.id,text:e.textContent.trim().slice(0,70),...box(r),
     font:parseFloat(s.fontSize),disabled:!!e.disabled,clipped:c.width<r.width-1||c.height<r.height-1,
     visibleWidth:c.width,visibleHeight:c.height,centerHit:!!hit&&(e===hit||e.contains(hit)),
     hit:hit&&key(hit),minTarget:minTarget(e),small:r.width<minTarget(e)||r.height<minTarget(e)};});
 const texts=[...document.querySelectorAll('b,strong,small,span,p,h2,h3,button,a,summary')]
   .filter(e=>rendered(e)&&e.childElementCount===0&&e.textContent.trim()&&clip(e).height>0)
   .map(e=>({selector:key(e),text:e.textContent.trim().slice(0,60),font:parseFloat(getComputedStyle(e).fontSize),minFont:minFont(e)}))
   .filter(e=>e.font<e.minFont);
 const pseudoTexts=[...document.querySelectorAll('#roster .mon')]
   .filter(e=>rendered(e)&&clip(e).height>0).flatMap(e=>['::before','::after'].map(p=>{
     const s=getComputedStyle(e,p);return {selector:key(e)+p,text:s.content,font:parseFloat(s.fontSize),minFont:minFont(e)};
   }).filter(t=>!['none','normal','""'].includes(t.text)&&t.font<t.minFont));
 const boxes={}; for(const sel of ['#setup','#roster','#startBattle','#loadoutPanel','#game','#mobileJoystick',
   '#mobileActions','#jumpButton','#dashButton','#battleRail','#battleMenuButton','#battleMenu','#helpPanel',
   '#matchOverlay','#rotatePhone','#gbaShort','#vsScreen','.setup-body','.fighter-player','.fighter-enemy','.hud',
   '#moveCatalog','#moveSlots','.loadout-nav','.selected-mon']){
   let e=document.querySelector(sel);if(e&&rendered(e))boxes[sel]=box(e.getBoundingClientRect());}
 // GBA uses fixed-position children and zero-sized legacy wrapper boxes.
 // Measure the same real controls, not a nonexistent wrapper rectangle.
 if(document.documentElement.dataset.gba){
  for(const [key,selector] of [['.hud','.skill'],['#mobileActions','#jumpButton,#dashButton,#diveButton']]){
   const parts=[...document.querySelectorAll(selector)].filter(rendered).map(e=>box(e.getBoundingClientRect()));
   if(parts.length){const x=Math.min(...parts.map(r=>r.x)),y=Math.min(...parts.map(r=>r.y)),
    right=Math.max(...parts.map(r=>r.right)),bottom=Math.max(...parts.map(r=>r.bottom));
    boxes[key]={x,y,right,bottom,width:right-x,height:bottom-y,parts};}
  }
 }
 const skills=[...document.querySelectorAll('.skill')].filter(rendered).map(e=>box(e.getBoundingClientRect()));
 const scroll={};for(const sel of ['#setup','.setup-body','#roster','#loadoutPanel','#battleMenu','#helpPanel']){
  const e=document.querySelector(sel);if(e)scroll[sel]={clientWidth:e.clientWidth,scrollWidth:e.scrollWidth,
    clientHeight:e.clientHeight,scrollHeight:e.scrollHeight,scrollTop:e.scrollTop};}
 return {viewport:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio,
   visual:visualViewport&&{width:visualViewport.width,height:visualViewport.height,scale:visualViewport.scale}},
  document:{clientWidth:document.documentElement.clientWidth,scrollWidth:document.documentElement.scrollWidth},
  rotateOpen:!!document.querySelector('#rotatePhone:popover-open,#gbaShort:modal'),boxes,skills,scroll,targets,
  texts:[...texts,...pseudoTexts],
  css:{htmlTouch:getComputedStyle(document.documentElement).touchAction,
   overscroll:getComputedStyle(document.documentElement).overscrollBehavior,
   appSelect:getComputedStyle(document.querySelector('#app')).userSelect,
   appCallout:getComputedStyle(document.querySelector('#app')).getPropertyValue('-webkit-touch-callout')},
  selection:{layout:s2?'S2':'legacy',group:document.querySelector('.group-tabs [aria-selected="true"]')?.dataset.group},
  state:window.__waterTest?.snapshot()};
}"""


def baseline_route(page):
    path = os.environ.get('POIGHT_BASELINE_HTML')
    if path:
        body = Path(path).read_text()
        page.route(URL + '/?observe=1', lambda r: r.fulfill(body=body, content_type='text/html'))
        page.route(URL + '/?test=1&lazy=1', lambda r: r.fulfill(body=body, content_type='text/html'))


def poll(page, fn, timeout=30):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if page.evaluate(fn):
            return
        page.wait_for_timeout(50)
    raise TimeoutError(fn)


def tap(page, selector):
    page.locator(selector).first.tap(timeout=2200)


def safe_inject(page):
    return page.evaluate(r"""() => {
      let n=0;for(const style of document.querySelectorAll('style')){
       style.textContent=style.textContent.replace(/env\(safe-area-inset-(top|bottom|left|right)(?:,[^)]*)?\)/g,
        (_,side)=>{n++;return ({top:'47px',bottom:'34px',left:'0px',right:'0px'})[side];});}
      return n;
    }""")


def capture(page, record, step):
    name = f"{record['device']}-{record['direction']}-{record['variant']}-{step}.png"
    path = SHOTS / name
    page.screenshot(path=str(path), full_page=True, scale='css')
    m = page.evaluate(METRICS)
    m['screenshot'] = str(path.relative_to(ROOT))
    record['steps'][step] = m
    return m


def production(pw, device, direction, variant):
    descriptor = dict(pw.devices[device])
    engine = descriptor.pop('default_browser_type')
    original = descriptor['viewport']
    w, h = original['width'], original['height']
    if direction == '横屏':
        w, h = h, w
    loss = {'基准': 0, '地址栏100': 100, '工具栏180': 180, '安全区47-34': 0}[variant]
    target = {'width': w, 'height': h-loss}
    # Portrait continuation is a real resize, not hiding the popover.
    landscape = {'width': original['height'], 'height': max(140, original['width']-loss)}
    descriptor['viewport'] = target
    browser = getattr(pw, engine).launch(headless=True)
    context = browser.new_context(**descriptor)
    page = context.new_page()
    page.set_default_timeout(4000)
    r = {'device': device, 'direction': direction, 'variant': variant, 'engine': engine,
         'descriptor': descriptor, 'steps': {}, 'errors': [], 'actions': [], 'incomplete': []}
    page.on('pageerror', lambda e: r['errors'].append(str(e)))
    page.on('response', lambda res: r['errors'].append(f'HTTP {res.status}: {res.url}') if res.status >= 400 else None)
    def action(label, selector):
        try:
            tap(page, selector)
            r['actions'].append({'name': label, 'ok': True})
            return True
        except (PlaywrightError, TimeoutError) as e:
            r['actions'].append({'name': label, 'ok': False, 'error': str(e)[:500]})
            return False
    def shot(step):
        if direction == '竖屏':
            page.set_viewport_size(target)
            page.wait_for_timeout(70)
        m = capture(page, r, step)
        if direction == '竖屏':
            page.set_viewport_size(landscape)
            page.wait_for_timeout(70)
        return m
    try:
        # Delayed portrait/icon response makes first-load content observable, no altered game logic.
        page.route('**/assets/portrait-*', lambda route: (time.sleep(.08), route.continue_()))
        baseline_route(page)
        page.goto(URL+'/?observe=1', wait_until='domcontentloaded')
        if variant == '安全区47-34':
            r['safeAreaReplacements'] = safe_inject(page)
        capture(page, r, '01-首次加载')
        poll(page, '() => document.querySelector("#setup").open')
        capture(page, r, '02-选人全屏')
        if direction == '竖屏':
            action('竖屏直接确定', '#startBattle')
            page.wait_for_timeout(150)
            r['portraitTapPhase'] = page.evaluate('window.__waterTest.snapshot().phase')
            capture(page, r, '02b-竖屏点确定后')
            if not page.evaluate('document.querySelector("#setup").open'):
                page.reload(wait_until='domcontentloaded')
                poll(page, '() => document.querySelector("#setup").open')
                if variant == '安全区47-34':
                    safe_inject(page)
            page.set_viewport_size(landscape)
            page.wait_for_timeout(100)
            r['continuation'] = '竖屏直接确定、重载恢复选人；每步旋回目标竖屏截图。MOB2 竖屏选人/配招不显示遮罩，VS 后才门禁。'
        # Evidence of hidden portrait selection without altering overlay: DOM values only.
        r['landscapeSelection'] = page.evaluate(METRICS)
        page.evaluate("() => {for(const s of ['.setup-body','#roster']){const e=document.querySelector(s);e.scrollTop=e.scrollHeight;}}")
        page.wait_for_timeout(80)
        shot('03-选人滚动到底')
        # Native browser scrollIntoView on a real Pokemon target.
        action('点当前页末只', '#roster .mon:last-child')
        shot('04-点开宝可梦')
        action('配招面板', '#toggleLoadout')
        shot('05-配招')
        action('完成配招', '#closeMoves')
        # Small SE landscape can be obstructed by a clipped footer; no force-click.
        if not action('确定VS', '#startBattle'):
            r['incomplete'].append('真实确定按钮无法点到；VS/对战/出招/菜单/胜负流程阻断。')
            shot('06-确定阻断')
            return r
        poll(page, '() => !document.querySelector("#vsScreen").hidden || window.__waterTest?.snapshot().phase==="playing"')
        if page.evaluate('!document.querySelector("#vsScreen").hidden'):
            page.wait_for_timeout(700)
        shot('06-VS开场')
        if page.evaluate('!document.querySelector("#vsScreen").hidden'):
            action('跳过VS', '#vsContinue')
        if page.evaluate('window.__waterTest.snapshot().phase') != 'playing':
            page.touchscreen.tap(landscape['width']*.5 if direction == '竖屏' else target['width']*.5,
                                 (landscape['height'] if direction == '竖屏' else target['height'])-2)
            r['actions'].append({'name':'VS旋转后点画布恢复','ok':True})
        poll(page, '() => window.__waterTest?.snapshot().phase==="playing"')
        page.wait_for_timeout(150)
        shot('07-对战中')
        r['landscapeBattle'] = page.evaluate(METRICS)
        before = page.evaluate('window.__waterTest.snapshot().player.spent')
        action('放一次招式', '.skill')
        page.wait_for_timeout(200)
        shot('08-放招式')
        r['castSpentDelta'] = page.evaluate('window.__waterTest.snapshot().player.spent') - before
        action('打开菜单', '#battleMenuButton')
        shot('09-菜单')
        r['menuPhase'] = page.evaluate('window.__waterTest.snapshot().phase')
        action('打开操作设置', '#help')
        shot('10-设置')
        if page.locator('#helpPanel').is_visible():
            action('震屏设置', '#shakeSetting')
            action('关闭操作设置', '#gbaHelpClose')
        # Canvas has a genuine pointerdown handler that closes help and resumes.
        page.touchscreen.tap((landscape['width'] if direction == '竖屏' else target['width'])*.5,
                             (landscape['height'] if direction == '竖屏' else target['height'])-2)
        r['canvasCloseHelp'] = not page.locator('#helpPanel').is_visible()
        action('再开菜单', '#battleMenuButton')
        action('声音切换', '#sound')
        shot('11-声音音乐入口')
        r['musicPanel'] = 'M9 保留 BGM 音乐入口；此矩阵操作声音开关，音乐生命周期与红血方案由战斗音乐专套另验。'
        if page.locator('#helpPanel').is_visible():
            if not page.locator('#battleMenu').is_visible():
                action('重开菜单以关闭设置', '#battleMenuButton')
            action('菜单内关闭设置', '#help')
        if page.locator('#helpPanel').is_visible():
            r['recovery'] = '设置面板无法通过菜单关闭；重载并重新点确定，另局完成旋转与自然结算。'
            page.reload(wait_until='domcontentloaded')
            poll(page, '() => document.querySelector("#setup").open')
            if variant == '安全区47-34':
                safe_inject(page)
            if not action('重载后真实确定', '#startBattle'):
                r['incomplete'].append('重载后仍无法点确定，旋转/结算未完成。')
                return r
            poll(page, '() => window.__waterTest?.snapshot().phase==="playing"')
        if page.locator('#battleMenu').is_visible():
            action('关闭菜单恢复对战', '#battleMenuButton')
        # Actual rotation: preserve IDs/HP, pause in portrait and resume on returning landscape.
        pre = page.evaluate('window.__waterTest.snapshot()')
        portrait = {'width': original['width'], 'height': original['height']-loss}
        page.set_viewport_size(portrait)
        page.wait_for_timeout(100)
        paused = page.evaluate('window.__waterTest.snapshot()')
        capture(page, {**r, 'direction': direction+'-旋转竖屏', 'steps': r['steps']}, '12-旋转暂停')
        page.set_viewport_size(landscape if direction == '竖屏' else target)
        page.wait_for_timeout(100)
        resumed = page.evaluate('window.__waterTest.snapshot()')
        r['rotation'] = {'beforePhase': pre['phase'], 'portraitPhase': paused['phase'],
                         'afterPhase': resumed['phase'], 'beforeHP': pre['player']['hp'],
                         'pausedHP': paused['player']['hp'], 'idsPreserved':
                         pre['player']['id']==resumed['player']['id'] and pre['enemy']['id']==resumed['enemy']['id']}
        shot('13-旋转恢复')
        # Resume through the real canvas handler if settings intentionally paused the match.
        if page.evaluate('window.__waterTest.snapshot().phase') != 'playing':
            page.touchscreen.tap((landscape['width'] if direction == '竖屏' else target['width'])*.5,
                                 (landscape['height'] if direction == '竖屏' else target['height'])-2)
        # Production animation/AI under Playwright virtual time. For result-only captures,
        # schedule rAF at 4Hz to avoid rendering 18000 unused frames. The game retains its
        # original 120Hz fixed physics and 0.25s accumulator cap. No setters/HP/endMatch.
        page.clock.install()
        page.evaluate('() => {window.requestAnimationFrame = cb => setTimeout(() => cb(performance.now()),250);}')
        r['resultClock'] = 'Playwright clock + 4Hz rAF scheduling; production 120Hz fixed-step AI; no state setters'
        virtual = 0
        while page.evaluate('window.__waterTest.snapshot().phase') != 'over' and virtual < 600000:
            if page.evaluate('window.__waterTest.snapshot().phase') != 'playing':
                break
            page.clock.run_for(15000)
            virtual += 15000
        r['resultVirtualMilliseconds'] = virtual
        if page.evaluate('window.__waterTest.snapshot().phase') == 'over':
            # UI2 reveals the result 800ms after KO; advance the same production clock.
            page.clock.run_for(850)
            shot('14-自然胜负')
        else:
            r['incomplete'].append('AI 600秒虚拟时间仍未结算或被暂停；不伪造胜负。')
            shot('14-未结算')
        return r
    except (PlaywrightError, TimeoutError, ValueError, KeyError) as exc:
        r['incomplete'].append(repr(exc))
        try:
            capture(page, r, '异常现场')
        except PlaywrightError as shot_error:
            r['incomplete'].append('截图失败：' + str(shot_error))
        return r
    finally:
        context.close()
        browser.close()


def touches(pw, device):
    """Chromium CDP supplementary input fixture, distinctly separate from production."""
    d = dict(pw.devices[device]); d.pop('default_browser_type')
    v = d['viewport']; d['viewport'] = {'width': v['height'], 'height': v['width']}
    b = pw.chromium.launch(headless=True); c = b.new_context(**d); p = c.new_page()
    r = {'device': device, 'engine': 'chromium-CDP', 'fixture': '?test=1&lazy=1', 'checks': [], 'errors': []}
    p.on('pageerror', lambda e: r['errors'].append(str(e)))
    def state():
        return p.evaluate('window.__waterTest.snapshot()')
    def call(m, v=None):
        return p.evaluate('([m,v]) => window.__waterTest[m](v)', [m,v])
    def check(n, ok, detail):
        r['checks'].append({'name': n, 'ok': bool(ok), 'detail': detail})
    try:
        baseline_route(p)
        p.goto(URL+'/?test=1&lazy=1')
        poll(p, '() => window.__waterTest?.snapshot().artReady', 60)
        call('reset', True)
        call('arrange', {'ai': False})
        cdp = c.new_cdp_session(p)
        def send(k, points):
            cdp.send('Input.dispatchTouchEvent', {'type': k, 'touchPoints': points})
            p.wait_for_timeout(35)
        o = {'x': 160, 'y': max(130, v['width']-85), 'id': 1}
        send('touchStart', [o]); send('touchMove', [{**o,'x':o['x']+4}])
        check('4px死区', state()['mobile']['vector']['x']==0, state()['mobile'])
        full = {**o,'x':o['x']+54}
        send('touchMove', [full]); x=state()['player']['x']; call('step', .15)
        check('54px满推跟手', state()['mobile']['vector']['x']==1 and state()['player']['x']>x,
              {'mobile':state()['mobile'],'deltaX':state()['player']['x']-x})
        bb=p.locator('.skill').first.bounding_box(); a={'x':bb['x']+bb['width']/2,'y':bb['y']+bb['height']/2,'id':2}
        spent=state()['player']['spent']
        send('touchStart',[full,a]); send('touchEnd',[a]); call('step',.25)
        s=state(); check('移动与松手出招同时成立',s['player']['spent']>spent and s['mobile']['pointerId'] is not None,
                        {'spentDelta':s['player']['spent']-spent,'mobile':s['mobile']})
        send('touchEnd',[])
        call('reset',True);call('arrange',{'ai':False})
        p.locator('#dashButton').tap();call('step',.05)
        check('闪按钮触发',state()['player']['dashing'],state()['player']['dodges'])
        # Native long press/contextmenu, double-tap and pinch on canvas in emulation.
        call('reset',True);call('arrange',{'ai':False})
        p.evaluate("() => {window.mobEvents={contextmenu:0,pointercancel:0};for(const k of Object.keys(mobEvents))document.addEventListener(k,()=>mobEvents[k]++);}")
        send('touchStart',[o]);p.wait_for_timeout(900);send('touchEnd',[])
        check('画布长按无文字选择', p.evaluate('getSelection().toString().length===0'), p.evaluate('mobEvents'))
        scale=p.evaluate('visualViewport.scale')
        for _ in range(2):
            send('touchStart',[o]);send('touchEnd',[]);p.wait_for_timeout(70)
        check('画布双击不放大',p.evaluate('visualViewport.scale')==scale,p.evaluate('visualViewport.scale'))
        two=[{'x':d['viewport']['width']/2-30,'y':d['viewport']['height']/2,'id':1},
             {'x':d['viewport']['width']/2+30,'y':d['viewport']['height']/2,'id':2}]
        send('touchStart',two);send('touchMove',[{**two[0],'x':two[0]['x']-70},{**two[1],'x':two[1]['x']+70}]);send('touchEnd',[])
        check('画布双指不缩放',p.evaluate('visualViewport.scale')==scale,p.evaluate('visualViewport.scale'))
        pos=p.evaluate('[scrollX,scrollY]')
        send('touchStart',[{'x':d['viewport']['width']/2,'y':10,'id':1}]);send('touchMove',[{'x':d['viewport']['width']/2,'y':d['viewport']['height']-10,'id':1}]);send('touchEnd',[])
        check('下拉文档未位移',p.evaluate('[scrollX,scrollY]')==pos,p.evaluate('[scrollX,scrollY]'))
        r['nativeOSLimit']='不代表 iOS/微信 原生刷新、橡皮筋、系统菜单已验收；需要真机。'
        p.screenshot(path=str(SHOTS/f'{device}-横屏-补充触摸.png'),scale='css')
        p.locator('#battleMenuButton').tap();p.locator('#setupButton').tap()
        r['scrollGesture'] = {}
        def swipe_panel(selector):
            e=p.locator(selector);bb=e.bounding_box()
            body=p.locator('.setup-body').bounding_box()
            top=max(bb['y'],body['y'],0)+5
            # S2 desktop-height roster has a 5px border: old bottom-5 starts
            # exactly on its non-scrollable border. Begin inside the client box;
            # retain the same native gesture and positive-scroll assertion.
            border=e.evaluate('(e)=>parseFloat(getComputedStyle(e).borderBottomWidth)')
            inset=max(5,border+10) if selector == '#roster' else 5
            bottom=min(bb['y']+bb['height'],body['y']+body['height'],d['viewport']['height'])-inset
            owner = p.locator('#loadoutPanel') if selector == '#moveCatalog' else e
            before=owner.evaluate('(e)=>e.scrollTop')
            extent=owner.evaluate('(e)=>({clientHeight:e.clientHeight,scrollHeight:e.scrollHeight})')
            if bottom-top<25:
                return {'available':False,'reason':'可视可滑动高度不足25px','top':top,'bottom':bottom,**extent}
            xx=bb['x']+bb['width']/2
            send('touchStart',[{'x':xx,'y':bottom,'id':1}])
            for i in range(1,9):
                send('touchMove',[{'x':xx,'y':bottom-(bottom-top)*i/8,'id':1}])
            send('touchEnd',[]);p.wait_for_timeout(200)
            after=owner.evaluate('(e)=>e.scrollTop')
            return {'available':True,'before':before,'after':after,'delta':after-before,**extent,
                    'owner': '#loadoutPanel' if selector == '#moveCatalog' else selector,
                    'css':e.evaluate('(e)=>({touch:getComputedStyle(e).touchAction,overflow:getComputedStyle(e).overflowY})')}
        r['scrollGesture']['roster']=swipe_panel('#roster')
        p.screenshot(path=str(SHOTS/f'{device}-横屏-补充原生滑动选人.png'),scale='css')
        p.locator('#toggleLoadout').tap()
        r['scrollGesture']['loadout']=swipe_panel('#loadoutPanel')
        r['scrollGesture']['catalog']=swipe_panel('#moveCatalog')
        r['scrollGesture']['layout']=p.evaluate(METRICS)
        p.screenshot(path=str(SHOTS/f'{device}-横屏-补充原生滑动配招.png'),scale='css')
    except (PlaywrightError, TimeoutError, ValueError, KeyError) as e:
        r['checks'].append({'name':'补充输入完成','ok':False,'detail':repr(e)})
    finally:
        c.close();b.close()
    return r


def collage(device, records):
    entries=[]
    for r in records:
        if r['device']!=device:continue
        for step,m in r['steps'].items():
            entries.append((f"{r['direction']} {r['variant']} {step}",ROOT/m['screenshot']))
    known={p for _,p in entries}
    for p in sorted(SHOTS.glob(f'{device}-横屏-补充*.png')):
        if p not in known:
            entries.append((p.stem,p))
    tw,th=320,220; cols=6; rows=(len(entries)+cols-1)//cols
    canvas=Image.new('RGB',(tw*cols,th*rows),'#172331'); draw=ImageDraw.Draw(canvas)
    # Pillow's bundled font does not carry Chinese; numbered cells map to contact-sheet-index.json.
    for i,(label,path) in enumerate(entries):
        with Image.open(path) as im:
            im=im.convert('RGB');im.thumbnail((tw-8,th-28))
            x=(i%cols)*tw;y=(i//cols)*th
            canvas.paste(im,(x+(tw-im.width)//2,y+24))
            draw.text((x+5,y+4),f'{device} #{i+1}',fill='white')
    dest=OUT/f'总览-{device}.png';canvas.save(dest)
    return [{'cell':i+1,'label':a,'screenshot':str(b.relative_to(ROOT))} for i,(a,b) in enumerate(entries)]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--devices',nargs='*',default=DEVICES)
    parser.add_argument('--variants',nargs='*',default=['基准','地址栏100','工具栏180','安全区47-34'])
    parser.add_argument('--input-only',action='store_true');parser.add_argument('--reuse',action='store_true')
    parser.add_argument('--finalize',action='store_true')
    args=parser.parse_args();SHOTS.mkdir(parents=True,exist_ok=True)
    path=OUT/'审计数据.json'
    data=json.loads(path.read_text()) if args.reuse and path.exists() else {'production':[],'input':[]}
    with sync_playwright() as pw:
        if not args.input_only and not args.finalize:
            for device in args.devices:
                for direction in ['竖屏','横屏']:
                    for variant in args.variants:
                        r=production(pw,device,direction,variant)
                        data['production']=[old for old in data['production'] if
                          (old['device'],old['direction'],old['variant'])!=(device,direction,variant)]+[r]
                        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
                        print(json.dumps({'device':device,'direction':direction,'variant':variant,
                          'screenshots':len(r['steps']),'incomplete':r['incomplete'],'errors':r['errors']},ensure_ascii=False),flush=True)
        for device in ([] if args.finalize else args.devices):
            r=touches(pw,device)
            data['input']=[old for old in data['input'] if old['device']!=device]+[r]
            path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    # Remove stale pilot/timeout images, keeping exactly the recorded production and input evidence.
    known={ROOT/m['screenshot'] for r in data['production'] for m in r['steps'].values()}
    known.update(p for p in SHOTS.glob('*补充*.png'))
    for p in SHOTS.glob('*.png'):
        if p not in known:
            p.unlink()
    index={d:collage(d,data['production']) for d in DEVICES if any(r['device']==d for r in data['production'])}
    (OUT/'拼图索引.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
    checks=[c for r in data['input'] for c in r['checks']]
    summary={'productionCombinations':len(data['production']), 'screenshots':len(list(SHOTS.glob('*.png'))),
      'passed':sum(c['ok'] for c in checks),'failed':sum(not c['ok'] for c in checks),
      'jsErrors':sum(len(r['errors']) for r in data['production']+data['input']),
      'incompleteCombinations':sum(bool(r['incomplete']) for r in data['production'])}
    (OUT/'摘要.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print('MOB_SUMMARY '+json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
