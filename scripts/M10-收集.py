"""Collect the two isolated completed lanes without replacing product sources."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'验收记录/M10'
JADE = ROOT/'.m10-lanes/Jade/M10'
sha = hashlib.sha256((ROOT/'候选试玩.html').read_bytes()).hexdigest()
assert hashlib.sha256((JADE/'候选试玩.html').read_bytes()).hexdigest() == sha
shutil.copytree(JADE/'验收记录/M10/Jade', OUT/'Jade', dirs_exist_ok=True)
# Preserve complete checks even when the lane runner consumed the printed summary.
shutil.copy2(JADE/'验收记录/UI2/summary.json', OUT/'Jade/界面GBA.json')
for root, rel, label in [(ROOT, '首开加载', '首开加载'),
                         (ROOT, '埋点', '埋点'),
                         (JADE, '选人页', '选人页'),
                         (JADE, 'UI2', '界面GBA')]:
    source = root/'验收记录'/rel
    if source.exists():
        shutil.copytree(source, OUT/'证据'/label, dirs_exist_ok=True)
for name in ['AUD实播.json', 'AUD响度大小.json']:
    if (ROOT/'验收记录/战斗音乐'/name).exists():
        target = OUT/('local复验' if (OUT/'local复验/summary.json').exists() else 'local')
        shutil.copy2(ROOT/'验收记录/战斗音乐'/name, target/name)
shots = OUT/'截图'
shots.mkdir(exist_ok=True)
for folder, prefix in [(OUT/'证据/首开加载/after/截图', '首开-'),
                       (OUT/'证据/选人页/截图', '选人-'),
                       (OUT/'证据/界面GBA/截图', 'GBA-')]:
    if folder.exists():
        for p in folder.glob('*.png'):
            shutil.copy2(p, shots/(prefix+p.name))
summary = []
for lane in ['local', 'Jade']:
    rows = json.loads((OUT/lane/'summary.json').read_text())
    assert all(r['candidateSHA256'] == sha for r in rows)
    summary.extend(rows)
assert len(summary) == 7
(OUT/'快检汇总.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(summary, ensure_ascii=False, indent=2))
if (OUT/'local复验/summary.json').exists():
    rechecks = json.loads((OUT/'local复验/summary.json').read_text())
    print('RECHECK', json.dumps(rechecks, ensure_ascii=False))
    assert all(r['candidateSHA256'] == sha for r in rechecks)
    latest = {r['suite']: r for r in summary + rechecks}
else:
    latest = {r['suite']: r for r in summary}
(OUT/'最终快检汇总.json').write_text(json.dumps(list(latest.values()), ensure_ascii=False, indent=2)+'\n')
# A successful recheck does not erase the first-run failures stored above.
assert all(r['exitCode']==0 and r['failed']==0 and r['jsErrors']==0 for r in latest.values())
