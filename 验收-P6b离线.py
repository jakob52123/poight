"""Keep native file:// playback working when Chromium disallows backdrop readback."""
import json
import time
from importlib import import_module

from playwright.sync_api import sync_playwright

helpers = import_module('验收-爆点空心')
ROOT = helpers.ROOT
OUT = ROOT / '验收记录/P6b'


def main():
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.on('pageerror', lambda e: errors.append(e.stack))
        page.goto((ROOT / '候选试玩.html').as_uri() + '?test=1')
        helpers.ready(page)
        catalog = page.evaluate('window.__waterTest.catalog()')
        profile = page.evaluate('window.__waterTest.snapshot().profile')
        for scene in ['emerald-rustborocity', 'arena-formal', 'arena-natural']:
            page.evaluate('(p)=>window.__waterTest.select(p)', {
                **profile, 'map': scene, 'player': 25, 'enemy': 6,
                'playerMoves': ['thunderbolt', 'thunder', 'quickattack', 'irontail'],
                'enemyMoves': next(r for r in catalog['roster'] if r['id'] == 6)['defaultMoves'],
            })
            page.evaluate('''()=>{const api=window.__waterTest;api.reset(true);
              const b=api.snapshot().environment.bounds,x=(b.left+b.right)/2;
              const y=(b.top+b.bottom)/2;
              api.arrange({ai:false,player:{x:x-30,y,a:0},enemy:{x:x+30,y}});
              api.step(0);api.cast('player','thunderbolt');
              for(let i=0;i<150;i++)api.step(1/120); }''')
            time.sleep(.02)
        browser.close()
    report = {'passed': 3 if not errors else 0, 'failed': int(bool(errors)),
              'jsErrors': len(errors), 'errors': errors}
    (OUT / '离线验收.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False))
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
