"""Independent evidence checks, old-50 equality and every new loadout's diff."""
import csv
import hashlib
import itertools
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from 游戏数据 import MOVES, roster_metadata, r200b_learnsets

OUT = ROOT / '验收记录/R200/补充1'
HERE = ROOT / '数值资料/Pi-20261011'
old_ids = set(json.loads((ROOT/'首发50.json').read_text())['ids'])
ids = json.loads((ROOT/'首发200.json').read_text())['ids']
lib = {r['id']:r for r in json.loads((ROOT/'素材/角色库/角色库.json').read_text())}
rows = [lib[n] for n in ids]
before = {r['id']:r for r in json.loads((OUT/'配招-before.json').read_text())}
after = {r['id']:r for r in roster_metadata(rows)}
learned = r200b_learnsets()
canonical = json.loads((HERE/'move-audit.json').read_text())['moves']
sources = json.loads((HERE/'learnset-R200b来源.json').read_text())['records']
assert len(sources) == 150 and {r['id'] for r in sources} == set(ids)-old_ids
for r in sources:
    raw = (HERE/r['raw']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == r['sha256']
    data = json.loads(raw)
    assert data['id'] == r['id'] and data['is_default']
    slugs = {m['move']['name'] for m in data['moves'] if m['version_group_details']}
    actual = [mid for mid in MOVES if mid != 'splash' and canonical[mid]['name'] in slugs]
    assert actual == r['runtimeMoveIDs'] == learned[r['id']]
# Compare textual rows with normalized line endings (Git autocrlf may normalize TSVs).
old_lines = (OUT/'learnset-original50.tsv').read_text().splitlines()
lines = (HERE/'learnset-audit.tsv').read_text().splitlines()
assert old_lines == lines[:51] and len(lines) == 201
changed = [n for n in old_ids if before[n] != after[n]]
assert not changed, changed
immune = {1:{8},2:{8},4:{9},5:{3},8:{1},13:{5},14:{17},16:{18}}
combos = {tuple(c['types']) for c in rows}
def attack(m):
    return MOVES[m]['damage'] > 0 and MOVES[m]['kind'] not in ('heal','guard','buff','splash')
def covers(moves):
    return all(any(not immune.get(MOVES[m]['type'],set()).intersection(t) for m in moves if attack(m)) for t in combos)
changes = []
fallback = []
for n in ids:
    if n in old_ids:
        continue
    a, b = after[n], before[n]
    assert {k:v for k,v in a.items() if k not in ('defaultMoves','learnset')} == {k:v for k,v in b.items() if k not in ('defaultMoves','learnset')}
    assert a['learnset'] == list(dict.fromkeys(b['learnset'] + learned[n]))
    d = a['defaultMoves']
    assert len(d) == len(set(d)) == 4 and covers(d)
    assert set(d) <= set(a['learnset'])
    if n == 132:
        assert not learned[n] and d == b['defaultMoves']
        note = '原作仅变身，暂用一般系'
    else:
        assert d[-1] == 'protect'
        assert MOVES[d[0]]['type'] in a['types'] and attack(d[0])
        assert MOVES[d[1]]['kind'] in ('melee','rush','spin')
        missing = [m for m in d if m not in learned[n] and m != 'protect']
        assert all(m in b['learnset'] for m in missing)
        note = '补自属性池：' + '/'.join(MOVES[m]['name'] for m in missing) if missing else ''
        if missing:
            # Independently prove a fully learnable three-attack structured loadout is impossible.
            attacks = [m for m in learned[n] if attack(m)]
            assert not any(MOVES[x]['type'] in a['types'] and MOVES[y]['kind'] in ('melee','rush','spin') and covers([x,y,z])
                           for x,y,z in itertools.permutations(attacks,3)), n
            fallback.append(dict(id=n,name=a['name'],moves=missing,note=note))
    if d != b['defaultMoves']:
        changes.append(dict(id=n, name=a['name'], before=b['defaultMoves'], after=d,
                            slots=[dict(slot=i+1,before=x,after=y) for i,(x,y) in enumerate(zip(b['defaultMoves'],d)) if x != y], note=note))
with (OUT/'配招前后对照.tsv').open('w',newline='') as f:
    writer=csv.writer(f,delimiter='\t')
    writer.writerow(['编号','名字','旧四招','新四招','变更槽位','备注'])
    for r in changes:
        names=lambda moves:'/'.join(MOVES[m]['name'] for m in moves)
        writer.writerow([r['id'],r['name'],names(r['before']),names(r['after']),
                         '；'.join(f"{s['slot']}:{MOVES[s['before']]['name']}→{MOVES[s['after']]['name']}" for s in r['slots']),r['note']])
report=dict(original50=50,changed=changed,new150=150,defaultChanged=len(changes),
            new150OtherDataChanged=[],original50AuditRowsChanged=[],coveragePassed=199,
            fallbackSpecies=len(fallback),fallback=fallback,ditto='原作仅变身，暂用一般系',
            changes=changes)
(OUT/'配招核验.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='changes'},ensure_ascii=False))
