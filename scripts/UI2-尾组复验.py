"""Wait for the isolated 8976 lane, then rerun its migrated layout assertion."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '验收记录/UI2'
meta = json.loads((OUT / 'parallel-8976.json').read_text())
clone = Path(meta['directory'])
while subprocess.run(['ps', '-p', str(meta['pid'])], capture_output=True, check=False).returncode == 0:
    time.sleep(2)
shutil.copy2(ROOT / '验收-集成联动.py', clone / '验收-集成联动.py')
command = ['bash', str(ROOT.parent / 'tools/远程执行.sh'), '8976', str(clone),
           'python', 'scripts/M7-批次.py', 'UI2-release-recheck', '--keep-going', '集成联动']
result = subprocess.run(command, env={**os.environ, 'HOST': 'local', 'POIGHT_SUITE_TIMEOUT': '1800'},
                        check=False)
(OUT / 'recheck-exit.json').write_text(json.dumps({'exitCode': result.returncode}))
sys.exit(result.returncode)
