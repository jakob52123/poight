"""Combine complete same-candidate receipts; preserve the initial failures and retry provenance."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '验收记录/首开加载/M9-delivery'
OUT.mkdir(parents=True, exist_ok=True)
sha = hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest()
proof = json.loads((ROOT / '验收记录/M9/final-inputs.json').read_text())
assert sha == proof['candidateSHA256']
assert hashlib.sha256((ROOT / '候选发布清单.json').read_bytes()).hexdigest() == proof['manifestSHA256']
for name, digest in proof['sources'].items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
baseline = ROOT / '验收记录/首开加载/M9-final'
assert (baseline / 'candidate-sha256.txt').read_text().strip() == sha
rows = json.loads((baseline / 'summary.json').read_text())
assert len(rows) == len({r['test'] for r in rows}) == 49
updates = []
for label, expected in [('M9-corrections', ['招式第1批', '招式动画-VA1', '战斗音乐']),
                        ('M9-music-verified', ['战斗音乐']),
                        ('M9-music-complete', ['战斗音乐'])]:
    retry = ROOT / '验收记录/集成批次' / label
    assert (retry / 'candidate-sha256.txt').read_text().strip() == sha
    batch = json.loads((retry / 'summary.json').read_text())
    assert [r['test'] for r in batch] == expected
    updates.extend((row, retry) for row in batch)
changes = []
for update, retry in updates:
    index = next(i for i, row in enumerate(rows) if row['test'] == update['test'])
    changes.append({'original': rows[index], 'replacement': update,
                    'source': str(retry.relative_to(ROOT)),
                    'finalTestSHA256': hashlib.sha256((ROOT / ('验收-' + update['test'] + '.py')).read_bytes()).hexdigest()})
    rows[index] = update
(OUT / 'summary.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
(OUT / 'provenance.json').write_text(json.dumps({'candidateSHA256': sha,
    'initialCompleteRun': str(baseline.relative_to(ROOT)), 'correctedGates': changes,
    'note': 'No runtime/artifact changes. Initial failures retained; interrupted redundant rerun is not evidence.'},
    ensure_ascii=False, indent=2) + '\n')
(OUT / 'candidate-sha256.txt').write_text(sha + '\n')
lines = [r['test'] + ' ' + json.dumps({k: r[k] for k in ['passed', 'failed', 'jsErrors']}, ensure_ascii=False)
         for r in rows]
total = {'suites': len(rows), 'passed': sum(r['passed'] for r in rows),
         'failed': sum(r['failed'] for r in rows), 'jsErrors': sum(r['jsErrors'] for r in rows)}
lines.append('TOTAL ' + json.dumps(total))
text = '\n'.join(lines) + '\n'
(OUT / '原样摘要.txt').write_text(text)
print(text, end='')
raise SystemExit(bool(total['failed'] or total['jsErrors'] or any(r['exitCode'] for r in rows)))
