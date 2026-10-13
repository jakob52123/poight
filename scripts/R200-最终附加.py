"""Serial final-candidate extras. Launch only through the authorized wrapper."""
import json
import os
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'验收记录/R200'
commands=[['逐精灵验收.py','--tag','final'],['scripts/R200-冒烟.py'],['scripts/R200-选人.py'],
          ['scripts/R200-离线探针.py'],['scripts/perf_network.py'],
          ['scripts/M7-批次.py','R200-fix-core','--keep-going','招式动画核心','手感']]
rows=[]
for args in commands:
    print('RUN',args,flush=True)
    p=subprocess.run([sys.executable,*args],cwd=ROOT,env={**os.environ,'PERF_LABEL':'R200-final'},
                     capture_output=True,text=True,timeout=1800)
    name=Path(args[0]).stem
    (OUT/f'final-{name}.log').write_text(p.stdout+p.stderr)
    row=dict(command=args,exitCode=p.returncode);rows.append(row)
    print(json.dumps(row,ensure_ascii=False),p.stdout[-1000:],p.stderr[-1000:],flush=True)
(OUT/'最终附加-退出.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
raise SystemExit(any(r['exitCode'] for r in rows))
