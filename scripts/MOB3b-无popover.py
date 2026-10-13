"""Old-browser Popover API simulation: real KO, visible result, rematch, real KO again."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audit', ROOT / '验收-手机适配.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
OUT = ROOT / '验收记录/MOB3b/无popover'
OUT.mkdir(parents=True, exist_ok=True)
checks, errors = [], []
INIT = r"""(() => {
  for (const name of ['showPopover', 'hidePopover', 'togglePopover'])
    delete HTMLElement.prototype[name];
  const matches = Element.prototype.matches;
  Element.prototype.matches = function(selector) {
    if (String(selector).includes(':popover-open'))
      throw new DOMException('Unsupported :popover-open selector', 'SyntaxError');
    return matches.call(this, selector);
  };
})();"""


def check(name, ok):
    checks.append({'name': name, 'ok': bool(ok)})
    if not ok:
        print('FAIL ' + name, flush=True)


with sync_playwright() as pw:
    for engine in ['chromium', 'webkit']:
        browser = getattr(pw, engine).launch(headless=True)
        for width, height, touch in [(844, 390, True), (1440, 900, False)]:
            label = f'{engine}-{width}x{height}'
            context = browser.new_context(viewport={'width': width, 'height': height},
                                          has_touch=touch, is_mobile=touch)
            page = context.new_page()
            page.on('pageerror', lambda e, label=label: errors.append({'device': label, 'error': str(e)}))
            page.add_init_script(INIT)
            page.goto(os.environ['POIGHT_TEST_URL'].rstrip('/') + '/?test=1&lazy=1')
            audit.poll(page, '() => window.__waterTest?.snapshot().artReady', 60)
            check(label + ' Popover API absent', page.evaluate('typeof HTMLElement.prototype.showPopover === "undefined"'))
            check(label + ' unsupported selector throws SyntaxError', page.evaluate('''() => {
              try { document.body.matches(':popover-open'); return false; }
              catch (e) { return e.name === 'SyntaxError'; }
            }'''))
            page.evaluate('__waterTest.reset(true)')
            for round_no in [1, 2]:
                page.evaluate('''() => {
                  const t = __waterTest;
                  t.arrange({ai:false,enemy:{hp:1,hurt:0}});
                  t.testDamage('enemy',999); t.step(.3);
                }''')
                audit.poll(page, '() => __waterTest.snapshot().phase === "over" && !document.querySelector("#matchOverlay").hidden')
                result = page.locator('#matchOverlay')
                check(label + f' round {round_no} result visible', result.is_visible())
                check(label + f' round {round_no} fallback has no popover', not result.evaluate('e => e.hasAttribute("popover")'))
                check(label + f' round {round_no} rematch is topmost', page.locator('#gbaRematch').evaluate('''e => {
                  const r=e.getBoundingClientRect(), hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
                  return hit === e || e.contains(hit);
                }'''))
                page.screenshot(path=OUT / f'{label}-round{round_no}.png', scale='css')
                if round_no == 1:
                    if touch:
                        page.locator('#gbaRematch').tap()
                    else:
                        page.locator('#gbaRematch').click()
                    check(label + ' rematch resumes and hides result', page.evaluate('''
                      __waterTest.snapshot().phase === 'playing' && document.querySelector('#matchOverlay').hidden
                    '''))
            page.locator('#gbaChange').click()
            check(label + ' change Pokemon opens setup', page.locator('#setup').evaluate('e => e.open'))
            context.close()
        browser.close()
report = {'candidateSHA256': hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest(),
          'passed': sum(c['ok'] for c in checks), 'failed': sum(not c['ok'] for c in checks),
          'jsErrors': len(errors), 'checks': checks, 'errors': errors}
(OUT / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print('NO_POPOVER_SUMMARY ' + json.dumps({k: report[k] for k in ['passed', 'failed', 'jsErrors']}), flush=True)
raise SystemExit(bool(report['failed'] or report['jsErrors']))
