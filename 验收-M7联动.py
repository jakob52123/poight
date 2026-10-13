"""Frozen arena: screen-space FX, statuses, source links, seeded demo edge pixels."""
import base64
import colorsys
import hashlib
import io
import json
import os
import time
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/M7联动'
SHOTS = OUT / '截图'
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ['POIGHT_TEST_URL'].rstrip('/')
CHECKS, ERRORS, SAMPLES = [], [], []
HERO = ['thunderbolt', 'quickattack', 'irontail', 'thunder',
        'flamethrower', 'fireblast', 'dragonclaw', 'airslash']
KINDS = dict(zip(HERO, ['beam', 'rush', 'tail', 'thunder', 'beam', 'projectile', 'claw', 'projectile']))
CORE = {'watergun', 'icebeam', 'earthquake'}
CASES = [(7, 'watergun'), (9, 'icebeam'), (95, 'earthquake')] + [
    (25 if mid in HERO[:4] else 6, mid) for mid in HERO] + [(6, 'bite')]


def check(name, ok, detail=None):
    CHECKS.append({'name': name, 'ok': bool(ok), 'detail': detail})
    if not ok:
        print('FAIL', name, json.dumps(detail, ensure_ascii=False), flush=True)


def wait(page, expression):
    for _ in range(2400):
        if page.evaluate(expression):
            return
        time.sleep(.025)
    raise TimeoutError(expression)


def call(page, name, *args):
    return page.evaluate('([m,args])=>__waterTest[m](...args)', [name, args])


def snap(page):
    return call(page, 'snapshot')


def image(raw):
    return Image.open(io.BytesIO(base64.b64decode(raw.split(',')[1]))).convert('RGB')


def arrange(page, caster, mid, target=6):
    cat = call(page, 'catalog')
    roster = {p['id']: p for p in cat['roster']}
    call(page, 'select', {**snap(page)['profile'], 'player': caster, 'enemy': target,
                         'playerMoves': roster[caster]['defaultMoves'],
                         'enemyMoves': roster[target]['defaultMoves'],
                         'map': 'arena-formal', 'shake': False})
    call(page, 'reset', True)
    distance = (22 if cat['moves'][mid]['kind'] == 'melee' else
                55 if mid == 'earthquake' else 100 if mid in CORE else 95)
    call(page, 'arrange', {'ai': False, 'player': {'x': 600, 'y': 570, 'a': 0},
                          'enemy': {'x': 600 + distance, 'y': 570, 'a': 3.141592653589793}})
    call(page, 'equip', 'player', [mid])
    call(page, 'step', .3)
    return snap(page)


def moves(page):
    page.evaluate((ROOT / 'tests/招式动画像素.js').read_text())
    page.evaluate((ROOT / 'tests/主角动画像素.js').read_text())
    for caster, mid in CASES:
        target = 7 if mid in CORE else 6 if caster != 6 else 25
        start = arrange(page, caster, mid, target)
        hp = start['enemy']['hp']
        call(page, 'cast', 'player', mid)
        ticks = page.evaluate('''hp=>{
          for(let i=1;i<=240;i++){__waterTest.step(1/120,false);
            if(__waterTest.snapshot().enemy.hp<hp)return i;}
          return null;
        }''', hp)
        check(mid + ' real damaging tick exists', ticks is not None)
        if ticks is None:
            continue
        arrange(page, caster, mid, target)
        call(page, 'cast', 'player', mid)
        before = mid in ['watergun', 'icebeam', 'earthquake', 'thunderbolt',
                         'flamethrower', 'fireblast', 'airslash', 'quickattack']
        page.evaluate('n=>{for(let i=0;i<n;i++)__waterTest.step(1/120,false);}', ticks - int(before))
        if mid in HERO:
            page.evaluate('p=>Object.assign(heroProbe,p)', {
                'enabled': True, 'id': mid, 'kind': KINDS[mid], 'last': None, 'contact': None})
        elif mid in ['watergun', 'icebeam', 'earthquake']:
            page.evaluate('pixelProbe.enabled=true')
        call(page, 'render')
        scale = page.locator('#game').evaluate('(c)=>c.getBoundingClientRect().width/__waterTest.snapshot().viewport.width')
        sample = {'id': mid, 'screenScale': scale,
                  'sourceScreenHeight': start['player']['body']['visibleSize'][1] * scale,
                  'targetScreenHeight': start['enemy']['body']['visibleSize'][1] * scale}
        m = None
        if mid in HERO:
            m = page.evaluate('measureHeroPixels()')
        elif mid != 'bite':
            m = page.evaluate('measureMovePixels()')
        if m:
            for key in ['composite', 'background', 'mask']:
                image(m.pop(key)).save(SHOTS / f'{mid}-{key}.png')
            sample['pixels'] = m
            check(mid + ' opaque screen raster exists', m['count'] > 20, m['count'])
            check(mid + ' luma contrast >=60 (unchanged)', m['contrast'] >= 60, m['contrast'])
            if mid not in ['irontail', 'quickattack']:
                check(mid + ' saturation >=.55 and colored coverage >=.30 (unchanged)',
                      m['saturation'] >= .55 and m['colorFraction'] >= .30,
                      [m['saturation'], m['colorFraction']])
            if mid in ['watergun', 'airslash', 'fireblast']:
                size = (m['beadDiameter'] if mid == 'watergun' else m['normal'] if mid == 'airslash'
                        else min(m['width'], m['height'])) * scale
                check(mid + ' projectile screen diameter >= .30 caster screen height',
                      size >= sample['sourceScreenHeight'] * .30, [size, sample['sourceScreenHeight']])
                check(mid + ' 14-world-pixel floor converted by actual camera scale', size >= 14 * scale)
            if mid in ['icebeam', 'thunderbolt', 'flamethrower']:
                size = m['minimumBeamWidth'] * scale
                check(mid + ' beam screen width >= .25 caster screen height',
                      size >= sample['sourceScreenHeight'] * .25, [size, sample['sourceScreenHeight']])
                check(mid + ' 10-world-pixel floor converted by actual camera scale', size >= 10 * scale)
        else:
            check(mid + ' raster probe exists or common bite contact', mid == 'bite')
        if before:
            check(mid + ' no precontact HP loss', snap(page)['enemy']['hp'] == hp)
            call(page, 'step', 1 / 120)
        state = snap(page)
        bursts = [b for b in state['animation']['bursts'] if b['id'] == mid]
        check(mid + ' contact on damaging frame', bool(bursts) and state['enemy']['hp'] < hp)
        if bursts:
            # Production contact diameter is world-space; use the actual CSS Canvas transform.
            size = bursts[-1]['size'] * scale
            check(mid + ' impact screen diameter >= .8 target screen height',
                  size + 1e-9 >= .8 * sample['targetScreenHeight'], [size, sample['targetScreenHeight']])
            sample['impactScreenDiameter'] = size
        if mid in ['thunderbolt', 'fireblast']:
            page.screenshot(path=str(SHOTS / ('十万伏特-命中.png' if mid == 'thunderbolt' else '大字爆炎-命中.png')))
        SAMPLES.append(sample)
        page.evaluate('pixelProbe.enabled=false;heroProbe.enabled=false')
    check('12 distinct sampled moves', len({s['id'] for s in SAMPLES}) == 12)


def statuses(page):
    for caster, target, side in [(25, 6, 'enemy'), (25, 6, 'player')]:
        for status in ['frz', 'par']:
            arrange(page, caster, 'watergun', target)
            page.evaluate('([s,id])=>{__waterTest.statusTest.types(s,[1]);__waterTest.statusTest.apply(s,id);}', [side, status])
            call(page, 'step', .25)
            data = page.evaluate('s=>__waterTest.statusTest.visual(s)', side)
            shown, base = image(data['shown']), image(data['base'])
            b = data['box']
            x, y, w, h = [b[k] for k in ('x', 'y', 'width', 'height')]
            box = (int(x), int(y), int(x+w), int(y+h))
            if status == 'frz':
                diff = ImageChops.difference(shown, base).crop(box)
                changed = sum(max(p) > 8 for p in diff.get_flattened_data()) / (diff.width * diff.height)
                check(side + ' frozen enclosure covers >=90% actual sprite bbox', changed >= .90, changed)
                if side == 'enemy':
                    page.screenshot(path=str(SHOTS / '喷火龙-冰块.png'))
            else:
                colors = []
                contrast = []
                for yy in range(max(0, int(y)-40), min(shown.height, int(y+h)+40)):
                    for xx in range(max(0, int(x)-40), min(shown.width, int(x+w)+40)):
                        if x-3 <= xx <= x+w+3 and y-3 <= yy <= y+h+3:
                            continue
                        a, bg = shown.getpixel((xx, yy)), base.getpixel((xx, yy))
                        if max(abs(a[i]-bg[i]) for i in range(3)) < 20:
                            continue
                        colors.append(colorsys.rgb_to_hsv(*(v/255 for v in a))[1])
                        contrast.append(abs(sum((a[i]-bg[i])*q for i, q in enumerate([.2126, .7152, .0722]))))
                check(side + ' paralysis sparks remain visible on small actor', len(colors) >= 30, len(colors))
                check(side + ' paralysis saturation/brightness thresholds unchanged', bool(colors) and
                      sorted(colors)[len(colors)//2] >= .55 and sum(contrast)/len(contrast) >= 60,
                      {'count': len(colors), 'contrast': sum(contrast)/max(1, len(contrast))})


def arena_ai(page):
    arrange(page, 25, 'thunderbolt')
    scene = next(s for s in call(page, 'catalog')['scenes'] if s['id'] == 'arena-formal')
    check('A2 collision data has no old rails', all(o['kind'] != 'fence' for o in scene['collisionContract']))
    call(page, 'equip', 'enemy', ['scratch'])
    call(page, 'arrange', {'ai': True, 'player': {'x': 500, 'y': 700},
                          'enemy': {'x': 100, 'y': 700}})
    states = []
    for _ in range(8):
        call(page, 'step', .5)
        states.append(snap(page)['enemy']['x'])
    check('live AI crosses removed left rail (x=90..136), never stalls there',
          max(states) > 200, states)


def links(page, width, height):
    page.set_viewport_size({'width': width, 'height': height})
    page.reload()
    wait(page, 'window.__waterTest?.snapshot().artReady')
    page.locator('#battleMenuButton').click()
    page.locator('#setupButton').click()
    wait(page, 'document.querySelector("#setup").open')
    for title, href in [('致敬《宝可梦：羁绊之旅》', 'https://www.bilibili.com/video/BV16bHd6jE1a/'),
                        ('源码', 'https://github.com/jakob52123/poight')]:
        link = page.locator('#setup .setup-credit a').filter(has_text=title)
        check(f'{width} {title} exact external link', link.count() == 1 and
              link.get_attribute('href') == href and link.get_attribute('target') == '_blank' and
              link.get_attribute('rel') == 'noopener')
        if link.count():
            box = link.bounding_box()
            check(f'{width} {title} visible within viewport', link.is_visible() and box is not None and
                  box['x'] >= 0 and box['y'] >= 0 and box['x']+box['width'] <= width and
                  box['y']+box['height'] <= height, box)
    check(f'{width} credit does not overlap any setup button', page.evaluate('''()=>{
      const r=document.querySelector('.setup-credit').getBoundingClientRect();
      return [...document.querySelectorAll('#setup button:not([popovertarget="analyticsPrivacy"])')].every(b=>{
        if(!b.checkVisibility())return true;
        const q=b.getBoundingClientRect();let x=q.left,y=q.top,right=q.right,bottom=q.bottom;
        for(let a=b.parentElement;a;a=a.parentElement){const s=getComputedStyle(a),v=a.getBoundingClientRect();
          if(['auto','scroll','hidden','clip'].includes(s.overflowX)){x=Math.max(x,v.left);right=Math.min(right,v.right);}
          if(['auto','scroll','hidden','clip'].includes(s.overflowY)){y=Math.max(y,v.top);bottom=Math.min(bottom,v.bottom);}}
        return right<=x || bottom<=y || right<=r.left || x>=r.right || bottom<=r.top || y>=r.bottom;});
    }'''))
    check(f'{width} anonymous privacy control stays inside credit', page.evaluate('''()=>{
      const credit=document.querySelector('.setup-credit').getBoundingClientRect();
      const button=document.querySelector('[popovertarget="analyticsPrivacy"]');
      if (!button) return false;
      const r=button.getBoundingClientRect();
      return r.width>0 && r.height>0 && r.left>=credit.left && r.right<=credit.right &&
        r.top>=credit.top && r.bottom<=credit.bottom;
    }'''))
    page.screenshot(path=str(SHOTS / f'选人页-{width}x{height}.png'))


def demo(browser):
    runs = []
    query = '?demo=1&hud=0&w=1080&h=1920&fps=60&seed=7&paused=1'
    for run in range(2):
        page = browser.new_page(viewport={'width': 1080, 'height': 1920})
        page.on('pageerror', lambda e: ERRORS.append(str(e)))
        page.goto(URL + '/' + query)
        wait(page, 'window.__demo?.ready')
        if run:
            page.evaluate('__demo.step(600)')
            runs.append((page.evaluate('__demo.snapshot()'), page.locator('#game').evaluate('(c)=>c.toDataURL()')))
        else:
            for sample in range(61):
                result = page.evaluate('''()=>{
                  const c=document.querySelector('#game'),g=c.getContext('2d'),w=c.width,h=c.height,
                    d=g.getImageData(0,0,w,h).data,ex=Math.ceil(w*.02),ey=Math.ceil(h*.02);
                  let outside=0,transparent=0,total=0;
                  for(let y=0;y<h;y++)for(let x=0;x<w;x++){
                    if(x>=ex&&x<w-ex&&y>=ey&&y<h-ey)continue;
                    const i=(y*w+x)*4;total++;
                    if(d[i]===115&&d[i+1]===205&&d[i+2]===164)outside++;
                    if(d[i+3]!==255)transparent++;
                  }
                  return {outside,transparent,total,camera:__demo.snapshot().camera};
                }''')
                check(f'demo {sample/2:.1f}s all edge 2% pixels contain no outside-world color',
                      result['outside'] == result['transparent'] == 0, result)
                camera = result['camera']
                for axis, span, extent in [('x', 'width', 2100), ('y', 'height', 1400)]:
                    value, size = camera[axis], camera[span]
                    check(f'demo {sample/2:.1f}s {axis} clamped or centered in explicit edge padding',
                          abs(value-(extent-size)/2) < 1e-7 if size > extent else
                          value >= -1e-7 and value+size <= extent+1e-7, camera)
                if sample == 20:
                    raw = page.locator('#game').evaluate('(c)=>c.toDataURL()')
                    runs.append((page.evaluate('__demo.snapshot()'), raw))
                    image(raw).save(SHOTS / '演示-1080x1920-第600帧.png')
                if sample < 60:
                    page.evaluate('__demo.step(30)')
        page.close()
    check('S1/V1/demo seed7 frame600 snapshots identical', runs[0][0] == runs[1][0])
    check('S1/V1/demo seed7 frame600 PNG bytes identical', runs[0][1] == runs[1][1])
    check('S1 uses injected seeded RNG, never Math.random', 'Math.random' not in
          (ROOT / '异常状态.js').read_text() and 'random: rand' in (ROOT / '对战.js').read_text())


try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.on('pageerror', lambda e: ERRORS.append(str(e)))
        page.goto(URL + '/?test=1')
        wait(page, 'window.__waterTest?.snapshot().artReady')
        moves(page)
        statuses(page)
        arena_ai(page)
        arrange(page, 25, 'thunderbolt')
        call(page, 'reset', True)
        call(page, 'arrange', {'ai': True})
        call(page, 'step', .5)
        page.screenshot(path=str(SHOTS / '正规场-1440x900.png'))
        links(page, 1440, 900)
        links(page, 844, 390)
        page.close()
        phone = browser.new_page(viewport={'width': 844, 'height': 390},
                                 has_touch=True, is_mobile=True)
        phone.on('pageerror', lambda e: ERRORS.append(str(e)))
        phone.goto(URL + '/?test=1')
        wait(phone, 'window.__waterTest?.snapshot().artReady')
        arrange(phone, 25, 'thunderbolt')
        call(phone, 'reset', True)
        call(phone, 'arrange', {'ai': True})
        call(phone, 'step', .5)
        phone.screenshot(path=str(SHOTS / '手机横屏-844x390.png'))
        phone.close()
        demo(browser)
        browser.close()
    check('0 JavaScript errors', not ERRORS, ERRORS)
finally:
    report = {'passed': sum(c['ok'] for c in CHECKS), 'failed': sum(not c['ok'] for c in CHECKS),
              'jsErrors': len(ERRORS), 'errors': ERRORS, 'checks': CHECKS, 'moveSamples': SAMPLES,
              'candidateSHA256': hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest()}
    (OUT / '浏览器验收.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['passed', 'failed', 'jsErrors']}, ensure_ascii=False))
if report['failed'] or report['jsErrors']:
    raise SystemExit(1)
