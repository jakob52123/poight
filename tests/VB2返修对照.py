"""Assemble SHA-verified e7ee331 vs current four-time GIF evidence; no browser."""
import hashlib
import io
import json
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '验收记录/招式动画-VB2'
IDS = [
    'aquajet', 'flamecharge', 'tackle', 'machpunch', 'bodyslam', 'doubleedge',
    'waterfall', 'flamewheel', 'spark', 'wildcharge', 'rollout', 'zenheadbutt',
    'shadowsneak', 'phantomforce', 'bravebird', 'closecombat', 'rapidspin', 'aquatail', 'bonerush',
]
receipt = json.loads((ROOT / 'tests/VB2返修前SHA.json').read_text())
font_paths = ['/System/Library/Fonts/STHeiti Medium.ttc',
              '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']
font_path = next((p for p in font_paths if Path(p).exists()), None)
font = ImageFont.truetype(font_path, 18) if font_path else ImageFont.load_default()
overview = Image.new('RGB', (2400, 352 * len(IDS)), '#20313c')
read_receipt = {}
with zipfile.ZipFile(ROOT / 'tests/VB2返修前.zip') as archive:
    for row, mid in enumerate(IDS):
        name = mid + '-四时刻-GIF解码.png'
        old = archive.read(name)
        assert hashlib.sha256(old).hexdigest() == receipt['files'][name]
        new_path = OUT / '截图' / name
        new = new_path.read_bytes()
        before = Image.open(io.BytesIO(old)).convert('RGB')
        after = Image.open(io.BytesIO(new)).convert('RGB')
        assert before.size == after.size == (1200, 324)
        pair = Image.new('RGB', (2400, 352), '#20313c')
        draw = ImageDraw.Draw(pair)
        draw.text((5, 3), mid + ' / 返修前 e7ee331 / 四时刻', font=font, fill='white')
        draw.text((1205, 3), mid + ' / 返修后 / 相同四时刻', font=font, fill='white')
        pair.paste(before, (0, 28))
        pair.paste(after, (1200, 28))
        pair.save(OUT / '截图' / (mid + '-返修对照.png'))
        overview.paste(pair, (0, row * 352))
        read_receipt[mid] = {'before': hashlib.sha256(old).hexdigest(),
                             'after': hashlib.sha256(new).hexdigest()}
overview.save(OUT / '返修对照.png')
(OUT / '返修对照SHA.json').write_text(json.dumps({
    'baselineCommit': receipt['commit'],
    'candidateSHA256': hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest(),
    'panels': read_receipt}, ensure_ascii=False, indent=2) + '\n')
print('COMPARISON 19 rows / same four times / SHA-verified e7ee331 baseline')
