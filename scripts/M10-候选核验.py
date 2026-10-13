"""Offline integrity gate for the frozen stage-one candidate; no publishing."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '验收记录/M10'
OUT.mkdir(parents=True, exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = json.loads((ROOT / '候选发布清单.json').read_text())
assets = manifest['assets']
bad = [name for name, item in assets.items() if not (ROOT / name).is_file()
       or (ROOT / name).stat().st_size != item['bytes'] or sha(ROOT / name) != item['sha256']]
mp3 = sorted(name for name in assets if name.endswith('.mp3'))
missing_mp3 = sorted(str(p.relative_to(ROOT)) for p in (ROOT/'assets').glob('*.mp3')
                     if str(p.relative_to(ROOT)) not in assets)
stone_sha = 'ec3849ad57d94f0a64a8b95e2f9e188051659d7eb0f5ccc2b836f6684c66ed39'
stone = [name for name, item in assets.items() if item['sha256'] == stone_sha]
syntax = {name: subprocess.run(['node', '--check', name], cwd=ROOT, capture_output=True,
                               text=True).returncode for name in
          ['对战.js', '战斗音乐.js', '埋点.js', '按需资源.js']}
result = dict(candidateSHA256=sha(ROOT/'候选试玩.html'),
              manifestCandidateSHA256=manifest['candidateSHA256'],
              htmlBytes=(ROOT/'候选试玩.html').stat().st_size,
              assetCount=len(assets), assetBytes=sum(item['bytes'] for item in assets.values()),
              musicFiles=len(mp3), musicBytes=sum(assets[name]['bytes'] for name in mp3),
              musicAssets=mp3, missingMP3=missing_mp3, invalidAssets=bad,
              stoneEdgeSHA256=stone_sha, stoneEdgeFiles=stone, syntax=syntax)
result['passed'] = (result['candidateSHA256'] == result['manifestCandidateSHA256']
                    and not bad and not missing_mp3 and len(mp3) == 9
                    and bool(stone) and not any(syntax.values()))
(OUT/'候选核验.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(result, ensure_ascii=False, indent=2))
assert result['passed']
