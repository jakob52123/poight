"""GBA normal-route presentation + unchanged input, on four real viewport/touch contexts.
Test hooks only arrange opponents/resources; buttons/keys trigger all tested actions.
Run via tools/远程执行.sh. No external assets or network services.
"""
import json
import os
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import Error, sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/UI2'
SHOTS = OUT / '截图'
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ['POIGHT_TEST_URL'].rstrip('/')
CHECKS, ERRORS = [], []


def check(name, ok, detail=None):
    CHECKS.append({'name': name, 'ok': bool(ok), 'detail': detail})
    if not ok:
        print('FAIL', name, detail, flush=True)


def wait(page, expression, timeout=30):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if page.evaluate(expression):
            return
        page.wait_for_timeout(15)
    raise TimeoutError(expression)


def call(page, method, value=None):
    return page.evaluate('([m,v])=>__waterTest[m](v)', [method, value])


def snap(page):
    return call(page, 'snapshot')


def fresh(page):
    call(page, 'reset', True)
    call(page, 'arrange', {'ai': False, 'player': {'x': 650, 'y': 680},
                           'enemy': {'x': 950, 'y': 680}})
    call(page, 'step', .01)


def audit(page, label, touch, battle=False):
    metrics = page.evaluate('''(battle)=>{
      const visible=e=>e.checkVisibility()&&!!e.getClientRects().length;
      const rect=e=>({id:e.id||e.className,...e.getBoundingClientRect().toJSON()});
      const inView=r=>r.width>0&&r.height>0&&r.right>0&&r.bottom>0&&r.x<innerWidth&&r.y<innerHeight;
      const modal=[...document.querySelectorAll('dialog:modal')].at(-1);
      // S2's chosen dense tags use 9px; desktop A uses 10px keys / 11px names.
      // All unmodified screens, touch battle text and other controls retain the 12px gate.
      const minFont=e=>document.documentElement.dataset.selection==='S2'&&e.closest('#setup')&&
        !e.closest('#loadoutPanel') ? 9 : document.documentElement.dataset.moveStrip&&e.closest('.skill') ?
        (e.tagName==='KBD'?10:11) : 12;
      const fonts=[...document.querySelectorAll('body *')].filter(e=>visible(e)&&
        e.closest('#setup[open],#scenePicker[open],#helpPanel:not([hidden]),#battleMenu:not([hidden]),#vsScreen:not([hidden]),#matchOverlay:not([hidden]),#battleRail,#gbaClock,#gbaResources,.skill,#battleMenuButton,#gbaPause')&&
        [...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())&&
        inView(e.getBoundingClientRect())&&getComputedStyle(e).fontSize.replace('px','')<minFont(e))
        .map(e=>({id:e.id||e.className,font:getComputedStyle(e).fontSize}));
      for(const e of document.querySelectorAll('#setup .mon')) if(visible(e))
        for(const pseudo of ['::before','::after']) {const s=getComputedStyle(e,pseudo);
          if(!['none','normal','""'].includes(s.content)&&parseFloat(s.fontSize)<minFont(e))
            fonts.push({id:e.dataset.id+pseudo,font:s.fontSize});}
      const targets=[...document.querySelectorAll('button,input:not([type=hidden]),select,summary,a')]
        .filter(e=>visible(e)&&!e.disabled&&inView(e.getBoundingClientRect())&&
          (!modal||modal.contains(e)))
        .map(e=>{const r=rect(e),s2=document.documentElement.dataset.selection==='S2';
          const min=s2&&e.closest('#typeChoices')?23:s2&&e.closest('.roster-toolbar')?23:
            s2&&innerHeight<=500&&e.matches('.fighter-panel')?32:44;
          return {...r,min};}).filter(r=>r.width<r.min-.1||r.height<r.min-.1);
      const boxes=battle?[...document.querySelectorAll('.battle-card,#gbaClock,#gbaResources,#gbaKeys,#battleMenuButton,#gbaPause,#mobileJoystick,.skill,#dashButton,#jumpButton,#diveButton')]
        .filter(visible).map(rect):[];
      const m=window.__waterTest?.snapshot().arenaView?.minimap;
      if(battle&&m) boxes.push({id:'minimap',x:m.x,y:m.y,width:m.width,height:m.height,
        right:m.x+m.width,bottom:m.y+m.height});
      const overlaps=[];
      boxes.forEach((a,i)=>boxes.slice(i+1).forEach(b=>{
        if(a.x<b.right-.5&&a.right>b.x+.5&&a.y<b.bottom-.5&&a.bottom>b.y+.5)
          overlaps.push([a.id,b.id]);}));
      return {width:innerWidth,height:innerHeight,scroll:document.documentElement.scrollWidth,
        fonts,targets,boxes,overlaps,outside:boxes.filter(r=>r.x<-.5||r.y<-.5||r.right>innerWidth+.5||r.bottom>innerHeight+.5)};
    }''', battle)
    check(label + ' 无横向滚动', metrics['scroll'] <= metrics['width'], metrics['scroll'])
    check(label + ' 可见文字符合12px / S2密集标签9px / A键名10–11px', not metrics['fonts'], metrics['fonts'])
    if touch:
        check(label + ' 可点区域符合44px / S2标签23px与双卡32px', not metrics['targets'], metrics['targets'])
    if battle:
        hud = snap(page)['hud']
        check(label + ' 画布角色标签/伤害后缀≥12px', hud['tagFont'] >= 12 and hud['suffixFont'] >= 12)
        check(label + ' HUD/操作/小地图不相交', not metrics['overlaps'], metrics)
        check(label + ' 控件全部在视口内', not metrics['outside'], metrics['outside'])
    return metrics


def ko(page, loser='enemy'):
    # Actual damage() and finishMatch(), not a fabricated overlay or direct outcome.
    return page.evaluate('''side=>{const t=__waterTest;
      t.arrange({ai:false,[side]:{hp:1,hurt:0}});
      t.testDamage(side,999);t.step(.3);
      const at=performance.now();window.gbaKOAt=at;window.gbaResultAt=null;
      const el=document.querySelector('#matchOverlay');
      const observer=new MutationObserver(()=>{if(!el.hidden&&window.gbaResultAt===null){
        window.gbaResultAt=performance.now();observer.disconnect();}});
      observer.observe(el,{attributes:true,attributeFilter:['hidden']});
      return {at,hidden:el.hidden,phase:t.snapshot().phase};}''', loser)


def compare():
    refs = ROOT.parent / 'UI1/mockups/截图'
    pairs = [('整体风格-A-1440x900.png', '选人-1440x900.png', '整体风格'),
             ('选人页-A-1440x900.png', '选人-1440x900.png', '选人页'),
             ('VS开场-A-1440x900.png', 'VS-1440x900.png', 'VS开场'),
             ('对战界面-A-1440x900.png', '对战-1440x900.png', '对战界面'),
             ('手机操作-A-844x390.png', '对战-844x390.png', '手机操作'),
             ('胜负结算-B-1440x900.png', '结算-1440x900.png', '胜负结算'),
             ('胜负结算-B-844x390.png', '结算-844x390.png', '手机结算')]
    directory = OUT / '对照'
    directory.mkdir(exist_ok=True)
    for ref, actual, label in pairs:
        if not (refs / ref).exists() or not (SHOTS / actual).exists():
            continue
        left, right = Image.open(refs / ref).convert('RGB'), Image.open(SHOTS / actual).convert('RGB')
        assert left.size == right.size
        combined = Image.new('RGB', (left.width * 2, left.height))
        combined.paste(left, (0, 0))
        combined.paste(right, (left.width, 0))
        combined.save(directory / (label + '.png'))


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        for width, height in [(1440, 900), (844, 390), (390, 844), (667, 375)]:
            touch = width < 1000
            label = f'{width}x{height}'
            context = browser.new_context(viewport={'width': width, 'height': height},
                                          has_touch=touch, is_mobile=touch)
            page = context.new_page()
            page.on('pageerror', lambda e: ERRORS.append(str(e)))
            try:
                page.goto(URL + '/?test=1&lazy=1')
                wait(page, 'window.__waterTest?.snapshot().artReady')
                page.locator('#battleMenuButton').click()
                page.locator('#setupButton').click()
                page.locator('.mon').last.click()
                check(label + ' 初代组末只真实点选', page.locator('.mon').last.get_attribute('aria-pressed') == 'true')
                page.locator('.group-tabs [data-group="popular"]').click()
                page.locator('.mon').last.click()
                check(label + ' 精选组末只真实点选', page.locator('.mon').last.get_attribute('aria-pressed') == 'true')
                page.locator('.group-tabs [data-group="initial"]').click()
                page.locator('.mon[data-id="25"]').click()
                page.locator('#chooseEnemy').click()
                page.locator('.mon[data-id="6"]').click()
                page.locator('#choosePlayer').click()
                page.wait_for_timeout(200)
                expected = sum(c['id'] <= 151 for c in page.evaluate('__waterTest.catalog().roster'))
                check(label + ' 当前分组全员DOM', page.locator('.mon').count() == expected)
                for text, href in [('致敬《宝可梦：羁绊之旅》', 'https://www.bilibili.com/video/BV16bHd6jE1a/'),
                                   ('源码', 'https://github.com/jakob52123/poight')]:
                    link = page.get_by_role('link', name=text, exact=True)
                    check(label + ' ' + text, link.is_visible() and link.get_attribute('href') == href)
                audit(page, label + ' 选人', touch)
                page.screenshot(path=SHOTS / f'选人-{label}.png')
                page.locator('#setupMapButton').click()
                audit(page, label + ' 地图设置', touch)
                page.screenshot(path=SHOTS / f'地图-{label}.png')
                page.locator('#cancelScene').click()
                page.locator('#toggleLoadout').click()
                check(label + ' 配招目录可滚动访问', page.locator('#moveCatalog').is_visible())
                page.locator('.ai-options summary').click()
                page.locator('#difficulty button').last.scroll_into_view_if_needed()
                check(label + ' AI入口可达', page.locator('#difficulty button').last.is_visible())
                audit(page, label + ' 配招', touch)
                page.screenshot(path=SHOTS / f'配招-{label}.png')
                page.locator('#closeMoves').click()
                page.locator('#startBattle').click()
                wait(page, '!document.querySelector("#vsScreen").hidden')
                page.wait_for_timeout(1050)
                audit(page, label + ' VS', touch)
                page.screenshot(path=SHOTS / f'VS-{label}.png')
                page.locator('#vsContinue').click()
                check(label + ' VS进入playing', snap(page)['phase'] == 'playing')
                check(label + ' 无竖屏拦截', not page.locator('#rotatePhone').is_visible())
                fresh(page)
                audit(page, label + ' 对战', touch, True)
                if touch:
                    page.locator('#gbaPause').tap()
                    check(label + ' 暂停按钮可点击', snap(page)['phase'] == 'paused')
                    page.locator('#gbaPause').tap()
                    check(label + ' 继续按钮可点击', snap(page)['phase'] == 'playing')
                page.locator('#battleMenuButton').click()
                audit(page, label + ' 菜单', touch)
                page.locator('#help').click()
                audit(page, label + ' 操作设置', touch)
                page.screenshot(path=SHOTS / f'操作设置-{label}.png')
                page.locator('#gbaHelpClose').click()
                check(label + ' 设置显式返回对战', snap(page)['phase'] == 'playing')
                for i in range(4):
                    fresh(page)
                    button = page.locator('.skill').nth(i)
                    if touch:
                        button.tap()
                    else:
                        button.click()
                    call(page, 'step', .02)
                    before = snap(page)['player']
                    check(label + f' 招式{i+1}真实消耗', before['spent'] > 0)
                    cd = button.locator('.gba-cd').inner_text()
                    check(label + f' 招式{i+1}圆内小数冷却', '.' in cd and button.locator('.gba-cd').is_visible())
                    call(page, 'step', .3)
                    check(label + f' 招式{i+1}冷却递减', float(button.locator('.gba-cd').inner_text()) < float(cd))
                    button.click()
                    check(label + f' 招式{i+1}冷却不重复消费', snap(page)['player']['spent'] == before['spent'])
                call(page, 'step', .9)  # Let the rejection feedback expire; keep a real cooldown.
                page.screenshot(path=SHOTS / f'对战-{label}.png')
                fresh(page)
                if touch:
                    page.locator('#dashButton').tap()
                else:
                    page.keyboard.press('Shift')
                call(page, 'step', .01)
                check(label + ' 闪避实际触发', snap(page)['player']['dashing'])
                fresh(page)
                if touch:
                    page.locator('#jumpButton').tap()
                else:
                    page.keyboard.press('Space')
                call(page, 'step', .05)
                check(label + ' 跳跃实际触发', snap(page)['player']['jumpHeight'] > 0)
                fresh(page)
                start = ko(page)
                frozen = snap(page)
                check(label + ' KO立即锁定但不弹结算', start['phase'] == 'over' and start['hidden'])
                page.keyboard.press('r')
                page.mouse.click(width / 2, height / 2)
                check(label + ' KO延迟输入不可重开', snap(page)['phase'] == 'over')
                wait(page, 'window.gbaResultAt!==null')
                duration = page.evaluate('(gbaResultAt-gbaKOAt)/1000')
                check(label + ' KO延迟0.75–0.9s', .75 <= duration <= .9, duration)
                now = snap(page)
                check(label + ' KO无AI/资源/位置更新', all(now[s][k] == frozen[s][k]
                      for s in ['player', 'enemy'] for k in ['hp', 'stamina', 'x', 'y']))
                audit(page, label + ' 结算', touch)
                page.screenshot(path=SHOTS / f'结算-{label}.png')
                page.locator('#gbaRematch').click()
                check(label + ' 再战恢复满血', snap(page)['phase'] == 'playing' and
                      snap(page)['player']['hp'] == snap(page)['player']['maxHP'])
                call(page, 'arrange', {'ai': False})
                ko(page, 'player')
                wait(page, 'window.gbaResultAt!==null')
                check(label + ' 失败文案与CPU立绘', page.locator('#matchTitle').inner_text() == '失败' and
                      page.locator('#winnerPortrait').get_attribute('data-id') == '6')
                page.screenshot(path=SHOTS / f'失败-{label}.png')
                page.locator('#gbaChange').click()
                check(label + ' 换宝可梦返回选人', page.locator('#setup').is_visible())
                if touch and width > height:
                    fresh(page)
                    page.evaluate('''()=>{for(const [k,v] of Object.entries({top:47,bottom:34,left:47,right:47}))
                      document.documentElement.style.setProperty('--safe-'+k,v+'px');
                      dispatchEvent(new Event('resize'));}''')
                    page.wait_for_timeout(100)
                    audit(page, label + ' 四边安全区', True, True)
                    page.screenshot(path=SHOTS / f'安全区-{label}.png')
                    page.evaluate('''()=>{for(const k of ['top','bottom','left','right'])
                      document.documentElement.style.removeProperty('--safe-'+k);
                      dispatchEvent(new Event('resize'));}''')
                if width == 844:
                    for compact_width, compact_height in [(844, 210), (568, 320), (568, 220), (320, 568)]:
                        page.set_viewport_size({'width': compact_width, 'height': compact_height})
                        page.wait_for_timeout(100)
                        fresh(page)
                        audit(page, f'地址栏 {compact_width}x{compact_height}', True, True)
                        page.screenshot(path=SHOTS / f'紧凑-{compact_width}x{compact_height}.png')
                    page.set_viewport_size({'width': 568, 'height': 140})
                    page.wait_for_timeout(100)
                    check('140px极矮视口明确提示并暂停', page.locator('#gbaShort').is_visible() and
                          snap(page)['phase'] == 'paused')
                    check('极矮提示为真实modal防止点穿', page.locator('#gbaShort').evaluate(
                        'e=>e.matches(":modal")&&e.contains(document.activeElement)'))
                    page.keyboard.press('Escape')
                    page.keyboard.press('r')
                    check('极矮modal拦截全局快捷键', snap(page)['phase'] == 'paused' and
                          page.locator('#gbaShort').is_visible())
                    page.screenshot(path=SHOTS / '紧凑-568x140-提示.png')
                    page.set_viewport_size({'width': width, 'height': height})
                    page.wait_for_timeout(100)
                    check('恢复可用高度后原局继续', not page.locator('#gbaShort').is_visible() and
                          snap(page)['phase'] == 'playing')
                    shore = page.evaluate('''async()=>{const t=__waterTest,c=t.catalog(),a=c.terrains[0],
                      walk=atob(a.walkB64),water=atob(a.waterB64),cols=a.columns;
                      let cell=-1;for(let i=cols;i<walk.length-cols;i++) {
                        if(!water.charCodeAt(i)||!walk.charCodeAt(i-1))continue;
                        let ok=true;for(let dx=0;dx<3;dx++)for(let dy=-1;dy<=1;dy++)
                          ok&&=!!water.charCodeAt(i+dx+dy*cols);
                        if(ok){cell=i;break;}}
                      if(cell<0)throw Error('no shoreline fixture');
                      const map=c.scenes.find(s=>s.terrainID===a.id).id;
                      await t.select({...t.snapshot().profile,map});
                      return {x:(cell%cols+.5)*a.cellSize,y:(Math.floor(cell/cols)+.5)*a.cellSize};}''')
                    for water_width, water_height in [(844, 390), (390, 844), (667, 375), (844, 210), (320, 568)]:
                        page.set_viewport_size({'width': water_width, 'height': water_height})
                        page.wait_for_timeout(100)
                        call(page, 'reset', True)
                        call(page, 'arrange', {'ai': False, 'player': shore})
                        call(page, 'step', .02)
                        audit(page, f'水中 {water_width}x{water_height}', True, True)
                        page.locator('#diveButton').tap()
                        check(f'{water_width}x{water_height} 潜按钮实际可用', snap(page)['player']['diving'])
                        page.screenshot(path=SHOTS / f'潜水-{water_width}x{water_height}.png')
                if width == 1440:
                    page.evaluate('''async()=>{const t=__waterTest;
                      await t.select({...t.snapshot().profile,player:129,playerMoves:['splash']});}''')
                    ko(page, 'player')
                    wait(page, 'window.gbaResultAt!==null')
                    check('鲤鱼王原结算钩子文案保留', page.locator('#matchHint').text_content() == '鲤鱼王尽力了。')
                    check('鲤鱼王彩蛋在新B版页脚可见', page.locator('.result-footer span').inner_text() == '鲤鱼王尽力了。')
                    page.screenshot(path=SHOTS / '结算-鲤鱼王.png')
            except (Error, TimeoutError, AssertionError, KeyError, TypeError) as error:
                check(label + ' 驱动完整执行', False, str(error))
                page.screenshot(path=SHOTS / f'异常-{label}.png')
            finally:
                context.close()
        browser.close()
    compare()
    check('无JS错误', not ERRORS, ERRORS)


try:
    main()
finally:
    summary = {'passed': sum(c['ok'] for c in CHECKS), 'failed': sum(not c['ok'] for c in CHECKS),
               'jsErrors': len(ERRORS), 'checks': CHECKS, 'errors': ERRORS}
    (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print('GBA_SUMMARY', json.dumps({k: summary[k] for k in ['passed', 'failed', 'jsErrors']}), flush=True)
raise SystemExit(bool(summary['failed'] or summary['jsErrors']))
