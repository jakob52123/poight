"""M6a: director preview HTTP/live start, exact screenshots and seeded replay audit."""
import hashlib
import json
import statistics
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/M6a'
SHOTS = OUT / '截图'
SHOTS.mkdir(parents=True, exist_ok=True)
URL = 'http://localhost:8793/'
checks, errors = [], []


def check(name, ok):
    checks.append({'name': name, 'ok': bool(ok)})
    assert ok, name


def wait(page, expression):
    end = time.monotonic() + 120
    while time.monotonic() < end:
        if page.evaluate(expression):
            return
        page.wait_for_timeout(50)
    raise AssertionError(expression)


def snap(page):
    return page.evaluate('window.__waterTest.snapshot()')


with urlopen(URL, timeout=60) as response:
    html = response.read()
    check('8793 HTTP 200 and exact M candidate', response.status == 200
          and html == (ROOT / '候选试玩.html').read_bytes())
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(URL + '?observe=1', timeout=120000)
    wait(page, 'window.__waterTest?.snapshot().artReady')
    page.locator('#startBattle').click()
    wait(page, "window.__waterTest.snapshot().phase === 'playing'")
    before = snap(page)['elapsed']
    page.keyboard.press('j')
    page.wait_for_timeout(300)
    check('8793 live UI starts and real-time battle advances', snap(page)['elapsed'] > before)
    page.goto(URL + '?test=1', timeout=120000)
    wait(page, 'window.__waterTest?.snapshot().artReady')
    profile = page.evaluate('''() => {
      const c=__waterTest.catalog(), roster=Object.fromEntries(c.roster.map(c=>[c.id,c]));
      return {...__waterTest.snapshot().profile,player:25,enemy:6,map:'arena-formal',
        playerMoves:roster[25].defaultMoves,enemyMoves:roster[6].defaultMoves};
    }''')
    check('Pikachu versus Charizard selected', page.evaluate('p=>__waterTest.select(p)', profile))
    page.evaluate('__waterTest.reset(true); __waterTest.arrange({ai:false})')
    page.locator('#game').focus()
    page.keyboard.down('j')
    page.evaluate('__waterTest.step(.1)')
    state = snap(page)
    check('100ms thunderbolt windup, no early emission', state['player']['attack']['id'] == 'thunderbolt'
          and not state['player']['attack']['emitted'])
    page.screenshot(path=str(SHOTS / '皮卡丘vs喷火龙-十万伏特100ms-1440x900.png'))
    page.keyboard.up('j')
    page.close()
    context = browser.new_context(viewport={'width': 844, 'height': 390}, has_touch=True, is_mobile=True)
    page = context.new_page()
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(URL + '?test=1', timeout=120000)
    wait(page, 'window.__waterTest?.snapshot().artReady')
    check('Touch match selected', page.evaluate('p=>__waterTest.select(p)', profile))
    page.evaluate('__waterTest.reset(true); __waterTest.arrange({ai:false})')
    before = snap(page)['player']['x']
    page.locator('#dashButton').tap()
    page.evaluate('__waterTest.step(.09)')
    state = snap(page)
    check('Touch dash away from Charizard', state['player']['dashing'] and state['player']['x'] < before)
    page.screenshot(path=str(SHOTS / '触屏闪-844x390.png'))
    page.set_viewport_size({'width': 390, 'height': 844})
    wait(page, "window.__waterTest.snapshot().phase === 'paused'")
    page.screenshot(path=str(SHOTS / '竖屏暂停-390x844.png'))
    context.close()
    browser.close()
check('No JS errors', not errors)
paths = [ROOT / f'验收记录/集成批次/M6a-模拟-{i}.jsonl' for i in (1, 2)]
check('20 seeded games byte-identical', paths[0].read_bytes() == paths[1].read_bytes())
rows = [json.loads(line) for line in paths[0].read_text().splitlines()]
check('Game actual HP x3 without override, all 20 complete', len(rows) == 20
      and all(r['hpMultiplier'] == 3 and r['maxHP'] == {'a': 276, 'b': 303}
              and r['winner'] in ('a', 'b') for r in rows))
report = {'passed': len(checks), 'failed': 0, 'jsErrors': len(errors),
          'candidateSHA256': hashlib.sha256(html).hexdigest(),
          'byteIdentical': True, 'simulationSHA256': hashlib.sha256(paths[0].read_bytes()).hexdigest(),
          'seconds': [r['seconds'] for r in rows],
          'medianSeconds': statistics.median(r['seconds'] for r in rows),
          'H1MedianSeconds': 25.69166666666667,
          'medianDeltaSeconds': statistics.median(r['seconds'] for r in rows)-25.69166666666667,
          'checks': checks}
(OUT / '交付核验.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
