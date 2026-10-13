"""Focused first-frame checks, always invoked through the local slot wrapper."""
import importlib.util
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audit', ROOT / '验收-手机适配.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
label = sys.argv[1]
OUT = ROOT / '验收记录/MOB3' / label
OUT.mkdir(parents=True, exist_ok=True)
rows = []
errors = []
with sync_playwright() as pw:
    for device in audit.DEVICES:
        desc = dict(pw.devices[device])
        engine = desc.pop('default_browser_type')
        original = desc['viewport']
        browser = getattr(pw, engine).launch(headless=True)
        for landscape in [False, True]:
            for variant in ['基准', '地址栏100', '安全区47-34']:
                w, h = original['width'], original['height']
                if landscape:
                    w, h = h, w
                if variant == '地址栏100':
                    h -= 100
                context = browser.new_context(**{**desc, 'viewport': {'width': w, 'height': h}})
                page = context.new_page()
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(os.environ['POIGHT_TEST_URL'].rstrip('/') + '/?observe=1')
                audit.poll(page, '() => document.querySelector("#setup").open', 60)
                if variant == '安全区47-34':
                    audit.safe_inject(page)
                page.wait_for_timeout(80)
                select = page.evaluate(audit.METRICS)
                first = next(t for t in select['targets'] if t.get('id'))
                confirm = next(t for t in select['targets'] if t['selector'] == '#startBattle')
                try:
                    audit.tap(page, '#roster .mon:last-child')
                    last_reachable = True
                except (PlaywrightError, TimeoutError):
                    last_reachable = False
                audit.tap(page, '#toggleLoadout')
                page.wait_for_timeout(80)
                loadout = page.evaluate(audit.METRICS)
                cards = [t for t in loadout['targets'] if '.move-card' in t['selector']]
                required = 44 if h <= 220 else 25
                row = {'case': f'{device}/{"横屏" if landscape else "竖屏"}/{variant}',
                       'selection': not first['clipped'] and first['centerHit'], 'lastReachable': last_reachable,
                       'confirm': not confirm['clipped'] and confirm['centerHit'],
                       'catalog': any(t['visibleHeight'] >= required for t in cards),
                       'fullCard': any(not t['clipped'] and t['centerHit'] for t in cards),
                       'select': select, 'loadout': loadout}
                rows.append(row)
                page.screenshot(path=OUT / f'{len(rows):02}-配招.png', scale='css')
                print(json.dumps({k: row[k] for k in ['case', 'selection', 'confirm', 'catalog', 'fullCard']}, ensure_ascii=False), flush=True)
                context.close()
        browser.close()
summary = {k: {'passed': sum(r[k] for r in rows), 'failed': sum(not r[k] for r in rows)}
           for k in ['selection', 'lastReachable', 'confirm', 'catalog', 'fullCard']}
summary['jsErrors'] = len(errors)
(OUT / 'summary.json').write_text(json.dumps({'summary': summary, 'rows': rows, 'errors': errors}, ensure_ascii=False, indent=2))
print('FIRST_FRAME_SUMMARY ' + json.dumps(summary), flush=True)
gates = ['catalog', 'fullCard'] if label == 'MOB-02' else ['selection', 'lastReachable', 'confirm', 'catalog', 'fullCard']
raise SystemExit(bool(any(summary[k]['failed'] for k in gates) or errors))
