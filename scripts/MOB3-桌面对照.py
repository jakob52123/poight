"""Compare 3491d05's frozen candidate to the mobile-only candidate in all three desktop states."""
import json
import os
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '验收记录/MOB3/桌面对照'
OUT.mkdir(parents=True, exist_ok=True)
# Use the existing GBA suite's unchanged preparation hooks.
URL = os.environ['POIGHT_TEST_URL'].rstrip('/') + '/?test=1&lazy=1'
BASE = (ROOT / '验收记录/MOB3/改前/候选试玩.html').read_text()
checks, errors = [], []

def wait(page, fn):
    import time
    end = time.monotonic() + 60
    while time.monotonic() < end:
        if page.evaluate(fn):
            return
        page.wait_for_timeout(20)
    raise TimeoutError(fn)

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    for baseline in [True, False]:
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        # Manual physics and the same portrait/rAF frame on both sides; wall-time KO delay remains real.
        page.add_init_script('''const nativeRAF = window.requestAnimationFrame.bind(window);
          window.requestAnimationFrame = callback => nativeRAF(() => callback(0));''')
        if baseline:
            page.route(URL, lambda route: route.fulfill(body=BASE, content_type='text/html'))
        page.goto(URL)
        wait(page, 'window.__waterTest?.snapshot().artReady')
        page.locator('#battleMenuButton').click()
        page.locator('#setupButton').click()
        page.wait_for_timeout(200)
        page.screenshot(path=OUT / f'选人-{"before" if baseline else "after"}.png', animations='disabled')
        page.locator('#closeSetup').click()
        page.evaluate('''()=>{const t=__waterTest;t.reset(true);t.arrange({ai:false});t.step(.01);t.render();}''')
        page.screenshot(path=OUT / f'对战-{"before" if baseline else "after"}.png', animations='disabled')
        page.evaluate('''()=>{const t=__waterTest;t.arrange({ai:false,enemy:{hp:1,hurt:0}});t.testDamage('enemy',999);t.step(.3);}''')
        wait(page, '!document.querySelector("#matchOverlay").hidden')
        page.screenshot(path=OUT / f'结算-{"before" if baseline else "after"}.png', animations='disabled')
        context.close()
    browser.close()
for name in ['选人', '对战', '结算']:
    before, after = [Image.open(OUT / f'{name}-{suffix}.png').convert('RGB') for suffix in ['before', 'after']]
    diff = ImageChops.difference(before, after)
    changed = sum(pixel != (0, 0, 0) for pixel in diff.getdata())
    diff.save(OUT / f'{name}-diff.png')
    row = {'state': name, 'width': 1440, 'height': 900, 'changedPixels': changed, 'ok': changed == 0}
    checks.append(row)
    print('DESKTOP_DIFF ' + json.dumps(row, ensure_ascii=False), flush=True)
report = {'passed': sum(c['ok'] for c in checks), 'failed': sum(not c['ok'] for c in checks),
          'jsErrors': len(errors), 'checks': checks, 'errors': errors,
          'baselineCommit': '3491d05', 'visualClock': 'same rAF timestamp 0; manual physics, real wall-time KO lock', 'baselineSHA256': __import__('hashlib').sha256(BASE.encode()).hexdigest()}
(OUT / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print('DESKTOP_SUMMARY ' + json.dumps({k: report[k] for k in ['passed', 'failed', 'jsErrors']}), flush=True)
raise SystemExit(bool(report['failed'] or report['jsErrors']))
