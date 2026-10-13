"""Select latest raw suite receipts, verifying one candidate SHA and all 37 names."""
import ast
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
labels = sys.argv[1:] or ['B2-release', 'B2-migration-retry', 'B2-migration-retry-2']
sha = hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest()
tree = ast.parse((ROOT / 'scripts/PERF-全量.py').read_text())
groups = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == 'groups' for t in n.targets))
names = [name for group in groups for name in group]
selected = {}
for index, label in enumerate(labels):
    batch = ROOT / '验收记录/集成批次' / label
    assert (batch / 'candidate-sha256.txt').read_text().strip() == sha, label
    rows = json.loads((batch / 'summary.json').read_text())
    if index == 0:
        assert [r['test'] for r in rows] == names
    assert len({r['test'] for r in rows}) == len(rows)
    for row in rows:
        assert row['test'] in names
        selected[row['test']] = {**row, 'sourceBatch': label}
assert len(selected) == len(names) == 37
rows = [selected[name] for name in names]
out = ROOT / '验收记录/B2平衡/最终37套'
out.mkdir(parents=True, exist_ok=True)
(out / 'summary.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
(out / 'candidate-sha256.txt').write_text(sha + '\n')
lines = [r['test'] + ' ' + json.dumps({k: r[k] for k in ('passed', 'failed', 'jsErrors')},
                                    ensure_ascii=False) for r in rows]
total = {'suites': len(rows), 'passed': sum(r['passed'] for r in rows),
         'failed': sum(r['failed'] for r in rows), 'jsErrors': sum(r['jsErrors'] for r in rows)}
lines.append('TOTAL ' + json.dumps(total))
text = '\n'.join(lines) + '\n'
(out / '原样选取摘要.txt').write_text(text)
print(text, end='')
# Do not relabel the known poison-contrast failure as success.
raise SystemExit(bool(total['failed'] or total['jsErrors']))
