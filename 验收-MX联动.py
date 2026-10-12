"""MX: demo framing/HUD/determinism on expanded arenas, plus ordinary-mode guards."""
import base64
import hashlib
import importlib.util
import json
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/MX联动'
SHOTS = OUT / '截图'
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ['POIGHT_TEST_URL'].rstrip('/')
CHECKS, ERRORS, SAMPLES = [], [], {}


def check(name, ok, detail=None):
    CHECKS.append({'name': name, 'ok': bool(ok), 'detail': detail})
    assert ok, (name, detail)


def wait(page, expression):
    for _ in range(2400):
        if page.evaluate(expression):
            return
        time.sleep(.025)
    raise TimeoutError(expression)


def png(page):
    return base64.b64decode(page.evaluate("document.querySelector('#game').toDataURL().split(',')[1]"))


def hooks(page):
    page.evaluate('''() => {
      window.__mxCalls = {map: 0, edge: 0, follow: 0, demo: 0};
      for (const [method, key] of [['drawArenaMap','map'], ['drawEdge','edge'], ['camera','follow']]) {
        const proto = PoightBattleHUD.prototype, original = proto[method];
        proto[method] = function(...args) { __mxCalls[key]++; return original.apply(this,args); };
      }
      const original = PoightDemo.prototype.camera;
      PoightDemo.prototype.camera = function(...args) {
        __mxCalls.demo++;
        window.__mxWorld = args[2];
        return original.apply(this,args);
      };
    }''')


try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        for width, height in ((1080, 1920), (1920, 1080)):
            context = browser.new_context(viewport={'width': width, 'height': height})
            query = f'?demo=1&hud=0&w={width}&h={height}&fps=60&seed=7&paused=1'
            runs = []
            for run in range(2):
                page = context.new_page()
                page.on('pageerror', lambda error: ERRORS.append(str(error)))
                page.goto(URL + '/' + query)
                wait(page, 'window.__demo?.ready')
                hooks(page)
                if run == 0:
                    rows = []
                    # Step every output frame, including frame zero and exactly 30 seconds.
                    for start, count in ((0, 600), (600, 600), (1200, 600)):
                        rows += page.evaluate('''count => {
                          const rows = [], ctx = document.querySelector('#game').getContext('2d');
                          for(let i=0; i<count; i++) {
                            const s = __demo.snapshot(), c = s.camera;
                            const samples = [];
                            for(const [x,y] of [[0,0],[s.canvas.width-1,0],
                              [0,s.canvas.height-1],[s.canvas.width-1,s.canvas.height-1]]) {
                              const wx=c.x+x/c.zoom, wy=c.y+y/c.zoom;
                              if(wx<0 || wy<0 || wx>2100 || wy>1400)
                                samples.push([...ctx.getImageData(x,y,1,1).data]);
                            }
                            rows.push({frame:s.frame, centers:s.centers, camera:c, outside:samples});
                            __demo.step(1);
                          }
                          return rows;
                        }''', count)
                        if start == 0:
                            frame600 = page.evaluate('JSON.stringify(__demo.snapshot())')
                            frame600_png = png(page)
                            (SHOTS / f'演示-hud0-{width}x{height}-第600帧.png').write_bytes(frame600_png)
                    state = page.evaluate('__demo.snapshot()')
                    rows.append({'frame': state['frame'], 'centers': state['centers'],
                                 'camera': state['camera'], 'outside': []})
                    for row in rows:
                        check(f'{width}x{height} frame{row["frame"]} 双方中心中间80%', all(
                            .1 - 1e-9 <= p[axis] <= .9 + 1e-9
                            for p in row['centers'] for axis in ('nx', 'ny')), row['centers'])
                        if row['outside']:
                            check(f'{width}x{height} frame{row["frame"]} 场外不透明且非黑', all(
                                pixel[3] == 255 and max(pixel[:3]) > 32
                                for pixel in row['outside']), row['outside'])
                    check(f'{width}x{height} 30秒1800帧', state['frame'] == 1800)
                    check(f'{width}x{height} 默认双方中点镜头', state['cameraMode'] == 2)
                    check(f'{width}x{height} 扩建世界2100x1400', page.evaluate('__mxWorld') ==
                          {'width': 2100, 'height': 1400})
                    check(f'{width}x{height} 距离自适应缩放', len({round(r['camera']['zoom'], 3) for r in rows}) > 10)
                    calls = page.evaluate('__mxCalls')
                    check(f'{width}x{height} demo镜头独占', calls['demo'] > 0 and calls['follow'] == 0, calls)
                    check(f'{width}x{height} hud0小地图和箭头绘制均未调用', calls['map'] == calls['edge'] == 0, calls)
                    SAMPLES[str((width, height))] = rows
                    runs.append((frame600, frame600_png))
                else:
                    page.evaluate('__demo.step(600)')
                    runs.append((page.evaluate('JSON.stringify(__demo.snapshot())'), png(page)))
                page.close()
            check(f'{width}x{height} 600帧快照逐字节相同', runs[0][0].encode() == runs[1][0].encode())
            check(f'{width}x{height} 600帧PNG逐字节相同', runs[0][1] == runs[1][1])
            (OUT / f'{width}x{height}-600帧.json').write_text(runs[0][0] + '\n')
            context.close()
        # Reuse A1's actual-alpha render measurements, not a surrogate sprite box.
        spec = importlib.util.spec_from_file_location('a1_scale', ROOT / '验收-场地比例.py')
        a1 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(a1)
        for width, height in ((1440, 900), (844, 390), (2560, 1440)):
            context = browser.new_context(viewport={'width': width, 'height': height})
            page = context.new_page()
            page.on('pageerror', lambda error: ERRORS.append(str(error)))
            page.goto(URL + '/?test=1')
            wait(page, 'window.__waterTest?.snapshot().artReady')
            a1.select(page, 'arena-formal')
            hooks(page)
            check(f'{width} 普通模式不暴露演示API', page.evaluate("typeof __demo === 'undefined'"))
            metric = a1.render_metric(page)
            check(f'{width} 普通皮卡丘可见屏高4–6%', .04 <= metric['screenHeight'] / height <= .06, metric)
            check(f'{width} 普通像素插值关闭', not metric['smoothing'])
            if width == 1440:
                a1.call(page, 'arrange', {'ai': True})
                a1.call(page, 'step', 4)
                page.keyboard.press('1')
                a1.call(page, 'step', .2)
                page.screenshot(path=str(SHOTS / '普通开打-1440x900.png'))
            a1.call(page, 'arrange', {'ai': False, 'player': {'x': 1050, 'y': 700},
                                      'enemy': {'x': 1900, 'y': 700}})
            a1.call(page, 'step', .6)
            a1.call(page, 'render')
            state = a1.snap(page)
            calls = page.evaluate('__mxCalls')
            check(f'{width} 普通A1镜头独占', calls['follow'] > 0 and calls['demo'] == 0, calls)
            check(f'{width} 普通小地图照常绘制', calls['map'] > 0 and state['arenaView']['minimap'] is not None)
            check(f'{width} 普通出屏箭头照常绘制', calls['edge'] > 0 and state['arenaView']['edge'] is not None)
            a1.framing(page, f'{width}普通跟随')
            context.close()
        CHECKS.extend(a1.CHECKS)
        browser.close()
    check('0 JS错误', not ERRORS, ERRORS)
finally:
    report = {'passed': sum(c['ok'] for c in CHECKS), 'failed': sum(not c['ok'] for c in CHECKS),
              'jsErrors': len(ERRORS), 'errors': ERRORS, 'checks': CHECKS,
              'candidateSHA256': hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest()}
    (OUT / '浏览器验收.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    (OUT / '逐帧镜头.json').write_text(json.dumps(SAMPLES, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('passed', 'failed', 'jsErrors')}, ensure_ascii=False))
