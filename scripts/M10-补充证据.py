"""Serial screenshots then randomized round audio; run through PRIORITY wrapper."""
import json
import subprocess
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'验收记录/M10/第二段'
rows=[]
for script in ['scripts/M10-截图审计.py','scripts/M10-200局音乐.py']:
 start=time.monotonic()
 p=subprocess.run([sys.executable,script],cwd=ROOT,capture_output=True,text=True,timeout=600)
 text=p.stdout+p.stderr
 (OUT/(Path(script).stem+'.log')).write_text(text)
 print(text,flush=True)
 rows.append(dict(script=script,exitCode=p.returncode,seconds=round(time.monotonic()-start,2)))
 (OUT/'补充证据执行.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
raise SystemExit(any(r['exitCode'] for r in rows))
