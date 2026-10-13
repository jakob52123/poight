"""Extend B2 expectations from calibrated source data, never from browser measurements.
Original fifty golden ranges/distributions are not changed. Bounds retain original
B2 tolerances; dash 850px/s * .30s, 15 stamina is the unchanged combat contract.
"""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
legacy=json.loads((ROOT/'tests/B2区间.json').read_text())
body=json.loads((ROOT/'数值资料/体型校准/映射记录.json').read_text())['species']
import sys
sys.path.insert(0,str(ROOT))
from 游戏数据 import roster_metadata
ids=json.loads((ROOT/'首发200.json').read_text())['ids']
metadata={c['id']:c for c in roster_metadata([c for c in json.loads((ROOT/'素材/角色库/角色库.json').read_text()) if c['id'] in ids])}
new={}
for c in body:
    n=c['id']
    if str(n) in legacy['species']:continue
    height=c['body']['visibleSize'][1]
    speed=c['speed'];hp=metadata[n]['hp'];walk=speed/height;dash=255/height
    new[str(n)]={'speed':[speed-.01,speed+.01],'hp':[hp,hp],
                 'walk':[walk-.001,walk+.001],'dash':[dash-.002,dash+.002],
                 'duration':[.3,.309],'cost':[15,15],'dashPixels':[254.99,255.01]}
groups=[]
for g in legacy['sizeGroups']:
    members=[c for c in body if g['height'][0]<=c['body']['visibleSize'][1]<g['height'][1]]
    values=[c['speed']/c['body']['visibleSize'][1] for c in members]
    groups.append(dict(name='R200-'+g['name'],height=g['height'],count=len(members),
                       min=[min(values)-.001,min(values)+.001],max=[max(values)-.001,max(values)+.001]))
result=dict(note='Independent pre-browser expectations from the same authorized body formula; all original B2 goldens retained separately.',species=new,sizeGroups=groups)
(ROOT/'tests/R200-B2区间.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
assert set(new).isdisjoint(legacy['species']) and len(new)+len(legacy['species'])==len(ids)
print('new B2 species',len(new),'groups',[(g['name'],g['count']) for g in groups])
