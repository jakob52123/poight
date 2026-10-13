"""Rebuild immutable eb38429 sources in this workspace to measure gzip-6 accurately.
No browser. Always rebuild HEAD work files afterwards. All outputs remain inside UI2.
"""
import gzip
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / '验收记录/UI2'
original = Path.read_text
changed = ['页面.html', '对战.js', '手机操作.js', '战斗界面方案.js', '立绘.js']
blobs = {ROOT / name: subprocess.check_output(['git', 'show', f'eb38429:{name}'], cwd=ROOT).decode()
         for name in changed}
base = subprocess.check_output(['git', 'show', 'eb38429:构建完整版.py'], cwd=ROOT).decode()


def baseline_read(path, *args, **kwargs):
    return blobs[path] if path in blobs else original(path, *args, **kwargs)


try:
    Path.read_text = baseline_read
    exec(compile(base, str(ROOT / '构建完整版.py'), 'exec'),  # noqa: S102 - immutable local git source
         {'__file__': str(ROOT / '构建完整版.py'), '__name__': '__main__'})
    data = (ROOT / '候选试玩.html').read_bytes()
    evidence = {'commit': 'eb38429', 'htmlBytes': len(data),
                'gzip6Bytes': len(gzip.compress(data, compresslevel=6, mtime=0)),
                'gzip9Bytes': len(gzip.compress(data, compresslevel=9, mtime=0))}
    (OUT / '首开基线-精确.json').write_text(json.dumps(evidence, indent=2))
finally:
    Path.read_text = original
    subprocess.run([sys.executable, str(ROOT / '构建完整版.py')], cwd=ROOT, check=True)
