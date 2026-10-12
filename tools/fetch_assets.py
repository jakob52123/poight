#!/usr/bin/env python3
"""Fetch only pinned, SHA-verified assets. Never stage downloaded artwork in Git."""
from pathlib import Path, PurePosixPath
from urllib.request import Request, urlopen
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import argparse, hashlib, json, subprocess, sys

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def target(relative):
    p = PurePosixPath(relative)
    if p.is_absolute() or not p.parts or any(v in ('.', '..', '.git') for v in p.parts):
        raise ValueError('Unsafe destination: ' + relative)
    dest = ROOT.joinpath(*p.parts)
    if not dest.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('Destination escapes repository')
    return dest


def write_verified(relative, data, expected):
    if sha(data) != expected:
        raise ValueError('SHA mismatch: ' + relative)
    dest = target(relative)
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_name(dest.name + '.download-part')
    temp.write_bytes(data)
    temp.replace(dest)


def download(entry):
    url = entry['url']
    # The manifest may not silently substitute a moving branch or arbitrary host.
    pins = ('PMDCollab/SpriteCollab/7f6ea6cc6892bbdd1376f803b3a1d7f376418895/',
            'pret/pokeemerald/731ad5bfd6e6f265508d0efcca0ba42f9dcf5881/',
            'smogon/pokemon-showdown-client/cc6f5c24adaaf0a5eb89effbb580516bbf3e7286/')
    cdn = any(url.startswith('https://play.pokemonshowdown.com/sprites/' + folder + '/')
              for folder in ('gen5', 'gen5ani'))
    if not any(url.startswith('https://raw.githubusercontent.com/' + p) for p in pins) and not cdn:
        raise ValueError('Unapproved or unpinned URL: ' + url)
    # Showdown's CDN has no commit-addressed URLs: freeze its exact source SHA,
    # and fail rather than substitute newer image bytes.
    dest = target(entry['path'])
    if dest.is_file() and sha(dest.read_bytes()) == entry['sha256']:
        return dest.read_bytes()
    with urlopen(Request(url, headers={'User-Agent': 'Poight-assets/1'}), timeout=30) as response:
        if response.geturl() != url:
            raise ValueError('Unexpected redirect')
        data = response.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024:
        raise ValueError('Asset exceeds size limit')
    write_verified(entry['path'], data, entry['sha256'])
    return data


def rgba_index_zero(data, palette_data=None):
    from PIL import Image
    source = Image.open(BytesIO(data))
    if source.mode != 'P':
        raise ValueError('Expected indexed PNG')
    palette = source.getpalette()
    if palette_data is not None:
        if palette_data.startswith(b'JASC-PAL'):
            colors = [tuple(map(int, line.split())) for line in palette_data.decode().splitlines()[3:] if line.strip()]
            palette = [channel for color in colors for channel in color]
        else:
            palette = Image.open(BytesIO(palette_data)).getpalette()
    image = Image.new('RGBA', source.size)
    image.putdata([tuple(palette[i * 3:i * 3 + 3]) + (255 if i else 0,)
                   for i in source.get_flattened_data()])
    return image


def convert(recipe):
    from PIL import Image
    palette = target(recipe['palette']).read_bytes() if recipe.get('palette') else None
    if recipe['operation'] == 'gif-portrait-atlas':
        from PIL import ImageSequence
        with Image.open(target(recipe['inputs'][0])) as gif:
            frames = [frame.convert('RGBA') for frame in ImageSequence.Iterator(gif)]
        box = frames[0].getbbox()
        for frame in frames[1:]:
            bounds = frame.getbbox()
            if bounds:
                box = (min(box[0], bounds[0]), min(box[1], bounds[1]),
                       max(box[2], bounds[2]), max(box[3], bounds[3]))
        width, height = box[2] - box[0], box[3] - box[1]
        columns = min(10, len(frames))
        result = Image.new('RGBA', (width * columns, height * ((len(frames) + columns - 1) // columns)))
        for index, frame in enumerate(frames):
            result.paste(frame.crop(box), (index % columns * width, index // columns * height))
        output = BytesIO()
        result.save(output, format='PNG', optimize=True)
        write_verified(recipe['path'], output.getvalue(), recipe['sha256'])
        return
    images = [rgba_index_zero(target(p).read_bytes(), palette) for p in recipe['inputs']]
    if recipe['operation'] == 'palette-index-zero':
        result = images[0]
    elif recipe['operation'] == 'ice-cube-96':
        result = Image.new('RGBA', (96, 96))
        for image, position in zip(images, ((0, 0), (0, 64), (64, 0), (64, 64))):
            result.paste(image, position)
    elif recipe['operation'] == 'fangs-four-frames':
        palettes = {
            'fire': {1: (92, 24, 16), 2: (172, 48, 24), 3: (244, 104, 40), 4: (255, 220, 132)},
            'bug': {1: (20, 52, 24), 2: (48, 104, 44), 3: (112, 180, 72), 4: (220, 255, 156)},
        }
        indexed = Image.open(target(recipe['inputs'][0]))
        image = indexed.convert('RGBA')
        indices = list(indexed.get_flattened_data())
        image.putdata([(0, 0, 0, 0) if i == 0 else
                       (*palettes.get(recipe['fangPalette'], {}).get(i, rgba[:3]), 255)
                       for i, rgba in zip(indices, image.get_flattened_data())])
        result = Image.new('RGBA', (64, 256))
        for frame in range(4):
            result.paste(image, (0, frame * 64))
    else:
        raise ValueError('Unknown recipe')
    output = BytesIO()
    # Matches the original conversion, including transparent RGB bytes.
    result.save(output, format='PNG', optimize=False, compress_level=6)
    write_verified(recipe['path'], output.getvalue(), recipe['sha256'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-partial', action='store_true',
                        help='Fetch available assets, but do not claim a buildable checkout')
    parser.add_argument('--only-conversions', action='store_true',
                        help='Verify source-SHA conversion recipes only, excluding unrelated downloads')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'tools/assets-manifest.json').read_text())
    required = {p for r in manifest['conversions'] for p in r['inputs']}
    required.update(r['palette'] for r in manifest['conversions'] if r.get('palette'))
    entries = [e for e in manifest['downloads'] if not args.only_conversions or e['path'] in required]
    with ThreadPoolExecutor(max_workers=6) as executor:
        list(executor.map(download, entries))
    for recipe in manifest['conversions']:
        convert(recipe)
    derived = 0
    for task in manifest.get('postprocess', []):
        script = target(task['script'])
        if sha(script.read_bytes()) != task['sha256']:
            raise ValueError('Postprocess source SHA mismatch')
        subprocess.run([sys.executable, str(script)], cwd=ROOT, check=True, timeout=60)
        for entry in task['outputs']:
            if sha(target(entry['path']).read_bytes()) != entry['sha256']:
                raise ValueError('Postprocess output SHA mismatch: ' + entry['path'])
            derived += 1
    print(json.dumps({'downloadsVerified': len(entries),
                      'originalSHAConversionsVerified': len(manifest['conversions']),
                      'originalSHAPostprocessVerified': derived,
                      'blockers': manifest['blockers']}, ensure_ascii=False))
    if manifest['blockers'] and not args.allow_partial:
        print('Asset reconstruction is incomplete; refusing to claim build readiness.', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
