"""Read-only reproduction of the all-move REAL-cast failures. Not a passing P6 receipt."""
import json
import os
import time
from importlib import import_module
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

p6 = import_module('验收-爆点空心')
ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/P6'
URL = os.environ['POIGHT_TEST_URL'].rstrip('/')
CASES = [('thunder', 25, 1, 76.7754, 83, 3, .4525),
         ('bite', 66, 1, 31.16, 55, 13, .16007194244604317),
         ('quickattack', 25, 1, 76.7754, 10, 15, .5048203330411919),
         ('hex', 94, 1, 85, 128, 4, .36315390447308565)]
errors, records = [], []
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1050, 'height': 800})
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(URL + '/?test=1')
    p6.ready(page)
    page.evaluate((ROOT / 'tests/爆点空心像素.js').read_text())
    catalog = page.evaluate('window.__waterTest.catalog()')
    roster = {r['id']: r for r in catalog['roster']}
    profile = page.evaluate('window.__waterTest.snapshot().profile')
    sheet = Image.new('RGB', (720, 388 * len(CASES)), '#253039')
    for row, (mid, caster, enemy, distance, tick, worst, expected) in enumerate(CASES):
        p6.setup(page, roster, profile, caster, enemy, 'arena-formal')
        page.evaluate('''({id,distance})=>{
          const api=window.__waterTest,s=api.snapshot();api.equip('player',[id]);
          api.arrange({enemy:{x:s.player.x+distance,y:s.player.y}});api.cast('player',id);
        }''', {'id': mid, 'distance': distance})
        page.evaluate('''n=>{for(let i=0;i<n;i++)window.__waterTest.step(1/120,false);
          window.__waterTest.step(0);}''', tick)
        first = p6.tile(page, mid + ' · 真实首次命中')
        page.evaluate('''n=>{const api=window.__waterTest;
          for(let i=0;i<n;i++){api.step(0);api.step(1/120,false);}api.step(0);}''', worst)
        reading = page.evaluate('window.measureHollow()')
        reading.update(id=mid, caster=caster, target=enemy, hitTick=tick, readingIndex=worst)
        reading['reproduced'] = abs(reading['originalFraction'] - expected) < .06
        records.append(reading)
        failed = p6.tile(page, mid + ' · 原色 ' + f"{reading['originalFraction']:.2%}")
        first.save(OUT / (mid + '-阻塞-首次命中.png'))
        failed.save(OUT / (mid + '-阻塞-最低原色.png'))
        if mid == 'thunder':
            # Diagnostic ablation ONLY, never part of the passing acceptance path.
            reading['diagnosticNoWhiteSweep'] = page.evaluate('''()=>{
              const proto=window.PoightHeroVisuals.prototype, original=proto.electrify;
              proto.electrify=function(ctx,target,...args){
                const age=this.shocks.get(target);this.shocks.delete(target);
                try{return original.call(this,ctx,target,...args);}
                finally{if(age!==undefined)this.shocks.set(target,age);}
              };
              try{window.__waterTest.step(0);return window.measureHollow().originalFraction;}
              finally{proto.electrify=original;window.__waterTest.step(0);}
            }''')
            reading['diagnosticNoRing'] = page.evaluate('''()=>{
              const proto=window.PoightHeroVisuals.prototype, original=proto.paint;
              proto.paint=function(ctx,s){
                if(s.kind==='thunder'&&s.part==='ring')return;
                return original.call(this,ctx,s);
              };
              try{window.__waterTest.step(0);return window.measureHollow().originalFraction;}
              finally{proto.paint=original;window.__waterTest.step(0);}
            }''')
        sheet.paste(first, (0, row * 388))
        sheet.paste(failed, (360, row * 388))
        time.sleep(.01)
    sheet.save(OUT / '真实施放阻塞.png')
    browser.close()
report = {'purpose': 'failure reproduction, NOT P6 acceptance', 'cases': records,
          'jsErrors': len(errors), 'errors': errors}
(OUT / '阻塞复现.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False), flush=True)
raise SystemExit(int(bool(errors) or not all(r['reproduced'] for r in records)))
