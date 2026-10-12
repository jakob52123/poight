"""Download Showdown originals with curl; lossless, composited GIF atlas conversion."""
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageSequence

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '素材/立绘'
NAMES = [
    'bulbasaur', 'ivysaur', 'venusaur', 'charmander', 'charmeleon', 'charizard',
    'squirtle', 'wartortle', 'blastoise', 'spearow', 'pikachu', 'raichu', 'psyduck',
    'abra', 'alakazam', 'machop', 'machoke', 'machamp', 'gastly', 'haunter', 'gengar',
    'onix', 'scyther', 'magikarp', 'gyarados', 'eevee', 'vaporeon', 'jolteon', 'flareon',
    'snorlax', 'articuno', 'zapdos', 'moltres', 'dratini', 'dragonair', 'dragonite',
    'mewtwo', 'mew', 'espeon', 'umbreon', 'steelix', 'scizor', 'ralts', 'kirlia',
    'gardevoir', 'lucario', 'leafeon', 'glaceon', 'greninja', 'sylveon',
]


def download(pair):
    ident, name = pair
    records = []
    for folder, ext in [('gen5', 'png'), ('gen5ani', 'gif')]:
        url = f'https://play.pokemonshowdown.com/sprites/{folder}/{name}.{ext}'
        path = OUT / f'{ident:04}-{name}.{ext}'
        result = subprocess.run(['curl', '-fL', '--retry', '2', '--max-time', '60', '-sS', url, '-o', str(path)], check=False)
        if result.returncode:
            path.unlink(missing_ok=True)
            records.append({'url': url, 'missing': True})
        else:
            expected = next(r['sha256'] for row in json.loads((OUT / '来源.json').read_text()) for r in row['sources'] if r['url'] == url)
            assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'Portrait SHA changed upstream'
            with Image.open(path) as image:
                image.verify()
            records.append({'url': url, 'file': path.name, 'bytes': path.stat().st_size,
                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return {'id': ident, 'name': name, 'sources': records, 'sourceFacing': 'left'}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ids = json.loads((ROOT / '首发50.json').read_text())['ids']
    with ThreadPoolExecutor(max_workers=8) as pool:
        sources = list(pool.map(download, zip(ids, NAMES, strict=True)))
    (OUT / '来源.json').write_text(json.dumps(sources, ensure_ascii=False, indent=2) + '\n')
    missing = [s for s in sources if any(x.get('missing') for x in s['sources'])]
    assert not missing, missing
    catalog = {}
    for source in sources:
        with Image.open(OUT / source['sources'][1]['file']) as gif:
            frames = [f.convert('RGBA') for f in ImageSequence.Iterator(gif)]
            durations = [max(10, f.info.get('duration', 100)) for f in ImageSequence.Iterator(gif)]
        box = frames[0].getbbox()
        for frame in frames[1:]:
            b = frame.getbbox()
            if b:
                box = (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
        w, h = box[2] - box[0], box[3] - box[1]
        columns = min(10, len(frames))
        atlas = Image.new('RGBA', (w * columns, h * ((len(frames) + columns - 1) // columns)))
        for i, frame in enumerate(frames):
            atlas.paste(frame.crop(box), (i % columns * w, i // columns * h))
        filename = f"{source['id']:04}-atlas.png"
        atlas.save(OUT / filename, optimize=True)
        catalog[source['id']] = {'file': filename, 'width': w, 'height': h, 'columns': columns,
                                'durations': durations, 'frames': len(frames), 'sourceFacing': 'left',
                                'sha256': hashlib.sha256((OUT / filename).read_bytes()).hexdigest()}
    (OUT / '图集.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'portraits': len(catalog), 'missing': missing,
                      'sourceBytes': sum(p.stat().st_size for p in OUT.iterdir())}))


if __name__ == '__main__':
    main()
