"""MOB2 assertions; execute through tools/远程执行.sh on port 8977."""
import argparse
import importlib.util
import json
import os
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent.resolve()
OUT = ROOT / '验收记录/MOB2'
OUT.mkdir(parents=True, exist_ok=True)
URL = os.environ['POIGHT_TEST_URL'].rstrip('/')
spec = importlib.util.spec_from_file_location('audit', ROOT / '验收-手机适配.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
CHECKS, ERRORS, RECORDS = [], [], []
ROSTER_COUNT = len(json.loads((ROOT / '首发200.json').read_text())['ids'])


def check(name, ok, detail=None):
    CHECKS.append({'name': name, 'ok': bool(ok), 'detail': detail})


def selection(pw, device, height_loss):
    d = dict(pw.devices[device])
    engine = d.pop('default_browser_type')
    v = d['viewport']
    d['viewport'] = {'width': v['height'], 'height': v['width'] - height_loss}
    browser = getattr(pw, engine).launch(headless=True)
    context = browser.new_context(**d)
    p = context.new_page()
    p.on('pageerror', lambda e: ERRORS.append(str(e)))
    name = f'{device}-{height_loss}'
    try:
        p.goto(URL + '/?observe=1', wait_until='domcontentloaded')
        audit.poll(p, '() => document.querySelector("#setup").open')
        m = p.evaluate(audit.METRICS)
        cards = [t for t in m['targets'] if t['id']]
        check(name + '-50 cards >=44', len(cards) == ROSTER_COUNT and
              all(t['width'] >= 44 and t['height'] >= 44 for t in cards), cards[0])
        confirm = next(t for t in m['targets'] if t['selector'] == '#startBattle')
        check(name + '-confirm initially visible', not confirm['clipped'] and confirm['centerHit'], confirm)
        p.locator('#roster .mon:last-child').tap(timeout=4000)
        check(name + '-select 50', p.locator('#roster .mon:last-child').get_attribute('data-player') == 'true')
        p.locator('#toggleLoadout').tap()
        loadout = p.evaluate(audit.METRICS)
        catalog = [t for t in loadout['targets'] if '.move-card' in t['selector']]
        check(name + '-catalog visible', any(t['visibleHeight'] >= 25 for t in catalog), catalog[:1])
        check(name + '-single scroll owner', p.locator('#loadoutPanel').evaluate(
            'e => getComputedStyle(e).overflowY === "auto" && getComputedStyle(document.querySelector("#moveCatalog")).overflowY === "visible"'))
        p.locator('.ai-options summary').tap()
        p.locator('#difficulty button').last.tap()
        check(name + '-scrolled role statistics >=12', p.locator('#selectedStats').evaluate(
            'e => parseFloat(getComputedStyle(e).fontSize) >= 12'))
        p.locator('#closeMoves').tap()
        check(name + '-sticky nav reachable after AI', p.locator('#loadoutPanel').is_hidden())
        RECORDS.append({'name': name, 'metrics': m, 'loadout': loadout})
    finally:
        context.close()
        browser.close()


def overlap(a, b):
    if 'parts' in a or 'parts' in b:
        return any(overlap(x, y) for x in a.get('parts', [a]) for y in b.get('parts', [b]))
    return min(a['x'] + a['width'], b['x'] + b['width']) - max(a['x'], b['x']) > 0.5 and \
        min(a['y'] + a['height'], b['y'] + b['height']) - max(a['y'], b['y']) > 0.5


def live(pw, device):
    d = dict(pw.devices[device])
    engine = d.pop('default_browser_type')
    browser = getattr(pw, engine).launch(headless=True)
    context = browser.new_context(**d)
    p = context.new_page()
    p.on('pageerror', lambda e: ERRORS.append(str(e)))
    try:
        p.goto(URL + '/?observe=1', wait_until='domcontentloaded')
        audit.poll(p, '() => document.querySelector("#setup").open')
        check(device + '-portrait selection unblocked', not p.locator('#rotatePhone').is_visible())
        p.locator('#roster .mon:last-child').tap()
        p.locator('#toggleLoadout').tap()
        check(device + '-portrait loadout unblocked', not p.locator('#rotatePhone').is_visible())
        p.locator('#closeMoves').tap()
        p.locator('#startBattle').tap()
        audit.poll(p, '() => window.__waterTest.snapshot().artReady')
        audit.poll(p, '() => !document.querySelector("#vsScreen").hidden')
        check(device + '-portrait VS unblocked', not p.locator('#rotatePhone').is_visible())
        p.locator('#vsContinue').tap()
        audit.poll(p, '() => document.querySelector("#rotatePhone").matches(":popover-open")')
        check(device + '-first start copy', p.locator('#rotatePhone h2').inner_text() == '请横屏开始')
        before = p.evaluate('window.__waterTest.snapshot()')
        p.keyboard.press('r')
        p.keyboard.press('j')
        p.touchscreen.tap(20, 100)
        p.wait_for_timeout(120)
        after = p.evaluate('window.__waterTest.snapshot()')
        check(device + '-portrait does not start or reset', after['phase'] == 'idle' and
              after['matchSeconds'] == before['matchSeconds'] and
              after['player']['spent'] == before['player']['spent'])
        check(device + '-real top layer barrier', p.evaluate('''() => {
          const e=document.elementFromPoint(20,100);
          return !!e?.closest('#rotatePhone') && document.querySelector('#app').inert;
        }'''))
        p.set_viewport_size({'width': d['viewport']['height'], 'height': d['viewport']['width']})
        audit.poll(p, '() => window.__waterTest.snapshot().phase === "playing"')
        p.locator('#battleMenuButton').tap()
        check(device + '-menu pauses', p.evaluate('window.__waterTest.snapshot().phase') == 'paused')
        p.locator('#gbaMenuReturn').tap()
        check(device + '-explicit return resumes', p.evaluate('window.__waterTest.snapshot().phase') == 'playing')
        p.locator('#battleMenuButton').tap()
        p.locator('#sound').tap()
        p.locator('#battleMenuButton').tap()
        p.locator('#gbaMenuReturn').tap()
        check(device + '-explicit return resumes an already paused match',
              p.evaluate('window.__waterTest.snapshot().phase') == 'playing')
        p.locator('#battleMenuButton').tap()
        p.locator('#help').tap()
        p.locator('#gbaHelpClose').tap()
        check(device + '-help explicit return resumes', p.evaluate('window.__waterTest.snapshot().phase') == 'playing')
        p.set_viewport_size(d['viewport'])
        p.wait_for_timeout(70)
        before = p.evaluate('window.__waterTest.snapshot()')
        check(device + '-rotation paused copy', before['phase'] == 'paused' and
              p.locator('#rotatePhone h2').inner_text() == '对战已暂停')
        p.keyboard.press('r')
        p.keyboard.down('d')
        p.touchscreen.tap(d['viewport']['width'] - 20, d['viewport']['height'] - 20)
        p.wait_for_timeout(150)
        p.keyboard.up('d')
        after = p.evaluate('window.__waterTest.snapshot()')
        check(device + '-rotation freezes clocks and HP', all(after[k] == before[k]
              for k in ['elapsed', 'matchSeconds']) and
              after['player']['hp'] == before['player']['hp'] and
              after['player']['x'] == before['player']['x'])
        p.set_viewport_size({'width': 568, 'height': 320})
        p.goto(URL + '/?test=1&lazy=1')
        audit.poll(p, '() => window.__waterTest?.snapshot().artReady', 60)
        p.evaluate('window.__waterTest.reset(true)')
        p.evaluate('window.__waterTest.arrange({ai:false})')
        p.evaluate('''() => {for(const style of document.querySelectorAll('style'))
          style.textContent=style.textContent.replace(/env\\(safe-area-inset-(top|bottom|left|right)(?:,[^)]*)?\\)/g,
          (_,s)=>({top:'47px',bottom:'34px',left:'47px',right:'44px'})[s]);}''')
        p.evaluate('window.__waterTest.render()')
        m = p.evaluate(audit.METRICS)
        for s in ['#battleMenuButton', '#mobileActions', '.hud', '#battleRail']:
            b = m['boxes'][s]
            check(device + '-all four safe insets ' + s,
                  b['x'] >= 47 and b['y'] >= 47 and b['right'] <= 568 - 44 and b['bottom'] <= 320 - 34, b)
        for a, b in [('#battleMenuButton', '#mobileActions'), ('#battleMenuButton', '.hud'),
                     ('#battleRail', '.hud'), ('#battleRail', '#mobileActions')]:
            check(device + '-safe non-overlap ' + a + b, not overlap(m['boxes'][a], m['boxes'][b]))
        minimap = m['state']['arenaView']['minimap']
        check(device + '-safe minimap >=8 margin', minimap['x'] >= 55 and minimap['y'] >= 55 and
              minimap['x'] + minimap['width'] <= 568 - 52 and
              minimap['y'] + minimap['height'] <= 320 - 42, minimap)
        p.evaluate('''() => {
          Object.defineProperty(visualViewport, 'height', {configurable:true, value:232});
          visualViewport.dispatchEvent(new Event('resize'));
          window.__waterTest.render();
        }''')
        check(device + '-visual viewport height without innerHeight resize', p.evaluate('''() =>
          innerHeight === 320 && document.querySelector('#app').getBoundingClientRect().height === 232
          && window.__waterTest.snapshot().arenaView.minimap.y >= 55
          && window.__waterTest.snapshot().arenaView.minimap.y +
             window.__waterTest.snapshot().arenaView.minimap.height <= 190
          && Math.abs(window.__waterTest.snapshot().viewport.height *
             window.__waterTest.snapshot().viewport.scale - 232) < .01
          && document.querySelector('#game').height === 232 * Math.min(devicePixelRatio, 2)'''))
        p.evaluate('''() => {
          delete visualViewport.height;
          visualViewport.dispatchEvent(new Event('resize'));
        }''')
        p.evaluate('window.__waterTest.arrange({ai:false,player:{hp:0}})')
        p.evaluate('window.__waterTest.step(.01)')
        p.evaluate('window.__waterTest.render()')
        check(device + '-result top layer', p.evaluate('document.querySelector("#matchOverlay").matches(":popover-open")'))
        check(device + '-over hides operation HUD', all(not p.locator(s).is_visible() for s in
              ['.hud', '#mobileActions', '#mobileJoystick', '#battleRail', '#battleMenuButton']))
        p.screenshot(path=OUT / f'{device}-safe-result.png', scale='css')
    finally:
        context.close()
        browser.close()


def desktop(pw):
    browser = pw.chromium.launch(headless=True)
    images = []
    content = (OUT / '基线.html').read_text()
    for baseline in [True, False]:
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        p = context.new_page()
        p.on('pageerror', lambda e: ERRORS.append(str(e)))
        if baseline:
            p.route(URL + '/?test=1&lazy=1', lambda route: route.fulfill(body=content, content_type='text/html'))
        p.goto(URL + '/?test=1&lazy=1')
        audit.poll(p, '() => window.__waterTest?.snapshot().artReady', 60)
        p.evaluate('window.__waterTest.reset(true)')
        p.evaluate('window.__waterTest.arrange({ai:false})')
        p.evaluate('window.__waterTest.step(.01)')
        p.evaluate('window.__waterTest.render()')
        dest = OUT / ('desktop-before.png' if baseline else 'desktop-after.png')
        p.screenshot(path=dest)
        images.append(Image.open(dest).convert('RGB'))
        context.close()
    diff = ImageChops.difference(*images)
    changed = sum(pixel != (0, 0, 0) for pixel in diff.getdata())
    diff.save(OUT / 'desktop-diff.png')
    check('desktop 1440x900 pixel difference is zero', changed == 0, changed)
    browser.close()


def matrix():
    data = json.loads((ROOT / os.environ.get('POIGHT_MOB_OUT', '验收记录/MOB') / '审计数据.json').read_text())
    check('48 production combinations', len(data['production']) == 48)
    expected_paused = []
    html = (ROOT / '候选试玩.html').read_text()
    roster_ids = [c['id'] for c in json.JSONDecoder().raw_decode(html.split('const DATA = ', 1)[1])[0]['roster']]
    for r in data['production']:
        name = f"{r['device']}-{r['direction']}-{r['variant']}"
        # MOB3 intentionally pauses these four unusably short battle viewports.
        # Require the real barrier and paused game, not a silently incomplete pass.
        if r['incomplete'] and r['variant'] == '工具栏180' and r['device'] in ['iPhone SE', 'Galaxy S9+']:
            m = r['steps'].get('异常现场', {})
            check(name + '-designed short-screen pause', bool(m) and m['rotateOpen'] and
                  m['state']['phase'] == 'paused' and m['viewport']['height'] < 210, m.get('state', {}).get('phase'))
            check(name + '-no JS errors during designed pause', not r['errors'], r['errors'])
            expected_paused.append(name)
            ERRORS.extend(r['errors'])
            continue
        check(name + '-production complete', not r['incomplete'], r['incomplete'])
        check(name + '-no page horizontal overflow', all(m['document']['clientWidth'] ==
              m['document']['scrollWidth'] for m in r['steps'].values()))
        required_steps = ['06-VS开场', '02-选人全屏', '05-配招', '07-对战中', '09-菜单']
        missing = [step for step in required_steps if step not in r['steps']]
        missing += [key for key in ['landscapeBattle', 'menuPhase', 'rotation'] if key not in r]
        check(name + '-all assertion stages observed', not missing, missing)
        if missing:
            ERRORS.extend(r['errors'])
            continue  # Explicit failed/incomplete record, never a passing substitution.
        vs = next((t for t in r['steps']['06-VS开场']['targets'] if t['selector'] == '#vsContinue'), None)
        check(name + '-VS skip visible', bool(vs) and not vs['clipped'] and vs['centerHit'], vs)
        m = r['steps']['02-选人全屏']
        check(name + '-selection not blocked', not m['rotateOpen'])
        cards = [t for t in m['targets'] if t['id']]
        s2 = m.get('selection', {}).get('layout') == 'S2'
        group = m.get('selection', {}).get('group')
        expected = sum((i <= 151) == (group == 'initial') for i in roster_ids) if s2 else len(roster_ids)
        check(name + '-current group all targets >=44', len(cards) == expected and all(t['width'] >= 44 and t['height'] >= 44 for t in cards))
        t = next(t for t in m['targets'] if t['selector'] == '#startBattle')
        check(name + '-confirm visible from first frame', not t['clipped'] and t['centerHit'], t)
        m = r['steps']['05-配招']
        check(name + '-portrait loadout allowed', not m['rotateOpen'])
        required = 44 if m['viewport']['height'] <= 220 else 25
        check(name + '-catalog initially has visible card', any(t['visibleHeight'] >= required
              for t in m['targets'] if '.move-card' in t['selector']))
        check(name + '-native select last pokemon', any(a['ok'] for a in r['actions'] if a['name'] == '点当前页末只'))
        m = r['landscapeBattle']
        height, width = m['viewport']['height'], m['viewport']['width']
        expected_boxes = ['#mobileActions', '#battleMenuButton', '.hud']
        check(name + '-all battle controls observed', all(s in m['boxes'] for s in expected_boxes), list(m['boxes']))
        if not all(s in m['boxes'] for s in expected_boxes):
            ERRORS.extend(r['errors'])
            continue
        for s in expected_boxes:
            b = m['boxes'][s]
            check(name + '-battle viewport ' + s, b['x'] >= 0 and b['y'] >= 0 and
                  b['right'] <= width + .5 and b['bottom'] <= height + .5, b)
        for a, b in [('#battleMenuButton', '#mobileActions'), ('#battleMenuButton', '.hud')]:
            check(name + '-battle non-overlap ' + a + b, not overlap(m['boxes'][a], m['boxes'][b]))
        mini = m['state']['arenaView']['minimap']
        check(name + '-minimap >=8 margins', mini['x'] >= 8 and mini['y'] >= 8 and
              mini['x'] + mini['width'] <= width - 8 and mini['y'] + mini['height'] <= height - 8, mini)
        check(name + '-menu paused', r['menuPhase'] == 'paused')
        check(name + '-rotation preserved and paused', r['rotation']['idsPreserved'] and
              r['rotation']['portraitPhase'] == 'paused')
        result = r['steps'].get('14-自然胜负')
        check(name + '-natural result over and controls hidden', bool(result) and
              result['state']['phase'] == 'over' and all(s not in result['boxes'] for s in
              ['.hud', '#mobileActions', '#mobileJoystick', '#battleRail', '#battleMenuButton']))
        for step in ['02-选人全屏', '05-配招', '07-对战中', '09-菜单']:
            m = r['steps'][step]
            check(name + '-' + step + '-text >=12 / S2 selector >=9', not m['texts'], m['texts'])
            small = [t for t in m['targets'] if t['small'] and not t['disabled']]
            check(name + '-' + step + '-targets >=44 / S2 tags23 cards32', not small, small)
        ERRORS.extend(r['errors'])
    check('exactly four designed 工具栏180 pauses', len(expected_paused) == 4, expected_paused)
    for r in data['input']:
        for panel in ['roster', 'loadout']:
            if panel not in r.get('scrollGesture', {}):
                check(r['device'] + '-native ' + panel + ' swipe observed', False, r['checks'])
                continue
            gesture = r['scrollGesture'][panel]
            overflow = gesture['scrollHeight'] > gesture['clientHeight'] + 1
            catalog = r['scrollGesture']['catalog'] if panel == 'loadout' else {}
            # Catalog swipes scroll this same single owner, not a nested catalog.
            delta = max(gesture.get('delta', 0), catalog.get('delta', 0)
                        if catalog.get('owner') == '#loadoutPanel' else 0)
            check(r['device'] + '-native ' + panel + ' swipe or all content fits',
                  delta > 0 if overflow else delta == 0 and gesture['clientHeight'] > 0,
                  {'surface': gesture, 'catalog': catalog, 'ownerDelta': delta})
        ERRORS.extend(r['errors'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', default='live')
    args = parser.parse_args()
    if args.stage == 'matrix':
        matrix()
    else:
        with sync_playwright() as pw:
            for device in audit.DEVICES:
                for loss in [0, 180]:
                    selection(pw, device, loss)
            if args.stage == 'live':
                for device in ['iPhone SE', 'Pixel 7']:
                    live(pw, device)
                desktop(pw)
    report = {'passed': sum(c['ok'] for c in CHECKS), 'failed': sum(not c['ok'] for c in CHECKS),
              'jsErrors': len(ERRORS), 'checks': CHECKS, 'errors': ERRORS, 'records': RECORDS,
              'stage': args.stage}
    (OUT / f'{args.stage}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('MOB2_SUMMARY ' + json.dumps({k: report[k] for k in ['passed', 'failed', 'jsErrors']}))
    raise SystemExit(bool(report['failed'] or report['jsErrors']))


if __name__ == '__main__':
    main()
