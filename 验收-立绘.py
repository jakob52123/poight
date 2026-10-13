"""BW portraits: authorized roster, real canvas pixels, direction, integer scaling and offline assets."""
import base64
import io
import json
import os
import time
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/立绘'
SHOTS = OUT / '截图'
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get('POIGHT_TEST_URL', 'http://localhost:8878/').rstrip('/')
checks, errors, failures = [], [], []
catalog = json.loads((ROOT / '素材/立绘/图集.json').read_text())


def check(name, ok, detail=None):
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
    assert ok, (name, detail)


def poll(page, expression, timeout=5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if page.evaluate(expression):
            return True
        page.wait_for_timeout(20)
    return False


def pixels(el):
    value = el.evaluate('e => ({frame:Number(e.dataset.frame), scale:Number(e.dataset.scale), '
                        'facing:e.dataset.facing, png:e.toDataURL().split(",")[1]})')
    return value, Image.open(io.BytesIO(base64.b64decode(value['png']))).convert('RGBA')


def expected(ident, frame, scale, side):
    d = catalog[str(ident)]
    with Image.open(ROOT / '素材/立绘' / d['file']) as atlas:
        x, y = frame % d['columns'] * d['width'], frame // d['columns'] * d['height']
        tile = atlas.crop((x, y, x + d['width'], y + d['height'])).convert('RGBA')
    if side == 'player':
        tile = tile.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    return tile.resize((d['width'] * scale, d['height'] * scale), Image.Resampling.NEAREST)


def normalized(image):
    background = Image.new('RGBA', image.size, '#000000')
    return Image.alpha_composite(background, image).convert('RGB')


def geometry(el):
    return el.evaluate('''e => {
      const r=e.getBoundingClientRect(), p=e.parentElement.getBoundingClientRect();
      return {contained:r.left>=p.left-.5 && r.right<=p.right+.5 &&
        r.top>=p.top-.5 && r.bottom<=p.bottom+.5,
        fit:r.width<=e.width+.5 && r.height<=e.height+.5 && getComputedStyle(e).objectFit==='contain',
        nearest:getComputedStyle(e).imageRendering==='pixelated'};
    }''')


try:
    overview = Image.new('RGB', (1280, ((len(catalog)+4)//5)*110), '#102538')
    draw = ImageDraw.Draw(overview)
    for i, ident in enumerate(catalog):
        tile = expected(ident, 0, 2, 'enemy')
        x, y = i % 5 * 256, i // 5 * 110
        # Overview uses native size to fit every species, not the UI scaling.
        tile = tile.resize((tile.width // 2, tile.height // 2), Image.Resampling.NEAREST)
        overview.paste(tile, (x + (256 - tile.width) // 2, y), tile)
        draw.text((x + 8, y + 94), f'{ident} {next(s["name"] for s in json.loads((ROOT / "素材/立绘/来源.json").read_text()) if str(s["id"]) == ident)}', fill='white')
    overview.save(SHOTS / '全名单立绘总览.png')
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 900}, service_workers='block')
        context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(URL) else route.abort())
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('response', lambda response: failures.append(response.url) if response.status >= 400 else None)
        page.goto(URL + '/?test=1')
        check('资源就绪', poll(page, 'window.__waterTest?.snapshot().artReady'))
        # U1 moved the same setup action into the real battle menu.
        page.locator('#battleMenuButton').click()
        page.locator('#setupButton').click()
        for width, height in [(1440, 900), (844, 390)]:
            page.set_viewport_size({'width': width, 'height': height})
            for ident in catalog:
                for side, panel, portrait in [('player', 'pickPlayerPanel', 'playerPortrait'),
                                               ('enemy', 'pickEnemyPanel', 'enemyPortrait')]:
                    page.locator('#' + panel).click()
                    page.locator(f'#roster .mon[data-id="{ident}"]').click()
                    check(f'{width} {ident} {side} 加载', poll(page,
                          f'(() => {{const e=document.querySelector("#{portrait}");return e.dataset.id==="{ident}" && e.dataset.frame!==undefined;}})()'))
                    el = page.locator('#' + portrait)
                    value, actual = pixels(el)
                    check(f'{width} {ident} {side} GBA背板整数1至3倍', value['scale'] in (1, 2, 3), value['scale'])
                    g = geometry(el)
                    check(f'{width} {ident} {side} 无裁切且缩略contain最近邻', all(g.values()), g)
                    reference = expected(ident, value['frame'], value['scale'], side)
                    check(f'{width} {ident} {side} 面向及最近邻像素正确',
                          actual.size == reference.size and ImageChops.difference(normalized(actual), normalized(reference)).getbbox() is None)
                    if width == 1440:
                        changed = False
                        for _ in range(25):
                            page.wait_for_timeout(40)
                            _, second = pixels(el)
                            if ImageChops.difference(normalized(actual), normalized(second)).getbbox():
                                changed = True
                                break
                        if catalog[ident]['frames'] == 1:
                            source = next(s for s in json.loads((ROOT / '素材/立绘/来源.json').read_text()) if str(s['id']) == ident)
                            check(f'{ident} {side} 经授权缺GIF静态PNG回退', source['sources'][1].get('missing') and bool(source.get('fallback')) and not changed)
                        else:
                            check(f'{ident} {side} 动画两帧像素不同', changed)
            page.locator('#pickPlayerPanel').click()
            page.locator('#roster .mon[data-id="25"]').click()
            page.locator('#pickEnemyPanel').click()
            page.locator('#roster .mon[data-id="6"]').click()
            page.wait_for_timeout(200)
            page.screenshot(path=str(SHOTS / f'选人-{width}x{height}.png'))
        page.set_viewport_size({'width': 390, 'height': 844})
        page.wait_for_timeout(200)
        page.screenshot(path=str(SHOTS / '选人-390x844.png'))
        page.set_viewport_size({'width': 1440, 'height': 900})
        page.locator('#startBattle').click()
        check('VS过场', poll(page, 'window.__waterTest.snapshot().phase === "versus"'))
        page.wait_for_timeout(800)
        for side, ident, portrait in [('player', 25, 'vsPlayerIcon'), ('enemy', 6, 'vsEnemyIcon')]:
            el = page.locator('#' + portrait)
            value, actual = pixels(el)
            reference = expected(ident, value['frame'], value['scale'], side)
            check(f'VS {side} GBA整数放大朝向无裁切', value['scale'] in range(1, 13) and all(geometry(el).values())
                  and ImageChops.difference(normalized(actual), normalized(reference)).getbbox() is None)
        page.screenshot(path=str(SHOTS / 'VS-1440x900.png'))
        check('离线白名单加载无404', not failures, failures)
        check('0 JS错误', not errors, errors)
        browser.close()
except Exception as error:  # noqa: BLE001 - persist failure report for the harness
    checks.append({'name': '异常', 'ok': False, 'detail': repr(error)})
finally:
    report = {'passed': sum(c['ok'] for c in checks), 'failed': sum(not c['ok'] for c in checks),
              'jsErrors': len(errors), 'errors': errors, 'checks': checks}
    (OUT / '报告.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report['failed'] or errors:
        raise SystemExit(1)
