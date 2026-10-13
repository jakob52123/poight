"""Production cold-load budgets + real lazy eight-move and full dependency smoke tests."""
import json
import os
from pathlib import Path

from playwright.sync_api import Error, sync_playwright

from scripts.perf_network import measure, poll

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/首开加载'
checks, errors = [], []


def check(name, ok, detail=None):
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
    assert ok, (name, detail)


try:
    default_report = measure('after-7v4', pair=(7, 4))
    for phase, budget in [('selection', 1000000), ('battle', 1000000)]:
        check(f'7v4 {phase} <= {budget} bytes', default_report[phase]['bytes'] <= budget,
              default_report[phase])
        check(f'7v4 {phase} within R200 seconds budget', default_report[phase]['seconds'] <= (3.5 if phase == 'selection' else 6))
    check('7v4 no JS/network errors or 404', not default_report['errors'] and all(
        r['status'] == 200 for r in default_report['requests']), default_report['errors'])
    report = measure('after')
    check('cold selection <= 1000000 wire bytes', report['selection']['bytes'] <= 1000000,
          report['selection'])
    check('cold selection <= 3.5 seconds', report['selection']['seconds'] <= 3.5)
    check('VS to playable <= 1000000 additional wire bytes', report['battle']['bytes'] <= 1000000,
          report['battle'])
    check('VS to playable <= 6 seconds including VS animation', report['battle']['seconds'] <= 6)
    check('total including 25/6 selection portraits <= 1500000', report['totalWithPicks'] <= 1500000)
    check('production no JS/network errors or 404', not report['errors'] and all(
        r['status'] == 200 for r in report['requests']), report['errors'])
    selection_urls = [r['url'] for r in report['requests'] if r['phase'] == 'selection']
    check('selection no move atlases, character actions or terrain', all(
        any(key in url for key in ['/?', '/assets/icons-', '/assets/portrait-', '/assets/favicon-'])
        for url in selection_urls), selection_urls)
    check('no external JS resource', all(not r['url'].split('?')[0].endswith('.js')
                                        for r in report['requests']))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        cancel_page = browser.new_page(viewport={'width': 1440, 'height': 900})
        cancel_page.on('pageerror', lambda e: errors.append(str(e)))
        cancel_page.goto(os.environ['POIGHT_TEST_URL'].rstrip('/') + '/?observe=1')
        poll(cancel_page, '() => document.querySelector("#setup").open')
        check('fresh selection has not prepared a hidden battle', cancel_page.evaluate(
            '!window.__waterTest.snapshot().artReady'))
        cancel_page.locator('#closeSetup').click()
        poll(cancel_page, '() => window.__waterTest.snapshot().artReady && !document.querySelector("#setup").open')
        check('X cancels draft and prepares unchanged default match', cancel_page.evaluate(
            '() => { const s=window.__waterTest.snapshot(); return s.phase === "idle" && s.player.id === 7 && s.enemy.id === 4; }'))
        cancel_page.locator('#game').click()
        check('cancelled selection still allows normal start', cancel_page.evaluate(
            'window.__waterTest.snapshot().phase === "playing"'))
        cancel_page.close()
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        requests = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('request', lambda r: requests.append(r.url))
        page.on('response', lambda r: errors.append(f'HTTP {r.status}: {r.url}')
                if r.status >= 400 else None)
        # Unlike the existing arbitrary-equip fixture, lazy=1 uses exactly the
        # production preloader; no full-library warmup can hide missing dependencies.
        page.goto(os.environ['POIGHT_TEST_URL'].rstrip('/') + '/?test=1&lazy=1')
        poll(page, '() => window.__waterTest?.snapshot().artReady', timeout=30)
        catalog = page.evaluate('window.__waterTest.catalog()')
        roster = {c['id']: c for c in catalog['roster']}
        profile = page.evaluate('window.__waterTest.snapshot().profile')
        profile.update(player=25, enemy=6, playerMoves=roster[25]['defaultMoves'],
                       enemyMoves=roster[6]['defaultMoves'], map='arena-formal')
        selected = page.evaluate('(p) => window.__waterTest.select(p)', profile)
        # Reload the saved 25/6 profile: all JS image maps are now fresh, so the
        # preceding 7/4 fixture cannot mask an omitted dependency in these eight.
        page.reload()
        poll(page, '() => window.__waterTest?.snapshot().artReady', timeout=30)
        check('fresh lazy 25 vs 6 has no legacy atlas warmup', selected and page.evaluate(
            'window.__waterTest.snapshot().generated.loaded === 0'))
        page.wait_for_timeout(100)
        before_cast = len(requests)
        for side, ident in [('player', 25), ('enemy', 6)]:
            for mid in roster[ident]['defaultMoves']:
                result = page.evaluate('''({side, mid}) => {
                  const t = window.__waterTest;
                  t.reset(true);
                  t.arrange({ai:false, player:{x:450,y:500,a:0},
                    enemy:{x:505,y:500,a:Math.PI}});
                  const cast = t.cast(side, mid);
                  let drawn = false;
                  for(let i=0;i<180;i++) {
                    t.step(1/120);
                    drawn ||= t.snapshot().generated.drawn.includes(mid);
                  }
                  return {cast,drawn,loaded:t.snapshot().generated.loaded};
                }''', {'side': side, 'mid': mid})
                check(mid + ' casts with preloaded visible artwork', result['cast'] and result['drawn'], result)
                page.screenshot(path=str(OUT / 'after' / f'{mid}.png'))
        check('eight casts issue no late image requests', len(requests) == before_cast,
              requests[before_cast:])
        # Every learnable move gets a real match preload and rendered cast. This
        # specifically covers VA2/VB1/old raster dependencies without eager fixtures.
        for mid in catalog['moves']:
            caster = next(c for c in catalog['roster'] if mid in c['learnset'])
            p = {**profile, 'player': caster['id'], 'playerMoves': [mid],
                 'enemy': 129, 'enemyMoves': ['splash']}
            check(mid + ' lazy preload', page.evaluate('(p) => window.__waterTest.select(p)', p))
            # Fresh JS image maps for every move: preceding casts cannot hide missing keys.
            page.reload()
            poll(page, '() => window.__waterTest?.snapshot().artReady', timeout=30)
            page.wait_for_timeout(50)
            before_cast = len(requests)
            result = page.evaluate('''mid => {
              const t=window.__waterTest;
              t.reset(true);
              t.arrange({ai:false,player:{x:450,y:500,a:0,hp:50},enemy:{x:505,y:500,a:Math.PI}});
              const proto=window.PoightMoveAnimations.prototype, path=proto.path;
              let pathDrawn=false;
              proto.path=function(ctx,id,...args) {
                const result=path.call(this,ctx,id,...args);
                if(id===mid) pathDrawn=true;
                return result;
              };
              const cast=t.cast('player',mid);
              let drawn=false;
              for(let i=0;i<240;i++) {
                t.step(1/120);
                const s=t.snapshot();
                drawn ||= s.generated.drawn.includes(mid) || pathDrawn ||
                  (mid==='splash' && s.player.flightHeight>0);
              }
              proto.path=path;
              return {cast,drawn};
            }''', mid)
            page.wait_for_timeout(50)
            check(mid + ' lazy rendered cast', result['cast'] and result['drawn'], result)
            check(mid + ' no late image requests', len(requests) == before_cast,
                  requests[before_cast:])
        check('lazy matrix no JS/404 errors', not errors, errors)
        browser.close()
except (AssertionError, Error, TimeoutError, OSError, ValueError) as exc:
    checks.append({'name': 'completed', 'ok': False, 'detail': repr(exc)})
finally:
    result = {'passed': sum(c['ok'] for c in checks),
              'failed': sum(not c['ok'] for c in checks),
              'jsErrors': len(errors), 'errors': errors, 'checks': checks}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / '验收.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(bool(result['failed'] or errors))
