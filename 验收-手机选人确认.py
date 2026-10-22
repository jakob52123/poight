"""Run against a built preview: python3 验收-手机选人确认.py [http://localhost:8877]."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8877'
SHOTS = Path('/workspace/poight-shots'); SHOTS.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    for width, height in [(390, 844), (844, 390)]:
        context = browser.new_context(viewport={'width': width, 'height': height},
            is_mobile=True, has_touch=True,
            user_agent='Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/131.0 Mobile Safari/537.36')
        page = context.new_page()
        page.goto(URL + '/?observe=1')
        page.locator('#setup[open]').wait_for()
        page.locator('.side-tabs button').first.tap()
        page.locator('.mon[data-id="25"]').tap()
        page.locator('.side-tabs button').nth(1).tap()
        page.locator('.mon[data-id="1"]').tap()
        button = page.locator('#startBattle')
        # Must be in viewport without scrolling/programmatic relocation, with a real hit target.
        assert button.evaluate('''e => {const r=e.getBoundingClientRect();return r.left>=0 &&
            r.right<=innerWidth && r.top>=0 && r.bottom<=innerHeight &&
            e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));}''')
        page.screenshot(path=str(SHOTS / f'task1-after-{width}.png'))
        button.tap()
        page.wait_for_function('() => window.__waterTest?.snapshot().player?.id === 25', timeout=60000)
        state = page.evaluate('window.__waterTest.snapshot()')
        assert state['enemy']['id'] == 1, state['enemy']
        assert not page.locator('#setup').evaluate('(e)=>e.open')
        page.screenshot(path=str(SHOTS / f'task1-battle-{width}.png'))
        print(width, height, 'PASS: Pikachu vs Bulbasaur applied')
        context.close()
    browser.close()
