"""Extend native per-frame R1/R2/R3 landmarks for only the 150 new fighters.
Same alpha-bound anatomical approximation as existing generic species; no old
calibration is rewritten. This is not a claim of manual anatomical calibration.
"""
import hashlib
import json
import sys
from pathlib import Path
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from 招式特效.第1批锚点 import extend, WING
path = ROOT / '招式特效/主角锚点.json'
result = json.loads(path.read_text())
original_ids = json.loads((ROOT / '首发50.json').read_text())['ids']
original = {str(n): result[str(n)] for n in original_ids}
ids = set(json.loads((ROOT / '首发200.json').read_text())['ids']) - set(original_ids)
rows = [c for c in json.loads((ROOT / '素材/角色库/角色库.json').read_text()) if c['id'] in ids]
added = {}
extend(added, rows, ROOT)
mouth = [(.50,.37),(.24,.32),(.14,.30),(.25,.21),(.50,.19),(.75,.21),(.86,.30),(.76,.32)]
head = [(.50,.25),(.30,.23),(.24,.23),(.32,.19),(.50,.16),(.68,.19),(.76,.23),(.70,.23)]
hand = [(.28,.54),(.18,.52),(.18,.52),(.23,.46),(.26,.43),(.77,.46),(.82,.52),(.82,.52)]
roles = [('mouth','shoot'),('head','shoot'),('cannon','shoot'),('flower','shoot'),
         ('r3body','melee'),('headMelee','melee'),('hand','melee'),('foot','melee'),
         ('mouthMelee','melee'),('wing','shoot'),('plant','shoot')]
for c in rows:
    entries = added[c['id']]
    for part, role in roles:
        clip = c['art'][role]
        im = Image.open(ROOT / '素材/角色库' / clip['file']).convert('RGBA')
        w,h = clip['frameWidth'],clip['frameHeight']
        points = []
        for direction in range(8):
            poses = []
            for f in range(clip['frames']):
                row = direction if clip['rows'] == 8 else 0
                bb = im.crop((f*w,row*h,(f+1)*w,(row+1)*h)).getbbox()
                assert bb
                x0,y0,x1,y1 = bb
                u,v = ((.5,.53) if part=='r3body' else (.5,.97) if part=='foot' else
                       head[direction] if part in ['head','headMelee','flower','plant'] else
                       hand[direction] if part=='hand' else WING[direction] if part=='wing' else mouth[direction])
                poses.append([round(x0+(x1-x0)*u,2),round(y0+(y1-y0)*v,2)])
            points.append(poses)
        entries['r3-'+part] = dict(role=role,points=points,occludedRows=[])
        if part in ['mouth','head','cannon','flower','hand','foot','wing','plant']:
            entries[part] = entries['r3-'+part]
    result[str(c['id'])] = entries
assert {str(n): result[str(n)] for n in original_ids} == original
# Preserve the existing one-landmark-per-line archival layout.
lines=['{']
for i,(n,entries) in enumerate(result.items()):
    lines.append(f'  "{n}": {{')
    for j,(part,entry) in enumerate(entries.items()):
        lines.append('    '+json.dumps(part)+': '+json.dumps(entry,ensure_ascii=False,separators=(',',':'))+(',' if j+1<len(entries) else ''))
    lines.append('  }'+(',' if i+1<len(result) else ''))
lines.append('}')
path.write_text('\n'.join(lines)+'\n')
print(json.dumps({'landmarks':len(result),'added':len(added),'old50Changed':0,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}))
