"""Real releases, three body sizes, both arenas; never inject damage or alter move clocks."""
import json
import os
import time
from importlib import import_module

from playwright.sync_api import sync_playwright

helpers = import_module('验收-爆点空心')
ROOT, URL = helpers.ROOT, helpers.URL
OUT = ROOT / '验收记录/P6b'
OUT.mkdir(parents=True, exist_ok=True)
checks, errors, rows = [], [], []


def check(name, ok, detail=None):
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
    if not ok:
        print('FAIL ' + name + ' ' + json.dumps(detail, ensure_ascii=False), flush=True)


def save():
    report = {'passed': sum(c['ok'] for c in checks), 'failed': sum(not c['ok'] for c in checks),
              'jsErrors': len(errors), 'errors': errors, 'checks': checks}
    (OUT / '浏览器验收.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    (OUT / '全招真实施放.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    return report


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1050, 'height': 800}, device_scale_factor=1)
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(URL + '/?test=1')
        helpers.ready(page)
        page.evaluate((ROOT / 'tests/爆点空心像素.js').read_text())
        catalog = page.evaluate('window.__waterTest.catalog()')
        roster = {r['id']: r for r in catalog['roster']}
        moves = catalog['moves']
        profile = page.evaluate('window.__waterTest.snapshot().profile')
        check('complete inventory: 121', len(moves) == 121, len(moves))
        only = os.environ.get('POIGHT_P6B_MOVES')
        if only:
            moves = {k: v for k, v in moves.items() if k in only.split(',')}
        for scene in ['arena-formal', 'arena-natural']:
            for mid, move in moves.items():
                for enemy in [1, 6, 208]:
                    caster = next((r['id'] for r in roster.values()
                                   if mid in r['defaultMoves'] and r['id'] != enemy),
                                  94 if enemy != 94 else 25)
                    helpers.setup(page, roster, profile, caster, enemy, scene)
                    page.evaluate('(id)=>window.__waterTest.equip("player",[id])', mid)
                    support = move['kind'] in ['heal', 'guard', 'buff', 'splash']
                    efficacy = catalog['efficacy'].get(str(move['type']), {})
                    immune = any(efficacy.get(str(t), 1) == 0 and
                                 not (move.get('waterEffective') and t == 11)
                                 for t in roster[enemy]['types'])
                    result = page.evaluate('''({id,noHit})=>{
                      const api=window.__waterTest,s=api.snapshot(),m=api.catalog().moves[id];
                      let range=m.range;
                      if(m.hero||m.limb||m.batch2||m.r3)
                        range=Math.min(range,s.player.body.nominalSize*m.rangeBodies);
                      const distance=['melee','spin'].includes(m.kind)
                        ? Math.max(12,range-36+s.player.body.hurt.rx+s.enemy.body.hurt.rx-2)
                        : ['nova','zone'].includes(m.kind) ? 48 : Math.min(85,range*.65);
                      api.arrange({enemy:{x:s.player.x+distance,y:s.player.y},
                        ...(m.kind==='heal' ? {player:{hp:s.player.maxHP*.65}} : {})});
                      const hp=api.snapshot().enemy.hp,cast=api.cast('player',id);
                      for(let i=1;i<800;i++) {
                        api.step(1/120,false);
                        if(api.snapshot().enemy.hp<hp) {
                          api.step(0);const start=api.snapshot().animation.time,out=[];
                          for(let n=0;n<80;n++) {
                            api.step(0);
                            out.push({time:api.snapshot().animation.time-start,...window.measureHollow()});
                            window.hollowProbe.sampleRing=false;
                            if(api.snapshot().animation.time-start>=.15-1e-8)break;
                            api.step(1/120,false);
                          }
                          return {cast,tick:i,distance,readings:out};
                        }
                        if(noHit&&i===180) {
                          api.step(0);
                          return {cast,distance,noDamage:api.snapshot().enemy.hp===hp,
                            contacts:api.snapshot().animation.contacts.length,
                            readings:[window.measureHollow()]};
                        }
                      }
                      return {cast,distance,readings:[]};
                    }''', {'id': mid, 'noHit': support or immune})
                    prefix = f'{scene}/{mid}/{enemy}'
                    check(prefix + ' real input accepted', result['cast'], result['cast'])
                    if support or immune:
                        check(prefix + ' support/immunity: no fabricated hit',
                              result.get('noDamage') and result.get('contacts') == 0, result)
                        minimum = min((r['originalFraction'] for r in result['readings']), default=0)
                        check(prefix + ' unhit target remains original >=60%', minimum >= .60, minimum)
                        row = {'scene': scene, 'id': mid, 'target': enemy, 'caster': caster,
                               'status': 'support-no-hit' if support else 'type-immune-no-hit',
                               'minimum': minimum, 'result': result}
                    else:
                        check(prefix + ' real cast reaches target', bool(result['readings']),
                              {k: v for k, v in result.items() if k != 'readings'})
                        minimum = min((r['originalFraction'] for r in result['readings']), default=0)
                        check(prefix + ' every 120Hz frame 0-150ms original >=60%', minimum >= .60,
                              {'minimum': minimum, 'frames': len(result['readings'])})
                        if result['readings']:
                            ring = result['readings'][0]['ring']
                            if ring:
                                check(prefix + ' center transparent >=70%', ring['centerTransparent'] >= .70, ring)
                                check(prefix + ' outer diameter >=0.8H', ring['diameter'] >= .8 * ring['height'], ring)
                                check(prefix + ' band <=18% diameter', ring['bandWidth'] <= .18 * ring['diameter'], ring)
                                check(prefix + ' saturation >=0.55', ring['saturation'] >= .55, ring)
                                check(prefix + ' luminance contrast >=60', ring['contrast'] >= 60, ring)
                                check(prefix + ' primary ring HSL L >=60%',
                                      ring['primaryPixels'] > 0 and ring['primaryLightness'] >= .60, ring)
                            else:
                                check(prefix + ' dedicated contact', mid in ['thunder', 'dragonclaw'])
                        row = {'scene': scene, 'id': mid, 'target': enemy, 'caster': caster,
                               'status': 'real-hit', 'minimum': minimum, 'result': result}
                    rows.append(row)
                    print(prefix + ' ' + row['status'] + ' minimum=' + str(round(minimum, 6)), flush=True)
                save()
                time.sleep(.005)
        browser.close()
    report = save()
    minima = []
    for mid in moves:
        relevant = [r for r in rows if r['id'] == mid]
        hit = [r for r in relevant if r['status'] == 'real-hit']
        worst = min(hit or relevant, key=lambda r: r['minimum'])
        minima.append({'id': mid, 'name': moves[mid]['name'], 'minimum': worst['minimum'],
                       'target': worst['target'], 'scene': worst['scene'],
                       'status': worst['status'], 'realHitCases': len(hit),
                       'noHitCases': len(relevant) - len(hit)})
    (OUT / '每招最低保留率.json').write_text(json.dumps(minima, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['passed', 'failed', 'jsErrors']}, ensure_ascii=False))
    return int(bool(report['failed'] or errors))


if __name__ == '__main__':
    raise SystemExit(main())
