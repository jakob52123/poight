"""FX1: real before/after casts, two actor pairs and both arenas; no physics writes."""
import argparse
import base64
import io
import json
import math
import os
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/FX1'
OUT.mkdir(parents=True, exist_ok=True)
MOVES = ['ember', 'poisonsting', 'bubble', 'razorleaf', 'icywind', 'gust', 'swift',
         'triattack', 'leafstorm', 'psychocut', 'hydropump', 'solarbeam', 'psybeam',
         'dragonbreath', 'hyperbeam', 'signalbeam', 'gigadrain', 'freezedry', 'flashcannon']
PAIRS = [(6, 143), (25, 1)]
SCENES = ['arena-formal', 'arena-natural']
FONT = ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc', 12)
PROBE = r'''() => {
  window.fxTile = () => {
    const s=window.__waterTest.snapshot(), game=document.querySelector('#game'),
      k=game.width/s.viewport.width, c=document.createElement('canvas');
    c.width=300;c.height=300;const ctx=c.getContext('2d');ctx.imageSmoothingEnabled=false;
    const x=((s.player.x+s.enemy.x)/2-s.camera.x)*k,
      y=((s.player.y+s.enemy.y)/2-16-s.camera.y)*k,r=90*k;
    ctx.drawImage(game,Math.round(x-r),Math.round(y-r),Math.round(r*2),Math.round(r*2),0,0,300,300);
    return c.toDataURL();
  };
  window.fxMeasure = () => {
    const p=window.va2PixelProbe, e=p.entries.at(-1), cfg=window.PoightVA2Moves[e.args[0]],
      mask=cfg.beam?e.canvas:e.symbol, ctx=mask.getContext('2d'),
      data=ctx.getImageData(0,0,mask.width,mask.height).data, inv=e.matrix.inverse(),
      dx=e.args[2].x-e.args[1].x,dy=e.args[2].y-e.args[1].y,a=Math.atan2(dy,dx),
      lum=(r,g,b)=>.2126*r+.7152*g+.0722*b;
    let lo=Infinity,hi=-Infinity,nlo=Infinity,nhi=-Infinity,L=0,count=0,dark=0;
    for(let y=0;y<mask.height;y++)for(let x=0;x<mask.width;x++){
      const i=(y*mask.width+x)*4;if(data[i+3]<250)continue;
      const r=data[i]/255,g=data[i+1]/255,b=data[i+2]/255,
        mx=Math.max(r,g,b),mn=Math.min(r,g,b),l=(mx+mn)/2;
      L+=l;count++;if(l<.55 || (b>r*.8 && r>g*1.2))dark++;
      const q=new DOMPoint(x+.5,y+.5).matrixTransform(inv),
        u=q.x*Math.cos(a)+q.y*Math.sin(a),v=-q.x*Math.sin(a)+q.y*Math.cos(a);
      lo=Math.min(lo,u);hi=Math.max(hi,u);nlo=Math.min(nlo,v);nhi=Math.max(nhi,v);
    }
    const pixel=1/Math.hypot(e.matrix.a,e.matrix.b),
      result=window.measureVA2Pixels();
    delete result.composite;delete result.background;delete result.mask;
    return {...result,lightness:L/count,fireDarkFraction:dark/count,
      length:hi-lo+pixel,width:nhi-nlo+pixel,
      maxDimension:Math.max(hi-lo,nhi-nlo)+pixel};
  };
}'''
parser = argparse.ArgumentParser()
parser.add_argument('--baseline', action='store_true')
parser.add_argument('--priority', action='store_true')
args = parser.parse_args()
checks, errors, records = [], [], []


def check(name, ok, detail=None):
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
    if not ok:
        print('FAIL', name, detail, flush=True)


def ready(page):
    for _ in range(600):
        if page.evaluate('()=>{try{return !!window.__waterTest?.snapshot().artReady}catch{return false}}'):
            return
        time.sleep(.03)
    raise TimeoutError('art load')


def decode(raw):
    return Image.open(io.BytesIO(base64.b64decode(raw.split(',')[1]))).convert('RGB')


failure = None
try:
    if not args.baseline:
        for path in sorted((ROOT / '招式动画/VA2').glob('*.png')):
            rgba = Image.open(path).convert('RGBA')
            opaque = [p for p in rgba.get_flattened_data() if p[3] >= 250]
            minimum = min((max(p[:3])+min(p[:3]))/510 for p in opaque)
            check(path.name + ' every opaque source color HSL L >=55%', minimum >= .55, minimum)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(os.environ['POIGHT_TEST_URL'].rstrip('/') + '/?test=1')
        ready(page)
        page.evaluate((ROOT / 'tests/招式动画-VA2像素.js').read_text())
        page.evaluate(PROBE)
        profile = page.evaluate('window.__waterTest.snapshot().profile')
        roster = {r['id']: r for r in page.evaluate('window.__waterTest.catalog().roster')}
        baseline = {} if args.baseline else json.loads((OUT / '改前.json').read_text())['records']
        if not args.baseline:
            baseline = {r['key']: r for r in baseline}
        chosen = MOVES[:2] if args.priority else MOVES
        for mid in chosen:
            for cid, eid in PAIRS:
                for scene in SCENES:
                    key = f'{mid}/{cid}/{eid}/{scene}'
                    print('CAST', key, flush=True)
                    page.evaluate('(p)=>window.__waterTest.select(p)', {
                        **profile, 'player': cid, 'enemy': eid, 'map': scene,
                        'playerMoves': roster[cid]['defaultMoves'],
                        'enemyMoves': roster[eid]['defaultMoves'],
                    })
                    def reset(mid=mid, cid=cid, scene=scene):
                        page.evaluate('window.__waterTest.reset(true)')
                        s = page.evaluate('window.__waterTest.snapshot()')
                        b = s['environment']['bounds']
                        x = (b['left'] + b['right']) / 2 - (450 if scene == 'arena-formal' else 0)
                        y = (b['top'] + b['bottom']) / 2 - 95
                        page.evaluate('(v)=>window.__waterTest.arrange(v)', {
                            'ai': False, 'player': {'x': x, 'y': y, 'a': 0},
                            'enemy': {'x': x + (40 if mid == 'razorleaf' and cid == 25 else 100), 'y': y},
                        })
                        page.evaluate('(id)=>window.__waterTest.equip("player",[id])', mid)
                        page.evaluate('window.__waterTest.step(.1)')
                        return page.evaluate('window.__waterTest.snapshot()')
                    initial = reset()
                    check(key + ' real cast', page.evaluate('(id)=>window.__waterTest.cast("player",id)', mid))
                    timing = page.evaluate('''()=>{
                      const api=window.__waterTest,hp=api.snapshot().enemy.hp;
                      let release=null;for(let n=1;n<=480;n++){
                        api.step(1/120);const s=api.snapshot();
                        if(release===null&&s.bullets.length)release=n;
                        if(s.enemy.hp<hp)return {release,hit:n,damage:hp-s.enemy.hp,
                          burstSize:s.animation.bursts.at(-1).size,targetH:s.enemy.body.visibleSize[1]};
                      }return null;
                    }''')
                    check(key + ' actual contact', timing is not None)
                    if timing is None:
                        continue
                    reset()
                    page.evaluate('(id)=>window.__waterTest.cast("player",id)', mid)
                    page.evaluate('(n)=>{for(let i=0;i<n;i++)window.__waterTest.step(1/120)}', timing['hit'] - 2)
                    page.evaluate('window.va2PixelProbe.entries=[];window.va2PixelProbe.enabled=true;window.__waterTest.step(1/120)')
                    metrics = page.evaluate('window.fxMeasure()')
                    page.evaluate('window.va2PixelProbe.enabled=false')
                    records.append({'key': key, 'id': mid, **timing, **metrics})
                    if not args.baseline:
                        before = baseline[key]
                        check(key + ' unchanged release/hit/damage', all(
                            before[k] == timing[k] for k in ['release', 'hit', 'damage']), timing)
                        check(key + ' HSL L >=55%', metrics['lightness'] >= .55, metrics['lightness'])
                        check(key + ' contrast >=60', metrics['contrast'] >= 60, metrics['contrast'])
                        minimum_color = .10 if mid == 'poisonsting' else .30
                        check(key + f' saturation >=.55/color >={minimum_color:.2f}',
                              metrics['saturation'] >= .55
                              and metrics['colorFraction'] >= minimum_color, metrics)
                        check(key + ' leading plane', metrics['frontOverrun'] <= metrics['pixelSize'], metrics['frontOverrun'])
                        check(key + ' impact >=.8 target H', timing['burstSize'] >= timing['targetH'] * .8)
                        h, pixel = metrics['height'], metrics['pixelSize']
                        # Raster quantization is <= one screen pixel at both contour ends.
                        if mid == 'poisonsting':
                            check(key + ' needle .30-.40H / <=.08H',
                                  .30*h-pixel <= metrics['length'] <= .40*h+pixel
                                  and metrics['width'] <= .08*h+pixel, metrics)
                        elif not page.evaluate('(id)=>!!window.PoightVA2Moves[id].beam', mid):
                            check(key + ' small projectile .25-.45H',
                                  .25*h-pixel <= metrics['maxDimension'] <= .45*h+pixel, metrics)
                        else:
                            check(key + ' unchanged beam width', abs(metrics['minimumBeamWidth']
                                  - before['minimumBeamWidth']) <= pixel, metrics['minimumBeamWidth'])
                        if mid == 'ember':
                            check(key + ' fire dark/brown/purple <=5%', metrics['fireDarkFraction'] <= .05, metrics)
                    if (cid, eid, scene) == (6, 143, 'arena-formal'):
                        indices = [max(0, timing['release']-2), (timing['release']+timing['hit'])//2,
                                   timing['hit'], timing['hit']+19]
                        reset()
                        page.evaluate('(id)=>window.__waterTest.cast("player",id)', mid)
                        frames, previous = [], 0
                        for n in indices:
                            page.evaluate('(n)=>{for(let i=0;i<n;i++)window.__waterTest.step(1/120)}', n-previous)
                            previous = n
                            frames.append(decode(page.evaluate('window.fxTile()')))
                        sheet = Image.new('RGB', (1200, 324), '#223540')
                        for col, (frame, tick) in enumerate(zip(frames, indices)):
                            sheet.paste(frame, (300*col, 24))
                            ImageDraw.Draw(sheet).text((300*col+5, 5), f'{mid} / {tick/120:.3f}s / 1x', font=FONT, fill='white')
                        folder = OUT / ('改前' if args.baseline else '改后')
                        folder.mkdir(exist_ok=True)
                        sheet.save(folder / (mid + '.png'))
                        if not args.baseline:
                            compare = Image.new('RGB', (1200, 688), '#223540')
                            d = ImageDraw.Draw(compare)
                            d.text((5, 5), '改前（线上 VA2）', font=FONT, fill='white')
                            compare.paste(Image.open(OUT / '改前' / (mid + '.png')), (0, 20))
                            d.text((5, 349), '改后（FX1）', font=FONT, fill='white')
                            compare.paste(sheet, (0, 364))
                            dest = OUT / '对比'
                            dest.mkdir(exist_ok=True)
                            compare.save(dest / (mid + '.png'))
        if not args.baseline and not args.priority:
            overview = Image.new('RGB', (1200, math.ceil(len(MOVES)/2)*172), '#223540')
            for i, mid in enumerate(MOVES):
                im = Image.open(OUT / '对比' / (mid + '.png'))
                overview.paste(im.resize((600, 172), Image.Resampling.NEAREST), ((i%2)*600, (i//2)*172))
            overview.save(OUT / '对比总览.png')
            for w, h in [(1440, 900), (390, 844), (844, 390)]:
                page.set_viewport_size({'width': w, 'height': h})
                reset()
                page.evaluate('window.__waterTest.cast("player","flashcannon");window.__waterTest.step(.6)')
                page.screenshot(path=str(OUT / f'实战-{w}x{h}.png'))
        browser.close()
except Exception as exc:  # noqa: BLE001
    failure = f'{type(exc).__name__}: {exc}'
finally:
    report = {'passed': sum(c['ok'] for c in checks),
              'failed': sum(not c['ok'] for c in checks) + bool(failure),
              'jsErrors': len(errors), 'failure': failure, 'errors': errors,
              'checks': checks, 'records': records}
    filename = '改前.json' if args.baseline else '优先验收.json' if args.priority else '浏览器验收.json'
    (OUT / filename).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['passed', 'failed', 'jsErrors', 'failure']}, ensure_ascii=False))
    if report['failed'] or errors:
        raise SystemExit(1)
