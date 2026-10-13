"""Run via tools/远程执行.sh 8999. Own IPv6 collector shares only the allocated port."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener

from playwright.sync_api import Error, sync_playwright

from scripts.perf_network import poll
from scripts.埋点日报 import EVENTS, FIELDS, load, parse_line

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/埋点'
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / 'events.jsonl'
LOG.write_text('')
checks, errors, csp, requests = [], [], [], []
collector = None
browser = None
opener = build_opener(ProxyHandler({}))
port = urlsplit(os.environ['POIGHT_TEST_URL']).port
URL = f'http://localhost:{port}/'


def check(name, ok, detail=None):
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
    assert ok, (name, detail)


def page(context, suffix, init=None):
    if init:
        context.add_init_script(init)
    p = context.new_page()
    p.on('pageerror', lambda e: errors.append(str(e)) if 'EVT_EXPECTED' not in str(e) else None)
    p.on('console', lambda m: csp.append(m.text) if 'Content Security Policy' in m.text or
         'violates' in m.text or 'Refused to' in m.text else None)
    p.on('request', lambda r: requests.append(r.url))
    p.goto(URL + suffix, wait_until='domcontentloaded')
    return p


def rows():
    return load(LOG)[0]


def count(event=None):
    return sum(event is None or e['e'] == event for e in rows())


def wait_event(p, name, minimum=1):
    deadline = time.monotonic() + 15
    while count(name) < minimum:
        assert time.monotonic() < deadline, ('missing event', name, minimum)
        p.wait_for_timeout(50)


def click(p, selector):
    if selector == '#setupButton' and p.locator('#gbaChange').is_visible():
        selector = '#gbaChange'
    if not p.locator(selector).is_visible():
        p.locator('#battleMenuButton').click()
    p.locator(selector).click()


def start(p):
    p.locator('#startBattle').click()
    poll(p, '() => window.__waterTest.snapshot().phase === "playing" && document.querySelector("#vsScreen").hidden', 30)
    p.wait_for_timeout(1100)


def win(p):
    # Real successful keyboard cast/damage/finish path; only fixture HP/positions and
    # simulation time are controlled. No direct telemetry finish calls.
    p.evaluate('''() => window.__waterTest.arrange({ai:false,
      player:{x:450,y:500,a:0,hurt:0,stamina:100},
      enemy:{x:505,y:500,a:Math.PI,hp:1,hurt:0}})''')
    p.keyboard.press('j')
    p.evaluate('() => window.__waterTest.step(8)')
    check('actual cast finishes a winning battle', p.evaluate(
        '() => window.__waterTest.snapshot().phase === "over"'))
    p.wait_for_timeout(1200)


try:
    check('only allocated EVT/M8X/M9/MOB3/R200/AUD/UI3b/M10 port', port in (
        8999, 8978, 8979, 8981, 8982, 8983, 8984, 8985,
        *range(8986, 8998), *range(9000, 9012)))
    collector_log = (OUT / 'collector.log').open('w')
    collector = subprocess.Popen([sys.executable, str(ROOT / '预览服务.py'), '--candidate',
        '--host', 'localhost', '--port', str(port), '--collect', str(LOG)], cwd=ROOT,
        stdout=collector_log, stderr=subprocess.STDOUT)
    (OUT/'collector-process.json').write_text(json.dumps({'pid': collector.pid}))
    for _ in range(100):
        try:
            with opener.open(URL, timeout=2) as response:
                check('CSP connect none unchanged', "connect-src 'none'" in response.headers['Content-Security-Policy'])
            break
        except OSError:
            time.sleep(.1)
    else:
        raise TimeoutError('collector did not start')
    with opener.open(os.environ['POIGHT_TEST_URL'] + 'e?v=1', timeout=2) as response:
        raise AssertionError(('uncollected /e unexpectedly active', response.status))
except (OSError, AssertionError, TimeoutError) as exc:
    # Expected HTTP404 from wrapper's default non-collecting preview.
    if getattr(exc, 'code', None) != 404:
        checks.append({'name': 'collector startup', 'ok': False, 'detail': repr(exc)})
    else:
        check('no --collect leaves /e at old 404', True)

try:
    assert collector and collector.poll() is None and not any(not c['ok'] for c in checks)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        desktop = browser.new_context(viewport={'width': 1440, 'height': 900})
        p = page(desktop, '?test=1&lazy=1&track=1&from=github&utm_source=douyin')
        poll(p, '() => window.__waterTest?.snapshot().artReady', 30)
        click(p, '#setupButton')
        poll(p, '() => document.querySelector("#setup").open && [...document.querySelectorAll("#playerPortrait,#enemyPortrait")].every(n=>n.dataset.frame)')
        wait_event(p, 'select_ready')
        shots = OUT / '截图'
        shots.mkdir(exist_ok=True)
        p.screenshot(path=str(shots / 'desktop-1440x900.png'))
        p.locator('.mon[data-id="7"]').click()
        p.locator('#pickEnemyPanel').click()
        p.locator('.mon[data-id="4"]').click()
        p.locator('#toggleLoadout').click()
        p.locator('#defaultMoves').click()
        p.wait_for_timeout(1100)
        p.locator('#randomEnemy').click()
        p.wait_for_timeout(1100)
        p.locator('#closeMoves').click()
        p.locator('.mon[data-id="4"]').click()
        # Links really receive a click, but no external URL is allowed to load.
        p.evaluate('() => document.querySelector(".setup-credit").addEventListener("click",e=>{if(e.target.closest("a")) e.preventDefault()},true)')
        p.locator('.setup-credit a').first.click()
        p.wait_for_timeout(1100)
        p.locator('.setup-credit a').nth(1).click()
        p.locator('[popovertarget="analyticsPrivacy"]').click()
        check('privacy explanation opens', p.locator('#analyticsPrivacy').is_visible())
        p.keyboard.press('Escape')
        start(p)
        click(p, '#help')
        p.locator('#aimSetting').click()
        p.keyboard.press('Escape')
        p.locator('#game').click()
        p.wait_for_timeout(1100)
        click(p, '#sound')
        click(p, '#help')
        p.keyboard.press('Escape')
        p.locator('#game').click()
        win(p)
        wait_event(p, 'battle_end')
        p.locator('#gbaRematch').click()
        p.wait_for_timeout(1200)
        check('rematch UI enters playing', p.evaluate('window.__waterTest.snapshot().phase === "playing"'))
        win(p)
        wait_event(p, 'battle_end', 2)
        click(p, '#setupButton')
        wait_event(p, 'change_pokemon')
        # Exercise both browser error handlers; duplicate message must be suppressed.
        p.evaluate('() => setTimeout(()=>{throw new Error("EVT_EXPECTED window")},0)')
        p.wait_for_timeout(1100)
        p.evaluate('() => {setTimeout(()=>Promise.reject(new Error("EVT_EXPECTED rejection")),0)}')
        p.wait_for_timeout(1100)
        p.evaluate('() => setTimeout(()=>{throw new Error("EVT_EXPECTED window")},0)')
        p.wait_for_timeout(100)
        check('error message dedup across both handlers', count('error') == 2)
        p.evaluate('''() => {
          Object.defineProperty(document,"hidden",{configurable:true,get:()=>true});
          document.dispatchEvent(new Event("visibilitychange"));
          setTimeout(()=>delete document.hidden,50);
        }''')
        wait_event(p, 'session_end')
        check('hidden session snapshot counts completed games', any(
            e['e']=='session_end' and e['p']['n']==2 for e in rows()))
        # Reload is a new session on the same device; returning flag is real storage.
        old_id = rows()[0]['d']
        p.reload()
        p.wait_for_timeout(500)
        check('persistent ID and returning page_view', any(e['e'] == 'page_view' and
              e['p']['rv'] and e['d'] == old_id for e in rows()))
        p.close()
        desktop.close()

        phone = browser.new_context(viewport={'width': 844, 'height': 390}, is_mobile=True,
                                    has_touch=True, user_agent='Mozilla/5.0 (iPhone) Mobile')
        m = page(phone, '?observe=1&track=1&hud=3&from=douyin')
        wait_event(m, 'select_ready', 2)
        m.screenshot(path=str(shots / 'phone-844x390.png'))
        start(m)
        before_input = count('first_input')
        m.locator('#dashButton').tap()
        wait_event(m, 'first_input', before_input + 1)
        check('touch dash alone is first movement', count('first_input') == before_input + 1)
        cdp = phone.new_cdp_session(m)
        box = m.locator('#game').bounding_box()
        x, y = box['x'] + 60, box['y'] + box['height'] * .65
        for typ, xx in [('touchStart', x), ('touchMove', x + 45)]:
            cdp.send('Input.dispatchTouchEvent', {'type': typ,
                     'touchPoints': [{'x': xx, 'y': y}]})
            m.wait_for_timeout(300)
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        # Slow real rAF delivery for >3s (not a synthetic perf_low emit).
        m.evaluate('''() => {const raf=window.requestAnimationFrame.bind(window);
          window.requestAnimationFrame=fn=>raf(()=>setTimeout(()=>fn(performance.now()),55));}''')
        m.wait_for_timeout(4300)
        wait_event(m, 'perf_low')
        m.wait_for_timeout(1100)
        check('perf_low max one per battle', count('perf_low') == 1)
        click(m, '#setupButton')
        wait_event(m, 'quit')
        m.set_viewport_size({'width': 390, 'height': 844})
        m.wait_for_timeout(150)
        m.screenshot(path=str(shots / 'phone-390x844.png'))
        m.close()
        phone.close()
        time.sleep(.2)

        for name, suffix, init in [
            ('demo', '?demo=1', None), ('observe', '?observe=1', None),
            ('test', '?test=1&lazy=1', None),
            ('DNT beats forced tracking', '?observe=1&track=1',
             'Object.defineProperty(navigator,"doNotTrack",{get:()=>"1"})'),
            ('GPC beats forced tracking', '?observe=1&track=1',
             'Object.defineProperty(navigator,"globalPrivacyControl",{get:()=>true})'),
        ]:
            ctx = browser.new_context()
            before = count()
            z = page(ctx, suffix, init)
            z.wait_for_timeout(1200)
            z.close()
            ctx.close()
            time.sleep(.2)
            check(name + ' emits zero events', count() == before)
        local = browser.new_context()
        z = local.new_page()
        local_hits = []
        z.on('request', lambda r: local_hits.append(r.url) if urlsplit(r.url).path == '/e' else None)
        z.goto(os.environ['POIGHT_TEST_URL'] + '?observe=1')
        z.wait_for_timeout(700)
        z.close()
        local.close()
        check('localhost default disabled', not local_hits)

        denied = browser.new_context()
        before = count('page_view')
        z = page(denied, '?observe=1&track=1', '''Object.defineProperty(window,"localStorage",{
          get(){throw new DOMException("Denied","SecurityError")}})''')
        z.wait_for_timeout(1400)
        check('storage denial still sends events', count('page_view') == before + 1)
        start(z)
        before_quit = count('quit')
        z.evaluate('() => window.dispatchEvent(new PageTransitionEvent("pagehide"))')
        wait_event(z, 'quit', before_quit + 1)
        check('pagehide lifecycle reports active battle quit', count('quit') == before_quit + 1)
        z.goto('about:blank')
        z.close()
        denied.close()

        cap = browser.new_context()
        z = page(cap, '?observe=1&track=1')
        z.wait_for_timeout(1500)
        cap_session = rows()[-1]['s']
        z.evaluate('''() => {for(let i=0;i<400;i++)
          window.PoightEVT.setting("throttle",i)}''')
        z.wait_for_timeout(500)
        check('same event <=1 in one second', sum(e['s']==cap_session and e['e']=='setting'
              for e in rows()) == 1)
        z.evaluate('''() => {let tick=performance.now()+2000;
          Object.defineProperty(performance,"now",{value:()=>tick+=1001});
          for(let i=0;i<340;i++) window.PoightEVT.setting("cap",i)}''')
        z.wait_for_timeout(4500)
        z.close()
        cap.close()
        time.sleep(.3)
        check('session cap exercised at exactly 300', sum(e['s']==cap_session for e in rows()) == 300)
        browser.close()
        browser = None
    events, invalid, duplicate = load(LOG)
    check('every event implemented (move_use is aggregation)', {e['e'] for e in events} == EVENTS)
    check('valid protocol and all fields', invalid == 0 and all(
        set(FIELDS[e['e']].split()).issubset(e['p']) for e in events))
    check('battle_ready carries actual BGM id', all(e['p'].get('bgm') in
          {'c01','c02','c03','c04','c05','c06','c09','c15','orig'}
          for e in events if e['e']=='battle_ready'))
    check('single beacon <=600 UTF8 bytes', all(len(('/e?' + e['raw']).encode()) <= 600 for e in events))
    check('all sessions <=300', all(sum(e['s']==s for e in events) <= 300 for s in {e['s'] for e in events}))
    check('touch method recorded', any(e['e']=='first_input' and e['p']['i']=='touch' for e in events))
    check('keyboard method recorded', any(e['e']=='first_input' and e['p']['i']=='keyboard' for e in events))
    check('real cast counts aggregated', any(e['e']=='battle_end' and sum(e['p']['u'][0])>0 for e in events))
    check('pause recorded in finished battle', any(e['e']=='battle_end' and e['p']['pa'] for e in events))
    check('no CSP console errors', not csp, csp)
    check('no unexpected JS errors', not errors, errors)
    check('only same-origin image beacon transport', all(urlsplit(u).hostname in ('localhost', 'localhost')
          for u in requests))
    examples = {}
    for line in LOG.read_text().splitlines():
        row = json.loads(line)
        # Retain original JSONL, not reconstructed payloads.
        e = parse_line(line)['e']
        examples.setdefault(e, row)
    (OUT / '每种事件样例.jsonl').write_text('\n'.join(json.dumps(row, ensure_ascii=False)
        for row in examples.values()) + '\n')
    daily_log = OUT / '日报输入.jsonl'
    daily_log.write_text('\n'.join(line for line in LOG.read_text().splitlines()
                                  if parse_line(line)['s'] != cap_session) + '\n')
    result = subprocess.run([sys.executable, 'scripts/埋点日报.py', str(daily_log),
        '--md', str(OUT/'日报.md'), '--json', str(OUT/'日报.json')], cwd=ROOT,
        capture_output=True, text=True, check=True)
    print(result.stdout)
except (AssertionError, Error, TimeoutError, OSError, ValueError, subprocess.SubprocessError) as exc:
    checks.append({'name': 'completed', 'ok': False, 'detail': repr(exc)})
finally:
    if browser:
        try:
            browser.close()
        except Error:
            pass  # Playwright's context manager already stopped after a test failure.
    if collector:
        command = subprocess.run(['ps', '-o', 'command=', '-p', str(collector.pid)],
                                 capture_output=True, text=True, check=False).stdout
        if '预览服务.py' in command and '--collect' in command:
            collector.terminate()
            collector.wait(timeout=10)
        collector_log.close()
    result = {'passed': sum(c['ok'] for c in checks), 'failed': sum(not c['ok'] for c in checks),
              'jsErrors': len(errors), 'errors': errors, 'cspErrors': csp, 'checks': checks}
    (OUT/'验收.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(bool(result['failed'] or errors or csp))
