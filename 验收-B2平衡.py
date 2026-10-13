"""Queued live-engine calibration. Same fixture before/after; no second combat model."""
import hashlib
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
LABEL = sys.argv[1] if len(sys.argv) > 1 else 'after'
OUT = ROOT / '验收记录/B2平衡' / LABEL
OUT.mkdir(parents=True, exist_ok=True)
URL = os.environ['POIGHT_TEST_URL'].rstrip('/')
checks, errors = [], []


def check(name, ok, detail=None):
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(URL + '/?test=1')
        deadline = time.monotonic() + 120
        while not page.evaluate('window.__waterTest?.snapshot().artReady'):
            assert time.monotonic() < deadline, errors
            time.sleep(.05)
        catalog = page.evaluate('window.__waterTest.catalog()')
        roster = {c['id']: c for c in catalog['roster']}
        profile = page.evaluate('window.__waterTest.snapshot().profile')
        profile['map'] = 'arena-formal'
        samples = []
        for mon in roster.values():
            selected = {**profile, 'player': mon['id'], 'enemy': 7,
                        'playerMoves': mon['defaultMoves'], 'enemyMoves': roster[7]['defaultMoves']}
            assert page.evaluate('v => window.__waterTest.select(v)', selected)
            sample = page.evaluate('''() => {
              const t=window.__waterTest;
              const reset=()=>{t.reset(true);t.arrange({ai:false,
                player:{x:700,y:700},enemy:{x:1500,y:700}});};
              reset(); const a=t.snapshot().player;
              t.statusTest.move('player',1,0,1);const b=t.snapshot().player;
              reset();const start=t.snapshot().player;
              const accepted=t.dash('player',1,0);let ticks=0;
              while(t.snapshot().player.dashing && ticks<120){t.step(1/120,false);ticks++;}
              const end=t.snapshot().player;
              return {id:a.id,name:a.name,speed:b.x-a.x,height:a.body.visibleSize[1],
                nominal:a.body.nominalSize,hp:a.maxHP,walk:(b.x-a.x)/a.body.visibleSize[1],
                dash:(end.x-start.x)/a.body.visibleSize[1],dashPixels:end.x-start.x,
                duration:ticks/120,cost:end.spent-start.spent,accepted};
            }''')
            samples.append(sample)
            check(f"{mon['id']} walk equals configured speed", abs(sample['speed']-mon['speed']) < 1e-6)
            check(f"{mon['id']} dash accepted", sample['accepted'])
        (OUT / 'movement.json').write_text(json.dumps(samples, ensure_ascii=False, indent=2))
        games = []
        # Each pair: 20 full-HP ordinary direct-hit fixtures, ten in each direction.
        # Cycle every damaging default skill with a seeded offset; immune hits are not counted.
        # DOT/secondary debuffs and hitstop are isolated via existing test hooks, not new rules.
        for a, b in [(25, 6), (7, 4), (208, 25)]:
            assert page.evaluate('v => window.__waterTest.select(v)',
                                {**profile, 'player': a, 'enemy': b,
                                 'playerMoves': roster[a]['defaultMoves'],
                                 'enemyMoves': roster[b]['defaultMoves']})
            batch = page.evaluate('''() => {
              const t=window.__waterTest, cat=t.catalog(),out=[];
              for(let seed=1;seed<=20;seed++) {
                t.reset(true);t.arrange({ai:false,player:{x:700,y:700},enemy:{x:1100,y:700}});
                t.statusTest.seed(seed);
                const target=seed%2?'enemy':'player',source=target==='enemy'?'player':'enemy';
                const start=t.snapshot(),moves=start[source].moves.filter(id=>cat.moves[id].damage>0 &&
                  !['heal','buff','guard','splash'].includes(cat.moves[id].kind));
                let hits=0,attempts=0;const trace=[];
                while(t.snapshot()[target].hp>0 && attempts<1000) {
                  t.statusTest.clear(target);t.statusTest.clear(source);
                  const id=moves[(seed+attempts)%moves.length],before=t.snapshot()[target].hp;
                  t.injectMoveHit(target,id);const after=t.snapshot()[target].hp;
                  if(after<before){hits++;trace.push({move:id,amount:before-after});}
                  attempts++;
                }
                out.push({seed,source:start[source].id,target:start[target].id,hits,attempts,
                  knockedOut:t.snapshot()[target].hp===0,trace});
              }return out;
            }''')
            for game in batch:
                game['pair'] = f'{a}-{b}'
                check(f'{a}-{b} seed {game["seed"]} KO', game['knockedOut'])
            games.extend(batch)
        (OUT / 'hits.json').write_text(json.dumps(games, ensure_ascii=False, indent=2))
        # Same existing ordinary projectile, neutral/non-STAB for these six actors.
        # This isolates durability from default-loadout resistance and electric immunity.
        neutral = []
        for a, b in [(25, 6), (7, 4), (208, 25)]:
            assert page.evaluate('v => window.__waterTest.select(v)',
                                {**profile, 'player': a, 'enemy': b,
                                 'playerMoves': roster[a]['defaultMoves'],
                                 'enemyMoves': roster[b]['defaultMoves']})
            batch = page.evaluate('''() => {
              const t=window.__waterTest, cat=t.catalog(),out=[];
              for(let seed=1;seed<=20;seed++) {
                t.reset(true);t.arrange({ai:false});t.statusTest.seed(seed);
                const target=seed%2?'enemy':'player',source=target==='enemy'?'player':'enemy';
                const start=t.snapshot(),move=cat.moves.darkpulse;
                const targetTypes=cat.roster.find(c=>c.id===start[target].id).types;
                const sourceTypes=cat.roster.find(c=>c.id===start[source].id).types;
                const efficacy=targetTypes.reduce((v,type)=>v*cat.efficacy[move.type][type],1);
                let hits=0;const trace=[];
                while(t.snapshot()[target].hp>0 && hits<1000) {
                  t.statusTest.clear(target);t.statusTest.clear(source);
                  const before=t.snapshot()[target].hp;t.injectMoveHit(target,'darkpulse');
                  trace.push(before-t.snapshot()[target].hp);hits++;
                }
                out.push({seed,source:start[source].id,target:start[target].id,hits,trace,
                  efficacy,stab:sourceTypes.includes(move.type),
                  knockedOut:t.snapshot()[target].hp===0});
              }return out;
            }''')
            for game in batch:
                game['pair'] = f'{a}-{b}'
                check(f'neutral {a}-{b} seed {game["seed"]} KO', game['knockedOut'])
                check(f'neutral {a}-{b} seed {game["seed"]} neutral/non-STAB',
                      game['efficacy'] == 1 and not game['stab'])
            neutral.extend(batch)
        (OUT / 'neutral-hits.json').write_text(json.dumps(neutral, ensure_ascii=False, indent=2))
        dots = page.evaluate('''() => {
          const t=window.__waterTest,out=[];
          for(const id of ['brn','psn']) {
            t.reset(true);t.arrange({ai:false});t.statusTest.types('player',[1]);
            t.statusTest.apply('player',id);const initial=t.snapshot().player;
            t.step(1,false);const end=t.snapshot().player;
            out.push({id,hp:initial.maxHP,perSecond:initial.hp-end.hp,
              percent:100*(initial.hp-end.hp)/initial.maxHP});
          }return out;
        }''')
        distributions = {pair: dict(sorted(Counter(g['hits'] for g in games if g['pair'] == pair).items()))
                         for pair in ['25-6', '7-4', '208-25']}
        neutral_distributions = {
            pair: dict(sorted(Counter(g['hits'] for g in neutral if g['pair'] == pair).items()))
            for pair in ['25-6', '7-4', '208-25']}
        result = {'movement': samples, 'distributions': distributions, 'dots': dots,
                  'neutralDistributions': neutral_distributions}
        (OUT / 'measurements.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        if LABEL != 'before':
            limits = json.loads((ROOT / 'tests/B2区间.json').read_text())
            additions = json.loads((ROOT / 'tests/R200-B2区间.json').read_text())
            full_species = limits['species'] | additions['species']
            check('B2 bounds cover exactly the authorized roster', set(map(int, full_species)) == set(roster))
            for sample in samples:
                for key in ['speed', 'walk', 'dash', 'dashPixels', 'duration', 'cost', 'hp']:
                    lo, hi = full_species[str(sample['id'])][key]
                    check(f'{sample["id"]} adjusted {key} in [{lo},{hi}]', lo <= sample[key] <= hi, sample[key])
            # Retain all original population/min/max goldens on their original cohort;
            # additionally check the entire authorized roster against source-derived bounds.
            for group in limits['sizeGroups'] + additions['sizeGroups']:
                members = [s for s in samples if group['height'][0] <= s['height'] < group['height'][1]
                           and (group['name'].startswith('R200-') or str(s['id']) in limits['species'])]
                check(group['name']+' species count', len(members) == group['count'])
                for end, value in [('min', min(s['walk'] for s in members)),
                                   ('max', max(s['walk'] for s in members))]:
                    lo, hi = group[end]
                    check(group['name']+' walk '+end, lo <= value <= hi, value)
            for pair, wanted in limits['distributions'].items():
                check(pair+' default hit histogram', distributions[pair] == {int(k): v for k, v in wanted.items()}, distributions[pair])
            for pair, wanted in limits['neutralDistributions'].items():
                check(pair+' neutral hit histogram', neutral_distributions[pair] == {int(k): v for k, v in wanted.items()},
                      neutral_distributions[pair])
            for game in games:
                lo, hi = limits['hits'][str(game['source'])+'-'+str(game['target'])]
                check(f'{game["pair"]} seed {game["seed"]} hits in [{lo},{hi}]', lo <= game['hits'] <= hi, game['hits'])
            for game in neutral:
                check(f'neutral {game["pair"]} seed {game["seed"]} 5–7 hits',
                      5 <= game['hits'] <= 7, game['hits'])
            for dot in dots:
                lo, hi = limits['dot'][dot['id']]
                check(dot['id']+' percent/s', lo <= dot['percent'] <= hi, dot)
                lo, hi = limits['dotHP'][dot['id']]
                check(dot['id']+' HP/s', lo <= dot['perSecond'] <= hi, dot)
            by_id = {s['id']: s for s in samples}
            for key, (lo, hi) in limits['referencePikachu'].items():
                check('PV Pikachu '+key, lo <= by_id[25][key] <= hi, by_id[25][key])
            for small, large in [(25, 143), (133, 208), (7, 6)]:
                by_id = {s['id']: s for s in samples}
                check(f'{small}/{large} size direction preserved',
                      by_id[small]['speed'] > by_id[large]['speed'] and by_id[small]['hp'] < by_id[large]['hp'])
        if LABEL != 'before':
            for scene in catalog['scenes']:
                if scene.get('type') != 'arena':
                    continue
                assert page.evaluate('v => window.__waterTest.select(v)',
                                     {**profile, 'map': scene['id'], 'tier': 'great',
                                      'player': 25, 'enemy': 6,
                                      'playerMoves': roster[25]['defaultMoves'],
                                      'enemyMoves': roster[6]['defaultMoves']})
                probe = page.evaluate('''() => {
                  const t=window.__waterTest;t.reset(true);t.arrange({ai:true});
                  let closest=Infinity;
                  for(let tick=0;tick<60;tick++) {
                    t.step(.1,false);const s=t.snapshot();
                    closest=Math.min(closest,Math.hypot(s.player.x-s.enemy.x,s.player.y-s.enemy.y));
                  }
                  const s=t.snapshot(),moves=t.catalog().moves;
                  const maximum=Math.max(...s.player.moves.concat(s.enemy.moves).map(id=>moves[id].range));
                  return {closest,maximum,decisions:s.ai.decisions};
                }''')
                check(scene['id']+' existing AI 6s opening approach',
                      probe['closest'] <= 2*probe['maximum'] and probe['closest'] < 745
                      and probe['decisions'] > 0, probe)
        for w, h in [(1440, 900), (390, 844), (844, 390)]:
            page.set_viewport_size({'width': w, 'height': h})
            page.evaluate("window.__waterTest.reset(true);window.__waterTest.autopilot('poke');window.__waterTest.step(2)")
            (OUT / '截图').mkdir(exist_ok=True)
            page.screenshot(path=str(OUT / '截图' / f'{w}x{h}.png'))
        check('no JS errors', not errors, errors)
        browser.close()


if __name__ == '__main__':
    try:
        main()
    finally:
        report = {'passed': sum(c['ok'] for c in checks), 'failed': sum(not c['ok'] for c in checks),
                  'errors': errors, 'checks': checks,
                  'candidateSHA256': hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest()}
        (OUT / '浏览器验收.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps({k: report[k] for k in ['passed', 'failed', 'errors']}, ensure_ascii=False))
        if report['failed'] or errors:
            raise SystemExit(1)
