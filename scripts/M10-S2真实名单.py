"""Run UI3b's unmodified selection assertions against the actual 200-fighter HTML.
Only extract its helper definitions and 3-viewport selection loop (AST); historical
50-fighter pixel comparisons and synthetic fixture builder are deliberately excluded.
"""
import ast
import hashlib
import json
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '验收记录/M10/第二段/S2'
OUT.mkdir(parents=True, exist_ok=True)
URL = os.environ['POIGHT_TEST_URL'].rstrip('/')
CHECKS, ERRORS, GEOMETRY = [], [], {}
BODY = None  # No response interception: production candidate, real combat metadata/art.
html = (ROOT / '候选试玩.html').read_text()
data, _ = json.JSONDecoder().raw_decode(html.split('const DATA = ', 1)[1])
ids = json.loads((ROOT / '首发200.json').read_text())['ids']
assert [c['id'] for c in data['roster']] == ids and len(ids) == 200
(OUT / '200只夹具来源.json').write_text(json.dumps({'sources': data['roster'], 'realCandidate': True}, ensure_ascii=False))
source = ast.parse((ROOT / 'UI3/UI3b-验收.py').read_text())
helpers = [n for n in source.body if isinstance(n, ast.FunctionDef) and n.name in ('check', 'wait', 'newpage')]
exec(compile(ast.Module(body=helpers, type_ignores=[]), 'UI3/UI3b-验收.py', 'exec'))
loop = next(n for n in ast.walk(source) if isinstance(n, ast.For) and ast.unparse(n.iter) == '[(1440, 900), (844, 390), (667, 375)]')
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    exec(compile(ast.Module(body=[loop], type_ignores=[]), 'UI3/UI3b-验收.py', 'exec'))
    browser.close()
report = dict(candidateSHA256=hashlib.sha256(html.encode()).hexdigest(), realRoster=True,
              passed=sum(c['ok'] for c in CHECKS), failed=sum(not c['ok'] for c in CHECKS),
              jsErrors=len(ERRORS), checks=CHECKS, errors=ERRORS, geometry=GEOMETRY)
(OUT / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({k: report[k] for k in ('passed', 'failed', 'jsErrors')}, ensure_ascii=False))
raise SystemExit(bool(report['failed'] or ERRORS))
