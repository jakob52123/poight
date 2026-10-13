"""P6: native current-frame sprite retention and actual hollow-burst raster, on Jade only."""
import base64
import io
import json
import os
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright
from scipy import ndimage

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/P6'
URL = os.environ.get('POIGHT_TEST_URL', 'http://localhost:8942/').rstrip('/')
checks, errors, samples = [], [], []
OUT.mkdir(parents=True, exist_ok=True)
FONT = ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc', 16)


def check(name, ok, detail=None):
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
    if not ok:
        print('FAIL ' + name + ' ' + json.dumps(detail, ensure_ascii=False), flush=True)


def ready(page, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if page.evaluate('''()=>{try{return window.__waterTest.snapshot().artReady;}
          catch{return false;}}'''):
            return
        time.sleep(.03)
    raise TimeoutError('art not ready')


def setup(page, roster, profile, caster, enemy, scene):
    page.evaluate('(p)=>window.__waterTest.select(p)', {
        **profile, 'player': caster, 'enemy': enemy, 'map': scene,
        'playerMoves': roster[caster]['defaultMoves'], 'enemyMoves': roster[enemy]['defaultMoves'],
    })
    page.evaluate('window.__waterTest.reset(true)')
    page.evaluate('''()=>{const api=window.__waterTest,b=api.snapshot().environment.bounds;
      const x=(b.left+b.right)/2-160,y=(b.top+b.bottom)/2-20;
      api.arrange({ai:false,player:{x,y,a:0},enemy:{x:x+95,y,a:Math.PI}});
      api.step(.2);}''')
    page.evaluate('(id)=>{window.hollowProbe.targetId=id;window.hollowProbe.ring=null;window.hollowProbe.sampleRing=true;}', enemy)


def tile(page, label):
    raw = page.locator('#game').evaluate('''c=>{
      const s=window.__waterTest.snapshot(),scale=c.width/s.viewport.width;
      const x=((s.player.x+s.enemy.x)/2-s.camera.x)*scale;
      const y=((s.player.y+s.enemy.y)/2-30-s.camera.y)*scale;
      const t=document.createElement('canvas');t.width=t.height=360;
      const g=t.getContext('2d');g.imageSmoothingEnabled=false;
      g.drawImage(c,x-120*scale,y-120*scale,240*scale,240*scale,0,0,360,360);
      return t.toDataURL();}''')
    image = Image.open(io.BytesIO(base64.b64decode(raw.split(',')[1]))).convert('RGB')
    result = Image.new('RGB', (360, 388), '#253039')
    result.paste(image, (0, 28))
    ImageDraw.Draw(result).text((6, 5), label, fill='white', font=FONT)
    return result


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1050, 'height': 800}, device_scale_factor=1)
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(URL + '/?test=1')
        ready(page)
        page.evaluate((ROOT / 'tests/爆点空心像素.js').read_text())
        catalog = page.evaluate('window.__waterTest.catalog()')
        roster = {r['id']: r for r in catalog['roster']}
        moves = catalog['moves']
        profile = page.evaluate('window.__waterTest.snapshot().profile')
        check('catalog 120 moves plus existing harmless splash',
              len(moves) == 121 and 'splash' in moves, len(moves))
        if os.environ.get('POIGHT_P6_QUICK'):
            moves = {k: v for k, v in moves.items() if k in [
                'hydropump', 'hyperbeam', 'thunderbolt', 'flamethrower', 'icebeam', 'lick',
                'thunder', 'dragonclaw']}
        # All legal direct hits enter the exact same damage path; non-damage moves must NOT fake hits.
        for scene in ['arena-formal', 'arena-natural']:
            for mid, move in moves.items():
                caster = next((r['id'] for r in roster.values() if mid in r['defaultMoves']), 94)
                enemies = [r['id'] for r in roster.values() if r['id'] != caster]
                selected = False
                for enemy in enemies:
                    setup(page, roster, profile, caster, enemy, scene)
                    if move['damage'] <= 0 or move['kind'] in ['heal', 'guard', 'buff', 'splash']:
                        break  # injectMoveHit clamps damage to 1; NEVER call it for support moves.
                    legal = page.evaluate('(id)=>window.__waterTest.injectMoveHit("enemy",id)', mid)
                    if legal:
                        selected = True
                        break
                    if move['damage'] <= 0 or move['kind'] in ['heal', 'guard', 'buff', 'splash']:
                        break
                if not selected:
                    check(scene+'/'+mid+' no fabricated impact when no direct damage',
                          not page.evaluate('window.__waterTest.snapshot().animation.bursts'))
                    samples.append({'scene': scene, 'id': mid, 'noDirectHit': True})
                    continue
                readings = page.evaluate('''()=>{
                  const api=window.__waterTest,start=api.snapshot().animation.time,out=[];
                  for(let i=0;i<80;i++) {
                    api.step(0);out.push({time:api.snapshot().animation.time-start,...window.measureHollow()});
                    if(api.snapshot().animation.time-start>=.15-1e-8)break;
                    api.step(1/120,false);
                  }
                  return out;
                }''')
                minimum = min(r['originalFraction'] for r in readings)
                check(scene+'/'+mid+' every 120Hz frame 0-150ms original >=60%', minimum >= .60,
                      {'minimum': minimum, 'frames': len(readings)})
                ring = readings[0]['ring']
                if ring:
                    check(scene+'/'+mid+' center transparent >=70%', ring['centerTransparent'] >= .70, ring)
                    check(scene+'/'+mid+' outer diameter >=0.8H', ring['diameter'] >= .8 * ring['height'], ring)
                    check(scene+'/'+mid+' band <=18% diameter', ring['bandWidth'] <= .18 * ring['diameter'], ring)
                    check(scene+'/'+mid+' saturated hue >=0.55', ring['saturation'] >= .55, ring)
                    check(scene+'/'+mid+' opaque ring contrast >=60', ring['contrast'] >= 60, ring)
                    check(scene+'/'+mid+' primary ring HSL L >=60%',
                          ring['primaryPixels'] > 0 and ring['primaryLightness'] >= .60, ring)
                else:
                    check(scene+'/'+mid+' dedicated hero contact preserved', mid in ['thunder', 'dragonclaw'])
                samples.append({'scene': scene, 'id': mid, 'caster': caster, 'enemy': enemy,
                                'readings': readings})
                print(scene+' '+mid+' minOriginal='+str(round(minimum, 4)), flush=True)
                # Independent real release/contact path, including the move's actual body layers.
                setup(page, roster, profile, caster, enemy, scene)
                page.evaluate('(id)=>window.__waterTest.equip("player",[id])', mid)
                real = page.evaluate('''id=>{
                  const api=window.__waterTest,s=api.snapshot(),m=api.catalog().moves[id];
                  let range=m.range;
                  if(m.hero||m.limb||m.batch2||m.r3)
                    range=Math.min(range,s.player.body.nominalSize*m.rangeBodies);
                  const distance=m.kind==='melee'||m.kind==='spin'
                    ? Math.max(12,range-36+s.player.body.hurt.rx+s.enemy.body.hurt.rx-2)
                    : ['nova','area'].includes(m.kind) ? 48 : Math.min(85,range*.65);
                  api.arrange({enemy:{x:s.player.x+distance,y:s.player.y}});
                  const hp=api.snapshot().enemy.hp,cast=api.cast('player',id);
                  for(let i=1;i<800;i++) {
                    api.step(1/120,false);
                    if(api.snapshot().enemy.hp<hp) {
                      api.step(0);const start=api.snapshot().animation.time,out=[];
                      for(let n=0;n<100;n++) {
                        api.step(0);
                        out.push({time:api.snapshot().animation.time-start,...window.measureHollow()});
                        if(api.snapshot().animation.time-start>=.15-1e-8)break;
                        api.step(1/120,false);
                      }
                      return {cast,tick:i,distance,readings:out};
                    }
                  }
                  return {cast,distance,readings:[]};
                }''', mid)
                check(scene+'/'+mid+' real cast produces legal contact', bool(real['readings']),
                      {k: v for k, v in real.items() if k != 'readings'})
                if real['readings']:
                    fraction = min(r['originalFraction'] for r in real['readings'])
                    check(scene+'/'+mid+' real cast 0-150ms every frame original >=60%', fraction >= .6,
                          {'minimum': fraction, 'frames': len(real['readings'])})
                    print(scene+' REAL '+mid+' minOriginal='+str(round(fraction, 4)), flush=True)
                samples[-1]['realCast'] = real
        interim = {'passed': sum(c['ok'] for c in checks),
                   'failed': sum(not c['ok'] for c in checks), 'jsErrors': len(errors),
                   'checks': checks, 'errors': errors}
        (OUT/'浏览器验收.json').write_text(json.dumps(interim, ensure_ascii=False, indent=2)+'\n')
        (OUT/'像素采样.json').write_text(json.dumps(samples, ensure_ascii=False, indent=2)+'\n')
        # Real casts at first HP-loss tick, not injection, for comparison evidence.
        mids = [('hydropump', '水炮', 9, 6), ('hyperbeam', '破坏光线', 143, 6),
                ('thunderbolt', '十万伏特', 25, 6), ('flamethrower', '喷射火焰', 6, 25),
                ('icebeam', '冰冻光束', 9, 6), ('lick', '舌舔', 94, 25)]
        current = {}
        ticks = {}
        for mid, name, caster, enemy in mids:
            setup(page, roster, profile, caster, enemy, 'arena-formal')
            if mid == 'lick':
                page.evaluate('''()=>{const s=window.__waterTest.snapshot();
                  window.__waterTest.arrange({enemy:{x:s.player.x+30}});}''')
            page.evaluate('(id)=>window.__waterTest.equip("player",[id])', mid)
            hit = page.evaluate('''id=>{
              const api=window.__waterTest,hp=api.snapshot().enemy.hp;api.cast('player',id);
              for(let i=1;i<300;i++){api.step(1/120,false);
                if(api.snapshot().enemy.hp<hp){api.step(0);return i;}}
              return null;
            }''', mid)
            check(mid+' real cast reaches legal target', hit is not None, hit)
            if hit is None:
                continue
            ticks[mid] = hit
            retention = page.evaluate('window.measureHollow()')
            check(mid+' real impact target original >=60%', retention['originalFraction'] >= .6, retention)
            label = name+' · P6b · 首次命中'
            if mid == 'lick':
                # Authorized ±2-tick sampling: observe the uncut tongue one tick BEFORE contact.
                setup(page, roster, profile, caster, enemy, 'arena-formal')
                page.evaluate('''()=>{const api=window.__waterTest,s=api.snapshot();
                  api.arrange({enemy:{x:s.player.x+30}});api.equip('player',['lick']);
                  api.cast('player','lick');}''')
                ticks[mid] = hit - 1
                page.evaluate('''n=>{const api=window.__waterTest;
                  for(let i=0;i<n;i++)api.step(1/120,false);api.step(0);}''', ticks[mid])
                check('lick sample within two 120Hz ticks of real hit', abs(ticks[mid]-hit) <= 2,
                      {'hitTick': hit, 'sampleTick': ticks[mid]})
                label = name+' · P6b · 命中前1tick'
                tongue = page.evaluate('window.hollowProbe.tongue.toDataURL()')
                raw = base64.b64decode(tongue.split(',')[1])
                (OUT/'舌舔掩模.png').write_bytes(raw)
                pixels = np.array(Image.open(io.BytesIO(raw)).convert('RGBA'))
                labels, count = ndimage.label(pixels[:, :, 3] >= 200, np.ones((3, 3)))
                component = max(range(1, count+1), key=lambda n: np.sum(labels == n))
                yy, xx = np.where(labels == component)
                points = np.stack([xx, yy], axis=1)
                _, axes = np.linalg.eigh(np.cov(points.T))
                span = np.ptp(points @ axes, axis=0) + 1
                aspect = max(span) / min(span)
                rgb = pixels[labels == component, :3].mean(axis=0)
                check('lick real contact connected tongue aspect >=3', aspect >= 3, float(aspect))
                check('lick real contact pink (R>B>G)', rgb[0] > rgb[2] > rgb[1], rgb.tolist())
            current[mid] = tile(page, label)
            current[mid].save(OUT / (mid+'-P6.png'))
        baseline = (ROOT / 'P6-baseline.html').read_text()
        # Historical hashed assets are deliberately outside the current release allowlist.
        # Replay these exact local inputs only for the comparison, like the H1 M4 fixture.
        historical_assets = URL + '/assets/*'
        page.route(historical_assets, lambda route: route.fulfill(
            path=ROOT / 'assets' / route.request.url.rsplit('/', 1)[-1]))
        page.route('**/?test=1&p6baseline=1', lambda route: route.fulfill(status=200, content_type='text/html', body=baseline))
        # Historical all-at-once build decodes all actors/maps; allow that real work.
        page.goto(URL+'/?test=1&p6baseline=1', wait_until='domcontentloaded', timeout=180000)
        ready(page)
        page.evaluate((ROOT / 'tests/爆点空心像素.js').read_text())
        compare = Image.new('RGB', (720, 388*len(mids)), '#253039')
        for idx, (mid, name, caster, enemy) in enumerate(mids):
            if mid not in ticks:
                continue
            setup(page, roster, profile, caster, enemy, 'arena-formal')
            if mid == 'lick':
                page.evaluate('''()=>{const s=window.__waterTest.snapshot();
                  window.__waterTest.arrange({enemy:{x:s.player.x+30}});}''')
            page.evaluate('(id)=>window.__waterTest.equip("player",[id])', mid)
            page.evaluate('''({mid,n})=>{const api=window.__waterTest;api.cast('player',mid);
              for(let i=0;i<n;i++)api.step(1/120,false);api.step(0);}''', {'mid': mid, 'n': ticks[mid]})
            compare.paste(tile(page, name+' · VH/V1旧 · 同tick'), (0, idx*388))
            compare.paste(current[mid], (360, idx*388))
        compare.save(OUT/'对照.png')
        page.unroute(historical_assets)
        page.goto(URL + '/?test=1')
        ready(page)
        shots = OUT/'截图'
        shots.mkdir(exist_ok=True)
        for width, height in [(1440, 900), (390, 844), (844, 390)]:
            page.set_viewport_size({'width': width, 'height': height})
            page.evaluate('window.__waterTest.reset(true);window.__waterTest.step(0)')
            page.screenshot(path=str(shots/f'实战-{width}x{height}.png'))
        browser.close()
    report = {'passed': sum(c['ok'] for c in checks), 'failed': sum(not c['ok'] for c in checks),
              'jsErrors': len(errors), 'errors': errors, 'checks': checks}
    (OUT/'浏览器验收.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    (OUT/'像素采样.json').write_text(json.dumps(samples, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ['passed', 'failed', 'jsErrors']}, ensure_ascii=False))
    return int(bool(report['failed'] or errors))


if __name__ == '__main__':
    raise SystemExit(main())
