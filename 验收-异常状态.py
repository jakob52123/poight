"""S1：固定种子、真实浏览器战斗状态/命中概率/输入/HUD验收。"""
import base64
import colorsys
import io
import json
import os
import statistics
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '验收记录/异常状态'
SHOTS = OUT / '截图'
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get('POIGHT_TEST_URL', 'http://localhost:8870/').rstrip('/')
checks, errors = [], []


def check(name, ok, detail=None):
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})


def luminance(rgb):
    return rgb[0]*.2126 + rgb[1]*.7152 + rgb[2]*.0722


def visual_check(page, status, age):
    """Compare actual status rendering with the same frame minus the FX layer, on red soil."""
    data = page.evaluate("window.__waterTest.statusTest.visual('player')")
    images = [Image.open(io.BytesIO(base64.b64decode(data[k].split(',')[1]))).convert('RGB')
              for k in ('shown', 'base')]
    shown, base = images
    b = data['box']
    x, y, w, h = (b[k] for k in ('x', 'y', 'width', 'height'))
    if status == 'frz':
        body = shown.crop((int(x), int(y), int(x+w), int(y+h)))
        pixels = list(body.get_flattened_data())
        cyan = sum(g > r + 22 and blue > r + 30 and g > 140
                   for r, g, blue in pixels) / len(pixels)
        check(f'freeze cyan body occupancy >=40% age {age}', cyan >= .4, cyan)
    differences, saturations = [], []
    # Satellite regions exclude sprite body, overhead HUD and floating text.
    for yy in range(max(0, int(y)-8), min(shown.height, int(y+h)+32)):
        for xx in range(max(0, int(x)-35), min(shown.width, int(x+w)+35)):
            if x-3 <= xx <= x+w+3 and y-3 <= yy <= y+h+3:
                continue
            a, bg = shown.getpixel((xx, yy)), base.getpixel((xx, yy))
            if max(abs(a[i]-bg[i]) for i in range(3)) < 20:
                continue
            differences.append(abs(luminance(a)-luminance(bg)))
            saturations.append(colorsys.rgb_to_hsv(*(v/255 for v in a))[1])
    contrast = statistics.mean(differences) if differences else 0
    saturation = statistics.median(saturations) if saturations else 0
    check(f'{status} persistent FX brightness difference >=60 age {age}',
          len(differences) >= 30 and contrast >= 60,
          {'pixels': len(differences), 'meanAbsLumaDifference': contrast})
    check(f'{status} persistent FX saturation >=.55 age {age}', saturation >= .55, saturation)
    return data


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(URL + '/?test=1')
        deadline = time.monotonic() + 60
        while not page.evaluate('window.__waterTest?.snapshot().artReady'):
            assert time.monotonic() < deadline, errors
            time.sleep(.03)
        catalog = page.evaluate('window.__waterTest.catalog()')
        roster = {c['id']: c for c in catalog['roster']}
        profile = page.evaluate('window.__waterTest.snapshot().profile')
        arena = next(s['id'] for s in catalog['scenes'] if s.get('type') == 'arena')
        profile.update(player=25, enemy=6, playerMoves=roster[25]['defaultMoves'],
                       enemyMoves=roster[6]['defaultMoves'], map=arena)
        assert page.evaluate('p => window.__waterTest.select(p)', profile)
        # Use real engine entry points. State application hook isolates durations from hitstop.
        result = page.evaluate('''() => {
          const t = window.__waterTest, s = t.statusTest, out = [];
          const check = (name, ok, detail = null) => out.push({name, ok: !!ok, detail});
          const snap = () => t.snapshot();
          const reset = () => {
            t.reset(true); t.arrange({ai:false, player:{x:400,y:400},enemy:{x:540,y:400}});
            s.types('player',[1]); s.types('enemy',[1]); s.seed(1);
            t.equip('player',['scratch','protect','rapidspin','watergun']);
            t.equip('enemy',['scratch','protect','watergun','ember']);
          };
          for (const [id, duration, label] of [['par',5,'麻痹'],['brn',5,'烧伤'],
              ['frz',1.5,'冰冻'],['psn',6,'中毒']]) {
            reset(); check(id+' apply', s.apply('player',id));
            check(id+' label appears',snap().player.statusLabel === label);
            t.step(duration-1/120,false);
            check(id+' lives until last frame',snap().player.status?.left > 0);
            t.step(1/120,false);
            check(id+' expires on exact frame',snap().player.status === null);
            check(id+' label disappears',snap().player.statusLabel === null);
          }
          for (const [id, rate, duration] of [['brn',.02,5],['psn',.015,6]]) {
            reset(); s.apply('player',id); const initial=snap().player;
            for(let second=1;second<=duration;second++) {
              t.step(1,false); const now=snap().player;
              check(id+' DOT second '+second,
                Math.abs(now.hp-(initial.hp-initial.maxHP*rate*second))<1e-6, now.hp);
            }
            reset(); s.apply('player',id); t.arrange({player:{hp:1}});t.step(1,false);
            check(id+' DOT lethal clamped zero',snap().player.hp === 0 && snap().phase === 'over');
          }
          reset(); let x=snap().player.x; s.move('player',1,0,.1);
          const normal=snap().player.x-x;
          reset(); s.apply('player','par');x=snap().player.x;s.move('player',1,0,.1);
          check('par speed x0.6',Math.abs((snap().player.x-x)/normal-.6)<1e-6);
          // seed=1: first LCG sample <.25, so first 1.5s check stiffens.
          t.step(1.5,false); check('par stiff at seeded 1.5s',snap().player.status.stiff === .5);
          x=snap().player.x;s.move('player',1,0,.1);
          check('stiff blocks movement/cast',snap().player.x===x && !t.cast('player','scratch'));
          s.queue(0);t.step(.49,false);check('stiff input expires after 120ms',!snap().queued);
          t.step(.03,false);check('expired stiff input never casts on release',!snap().player.attack);
          reset();s.apply('player','par');t.step(1.5,false);t.step(.42,false);
          s.queue(0);t.step(.08,false);
          check('recent stiff input casts on release frame',!!snap().player.attack);
          reset();s.apply('player','frz');t.step(1,false);s.queue(0);t.step(.5,false);
          check('expired frozen input never casts on thaw',!snap().player.attack && !snap().queued);
          reset();s.apply('player','frz');t.step(1.42,false);s.queue(0);t.step(.08,false);
          check('recent frozen input casts on thaw frame',!!snap().player.attack);
          for (const [id, duration] of [['par',.5],['frz',1.5]]) {
            const block = () => { reset(); s.apply('player',id); if(id==='par') t.step(1.5,false); };
            const shift = () => document.dispatchEvent(new KeyboardEvent('keydown',{code:'ShiftLeft',bubbles:true}));
            block(); shift();
            check(id+' M6b dodge queued for 80ms while blocked',!!snap().dashMemory && !snap().player.dashing);
            t.step(duration+.01,false);
            check(id+' M6b expired dodge never executes on release',snap().player.dodges===0 && !snap().dashMemory);
            block();t.step(duration-.06,false);shift();t.step(.06,false);
            check(id+' M6b recent dodge executes on release frame',snap().player.dodges===1);
          }
          for(const mid of ['scratch','rapidspin','tackle','watergun']) {
            reset(); s.freshHit('enemy',mid);const normal=snap().enemy.maxHP-snap().enemy.hp;
            reset(); s.apply('player','brn');s.freshHit('enemy',mid);
            const burnt=snap().enemy.maxHP-snap().enemy.hp;
            check('burn power '+mid, mid==='watergun' ? burnt===normal :
              Math.abs(burnt-normal*.6)<=1, {normal,burnt});
          }
          reset(); const pose=snap().player;s.apply('player','frz');
          s.queue(0);check('freeze buffers input without executing',!!snap().queued && !snap().player.attack);
          check('freeze rejects cast/dash/jump',!t.cast('player','scratch') &&
            !t.dash('player',1,0) && !t.jump('player'));
          s.move('player',1,0,.5); t.step(.5,false);
          check('freeze holds location and exact frame',snap().player.x===pose.x &&
            snap().player.anim===pose.anim && snap().player.animFrame===pose.animFrame);
          const hp=snap().player.hp;t.injectMoveHit('player','ember');
          check('fire hit deals damage and thaws',snap().player.hp<hp &&
            snap().player.status===null && snap().player.freezeGrace===2);
          check('immediate refreeze blocked',!s.apply('player','frz'));
          // Combat dt excludes hitstop: step until combat clock reaches thaw+2.
          const thaw=snap().elapsed;
          while(snap().elapsed-thaw<2-1/120) t.step(1/120,false);
          check('2s grace before last frame',!s.apply('player','frz'));
          t.step(2/120,false);check('refreeze after grace',s.apply('player','frz'));
          reset();s.apply('player','frz');t.step(1.5,false);
          check('natural thaw also grants grace',snap().player.freezeGrace===2);
          for(const [id,types] of [['par',[13]],['brn',[10]],['frz',[15]],
              ['psn',[4]],['psn',[9]],['psn',[1,9]]]) {
            reset();s.types('player',types);
            check(id+' type immunity '+types,!s.apply('player',id));
          }
          for(const first of ['par','brn','frz','psn']) {
            reset();s.apply('player',first);
            for(const second of ['par','brn','frz','psn']) {
              check(first+' cannot be overwritten by '+second,!s.apply('player',second) &&
                snap().player.status.id===first);
            }
          }
          reset();t.cast('player','protect');t.step(.5,false);
          check('protect active',snap().player.shield>0);
          for(const id of ['par','brn','frz','psn']) check('protect blocks '+id,!s.apply('player',id));
          // Verify actual hit probability (not direct apply), including secondary arrays and triattack.
          for(const m of Object.values(t.catalog().moves).filter(m=>m.statuses)) {
            reset();s.types('enemy',[11]);const count={};let hits=0;
            for(let i=0;i<2000;i++) {
              const result=s.freshHit('enemy',m.id);hits+=result.hit?1:0;
              if(result.status) count[result.status.id]=(count[result.status.id]||0)+1;
            }
            check(m.id+' 2000 forced hits',hits===2000,hits);
            for(const row of m.statuses) {
              const actual=(count[row.id]||0)/20;
              check(m.id+' '+row.id+' probability ±3pp',Math.abs(actual-row.chance)<=3,
                {expected:row.chance,actual,n:2000});
            }
          }
          reset();s.freshHit('enemy','inferno');
          const labels=snap().hud.floats.filter(f=>f.side==='enemy');
          const statusFloat=labels.find(f=>f.text==='烧伤了！');
          const damageFloat=labels.find(f=>f.text.startsWith('−'));
          check('status float uses T1 non-overlapping slots',statusFloat && damageFloat &&
            statusFloat.slot!==damageFloat.slot &&
            (statusFloat.box.y+statusFloat.box.height<=damageFloat.box.y ||
             damageFloat.box.y+damageFloat.box.height<=statusFloat.box.y));
          // CPU uses identical gate, with its autonomous policy enabled.
          reset();s.apply('enemy','frz');const before=snap().enemy;
          t.arrange({ai:true});t.step(1,false);const after=snap().enemy;
          check('frozen CPU cannot act',before.x===after.x && before.y===after.y && !after.attack);
          reset();s.apply('enemy','par');t.step(1.5,false);t.arrange({ai:true});
          const stiff=snap().enemy;t.step(.3,false);
          check('stiff CPU cannot act',snap().enemy.x===stiff.x && snap().enemy.y===stiff.y &&
            !snap().enemy.attack);
          reset();s.apply('player','brn');t.cast('player','rapidspin');t.step(.6,false);
          check('rapidspin clears new status',snap().player.status===null);
          return out;
        }''')
        checks.extend(result)
        # Persistent readability, using actual displayed red-soil pixels at several phases.
        for status in ('frz', 'par', 'brn', 'psn'):
            for age in (.25, .75, 1.25):
                page.evaluate('''({status,age}) => {
                  const t=window.__waterTest;
                  t.reset(true);t.arrange({ai:false,player:{x:460,y:400},enemy:{x:820,y:400}});
                  t.statusTest.types('player',[1]);t.statusTest.seed(1);
                  t.statusTest.apply('player',status);t.step(age);
                }''', {'status':status,'age':age})
                visual_check(page, status, age)
        for fire in (False, True):
            thaw = page.evaluate('''fire => {
              const t=window.__waterTest;t.reset(true);
              t.arrange({ai:false,player:{x:460,y:400},enemy:{x:820,y:400}});
              t.statusTest.types('player',[1]);t.statusTest.apply('player','frz');t.step(.25);
              if(fire) t.injectMoveHit('player','ember'); else t.step(1.25);
              return t.statusTest.visual('player');
            }''', fire)
            check(f'thaw fragments start fire={fire}', thaw['thaw'] == {'age':0,'fire':fire})
            page.evaluate('window.__waterTest.step(.15)')
            thaw = page.evaluate("window.__waterTest.statusTest.visual('player')")
            check(f'thaw fragments visible fire={fire}',
                  thaw['thaw'] is not None and thaw['shown'] != thaw['base'])
            page.screenshot(path=str(SHOTS/('火系解冻.png' if fire else '自然碎冰.png')))
            page.evaluate('window.__waterTest.step(.3)')
            check(f'thaw fragments finish fire={fire}',
                  page.evaluate("window.__waterTest.statusTest.visual('player').thaw") is None)
        for name, pid, eid, move, status in [
            ('皮卡丘-冰冻光束',25,7,'icebeam','frz'),
            ('喷火龙-十万伏特',6,25,'thunderbolt','par'),
            ('杰尼龟-烧伤',7,6,'flamethrower','brn'),
            ('皮卡丘-中毒',25,94,'poisongas','psn')]:
            profile.update(player=pid, enemy=eid, playerMoves=roster[pid]['defaultMoves'],
                           enemyMoves=roster[eid]['defaultMoves'])
            assert page.evaluate('p => window.__waterTest.select(p)',profile)
            achieved = page.evaluate('''({move,status})=>{
              const t=window.__waterTest;
              for(let i=0;i<200;i++) {
                t.reset(true);t.arrange({ai:false,
                  player:{x:460,y:400},enemy:{x:820,y:400}});t.statusTest.seed(i+1);
                const r=t.statusTest.freshHit('player',move);
                if(r.status?.id===status) {t.step(.8);return true;}
              }return false;
            }''', {'move':move,'status':status})
            check(name+' real hit screenshot',achieved)
            page.screenshot(path=str(SHOTS/(name+'.png')))
            if status=='frz':
                page.locator('#game').screenshot(path=str(SHOTS/'状态标签-画布.png'))
                hud = page.evaluate('window.__waterTest.snapshot().hud.actors[0].box')
                with Image.open(SHOTS/'状态标签-画布.png') as image:
                    x, y = int(hud['x']), int(hud['y'])
                    crop = image.crop((x-28,y-22,x+95,y+85))
                    crop.resize((492,428),Image.Resampling.NEAREST).save(SHOTS/'状态标签-特写.png')
                    label = image.crop((x+52,y-5,x+82,y+9)).convert('RGB')
                    check('ice label background actually rasterized',
                          sum(pixel == (182,233,255) for pixel in label.get_flattened_data()) > 30)
                for width,height in [(390,844),(844,390)]:
                    page.set_viewport_size({'width':width,'height':height})
                    page.evaluate('window.__waterTest.render()')
                    page.screenshot(path=str(SHOTS/f'手机-{width}x{height}.png'))
                page.set_viewport_size({'width':1440,'height':900})
        check('0 JS errors',not errors,errors)
        browser.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        check('acceptance completed without exception', False, str(exc))
        raise
    finally:
        report={'passed':sum(c['ok'] for c in checks),
                'failed':sum(not c['ok'] for c in checks),'jsErrors':len(errors),
                'errors':errors,'checks':checks}
        (OUT/'验收.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(report,ensure_ascii=False,indent=2))
    assert not report['failed'] and not errors
