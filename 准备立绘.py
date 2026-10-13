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
    ids = json.loads((ROOT / '首发200.json').read_text())['ids']
    # Incremental R200: keep the original 50 originals, atlas bytes and timings unchanged.
    previous = {s['id']: s for s in json.loads((OUT / '来源.json').read_text())}
    catalog = json.loads((OUT / '图集.json').read_text())
    facts = json.loads((ROOT / '数值资料/体型校准/来源.json').read_text())['species']
    aliases = {'nidoran-f': 'nidoranf', 'nidoran-m': 'nidoranm', 'mr-mime': 'mrmime',
               'farfetchd': 'farfetchd', 'mimikyu-disguised': 'mimikyu', 'ho-oh': 'hooh'}
    names = {s['id']: aliases.get(s['name'], s['name']) for s in facts}
    with ThreadPoolExecutor(max_workers=4) as pool:
        added = list(pool.map(download, [(n, names[n]) for n in ids
            if n not in previous or previous[n]['sources'][0].get('missing')]))
    previous.update({s['id']: s for s in added})
    sources = [previous[n] for n in ids]
    (OUT / '来源.json').write_text(json.dumps(sources, ensure_ascii=False, indent=2) + '\n')
    missing = [s for s in sources if any(x.get('missing') for x in s['sources'])]
    assert all(not s['sources'][0].get('missing') for s in sources), missing
    for source in sources:
        if str(source['id']) in catalog:
            continue
        animated = not source['sources'][1].get('missing')
        if not animated:
            source['fallback'] = 'gen5 PNG; gen5ani GIF unavailable'
        with Image.open(OUT / source['sources'][1 if animated else 0]['file']) as gif:
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
        catalog[str(source['id'])] = {'file': filename, 'width': w, 'height': h, 'columns': columns,
                                'durations': durations, 'frames': len(frames), 'sourceFacing': 'left',
                                'sha256': hashlib.sha256((OUT / filename).read_bytes()).hexdigest()}
    (OUT / '来源.json').write_text(json.dumps(sources, ensure_ascii=False, indent=2) + '\n')
    (OUT / '图集.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'portraits': len(catalog), 'missing': missing,
                      'sourceBytes': sum(p.stat().st_size for p in OUT.iterdir())}))


if __name__ == '__main__':
    main()
