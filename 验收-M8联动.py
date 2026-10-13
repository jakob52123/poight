"""M9 merged-route gate: actual GBA input, lazy art, B2 stats, BGM3, KO and screenshots.
Run exclusively through HOST=local tools/远程执行.sh. No direct telemetry calls.
"""
import hashlib
import json
import os
import time
from pathlib import Path

from playwright.sync_api import Error, sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/M9联动'
SHOTS = OUT / '截图'
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ['POIGHT_TEST_URL'].rstrip('/')
CHECKS, ERRORS = [], []


def check(name, ok, detail=None):
    CHECKS.append({'name': name, 'ok': bool(ok), 'detail': detail})
    if not ok:
        print('FAIL', name, json.dumps(detail, ensure_ascii=False), flush=True)


def wait(page, expression, timeout=60):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if page.evaluate(expression):
            return
        page.wait_for_timeout(20)
    raise TimeoutError(expression)


def call(page, method, *args):
    return page.evaluate('([m,a])=>__waterTest[m](...a)', [method, args])


def state(page):
    return call(page, 'snapshot')


def hit(page):
    hp = state(page)['enemy']['hp']
    page.locator('.skill').first.click()
    return page.evaluate('''hp=>{for(let i=0;i<360;i++){
      __waterTest.step(1/120);if(__waterTest.snapshot().enemy.hp<hp)return i+1;
    }return null;}''', hp)


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    for width, height in [(1440, 900), (844, 390), (390, 844)]:
        label = f'{width}x{height}'
        context = browser.new_context(viewport={'width': width, 'height': height},
                                      has_touch=width < 1000, is_mobile=width < 1000)
        page = context.new_page()
        page.on('pageerror', lambda e: ERRORS.append(str(e)))
        page.on('response', lambda r: ERRORS.append(f'HTTP {r.status} {r.url}') if r.status >= 400 else None)
        images = []
        page.on('request', lambda r, images=images: images.append(r.url) if '/assets/' in r.url else None)
        try:
            page.goto(URL + '/?test=1&lazy=1')
            wait(page, 'window.__waterTest?.snapshot().artReady')
            page.locator('#battleMenuButton').click()
            page.locator('#setupButton').click()
            page.locator('.mon[data-id="25"]').click()
            page.locator('#chooseEnemy').click()
            page.locator('.mon[data-id="6"]').click()
            wait(page, 'Array.from(document.querySelectorAll("#playerPortrait,#enemyPortrait")).every(e=>e.dataset.frame)')
            check(label + ' GBA and authorized roster entries', page.locator('html').get_attribute('data-gba') == 'true' and page.locator('.mon').count() == len(json.loads((ROOT / '首发200.json').read_text())['ids']))
            privacy = page.locator('[popovertarget="analyticsPrivacy"]')
            check(label + ' anonymous statistics retained', privacy.is_visible())
            check(label + ' privacy is on credit line', page.evaluate('''()=>{
              const b=document.querySelector('[popovertarget="analyticsPrivacy"]').getBoundingClientRect(),
                a=document.querySelector('.setup-credit a').getBoundingClientRect();
              return Math.abs((a.top+a.bottom-b.top-b.bottom)/2)<2;
            }'''))
            page.screenshot(path=SHOTS / f'选人-{label}.png')
            privacy.click()
            check(label + ' privacy opens', page.locator('#analyticsPrivacy').is_visible())
            page.keyboard.press('Escape')
            page.locator('#startBattle').click()
            wait(page, '!document.querySelector("#vsScreen").hidden')
            page.wait_for_timeout(1000)
            page.screenshot(path=SHOTS / f'VS-{label}.png')
            page.locator('#vsContinue').click()
            check(label + ' real VS starts battle', state(page)['phase'] == 'playing')
            catalog = call(page, 'catalog')
            roster = {p['id']: p for p in catalog['roster']}
            for side in ['player', 'enemy']:
                actor = state(page)[side]
                check(label + ' B2 speed retained ' + side, actor['speed'] == roster[actor['id']]['speed'])
                check(label + ' body system retained ' + side, actor['body']['visibleSize'][1] > 0)
            check(label + ' BGM3 default R3', state(page)['music']['redMode'] == 'r3', state(page)['music'])
            call(page, 'arrange', {'ai': False, 'player': {'x': 600, 'y': 570, 'a': 0},
                                    'enemy': {'x': 695, 'y': 570, 'a': 3.141592653589793}})
            page.wait_for_timeout(100)
            before = len(images)
            tick = hit(page)
            check(label + ' actual thunderbolt damaging tick', tick is not None, tick)
            check(label + ' actual thunderbolt contact ring', any(b['id'] == 'thunderbolt' for b in state(page)['animation']['bursts']))
            page.screenshot(path=SHOTS / f'十万伏特命中-{label}.png')
            call(page, 'reset', True)
            call(page, 'arrange', {'ai': False, 'player': {'x': 600, 'y': 570, 'a': 0},
                                    'enemy': {'x': 695, 'y': 570, 'a': 3.141592653589793, 'hp': 1}})
            check(label + ' real cast causes KO', hit(page) is not None and state(page)['phase'] == 'over')
            frozen = state(page)
            check(label + ' KO music stopped', not frozen['music']['playing'])
            check(label + ' KO result initially hidden', page.locator('#matchOverlay').is_hidden())
            page.keyboard.press('r')
            page.mouse.click(width / 2, height / 2)
            check(label + ' KO lock prevents restart', state(page)['phase'] == 'over')
            wait(page, '!document.querySelector("#matchOverlay").hidden')
            now = state(page)
            check(label + ' KO freezes clocks and actors', now['matchSeconds'] == frozen['matchSeconds'] and all(now[s][k] == frozen[s][k] for s in ['player', 'enemy'] for k in ['hp', 'stamina', 'x', 'y']))
            check(label + ' victory and winner original portrait', page.locator('.result-word').get_attribute('data-pixel') == 'VICTORY' and page.locator('#winnerPortrait').get_attribute('data-id') == '25')
            wait(page, '!!document.querySelector("#winnerPortrait").dataset.frame')
            page.screenshot(path=SHOTS / f'VICTORY-{label}.png')
            check(label + ' no late asset fetch through KO', len(images) == before, images[before:])
            page.locator('#gbaRematch').click()
            check(label + ' rematch resumes BGM and HP', state(page)['phase'] == 'playing' and state(page)['music']['playing'] and state(page)['player']['hp'] == state(page)['player']['maxHP'])
        except (Error, TimeoutError, AssertionError, KeyError, TypeError, ValueError) as exc:
            check(label + ' completed', False, repr(exc))
        finally:
            context.close()
    browser.close()
check('no JS/network errors', not ERRORS, ERRORS)
report = {'passed': sum(c['ok'] for c in CHECKS), 'failed': sum(not c['ok'] for c in CHECKS),
          'jsErrors': len(ERRORS), 'checks': CHECKS, 'errors': ERRORS,
          'candidateSHA256': hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest()}
(OUT / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: report[k] for k in ['passed', 'failed', 'jsErrors']}, ensure_ascii=False))
raise SystemExit(bool(report['failed'] or report['jsErrors']))
