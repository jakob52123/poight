"""Final contract blockers: exact cold bytes, stale full-suite fixture and Firefox.
Run serially via tools/远程执行.sh, never adjust production to fit old assertions.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.perf_network import measure, poll

OUT = ROOT / '验收记录/AUD'
network = measure('AUD-final', pair=(7, 4))
baseline = json.loads((OUT / '首开严格对照.json').read_text())
baseline_html = OUT / 'cd1e796-baseline/候选试玩.html'
comparison = {
    'baselineCommit': 'cd1e796',
    'baselineSHA': hashlib.sha256(baseline_html.read_bytes()).hexdigest(),
    'candidateSHA': hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest(),
    'baselineMeasurementSHAValid': hashlib.sha256(baseline_html.read_bytes()).hexdigest() == baseline['baselineSHA'],
    'baseline': baseline['baseline'], 'AUD': network['selection'],
    'deltaBytes': network['selection']['bytes'] - baseline['baseline']['bytes'],
    'identicalBytes': network['selection']['bytes'] == baseline['baseline']['bytes'],
    'musicBytesOnFirstOpen': sum(r['bytes'] for r in network['requests'] if r['phase'] == 'selection' and '.mp3' in r['url']),
    'errors': network['errors'],
}
(OUT / '收尾首开严格对照.json').write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + '\n')
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(os.environ['POIGHT_TEST_URL'].rstrip('/') + '/?test=1')
    poll(page, '()=>__waterTest?.snapshot().artReady')
    actual = page.evaluate('''()=>{
      const r=__waterTest.catalog().roster, me=r.find(c=>c.id===7);
      __waterTest.select({player:7,enemy:7,playerMoves:me.defaultMoves,enemyMoves:me.defaultMoves,tier:'great'});
      __waterTest.reset(true);__waterTest.arrange({ai:false});
      const s=__waterTest.snapshot();
      return {progressbars:document.querySelectorAll('[role="progressbar"]').length,
        hp:s.player.hp,maxHP:s.player.maxHP,stamina:s.player.stamina,map:s.profile.map,
        viewport:s.viewport,world:s.world};
    }''')
    actual['jsErrors'] = errors
    browser.close()
(OUT / '完整版旧断言取证.json').write_text(json.dumps(actual, ensure_ascii=False, indent=2) + '\n')
with (OUT / 'Firefox收尾复测.log').open('w') as out:
    try:
        p = subprocess.run([sys.executable, str(OUT / '测原生循环.py'), 'firefox'], cwd=ROOT,
                           stdout=out, stderr=subprocess.STDOUT, timeout=50)
        firefox_rc = p.returncode
    except subprocess.TimeoutExpired:
        firefox_rc = 124
        out.write('\nFirefox driver timed out after 50 seconds.\n')
seams = json.loads((OUT / '原生循环.json').read_text())
seam_checks = {engine: all('gapMS' in seams[engine][ident] and seams[engine][ident]['gapMS'] <= 60
                          for ident in ['c01','c02','c03','c04','c05','c06','c09','c15'])
               and not seams[engine].get('jsErrors') for engine in ['chromium','webkit']}
checks = {
    'baseline measured SHA matches': comparison['baselineMeasurementSHAValid'],
    'first-open exact baseline bytes': comparison['identicalBytes'],
    'first-open zero MP3 bytes': comparison['musicBytesOnFirstOpen'] == 0,
    'cold-load zero JS/network errors': not comparison['errors'],
    'Chromium native loops <=60ms': seam_checks['chromium'],
    'WebKit native loops <=60ms': seam_checks['webkit'],
    'Firefox native-loop measurement completed': firefox_rc == 0,
}
report = {'passed': sum(checks.values()), 'failed': sum(not v for v in checks.values()),
          'jsErrors': len(errors) + len(comparison['errors']), 'checks': checks,
          'firefoxReturncode': firefox_rc, 'coldBytes': comparison, 'fullFixtureActual': actual}
(OUT / '收尾契约阻塞.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
sys.exit(bool(report['failed']))
