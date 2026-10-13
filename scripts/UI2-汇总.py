"""Merge raw suite results from the two UI2-authorized ports; never relabel failures.
8976 uses an isolated temporary clone to avoid shared fixture cleanup races.
"""
import ast
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '验收记录/UI2'
meta = json.loads((OUT / 'parallel-8976.json').read_text())
clone = Path(meta['directory'])
sha = hashlib.sha256((OUT / '全量候选.html').read_bytes()).hexdigest()
assert sha == meta['candidateSHA256']
assert hashlib.sha256((clone / '候选试玩.html').read_bytes()).hexdigest() == sha
inventory = next(ast.literal_eval(node.value) for node in
                 ast.parse((ROOT / 'scripts/PERF-全量.py').read_text()).body
                 if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                 and node.targets[0].id == 'groups')
expected = ['界面GBA', *(name for group in inventory for name in group)]
assert len(expected) == len(set(expected)) == 38
primary = ROOT / '验收记录/集成批次/UI2-release-8975'
secondary = clone / '验收记录/集成批次/UI2-release-8976'
assert (secondary / 'candidate-sha256.txt').read_text().strip() == sha
rows = {}
origins = {}
rest = ROOT / '验收记录/集成批次/UI2-release-rest'
recheck = clone / '验收记录/集成批次/UI2-release-recheck'
core = clone / '验收记录/集成批次/UI2-core-recheck'
for directory in (primary, rest, secondary, recheck, core):
    if directory != primary:
        assert (directory / 'candidate-sha256.txt').read_text().strip() == sha
    for row in json.loads((directory / 'summary.json').read_text()):
        assert row['test'] in expected
        rows[row['test']] = row
        origins[row['test']] = str(directory)
missing = [name for name in expected if name not in rows]
if missing:
    raise SystemExit('Pending suites: ' + ', '.join(missing))
ordered = [rows[name] for name in expected]
# Preserve the complete parallel evidence before the OS can clean its temporary directory.
shutil.copytree(clone / '验收记录', OUT / '并行8976', dirs_exist_ok=True)
shutil.copytree(secondary, ROOT / '验收记录/集成批次/UI2-release-8976', dirs_exist_ok=True)
summary = {'candidateSHA256': sha, 'suites': ordered, 'origins': origins,
           'passed': sum(r['passed'] for r in ordered),
           'failed': sum(r['failed'] for r in ordered),
           'jsErrors': sum(r['jsErrors'] for r in ordered)}
(OUT / '全量汇总.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
lines = [r['test'] + ' ' + json.dumps({k: r[k] for k in ('passed', 'failed', 'jsErrors')},
                                     ensure_ascii=False) for r in ordered]
lines.append('TOTAL ' + json.dumps({'suites': 38, **{k: summary[k]
                           for k in ('passed', 'failed', 'jsErrors')}}))
text = '\n'.join(lines) + '\n'
(OUT / '原样摘要.txt').write_text(text)
(OUT / 'candidate-sha256.txt').write_text(sha + '\n')
print(text, end='')
final = json.loads((OUT / 'final-candidate.json').read_text())
final_root = Path(final['directory'])
gate = final_root / '验收记录/集成批次/UI2-final-gate'
assert (gate / 'candidate-sha256.txt').read_text().strip() == final['candidateSHA256']
checks = json.loads((gate / 'summary.json').read_text())
assert [r['test'] for r in checks] == ['界面GBA', '水溅跃']
shutil.copytree(final_root / '验收记录', OUT / '最终专项', dirs_exist_ok=True)
final['suites'] = checks
(OUT / '最终专项.json').write_text(json.dumps(final, ensure_ascii=False, indent=2))
print('FINAL_RECHECK ' + json.dumps(checks, ensure_ascii=False))
raise SystemExit(bool(summary['failed'] or summary['jsErrors'] or any(r['failed'] for r in checks)))
