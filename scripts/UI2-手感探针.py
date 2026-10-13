import json
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
url = os.environ['POIGHT_TEST_URL'].rstrip('/')
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page(viewport={'width': 1440, 'height': 900})
    page.on('pageerror', lambda e: print('JS', e, flush=True))
    page.on('response', lambda r: print('HTTP', r.status, r.url, flush=True) if r.status >= 400 else None)
    page.on('requestfailed', lambda r: print('NET', r.url, r.failure, flush=True))
    html = (root / '候选试玩.html').read_text().replace(
        'function rejectCast(slot, reason) {',
        'window.__h1Refusals = {cool:0, stamina:0, busy:0}; window.__h1Seen={};\n'
        'function rejectCast(slot, reason) {\n'
        'if(reason && window.__h1Seen[reason.code]!==window.__h1Attempt) {'
        'window.__h1Seen[reason.code]=window.__h1Attempt;'
        'window.__h1Refusals[reason.code] = (window.__h1Refusals[reason.code]||0)+1;}')
    html = html.replace('function impact(p, a, target) {',
                        'function impact(p, a, target) { if(p.isPlayer) window.__h1Release=true;')
    page.route(url + '/?test=1', lambda r: r.fulfill(body=html, content_type='text/html; charset=utf-8',
        headers={'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'"}))
    page.goto(url + '/?test=1')
    time.sleep(8)
    print(json.dumps(page.evaluate('''()=>({state:window.__waterTest?.snapshot(),
      message:document.querySelector('#setupMessage').textContent})'''), ensure_ascii=False), flush=True)
    b.close()
