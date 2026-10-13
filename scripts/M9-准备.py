"""Stage immutable inputs once before three local lanes; fingerprint release and sources."""
import hashlib
import json
import subprocess
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '验收记录/M9'
OUT.mkdir(parents=True, exist_ok=True)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


with tarfile.open(ROOT / 'MX-夹具.tar.gz') as archive:
    archive.extractall(ROOT, filter='data')
receipts = json.loads((ROOT / 'MX-夹具-sha256.json').read_text())
assert all(sha(ROOT / name) == digest for name, digest in receipts.items())
print('MX_FIXTURES', len(receipts), 'failed 0')
for stem in ['VB2远程输入', 'M8历史夹具']:
    hashes = json.loads((ROOT / f'tests/{stem}SHA.json').read_text())
    with zipfile.ZipFile(ROOT / f'tests/{stem}.zip') as archive:
        assert set(archive.namelist()) == set(hashes)
        for name, digest in hashes.items():
            path = ROOT / name
            assert path.resolve().is_relative_to(ROOT)
            data = archive.read(name)
            assert hashlib.sha256(data).hexdigest() == digest
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print(stem, len(hashes), 'failed 0')
fixture = ROOT / 'tests/M8X-FX1-baseline.tar.gz'
assert sha(fixture) == 'b4eed70345c00c5c5ddfbead8a416a95db8ff17d7677da3ddfe83ac7a65a00e5'
with tarfile.open(fixture) as archive:
    archive.extractall(ROOT / '验收记录/FX1', filter='data')
originals = json.loads((ROOT / 'tests/VB2原角色地图SHA.json').read_text())
changed = [name for name, digest in originals.items() if not (ROOT / name).exists() or sha(ROOT / name) != digest]
print('ORIGINAL_ASSETS', len(originals), 'failed', len(changed))
assert not changed, changed
files = [ROOT / '招式动画-VA2.js', ROOT / '招式动画/VA2素材.py',
         ROOT / '招式动画/VA2/制作贴图.py', *sorted((ROOT / '招式动画/VA2').glob('*.png'))]
proof = {'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
         'candidateSHA256': sha(ROOT / '候选试玩.html'),
         'manifestSHA256': sha(ROOT / '候选发布清单.json'),
         'FX1SourceSHA256': hashlib.sha256(b''.join(p.read_bytes() for p in files)).hexdigest(),
         'historicalP6SHA256': sha(ROOT / 'P6-baseline.html'),
         'sources': {str(p.relative_to(ROOT)): sha(p) for p in sorted(ROOT.glob('*.js'))}}
(OUT / 'final-inputs.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in proof.items() if k != 'sources'}, ensure_ascii=False))
