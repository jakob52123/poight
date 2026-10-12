"""单文件水枪小样的浏览器验收；无依赖安装、无业务写入、无外部 API。"""
from pathlib import Path
import json
import math
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
URL = 'http://localhost:8791/'
checks, errors, requests = [], [], []

def check(name, condition, details=None):
    checks.append({'name': name, 'passed': bool(condition), 'details': details})
    if not condition:
        raise AssertionError(name + ': ' + repr(details))

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    context = browser.new_context(viewport={'width': 1280, 'height': 900}, device_scale_factor=1)
    page = context.new_page()
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda r: requests.append(r.url))
    page.goto(URL + '?test=1', wait_until='load')
    page.wait_for_function('window.__waterTest && window.__waterTest.snapshot().artReady')
    snap = lambda: page.evaluate('window.__waterTest.snapshot()')
    step = lambda s: page.evaluate('(s) => window.__waterTest.step(s)', s)
    def reset():
        page.keyboard.press('r')
        check('重置后待机', snap()['phase'] == 'idle')
    def hold(key, seconds):
        page.keyboard.down(key)
        step(seconds)
        page.keyboard.up(key)
    s = snap()
    check('像素角色已加载', s['artReady'])
    check('初始坐标与零计数', s['player']['x'] == 215 and s['hits'] == 0 and s['taken'] == 0)
    hold('d', .4)
    s = snap(); straight = s['player']['x'] - 215
    check('D 右移，速度正确', abs(straight - 74) < .05, s['player'])
    check('松开即停', s['held'] == [])
    step(.2)
    check('无输入不漂移', abs(snap()['player']['x'] - s['player']['x']) < .01)
    reset()
    page.keyboard.down('d'); page.keyboard.down('w'); step(.4)
    page.keyboard.up('d'); page.keyboard.up('w')
    s = snap(); diagonal = math.hypot(s['player']['x'] - 215, s['player']['y'] - 280)
    check('斜向不加速', abs(diagonal - straight) < .05, {'straight': straight, 'diagonal': diagonal})
    reset(); hold('ArrowLeft', 2)
    check('方向键可用且边界不穿出', snap()['player']['x'] == 55, snap()['player'])
    reset(); hold('ArrowUp', .1)
    check('向上时朝向改变', abs(snap()['player']['a'] + math.pi / 2) < .001)
    reset(); hold('j', 1)
    s = snap()
    check('J 水枪可连发', s['player']['shots'] >= 3, s['player'])
    check('水枪实际命中并产生水花', s['hits'] >= 1 and s['drops'] > 0, s)
    reset(); hold('j', .1)
    s0 = snap(); step(5)
    s = snap()
    check('陪练实际移动', math.hypot(s['enemy']['x'] - s0['enemy']['x'], s['enemy']['y'] - s0['enemy']['y']) > 10, s['enemy'])
    check('陪练实际发射并命中玩家', s['enemy']['shots'] >= 2 and s['taken'] >= 1, s)
    reset()
    hold('d', .15)
    page.evaluate("window.dispatchEvent(new Event('blur'))")
    before = snap(); step(2); after = snap()
    check('失焦暂停且清除按键', after['phase'] == 'paused' and after['held'] == [] and after['elapsed'] == before['elapsed'])
    page.locator('#game').click(position={'x': 200, 'y': 200})
    check('点击场地恢复', snap()['phase'] == 'playing')
    page.locator('#reset').click()
    s = snap(); check('按钮重置双方和水弹', s['phase'] == 'idle' and s['hits'] == 0 and s['taken'] == 0 and s['bullets'] == 0)
    page.locator('#sound').click()
    check('声音可显式开启', page.locator('#sound').get_attribute('aria-pressed') == 'true')
    page.locator('#sound').click()
    check('声音可关闭', page.locator('#sound').get_attribute('aria-pressed') == 'false')
    reset(); hold('j', .5)
    page.screenshot(path=str(ROOT / '试玩截图.png'), full_page=True)
    dims = page.evaluate('({w:innerWidth,h:innerHeight,scrollW:document.documentElement.scrollWidth,scrollH:document.documentElement.scrollHeight})')
    check('桌面画面完整无滚动溢出', dims['scrollW'] <= dims['w'] and dims['scrollH'] <= dims['h'], dims)
    page.set_viewport_size({'width': 1280, 'height': 720})
    page.wait_for_timeout(100)
    dims = page.evaluate('({w:innerWidth,h:innerHeight,scrollW:document.documentElement.scrollWidth,scrollH:document.documentElement.scrollHeight})')
    check('720P 窗口仍完整显示', dims['scrollW'] <= dims['w'] and dims['scrollH'] <= dims['h'], dims)
    page.set_viewport_size({'width': 390, 'height': 844})
    page.wait_for_timeout(100)
    check('窄屏无横向溢出', page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
    # 普通入口真实 rAF 循环，不把手动步进测试当运行时验证。
    page.set_viewport_size({'width': 1280, 'height': 900})
    page.goto(URL, wait_until='load')
    page.keyboard.down('d'); page.wait_for_timeout(350); page.keyboard.up('d')
    page.keyboard.down('j'); page.wait_for_timeout(1200); page.keyboard.up('j')
    check('普通入口可开练', page.locator('#status').inner_text() == '水枪沿面朝方向发射')
    check('普通入口未暴露调试推进接口', page.evaluate('typeof window.__waterTest') == 'undefined')
    check('无浏览器运行错误', errors == [], errors)
    check('无外部运行时请求', all(u.startswith(URL) or u.startswith('data:') for u in requests), requests)
    # 同一文件离线也能直接打开，角色不依赖服务器或 CDN。
    page.goto((ROOT / 'index.html').as_uri() + '?test=1', wait_until='load')
    page.wait_for_function('window.__waterTest && window.__waterTest.snapshot().artReady')
    check('本地单文件离线可打开', page.evaluate('window.__waterTest.snapshot().artReady'))
    browser.close()

result = {'checks': checks, 'passed': sum(x['passed'] for x in checks), 'errors': errors, 'html_bytes': (ROOT / 'index.html').stat().st_size, 'art': 'existing PokeAPI sprites, not Codex-generated', 'not_implemented': ['dash', 'health/win/lose', 'trainer tactics', 'multiplayer', 'touch control']}
(ROOT / '验收结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'passed': result['passed'], 'html_bytes': result['html_bytes'], 'errors': errors}, ensure_ascii=False))
