"""Two authorized serial browser lanes, all receipts bound to frozen candidate SHA."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
lane=sys.argv[1]
OUT=ROOT/'验收记录/M10/第二段'/lane
OUT.mkdir(parents=True,exist_ok=True)
sha=hashlib.sha256((ROOT/'候选试玩.html').read_bytes()).hexdigest()
groups={
 'local': [('界面GBA',['验收-界面GBA.py'],'UI2/summary.json'),
 ('首开加载',['验收-首开加载.py'],'首开加载/验收.json'),
 ('埋点',['验收-埋点.py'],'埋点/验收.json'),
 ('战斗音乐',['验收-战斗音乐.py'],'战斗音乐/report.json'),
 ('手机操作',['验收-手机操作.py'],'手机操作/报告.json'),
 ('头顶血条',['验收-头顶血条.py'],'头顶血条/验收.json'),
 ('S2真实200',['scripts/M10-S2真实名单.py'],'M10/第二段/S2/summary.json')],
 'Jade': [('选人页',['验收-选人页.py'],'选人页/浏览器验收.json'),
 ('逐精灵',['逐精灵验收.py','--tag','M10-stage2'],'R200/逐精灵验收-M10-stage2.json'),
 ('200只冒烟',['scripts/R200-冒烟.py'],'R200/冒烟.json'),
 ('演示模式',['验收-演示模式.py'],'演示模式/演示模式验收.json'),
 ('M7联动',['验收-M7联动.py'],'M7联动/浏览器验收.json'),
 ('MOB2矩阵',['scripts/MOB2-验收.py','--matrix-only'],'MOB2/matrix.json'),
 ('MOB3b无popover',['scripts/MOB3b-无popover.py'],'MOB3b/无popover/summary.json')],
 'local补测': [('MOB2矩阵',['scripts/MOB2-验收.py','--matrix-only'],'MOB2/matrix.json'),
 ('MOB3b无popover',['scripts/MOB3b-无popover.py'],'MOB3b/无popover/summary.json'),
 ('截图审计',['scripts/M10-截图审计.py'],'M10/第二段/截图审计.json'),
 ('200局随机音乐',['scripts/M10-200局音乐.py'],'M10/第二段/200局随机音乐.json')]
}
summary=[]
for name,args,rel in groups[lane]:
 start=time.time()
 print('RUN',lane,name,sha,flush=True)
 try:
  p=subprocess.run([sys.executable,*args],cwd=ROOT,capture_output=True,text=True,timeout=1200)
  text,code=p.stdout+p.stderr,p.returncode
 except subprocess.TimeoutExpired as e:
  text,code=str(e),124
 (OUT/(name+'.log')).write_text(text)
 report=ROOT/'验收记录'/rel
 objects=[]
 for i,c in enumerate(text):
  if c!='{':continue
  try:
   obj,_=json.JSONDecoder().raw_decode(text[i:])
   if isinstance(obj,dict) and 'passed' in obj:objects.append(obj)
  except ValueError:pass
 obj=json.loads(report.read_text()) if report.exists() and report.stat().st_mtime>=start-2 else (objects[-1] if objects else {})
 (OUT/(name+'.json')).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
 row=dict(suite=name,host=lane,candidateSHA256=sha,exitCode=code,passed=obj.get('passed'),failed=obj.get('failed',int(code!=0)),jsErrors=obj.get('jsErrors',len(obj.get('errors',[]))),seconds=round(time.time()-start,2))
 summary.append(row)
 (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 print('RESULT',json.dumps(row,ensure_ascii=False),flush=True)
 if code:print(text[-6000:],flush=True)
assert hashlib.sha256((ROOT/'候选试玩.html').read_bytes()).hexdigest()==sha
raise SystemExit(any(r['exitCode'] or r['failed'] or r['jsErrors'] for r in summary))
