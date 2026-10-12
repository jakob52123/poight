"""Pack byte-identical local fixtures omitted by remote sync (no browser)."""
import hashlib
import json
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
files = {}
for name in ('体型与移速-修改前/收据.json', '体型与移速-修改前/候选发布清单.json',
             '绿宝石-接入前/收据.json', '绿宝石-接入前/候选发布清单.json', '平衡/汇总收据.json'):
    files['验收记录/' + name] = ROOT / '验收记录' / name
files['验收记录/手感/M4-baseline.html'] = ROOT.parent / 'H1/验收记录/手感/M4-baseline.html'
files['MX-远程bin/node'] = Path(shutil.which('node')).resolve()
files['验收记录/MX-夹具/关键帧核查.jpg'] = Path(
    './project')
frozen = ROOT / '.mx-performance-baseline'
for name in ('候选试玩.html', '候选发布清单.json', '预览服务.py', '素材/绿宝石场景/场景目录.json'):
    files['验收记录/丰缘全图/M-fd1eb0f/' + name] = frozen / name
for name in json.loads((frozen / '候选发布清单.json').read_text())['assets']:
    files['验收记录/丰缘全图/M-fd1eb0f/' + name] = frozen / name
base = ROOT.parent / 'T5'
record_path = '招式特效/生图重做/实景预览/构建记录.json'
record = json.loads((ROOT / record_path).read_text())['assets']
for mid in ('thunderbolt', 'quickattack', 'irontail', 'thunder', 'flamethrower',
            'fireblast', 'dragonclaw', 'airslash', 'stoneedge'):
    name = ('招式特效/主角八招/' + mid + '/' + mid + '-动画.png'
            if mid in ('thunderbolt', 'thunder') else record[mid]['output'])
    files['验收记录/MX-夹具/T5/' + name] = base / name
for name in (record_path, '招式特效/实战打包记录.json'):
    files['验收记录/MX-夹具/T5/' + name] = base / name
for folder in ('素材', '画面'):
    for source in (base / folder).rglob('*'):
        if source.is_file() and source.suffix.lower() in ('.png', '.jpg', '.gif', '.webp'):
            files['验收记录/MX-夹具/T5/' + str(source.relative_to(base))] = source
hashes = {name: hashlib.sha256(source.read_bytes()).hexdigest() for name, source in files.items()}
with tarfile.open(ROOT / 'MX-夹具.tar.gz', 'w:gz') as archive:
    for name, source in files.items():
        archive.add(source, arcname=name, recursive=False)
(ROOT / 'MX-夹具-sha256.json').write_text(json.dumps(hashes, ensure_ascii=False, indent=2) + '\n')
print('Packed', len(files), 'unchanged inputs')
