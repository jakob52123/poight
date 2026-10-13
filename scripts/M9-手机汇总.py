"""Map all 48 raw production records to MOB gates without hiding incomplete cases.
This is an additional classification, not a substitute for the imported MOB2 assertions.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '验收记录/MOB2'
data = json.loads((ROOT / '验收记录/MOB/审计数据.json').read_text())
assert len(data['production']) == 48
rows = []


def target(step, selector):
    return next((t for t in step.get('targets', []) if t['selector'] == selector), {})


def reachable(t):
    return bool(t) and not t['clipped'] and t['centerHit']


for r in data['production']:
    steps = r['steps']
    select = steps.get('02-选人全屏', {})
    loadout = steps.get('05-配招', {})
    vs = steps.get('06-VS开场', {})
    result = steps.get('14-自然胜负', {})
    cards = [t for t in select.get('targets', []) if t['id']]
    min_height = 44 if loadout.get('viewport', {}).get('height', 0) <= 220 else 25
    battle = r.get('landscapeBattle', {})
    width, height = battle.get('viewport', {}).get('width', 0), battle.get('viewport', {}).get('height', 0)
    controls = [battle.get('boxes', {}).get(s, {}) for s in ['#mobileActions', '#battleMenuButton', '.hud']]
    mini = battle.get('state', {}).get('arenaView', {}).get('minimap') or {}
    audited = [steps.get(s, {}) for s in ['02-选人全屏', '05-配招', '07-对战中', '09-菜单']]
    gates = {
        'MOB-01': len(cards) == len(json.loads((ROOT / '首发200.json').read_text())['ids']) and all(t['width'] >= 44 and t['height'] >= 44 for t in cards)
                  and any(a['ok'] for a in r['actions'] if a['name'] == '点名单最后一只'),
        'MOB-02': bool(loadout) and not loadout['rotateOpen'] and any(t['visibleHeight'] >= min_height
                  for t in loadout['targets'] if '.move-card' in t['selector'])
                  and any(a['ok'] for a in r['actions'] if a['name'] == '配招面板')
                  and any(a['ok'] for a in r['actions'] if a['name'] == '完成配招'),
        'MOB-03': all(s and not s['rotateOpen'] for s in [select, loadout, vs]),
        'MOB-04': all(b and b['x'] >= 0 and b['y'] >= 0 and b['right'] <= width + .5
                  and b['bottom'] <= height + .5 for b in controls) and bool(mini)
                  and mini['x'] >= 8 and mini['y'] >= 8 and mini['x'] + mini['width'] <= width - 8
                  and mini['y'] + mini['height'] <= height - 8,
        'MOB-06': reachable(target(select, '#startBattle')),
        'MOB-07': bool(result) and result['state']['phase'] == 'over' and all(s not in result['boxes']
                  for s in ['.hud', '#mobileActions', '#mobileJoystick', '#battleRail', '#battleMenuButton']),
        'MOB-08': r.get('menuPhase') == 'paused' and r.get('canvasCloseHelp', False),
        'MOB-09': all(s and not s['texts'] and not any(t['small'] and not t['disabled']
                  for t in s['targets']) for s in audited),
        'MOB-10': reachable(target(vs, '#vsContinue')),
    }
    rows.append({'case': f"{r['device']}/{r['direction']}/{r['variant']}",
                 'gates': {k: bool(v) for k, v in gates.items()}, 'incomplete': r['incomplete']})
summary = {gate: {'passed': sum(r['gates'][gate] for r in rows),
                  'failed': sum(not r['gates'][gate] for r in rows),
                  'failures': [r['case'] for r in rows if not r['gates'][gate]]}
           for gate in rows[0]['gates']}
report = {'scope': '48 production combinations; missing evidence fails, thresholds unchanged',
          'summary': summary, 'records': rows,
          'MOB-05': '四边安全区由界面GBA专套实测；矩阵安全区档详细几何保留在审计数据中。',
          'MOB-11': '音乐入口保留；音乐生命周期/动态红血另见战斗音乐专套，不冒充矩阵全操作。'}
(OUT / 'M9问题分类.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
for gate, row in summary.items():
    print(gate + ' ' + json.dumps({k: row[k] for k in ['passed', 'failed']}))
print('MOB-05 ' + report['MOB-05'])
print('MOB-11 ' + report['MOB-11'])
raise SystemExit(any(summary[k]['failed'] for k in ['MOB-01', 'MOB-02', 'MOB-03']))
