"""Targeted real KO/top-layer and short-screen transition checks (no weakened legacy gates)."""
import importlib.util
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audit', ROOT / '验收-手机适配.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
label = sys.argv[1]
OUT = ROOT / '验收记录/MOB3' / label
OUT.mkdir(parents=True, exist_ok=True)
checks, errors = [], []

def check(name, ok, detail=None):
    row = {'name': name, 'ok': bool(ok), 'detail': detail}
    checks.append(row)
    if not ok:
        print('FAIL ' + json.dumps(row, ensure_ascii=False), flush=True)

with sync_playwright() as pw:
    for device in audit.DEVICES:
        desc = dict(pw.devices[device])
        engine = desc.pop('default_browser_type')
        size = desc['viewport']
        desc['viewport'] = {'width': size['height'], 'height': size['width']}
        browser = getattr(pw, engine).launch(headless=True)
        context = browser.new_context(**desc)
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(os.environ['POIGHT_TEST_URL'].rstrip('/') + '/?test=1&lazy=1')
        audit.poll(page, '() => window.__waterTest?.snapshot().artReady', 60)
        page.evaluate('''()=>{const t=__waterTest;t.reset(true);t.arrange({ai:false,enemy:{hp:1,hurt:0}});t.testDamage('enemy',999);t.step(.3);}''')
        controls = ['.hud', '#battleRail', '#mobileActions', '#mobileJoystick', '#battleMenuButton', '#gbaPause', '#gbaResources', '#gbaClock']
        check(device + ' KO hides all rendered HUD immediately', all(not page.locator(s).is_visible() for s in controls))
        audit.poll(page, '() => document.querySelector("#matchOverlay").matches(":popover-open")')
        check(device + ' real over top layer', page.evaluate('window.__waterTest.snapshot().phase') == 'over')
        page.screenshot(path=OUT / f'{device}-结算.png', scale='css')
        page.locator('#gbaRematch').tap()
        check(device + ' rematch restores HUD', page.evaluate('window.__waterTest.snapshot().phase') == 'playing' and all(page.locator(s).is_visible() for s in ['#battleRail', '#mobileJoystick', '#gbaPause']))
        check(device + ' rematch removes old top layer', not page.locator('#matchOverlay').evaluate('e=>e.matches(":popover-open")'))
        context.close()
        browser.close()
report = {'passed': sum(c['ok'] for c in checks), 'failed': sum(not c['ok'] for c in checks),
          'jsErrors': len(errors), 'checks': checks, 'errors': errors}
(OUT / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print('STATE_SUMMARY ' + json.dumps({k: report[k] for k in ['passed', 'failed', 'jsErrors']}), flush=True)
raise SystemExit(bool(report['failed'] or report['jsErrors']))
