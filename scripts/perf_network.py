"""Cold Chromium CDP wire accounting (run only via Jade wrapper)."""
import json
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def poll(page, expression, timeout=240):
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if page.evaluate(expression):
            return
        page.wait_for_timeout(40)
    raise TimeoutError(expression)


def measure(label, pair=(25, 6)):
    out = ROOT / '验收记录/首开加载' / label
    out.mkdir(parents=True, exist_ok=True)
    errors, requests = [], {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        cdp = context.new_cdp_session(page)
        cdp.send('Network.enable')
        cdp.send('Network.setCacheDisabled', {'cacheDisabled': True})
        cdp.send('Network.emulateNetworkConditions', {
            'offline': False, 'latency': 50, 'downloadThroughput': 300000,
            'uploadThroughput': 300000, 'connectionType': 'cellular3g'})
        phase = 'selection'
        def request(e):
            requests[e['requestId']] = {'url': e['request']['url'], 'phase': phase,
                'initiator': e.get('initiator'), 'bytes': 0, 'status': None}
        def response(e):
            if e['requestId'] in requests:
                requests[e['requestId']]['status'] = e['response']['status']
        def finished(e):
            if e['requestId'] in requests:
                requests[e['requestId']]['bytes'] = e['encodedDataLength']
                requests[e['requestId']]['complete'] = True
        cdp.on('Network.requestWillBeSent', request)
        cdp.on('Network.responseReceived', response)
        cdp.on('Network.loadingFinished', finished)
        def failed(e):
            errors.append(e['errorText'])
            if e['requestId'] in requests:
                requests[e['requestId']]['complete'] = True
        cdp.on('Network.loadingFailed', failed)
        def settle():
            deadline = time.monotonic() + 240
            while any(not r.get('complete') for r in requests.values()):
                if time.monotonic() >= deadline:
                    raise TimeoutError('Network did not finish')
                page.wait_for_timeout(40)
        start = time.monotonic()
        page.goto(os.environ['POIGHT_TEST_URL'].rstrip('/') + '/?observe=1',
                  wait_until='domcontentloaded', timeout=240000)
        poll(page, '() => document.querySelector("#setup").open && !document.querySelector("#startBattle").disabled && document.querySelectorAll(".mon").length === (document.documentElement.dataset.selection === "S2" ? Number(document.querySelector("#selectionCount").textContent.split(" ").at(-1)) : window.__waterTest.snapshot().rosterCount) && [...document.querySelectorAll("#playerPortrait,#enemyPortrait")].every(e => e.dataset.frame)')
        # Finish already-started selection requests; no hidden background download is excluded.
        poll(page, '() => [...document.images].every(i => i.complete)')
        settle()
        selection_seconds = time.monotonic() - start
        selection_bytes = sum(r['bytes'] for r in requests.values())
        page.screenshot(path=str(out / 'selection.png'))
        (out / 'selection-network.json').write_text(json.dumps({
            'bytes': selection_bytes, 'seconds': selection_seconds,
            'requests': list(requests.values())}, ensure_ascii=False, indent=2))
        shots = out / '截图'
        shots.mkdir(exist_ok=True)
        for width, height in [(1440, 900), (390, 844), (844, 390), (667, 375)]:
            page.set_viewport_size({'width': width, 'height': height})
            page.wait_for_timeout(100)
            page.screenshot(path=str(shots / f'selection-{width}x{height}.png'))
        page.set_viewport_size({'width': 1440, 'height': 900})
        # Select through real UI; the default pair needs no extra portrait requests.
        if pair != (7, 4):
            page.locator(f'.mon[data-id="{pair[0]}"]').click()
            page.locator('#pickEnemyPanel').click()
            page.locator(f'.mon[data-id="{pair[1]}"]').click()
        poll(page, '() => [...document.querySelectorAll("#playerPortrait,#enemyPortrait")].every(e => e.dataset.frame)')
        settle()
        selection_with_picks = sum(r['bytes'] for r in requests.values())
        phase = 'battle'
        start = time.monotonic()
        page.locator('#startBattle').click()
        poll(page, '() => window.__waterTest?.snapshot().phase === "playing" && !document.querySelector("#setup").open && document.querySelector("#vsScreen").hidden')
        settle()
        battle_seconds = time.monotonic() - start
        battle_bytes = sum(r['bytes'] for r in requests.values() if r['phase'] == 'battle')
        page.screenshot(path=str(out / 'battle.png'))
        report = {'selection': {'bytes': selection_bytes, 'seconds': selection_seconds},
                  'battle': {'bytes': battle_bytes, 'seconds': battle_seconds},
                  'totalWithPicks': selection_with_picks + battle_bytes,
                  'errors': errors, 'requests': list(requests.values())}
        (out / 'network.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps({k: v for k, v in report.items() if k != 'requests'}, ensure_ascii=False), flush=True)
        browser.close()
        return report


if __name__ == '__main__':
    measure(os.environ.get('PERF_LABEL', 'before'))
