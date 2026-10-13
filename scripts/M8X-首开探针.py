"""Allocated-wrapper cold-load receipt and read-only loading diagnostics."""
import hashlib
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.perf_network import measure

OUT = ROOT / '验收记录/M8X'
label = sys.argv[1]
report = measure(label)
report['candidateSHA256'] = hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest()
(OUT / (label + '.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps({k: report[k] for k in ['selection', 'battle', 'errors', 'candidateSHA256']}, ensure_ascii=False), flush=True)
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('response', lambda r: errors.append(f'{r.status}: {r.url}') if r.status >= 400 else None)
    page.goto(os.environ['POIGHT_TEST_URL'].rstrip('/') + '/?test=1')
    page.wait_for_timeout(3000)
    print('SNAPSHOT', json.dumps(page.evaluate('window.__waterTest.snapshot()'), ensure_ascii=False)[:4000], flush=True)
    print('ERRORS', errors, flush=True)
    browser.close()
