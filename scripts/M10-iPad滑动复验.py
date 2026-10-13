"""Recheck six native-input devices after S2 swipe-coordinate migration, iPad x3.
Original 48 production cases stay byte-for-byte equivalent. Positive native-scroll
and all original input/matrix assertions remain unchanged; archive initial failure.
"""
import gzip
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'验收记录/M10/第二段/iPad滑动复验'
OUT.mkdir(parents=True,exist_ok=True)
raw=ROOT/'验收记录/MOB/审计数据.json'
original=raw.read_bytes()
(OUT/'首轮审计数据.json.gz').write_bytes(gzip.compress(original,mtime=0))
(OUT/'首轮matrix.json').write_bytes((ROOT/'验收记录/MOB2/matrix.json').read_bytes())
spec=importlib.util.spec_from_file_location('mob',ROOT/'验收-手机适配.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
rows=[]
with sync_playwright() as pw:
 for i,device in enumerate(m.DEVICES + ['iPad Mini','iPad Mini']):
  m.SHOTS=OUT/f'截图-{i+1}';m.SHOTS.mkdir(exist_ok=True)
  r=m.touches(pw,device);rows.append(r)
  (OUT/f'原样复验-{i+1}.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
  gesture=r['scrollGesture']['roster']
  print('REPEAT',i+1,json.dumps(gesture,ensure_ascii=False),flush=True)
  assert gesture['available'] and gesture['delta']>0 and not r['errors'] and all(c['ok'] for c in r['checks'])
data=json.loads(original)
by_device={r['device']:r for r in rows}
data['input']=[by_device[r['device']] for r in data['input']]
assert data['production']==json.loads(original)['production']
raw.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
p=subprocess.run([sys.executable,'验收-手机兜底.py','--stage','matrix'],cwd=ROOT,capture_output=True,text=True)
(OUT/'重判.log').write_text(p.stdout+p.stderr)
print(p.stdout+p.stderr,flush=True)
report=json.loads((ROOT/'验收记录/MOB2/matrix.json').read_text())
report.update(candidateSHA256=hashlib.sha256((ROOT/'候选试玩.html').read_bytes()).hexdigest(),iPadRepeatCount=3,devicesRetested=6,productionCasesUnchanged=True)
(OUT/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
raise SystemExit(p.returncode)
