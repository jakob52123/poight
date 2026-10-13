"""Data/coverage tables, original-50 equality proof and static asset gates."""
import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from 游戏数据 import MOVES, TYPES, roster_metadata, r200b_learnsets
from 体型数据 import apply

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '验收记录/R200'
LIB = ROOT / '素材/角色库'
ids = json.loads((ROOT / '首发200.json').read_text())['ids']
all_rows = {c['id']: c for c in json.loads((LIB / '角色库.json').read_text())}
rows = [all_rows[n] for n in ids]
flights = json.loads((LIB / '飞行修正/飞行包.json').read_text())
for c in rows:
    if str(c['id']) in flights:
        f = flights[str(c['id'])]
        c['audit'][f['art']['sourceAnimation']] = f['audit']
        for role in f['roles']:
            c['art'][role] = dict(f['art'])
        for role, offsets in f['bodyOffsets'].items():
            c['art'][role]['bodyOffsets'] = offsets
metadata = roster_metadata(rows)
for c in metadata:
    if str(c['id']) in flights:
        c['flightHeight'] = flights[str(c['id'])]['flightHeight']
receipt = apply(metadata, rows, ROOT, LIB)
old = json.loads((OUT / '原50基线.json').read_text())
by_id = {c['id']: c for c in metadata}
diffs = []
for c in old['roster']:
    # Compare the entire former runtime row, including type/name/flags/anchors,
    # not just the mandatory loadout, size and locomotion subset.
    for key in sorted((set(c) | set(by_id[c['id']])) - {'credits'}):
        if c.get(key) != by_id[c['id']].get(key):
            diffs.append(dict(id=c['id'], field=key, before=c.get(key), after=by_id[c['id']].get(key)))
# The cloned candidate baseline is trustworthy only when all determining sources
# are byte-identical to cd1e796. Archive their Git-blob fingerprints as proof.
source_proof = {}
for name in ['游戏数据.py', '体型数据.py']:
    historical = subprocess.check_output(['git', 'show', 'cd1e796:'+name], cwd=ROOT)
    initial = subprocess.check_output(['git', 'show', '76583a6:'+name], cwd=ROOT)
    assert initial == historical, name
    source_proof[name] = hashlib.sha256(historical).hexdigest()
assert not diffs, diffs
immune = {1:{8}, 2:{8}, 4:{9}, 5:{3}, 8:{1}, 13:{5}, 14:{17}, 16:{18}}
combos = {tuple(c['types']) for c in rows}
coverage = []
for c in metadata:
    attacks = [MOVES[m] for m in c['defaultMoves'] if MOVES[m]['damage'] > 0 and MOVES[m]['kind'] not in ('heal','guard','buff','splash')]
    covered = all(any(not immune.get(m['type'], set()).intersection(target) for m in attacks) for target in combos)
    if c['id'] == 129:
        assert c['defaultMoves'] == ['splash'] and not attacks
    else:
        assert attacks and covered and len(c['defaultMoves']) == 4, c
    assert c['body']['moveRadius'] <= 20
    coverage.append(dict(id=c['id'], covers=covered, exception='鲤鱼王仅水溅跃' if c['id']==129 else None))

def tsv(name, header, records):
    with (OUT / name).open('w') as f:
        writer = csv.writer(f, delimiter='\t'); writer.writerow(header); writer.writerows(records)

tsv('体型表.tsv', ['编号','名字','身高m','体重kg','尺寸映射','画面宽px','画面高px','scale','走速px/s','脚印半径px','来源SHA256'],
    [[c['id'],c['name'],c['body']['heightMeters'],c['body']['weightKg'],c['body']['dimensionMode'],*c['body']['visibleSize'],c['scale'],c['speed'],c['body']['moveRadius'],c['body']['sourceSHA256']] for c in metadata])
learned = r200b_learnsets()
def move_source(c):
    if c['id'] not in learned:
        return '原50保留', '鲤鱼王仅水溅跃' if c['id'] == 129 else '原50默认招与可选池不变'
    if c['id'] == 132:
        return '特例保留', '原作仅变身，暂用一般系'
    sources = ['可学' if m in learned[c['id']] else '通用守住' if m == 'protect' else '补自属性池' for m in c['defaultMoves']]
    added = [MOVES[m]['name'] for m, source in zip(c['defaultMoves'], sources) if source == '补自属性池']
    note = '补自属性池：' + '/'.join(added) if added else ''
    if '通用守住' in sources:
        note += ('；' if note else '') + '守住沿用通用规则'
    return '/'.join(sources), note

tsv('配招表.tsv', ['编号','名字','属性','四招中文名','covers','来源：可学/补自属性池','备注'],
    [[c['id'],c['name'],'/'.join(TYPES[t][0] for t in c['types']),'/'.join(MOVES[m]['name'] for m in c['defaultMoves']),r['covers'],*move_source(c)] for c,r in zip(metadata,coverage)])
tsv('飞行表.tsv', ['编号','名字','原生动作','帧序列','flightHeight','审核','方法'],
    [[n,all_rows[n]['name'],f['sourceAnimation'],','.join(map(str,f['sourceFrames'])),f['flightHeight'],'8方向/无裁切/像素保留',f['method']] for n in ids if (f:=flights.get(str(n)))])
proof = dict(original50=50, changed=diffs, historicalSources=source_proof, roster=len(metadata), flying=len(flights),
             coveragePassed=sum(c['covers'] for c in coverage), coverageException=[129], replacements=[])
(OUT / '数据核验.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(proof, ensure_ascii=False))
