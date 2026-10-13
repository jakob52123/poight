"""Reproducible local-only MP3 packaging. Reads only repository source copies."""
import csv
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / '素材/音乐/源'
RATE = 44100
# Whole bars: 02 and Skiff use 120 BPM/48 bars.
# 03 uses 14 x 7.2s repeating units: shared bar grid of measured .36/.45s pulses.
# Native looping 09/15 retain the authored full loop.
SEGMENTS = {'01': (0, None), '02': (7.5, 103.5), '03': (7.2, 108.0),
            '04': (32.0, 128.0), '05': (16.0, 112.0), '06': (16.0, 112.0),
            '09': (0, None), '15': (0, None)}


def run(*args):
    return subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-y', *map(str, args)],
                          capture_output=True, check=True)


def decode(path):
    return np.frombuffer(run('-v', 'error', '-i', path, '-ar', RATE, '-ac', 2,
                             '-f', 'f32le', '-').stdout, '<f4').reshape(-1, 2).copy()


def lufs(path):
    log = run('-i', path, '-af', 'ebur128=peak=true', '-f', 'null', '-').stderr.decode()
    return float(re.findall(r'I:\s+(-?[\d.]+) LUFS', log)[-1])


def main():
    rows = {r['编号']: r for r in csv.DictReader((SOURCE / '来源.tsv').open(), delimiter='\t')}
    catalog = []
    with tempfile.TemporaryDirectory(dir=ROOT) as temp:
        temp = Path(temp)
        for ident, (start, end) in SEGMENTS.items():
            intro = np.zeros((0, 2), np.float32)
            if ident == '01':
                intro = decode(SOURCE / '01. Battle Theme I (intro).ogg')
                path = SOURCE / '01. Battle Theme I (loop).ogg'
            else:
                path = next(SOURCE.glob(ident + '-*'))
            samples = decode(path)
            end = end or len(samples) / RATE
            loop = samples[round(start * RATE):round(end * RATE)]
            # Circular 40ms overlap (<=80ms), not a long fade/tempo/filter effect.
            # Authored loops retain all samples; only unmarked / truncated loops need repair.
            overlap = 0 if ident in ('01', '09', '15') else round(.04 * RATE)
            if overlap:
                w = np.linspace(0, 1, overlap, dtype=np.float32)[:, None]
                edge = loop[-overlap:] * (1 - w) + loop[:overlap] * w
                loop = np.concatenate([edge, loop[overlap:-overlap]])
            raw = temp / 'input.f32'
            np.concatenate([intro, loop]).astype('<f4').tofile(raw)
            wav = temp / 'normalized.wav'
            # Two-pass EBU loudnorm; linear gain where true peak permits it, no EQ/pitch change.
            scan = run('-f', 'f32le', '-ar', RATE, '-ac', 2, '-i', raw,
                       '-af', 'loudnorm=I=-16:TP=-1:LRA=20:print_format=json', '-f', 'null', '-')
            text = scan.stderr.decode(); stats = json.loads(text[text.rfind('{'):text.rfind('}') + 1])
            filt = ('loudnorm=I=-16:TP=-1:LRA=20:linear=true:measured_I={input_i}:'
                    'measured_TP={input_tp}:measured_LRA={input_lra}:measured_thresh={input_thresh}:'
                    'offset={target_offset}').format(**stats)
            run('-f', 'f32le', '-ar', RATE, '-ac', 2, '-i', raw, '-af', filt, '-ar', RATE, wav)
            def encode(kind, seek, duration):
                mp3 = temp / (kind + '.mp3')
                run('-i', wav, '-ss', seek, '-t', duration, '-map_metadata', '-1',
                    '-codec:a', 'libmp3lame', '-b:a', '80k', '-ar', RATE, '-ac', 2,
                    '-write_xing', '1', mp3)
                content = mp3.read_bytes(); digest = hashlib.sha256(content).hexdigest()
                filename = f'bgm-c{ident}{kind}-{digest[:12]}.mp3'
                (ROOT / 'assets' / filename).write_bytes(content)
                return filename, content, digest, lufs(mp3)
            intro_seconds = len(intro) / RATE
            filename, content, digest, level = encode('', intro_seconds, len(loop) / RATE)
            extra = {}
            if intro_seconds:
                intro_name, intro_bytes, intro_sha, intro_lufs = encode('-intro', 0, intro_seconds)
                extra = dict(intro='assets/' + intro_name, introDuration=intro_seconds,
                             introBytes=len(intro_bytes), introSHA256=intro_sha, introLUFS=intro_lufs)
            row = rows[ident]
            item = dict(id='c' + ident, name=row['曲名'], author=row['作者'], license=row['许可'],
                        url=row['页面URL'], attribution=row['署名要求原文'], src='assets/' + filename,
                        loopStart=0.0, duration=(len(intro) + len(loop)) / RATE,
                        sourceStart=start, sourceEnd=end, crossfadeMS=overlap / RATE * 1000,
                        kbps=80, bytes=len(content) + extra.get('introBytes', 0), sha256=digest, lufs=level, **extra)
            assert item['duration'] <= 120 and item['bytes'] <= 1_200_000
            assert abs(item['lufs'] + 16) <= 1
            catalog.append(item)
            print(ident, filename, item['duration'], item['bytes'], item['lufs'], flush=True)
    assert sum(t['bytes'] for t in catalog) <= 8_000_000
    (ROOT / '素材/音乐/外部BGM.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
