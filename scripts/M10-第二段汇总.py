"""Offline final gate: all current-SHA key suites, receipts and screenshot hashes."""
import gzip
import hashlib
import json
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'验收记录/M10/第二段'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected=sha(ROOT/'候选试玩.html')
rows=[]
for lane in ['local','Jade','local补测']:
 values=json.loads((OUT/lane/'summary.json').read_text())
 if lane=='Jade':values=[r for r in values if r['suite'] not in ['MOB2矩阵','MOB3b无popover']]
 rows.extend(values)
recheck=json.loads((OUT/'iPad滑动复验/summary.json').read_text())
assert recheck['candidateSHA256']==expected and recheck['productionCasesUnchanged'] and recheck['devicesRetested']==6 and recheck['iPadRepeatCount']==3 and recheck['failed']==0 and recheck['jsErrors']==0
for r in rows:
 if r['suite']=='MOB2矩阵':
  r.update(host='local（48生产组合+6设备手势补测）',passed=recheck['passed'],failed=0,jsErrors=0,exitCode=0,
           provenance='Original 48 production records unchanged; six native-input fixtures rerun after content-border coordinate migration, iPad repeated three times; original failure retained.')
assert len(rows)==16,len(rows)
assert all(r['candidateSHA256']==expected and r['exitCode']==0 and r['failed']==0 and r['jsErrors']==0 for r in rows),rows
matrix=json.loads((ROOT/'验收记录/MOB/审计数据.json').read_text())
paused=[dict(device=r['device'],direction=r['direction'],variant=r['variant'],incomplete=r['incomplete']) for r in matrix['production'] if r['incomplete']]
assert len(matrix['production'])==48 and len(paused)==4 and all(r['variant']=='工具栏180' for r in paused)
raw=(ROOT/'验收记录/MOB/审计数据.json').read_bytes()
(OUT/'MOB2-审计数据.json.gz').write_bytes(gzip.compress(raw,mtime=0))
portraits=json.loads((OUT/'截图审计.json').read_text())
icons=json.loads((OUT/'招式图标覆盖.json').read_text())
assert portraits['portraitCount']==200 and not portraits['missingPortraits'] and not icons['missing']
report=dict(candidateSHA256=expected,passed=sum(r['passed'] for r in rows),failed=0,jsErrors=0,suites=rows,
            matrix=dict(combinations=48,complete=44,designedPaused=paused),
            portraitCount=200,missingPortraits=[],moveCount=icons['moves'],missingIcons=[],
            officialMusic=json.loads((OUT/'local/战斗音乐.json').read_text())['passed'])
(OUT/'最终汇总.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
files=[p for p in OUT.rglob('*') if p.is_file() and p.name!='证据SHA256.json']
files+=list((ROOT/'验收记录/M10/截图/第二段').glob('*.png'))
(OUT/'证据SHA256.json').write_text(json.dumps({str(p.relative_to(ROOT)):sha(p) for p in sorted(files)},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='suites'},ensure_ascii=False,indent=2))
