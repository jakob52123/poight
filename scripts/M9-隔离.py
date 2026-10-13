"""Create three APFS clone snapshots entirely inside M9, before any browser runs.
Arena/A1/A2 tests temporarily rebuild the candidate, so shared writable lanes are invalid.
"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
name = sys.argv[1] if len(sys.argv) > 1 else 'M9-lanes'
assert name.startswith('M9-') and name.endswith('-lanes') and '/' not in name
LANES = ROOT / '验收记录' / name
LANES.mkdir(parents=True, exist_ok=True)
sha = hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest()
info = {}
for port in [8981, 8982, 8983]:
    dest = LANES / str(port) / 'M9'
    assert not dest.exists(), f'Refuse to overwrite a running/existing snapshot: {dest}'
    dest.mkdir(parents=True)
    for path in ROOT.iterdir():
        if path.name == '验收记录':
            continue
        subprocess.run(['cp', '-cR', str(path), str(dest / path.name)], check=True)
    evidence = dest / '验收记录'
    evidence.mkdir()
    for path in (ROOT / '验收记录').iterdir():
        if path.name.startswith('M9-') and 'lanes' in path.name:
            continue
        subprocess.run(['cp', '-cR', str(path), str(evidence / path.name)], check=True)
    assert hashlib.sha256((dest / '候选试玩.html').read_bytes()).hexdigest() == sha
    info[str(port)] = {'path': str(dest), 'candidateSHA256': sha, 'readyNs': time.time_ns()}
    print('LANE_READY', port, sha, flush=True)
(LANES / 'lane-info.json').write_text(json.dumps(info, ensure_ascii=False, indent=2) + '\n')
