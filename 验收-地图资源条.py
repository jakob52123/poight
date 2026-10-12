"""真实浏览器地图与资源条专项。包括取消、过期加载和失败回滚，不自动发布。"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/地图与资源条'
OUT.mkdir(exist_ok=True)
ap = argparse.ArgumentParser()
ap.add_argument('--url', default='http://localhost:8792/')
a = ap.parse_args()
checks, errors, requests, failures = [], [], [], []
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def check(name, condition, details=None):
    checks.append({'name': name, 'passed': bool(condition), 'details': details})
    if not condition:
        raise AssertionError(name + ': ' + repr(details))


def wait(page, expression, timeout=15000):
    end = time.monotonic() + timeout / 1000
    while time.monotonic() < end:
        if page.evaluate('()=>(' + expression + ')'):
            return
        page.wait_for_timeout(30)
    raise TimeoutError(expression)


def save():
    (OUT / '浏览器验收.json').write_text(json.dumps({
        'at': datetime.now(timezone.utc).isoformat(), 'url': a.url, 'passed': sum(c['passed'] for c in checks),
        'total': len(checks), 'checks': checks, 'errors': errors, 'unexpectedRequestFailures': failures,
        'candidateSHA256': sha(ROOT / '候选试玩.html'), 'scope': '技术功能与布局；不代表人类审美、手感、60FPS或已发布。加载失败／取消用例单独隔离，未真实丢失素材。'
    }, ensure_ascii=False, indent=2) + '\n')


with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='chrome', headless=True)
    context = browser.new_context(viewport={'width': 1440, 'height': 900})
    page = context.new_page()
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda r: requests.append(r.url))
    page.on('requestfailed', lambda r: failures.append({'url': r.url, 'failure': r.failure}))
    call = page.evaluate
    snap = lambda: call('()=>__waterTest.snapshot()')
    step = lambda t: call('(t)=>__waterTest.step(t)', t)
    arrange = lambda **kw: call('(v)=>__waterTest.arrange(v)', kw)

    def reset(ai=False):
        call('()=>__waterTest.reset(true)')
        arrange(ai=ai)

    def choose(scene):
        return call('(map)=>{const r=__waterTest.catalog().roster.find(c=>c.id===7);return __waterTest.select({player:7,enemy:7,playerMoves:r.defaultMoves,enemyMoves:r.defaultMoves,tier:"great",map});}', scene)

    def picker(scene=None, setup=False):
        page.locator('#setupMapButton' if setup else '#sceneButton').click()
        wait(page, 'Array.from(document.querySelectorAll("#sceneCards img")).every(i=>i.complete&&i.naturalWidth>0)')
        if scene:
            page.locator(f'[data-scene="{scene}"]').click()

    def commit(scene):
        picker(scene)
        page.locator('#applyScene').click()
        wait(page, f'__waterTest.snapshot().environment.id==="{scene}"&&!document.querySelector("#scenePicker").open')

    try:
        response = page.goto(a.url + '?test=1', wait_until='load')
        wait(page, 'window.__waterTest?.snapshot().artReady')
        check('加载的是当前候选HTML', hashlib.sha256(response.body()).hexdigest() == sha(ROOT / '候选试玩.html'))
        catalog = call('()=>__waterTest.catalog()')
        scenes = catalog['scenes']
        check('三张场景且50角色不扩容', [s['id'] for s in scenes] == ['forest', 'courtyard', 'coast'] and len(catalog['roster']) == 50)
        check('三张底图不同，不只改场景名称', len({s['groundSrc'] for s in scenes}) == 3)
        check('三张地图预览图全部可解码', all(s.get('previewSrc') for s in scenes))
        choose('forest')
        reset()
        arrange(player={'hp': 63, 'stamina': 42})
        check('上方明确标血量，下方明确标体力SP', page.locator('#playerHealthText').inner_text() == '血量 63 / 100' and page.locator('#staminaText').inner_text() == '42 / 100' and '体力 SP' in page.locator('.stamina-title').inner_text())
        check('进度条分别取HP和SP，不互相同步', page.locator('#playerHealthMeter').get_attribute('aria-valuenow') == '63' and page.locator('#staminaMeter').get_attribute('aria-valuenow') == '42')
        reset()
        call('()=>__waterTest.cast("player","watergun")')
        step(.08)
        check('出招扣体力、不扣自己的血量', snap()['player']['stamina'] == 94 and snap()['player']['hp'] == 100)
        reset()
        call('()=>__waterTest.injectWater({owner:"enemy",x:165,y:280,ux:1,uy:0})')
        step(.2)
        check('受击扣血量、体力独立', snap()['player']['hp'] < 100 and snap()['player']['stamina'] == 100)
        arrange(player={'hp': 63, 'stamina': 42})
        before = snap()
        picker('coast')
        page.screenshot(path=str(OUT / '地图选择-桌面.png'))
        step(1)
        check('打开地图菜单即暂停，键盘不会误出招', snap()['elapsed'] == before['elapsed'])
        page.keyboard.press('j')
        check('地图选择时招式按键不进入战斗', snap()['player']['spent'] == before['player']['spent'])
        page.keyboard.press('Escape')
        check('取消保留地图、血量、体力和时间', snap()['environment']['id'] == 'forest' and snap()['player']['hp'] == 63 and snap()['player']['stamina'] == 42 and snap()['elapsed'] == before['elapsed'])
        page.locator('#setupButton').click()
        picker('courtyard', setup=True)
        page.locator('#applyScene').click()
        check('选人页选图只改草稿、不提前重置对局', snap()['environment']['id'] == 'forest' and snap()['player']['hp'] == 63 and '石板庭院' in page.locator('#selectionSummary').inner_text())
        page.locator('#closeSetup').click()
        check('取消选人丢弃未确认地图', snap()['profile']['map'] == 'forest')
        page.locator('#setupButton').click()
        picker('coast', setup=True)
        page.locator('#applyScene').click()
        page.locator('#startBattle').click()
        wait(page, '__waterTest.snapshot().phase==="versus"')
        check('阵容确认进入所选地图，VS尚未开打', snap()['environment']['id'] == 'coast' and snap()['elapsed'] == 0 and '海岸沙洲' in page.locator('#vsTier').inner_text())
        page.locator('#vsContinue').click()
        arrange(ai=False, player={'hp': 46, 'stamina': 70})
        call('()=>__waterTest.cast("player","watergun")')
        step(.25)
        check('换场前确有已消耗状态和飞行物', snap()['player']['cool']['watergun'] > 0 and len(snap()['bullets']) > 0)
        commit('courtyard')
        s = snap()
        check('局中确认换场重置双方资源/计时/冷却/飞行物', s['phase'] == 'idle' and s['elapsed'] == 0 and not s['bullets'] and not s['zones'] and not s['held'] and all(s[side]['hp'] == s[side]['maxHP'] and s[side]['stamina'] == 100 and not any(s[side]['cool'].values()) for side in ('player', 'enemy')))
        check('地图切换不改角色配招与强度', s['profile']['player'] == s['profile']['enemy'] == 7 and s['profile']['tier'] == 'great')
        reset()
        arrange(player={'hp': 63, 'stamina': 42})
        page.screenshot(path=str(OUT / '资源条-桌面.png'))
        # Force navigation creation in one map, then demand invalidation in the next.
        call('()=>__waterTest.findPath(600,500,1000,500)')
        for scene in scenes:
            check(scene['name'] + '可实际载入', choose(scene['id']))
            s = snap()
            check(scene['name'] + '清除旧寻路网格', not s['environment']['navGridBuilt'])
            check(scene['name'] + '边界/碰撞/底图/出生点同步', s['environment']['bounds'] == scene['bounds'] and s['obstacles'] == scene['collisionContract'] and s['environment']['groundSrc'] == scene['groundSrc'] and all(abs(s[side][k] - scene['spawns'][side][k]) < .001 for side in ('player', 'enemy') for k in ('x', 'y')))
            positions = call('()=>{const s=__waterTest.snapshot();return [s.player,s.enemy].map(p=>__waterTest.freeAt(p.x,p.y,24));}')
            check(scene['name'] + '出生点有足够净空', all(positions))
            path = call('()=>{const s=__waterTest.snapshot();return __waterTest.findPath(s.player.x,s.player.y,s.enemy.x,s.enemy.y)}')
            check(scene['name'] + '可寻路到对方且每个路点合法', len(path) > 0 and call('(ps)=>ps.every(p=>__waterTest.freeAt(p.x,p.y,21))', path))
            check(scene['name'] + '所有可见障碍均有碰撞', call('()=>__waterTest.snapshot().obstacles.every(o=>!__waterTest.freeAt(o.x+o.w/2,o.y+o.h/2))'))
            o = scene['collisionContract'][0]
            x, y, right = o['x'] - 50, o['y'] + o['h'] / 2, o['x'] + o['w'] + 50
            reset()
            arrange(player={'x': x, 'y': y}, enemy={'x': right, 'y': y})
            call('()=>__waterTest.cast("player","watergun")')
            step(1)
            check(scene['name'] + '实战水枪被本图障碍挡住', snap()['enemy']['hp'] == 100 and not snap()['bullets'])
            reset()
            arrange(player={'x': x, 'y': y}, enemy={'x': right, 'y': y})
            page.keyboard.down('d')
            step(.5)
            page.keyboard.up('d')
            call('()=>__waterTest.dash("player",1,0)')
            step(.2)
            check(scene['name'] + '走路和闪避不穿障碍', snap()['player']['x'] <= o['x'] - 18 + .01 and call('()=>{const p=__waterTest.snapshot().player;return __waterTest.freeAt(p.x,p.y)}'))
            reset(ai=True)
            arrange(player={'x': right, 'y': y}, enemy={'x': x, 'y': y}, tier='master')
            valid = True
            for i in range(15):
                step(.1)
                valid = valid and call('()=>{const s=__waterTest.snapshot();return [s.player,s.enemy].every(p=>__waterTest.freeAt(p.x,p.y,17.99))}')
            check(scene['name'] + 'AI实际绕障碍而不是使用旧地图寻路', snap()['ai']['pathSearches'] > 0 and valid)
            reset()
            page.screenshot(path=str(OUT / (scene['id'] + '-对战.png')))
        check('旧草地图岩台不在海岸保留隐形碰撞', call('()=>__waterTest.freeAt(436,189)'))
        arrange(player={'x': 150, 'y': 510})
        page.keyboard.down('a')
        step(3)
        page.keyboard.up('a')
        check('海水边界真实阻挡而非沿用草地边界', snap()['player']['x'] == 112)
        s = snap()
        check('换场后镜头仍在世界内', 0 <= s['camera']['x'] <= s['world']['width'] - s['viewport']['width'] and 0 <= s['camera']['y'] <= s['world']['height'] - s['viewport']['height'])
        # Persistence, with old profile migration and invalid IDs checked separately below.
        page.reload(wait_until='load')
        wait(page, 'window.__waterTest?.snapshot().artReady')
        check('刷新恢复已确认地图', snap()['profile']['map'] == snap()['environment']['id'] == 'coast')
        bad = call('async()=>{const s=__waterTest.snapshot();try{await __waterTest.select({...s.profile,map:"missing"});return false;}catch{return __waterTest.snapshot().profile.map===s.profile.map;}}')
        check('非法地图拒绝，不能破坏当前对局', bad)
        for vw, vh in [(1920, 1080), (1280, 720), (844, 390), (390, 844)]:
            page.set_viewport_size({'width': vw, 'height': vh})
            page.wait_for_timeout(150)
            call('()=>__waterTest.render()')
            picker()
            box = page.locator('#applyScene').bounding_box()
            check(f'{vw}×{vh}换图确认按钮可见', box['y'] >= 0 and box['y'] + box['height'] <= vh and box['x'] >= 0 and box['x'] + box['width'] <= vw, box)
            check(f'{vw}×{vh}地图图片完整解码', page.locator('#sceneCards img').evaluate_all('(a)=>a.length===3&&a.every(i=>i.naturalWidth===400&&i.naturalHeight===250)'))
            page.screenshot(path=str(OUT / f'地图选择-{vw}x{vh}.png'))
            page.locator('#cancelScene').click()
            reset()
            arrange(player={'hp': 63, 'stamina': 42})
            page.wait_for_timeout(100)
            call('()=>__waterTest.render()')
            page.screenshot(path=str(OUT / f'资源条-{vw}x{vh}.png'))
            check(f'{vw}×{vh}页面无横向溢出', call('()=>document.documentElement.scrollWidth<=innerWidth'))
            page.locator('#setupButton').click()
            box = page.locator('#setupMapButton').bounding_box()
            check(f'{vw}×{vh}选人页换图入口可见', box['y'] >= 0 and box['y'] + box['height'] <= vh and box['x'] >= 0 and box['x'] + box['width'] <= vw, box)
            page.locator('#closeSetup').click()
        # Isolated delayed network request; closing must invalidate its completion.
        for scenario in ('cancel-late', 'failed-load'):
            isolated = browser.new_context(viewport={'width': 1280, 'height': 720})
            q = isolated.new_page()
            q.on('pageerror', lambda e: errors.append(str(e)))
            q.goto(a.url + '?test=1', wait_until='load')
            wait(q, 'window.__waterTest?.snapshot().artReady')
            q.evaluate('()=>{__waterTest.reset(true);__waterTest.arrange({ai:false,player:{hp:53,stamina:37}})}')
            ground_url = '**/' + next(s['groundSrc'] for s in scenes if s['id'] == 'courtyard')
            held = []
            q.route(ground_url, lambda route: held.append(route) if scenario == 'cancel-late' else route.abort())
            q.locator('#sceneButton').click()
            q.locator('[data-scene="courtyard"]').click()
            q.locator('#applyScene').click()
            if scenario == 'cancel-late':
                end = time.monotonic() + 5
                while not held and time.monotonic() < end:
                    q.wait_for_timeout(30)
                check('确实拦住新地图载入，非假延迟', bool(held))
                q.locator('#cancelScene').click()
                check('加载中取消立即保留旧资源和旧图', q.evaluate('()=>{const s=__waterTest.snapshot();return s.environment.id==="forest"&&s.player.hp===53&&s.player.stamina===37&&s.phase==="paused";}'))
                q.locator('#sceneButton').click()
                q.locator('[data-scene="coast"]').click()
                q.locator('#applyScene').click()
                wait(q, '__waterTest.snapshot().environment.id==="coast"&&!document.querySelector("#scenePicker").open')
                for route in held:
                    route.continue_()
                q.wait_for_timeout(250)
                check('旧地图晚到不能覆盖新选择', q.evaluate('()=>__waterTest.snapshot().environment.id==="coast"&&__waterTest.snapshot().profile.map==="coast"'))
            else:
                wait(q, 'document.querySelector("#sceneMessage").classList.contains("error")')
                check('载入失败不半切图，不丢旧对局', q.evaluate('()=>{const s=__waterTest.snapshot();return s.environment.id==="forest"&&s.profile.map==="forest"&&s.player.hp===53&&s.player.stamina===37;}'))
                check('失败可见且允许手动重试', '切换失败' in q.locator('#sceneMessage').inner_text() and q.locator('#applyScene').is_enabled())
                q.unroute(ground_url)
                q.locator('#applyScene').click()
                wait(q, '__waterTest.snapshot().environment.id==="courtyard"')
                check('手动重试不被失败缓存卡死', True)
            isolated.close()
        # Old saved loadout has no map; still boots forest rather than throwing.
        legacy = browser.new_context()
        legacy_profile = {k: v for k, v in snap()['profile'].items() if k != 'map'}
        legacy.add_init_script('localStorage.setItem("pocket-arena-loadout-v1",' + json.dumps(json.dumps(legacy_profile)) + ')')
        q = legacy.new_page()
        q.goto(a.url + '?test=1', wait_until='load')
        wait(q, 'window.__waterTest?.snapshot().artReady')
        check('旧存档没有map字段也可迁移', q.evaluate('()=>__waterTest.snapshot().profile.map==="forest"'))
        legacy.close()
        # File:// is a true local/offline load, not just disabling remote API calls.
        offline = browser.new_context()
        q = offline.new_page()
        remote = []
        q.on('request', lambda r: remote.append(r.url) if urlsplit(r.url).scheme in ('http', 'https') else None)
        q.goto((ROOT / '候选试玩.html').as_uri() + '?test=1', wait_until='load')
        wait(q, 'window.__waterTest?.snapshot().artReady')
        for scene in scenes:
            ok = q.evaluate('(map)=>__waterTest.select({...__waterTest.snapshot().profile,map})', scene['id'])
            check('离线可切换' + scene['name'], ok and q.evaluate('()=>__waterTest.snapshot().environment.id') == scene['id'])
        check('离线场景不需要网络', not remote, remote)
        offline.close()
        host = urlsplit(a.url).netloc
        external = [u for u in requests if urlsplit(u).scheme in ('http', 'https') and urlsplit(u).netloc != host]
        check('无外部请求和意外资源失败', not external and not failures, {'external': external, 'failures': failures})
        check('浏览器无脚本错误', not errors, errors)
        receipt = json.loads((ROOT / '验收记录/地图与资源条-修改前/收据.json').read_text())
        check('没有覆盖正式页面或发布清单', all(sha(ROOT / n) == receipt['hashes'][n] for n in ('index.html', '发布清单.json')))
        print(json.dumps({'passed': len(checks), 'errors': errors, 'report': str(OUT / '浏览器验收.json')}, ensure_ascii=False))
    except Exception:
        page.screenshot(path=str(OUT / '失败截图.png'))
        raise
    finally:
        save()
        browser.close()
