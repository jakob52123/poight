"""Contract-specific 140/180px tests: setup usable, actual battle paused, owned pause recovery."""
import importlib.util
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audit', ROOT / '验收-手机适配.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
OUT = ROOT / '验收记录/MOB3/极矮屏'
OUT.mkdir(parents=True, exist_ok=True)
checks, errors = [], []

def check(name, ok, detail=None):
    row = {'name': name, 'ok': bool(ok), 'detail': detail}
    checks.append(row)
    if not ok:
        print('FAIL ' + json.dumps(row, ensure_ascii=False), flush=True)

with sync_playwright() as pw:
    for engine in ['chromium', 'webkit']:
        browser = getattr(pw, engine).launch(headless=True)
        for width, height in [(568, 140), (568, 180), (658, 140), (658, 180), (320, 180)]:
            label = f'{engine}-{width}x{height}'
            context = browser.new_context(viewport={'width': width, 'height': height}, has_touch=True, is_mobile=True)
            page = context.new_page()
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(os.environ['POIGHT_TEST_URL'].rstrip('/') + '/?observe=1')
            audit.poll(page, '() => document.querySelector("#setup").open', 60)
            page.wait_for_timeout(100)
            metrics = page.evaluate(audit.METRICS)
            first = next(t for t in metrics['targets'] if t.get('id'))
            confirm = next(t for t in metrics['targets'] if t['selector'] == '#startBattle')
            check(label + ' no initial blocking modal', not metrics['rotateOpen'])
            check(label + ' complete initial avatar', not first['clipped'] and first['centerHit'], first)
            check(label + ' complete confirmation', not confirm['clipped'] and confirm['centerHit'], confirm)
            page.screenshot(path=OUT / f'{label}-选人.png', scale='css')
            page.locator('#roster .mon').last.tap()
            check(label + ' native last pokemon', page.locator('#roster .mon').last.get_attribute('aria-pressed') == 'true')
            page.locator('#toggleLoadout').tap()
            metrics = page.evaluate(audit.METRICS)
            check(label + ' loadout unblocked with >=44px card', not metrics['rotateOpen'] and any(
                t['visibleHeight'] >= 44 for t in metrics['targets'] if '.move-card' in t['selector']))
            page.screenshot(path=OUT / f'{label}-配招.png', scale='css')
            page.locator('#closeMoves').tap()
            page.locator('#startBattle').tap()
            audit.poll(page, '() => !document.querySelector("#vsScreen").hidden')
            check(label + ' VS not blocked', not page.locator('#gbaShort').is_visible())
            page.wait_for_timeout(750)
            page.locator('#vsContinue').tap()
            audit.poll(page, '() => document.querySelector("#gbaShort").matches(":modal")')
            check(label + ' actual battle is paused with exact guidance', page.evaluate('window.__waterTest.snapshot().phase') == 'paused' and '请退出全屏工具栏或横屏' in page.locator('#gbaShort').inner_text())
            page.screenshot(path=OUT / f'{label}-暂停提示.png', scale='css')
            page.keyboard.press('Escape')
            page.keyboard.press('r')
            check(label + ' modal prevents shortcut escape', page.locator('#gbaShort').is_visible() and page.evaluate('window.__waterTest.snapshot().phase') == 'paused')
            page.set_viewport_size({'width': width, 'height': max(320, width + 10) if width == 320 else 320})
            audit.poll(page, '() => !document.querySelector("#gbaShort").open && window.__waterTest.snapshot().phase === "playing"')
            check(label + ' recovered height resumes owned pause', True)
            page.locator('#gbaPause').tap()
            page.set_viewport_size({'width': width, 'height': height})
            audit.poll(page, '() => document.querySelector("#gbaShort").open')
            page.set_viewport_size({'width': width, 'height': max(320, width + 10) if width == 320 else 320})
            page.wait_for_timeout(100)
            check(label + ' recovery preserves a prior user pause', page.evaluate('window.__waterTest.snapshot().phase') == 'paused')
            page.locator('#battleMenuButton').tap()
            page.locator('#setupButton').tap()
            page.set_viewport_size({'width': width, 'height': height})
            page.wait_for_timeout(100)
            check(label + ' return to setup stays unblocked', page.locator('#setup').is_visible() and not page.locator('#gbaShort').is_visible())
            context.close()
        browser.close()
report = {'passed': sum(c['ok'] for c in checks), 'failed': sum(not c['ok'] for c in checks),
          'jsErrors': len(errors), 'checks': checks, 'errors': errors}
(OUT / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print('SHORT_SUMMARY ' + json.dumps({k: report[k] for k in ['passed', 'failed', 'jsErrors']}), flush=True)
raise SystemExit(bool(report['failed'] or report['jsErrors']))
