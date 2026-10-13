"""Render frozen 9f9c0ac and current synthesis, measure spectra/LUFS, create audition WAVs."""
import base64
import json
import os
import re
import shutil
import subprocess
import time
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright
from scipy.signal import lfilter, welch

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/战斗音乐/BGM3试听"
OUT.mkdir(parents=True, exist_ok=True)
RATE = 44100
RENDER = """async ([version,id]) => {
  const api=version==='old'?PoightMusicBaseline:PoightMusicScore;
  const {buffer,...metadata}=id==='dynamic'?await api.renderDynamic(30,1,'r3'):
    await api.render(id,60,1);
  const bytes=new Uint8Array(buffer.getChannelData(0).buffer), chunks=[];
  for(let i=0;i<bytes.length;i+=16384)
    chunks.push(String.fromCharCode(...bytes.subarray(i,i+16384)));
  return {...metadata,pcm:btoa(chunks.join(''))};
}"""


def db(value):
    return float(20 * np.log10(max(float(value), 1e-12)))


def wav(path, raw):
    pcm = np.round(raw * 32767).astype('<i2')
    assert np.max(np.abs(raw)) < 1
    with wave.open(str(path), 'wb') as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(RATE)
        stream.writeframes(np.column_stack([pcm, pcm]).tobytes())


def ffmpeg():
    executable = shutil.which('ffmpeg')
    if executable:
        return executable
    for path in ['/opt/homebrew/bin/ffmpeg', '/usr/local/bin/ffmpeg']:
        if Path(path).is_file():
            return path
    return None


def integrated_lufs(path):
    """BS.1770 De Man K-weighting, 400ms blocks, 75% overlap, absolute/relative gates."""
    with wave.open(str(path)) as stream:
        assert stream.getnchannels() == 2 and stream.getframerate() == RATE
        samples = np.frombuffer(stream.readframes(stream.getnframes()), '<i2').reshape(-1, 2)
    x = samples.astype(np.float64) / 32768
    k = np.tan(np.pi * 1681.974450955533 / RATE)
    q, vh = .7071752369554196, 10 ** (3.999843853973347 / 20)
    vb = vh ** .4996667741545416
    a0 = 1 + k / q + k * k
    b = [(vh + vb * k / q + k * k) / a0, 2 * (k * k - vh) / a0,
         (vh - vb * k / q + k * k) / a0]
    a = [1, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0]
    x = lfilter(b, a, x, axis=0)
    k, q = np.tan(np.pi * 38.13547087613982 / RATE), .5003270373238773
    a0 = 1 + k / q + k * k
    a = [1, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0]
    x = lfilter([1, -2, 1], a, x, axis=0)
    size, step = round(.4 * RATE), round(.1 * RATE)
    energy = np.sum(x * x, axis=1)
    cumulative = np.concatenate([[0], np.cumsum(energy)])
    starts = np.arange(0, len(x) - size + 1, step)
    blocks = (cumulative[starts + size] - cumulative[starts]) / size
    levels = -.691 + 10 * np.log10(np.maximum(blocks, 1e-30))
    absolute = levels >= -70
    relative = -.691 + 10 * np.log10(np.mean(blocks[absolute])) - 10
    return float(-.691 + 10 * np.log10(np.mean(blocks[absolute & (levels >= relative)])))


def lufs(path):
    executable = ffmpeg()
    if not executable:
        return integrated_lufs(path)
    result = subprocess.run([executable, '-hide_banner', '-i', str(path), '-af',
                             'ebur128=peak=true', '-f', 'null', '-'],
                            capture_output=True, text=True, check=True, timeout=120)
    values = re.findall(r'I:\s+(-?[\d.]+) LUFS', result.stderr)
    assert values, result.stderr
    return float(values[-1])


def spectrum(raw):
    frequency, power = welch(raw.astype(np.float64), fs=RATE, nperseg=4096,
                             noverlap=2048, window='hann')
    return {'centroidHz': float(np.sum(frequency * power) / np.sum(power)),
            'above4kFraction': float(np.sum(power[frequency > 4000]) / np.sum(power))}


def waveplot(raw, boundaries, name):
    image = Image.new('RGB', (1600, 1000), '#101c30')
    draw = ImageDraw.Draw(image)
    draw.text((30, 15), name + ' | 44.1kHz | independently scaled waveforms', fill='white')
    rows = [(0, len(raw) / RATE, 'Full duration')] + [
        (t - .05, t + .05, f'Boundary {t:.6f}s +/-50ms') for t in boundaries]
    for row, (start, end, text) in enumerate(rows):
        top = 60 + row * (900 / len(rows))
        mid, left, right = top + 95, 60, 1540
        part = raw[round(start * RATE):round(end * RATE)]
        scale = 85 / max(float(np.max(np.abs(part))), .001)
        draw.text((left, top), text, fill='white')
        draw.line((left, mid, right, mid), fill='#52637a')
        for x in range(right - left):
            a = int(x * len(part) / (right - left))
            b = max(a + 1, int((x + 1) * len(part) / (right - left)))
            values = part[a:b]
            draw.line((left + x, mid - float(values.max()) * scale,
                       left + x, mid - float(values.min()) * scale), fill='#69dfcd')
        for t in boundaries:
            if start < t < end:
                x = left + (t - start) / (end - start) * (right - left)
                draw.line((x, top + 25, x, mid + 90), fill='#ff8a88')
    image.save(OUT / (name + '-波形.png'))


def main():
    baseline = subprocess.check_output(['git', 'show', '9f9c0ac:战斗音乐.js'], text=True)
    baseline = baseline.replace('window.PoightMusicScore', 'window.PoightMusicBaseline').replace(
        'window.PoightBattleMusic', 'window.PoightBattleMusicBaseline')
    errors, results, metadata = [], {}, {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        context.add_init_script(baseline)
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(os.environ['POIGHT_TEST_URL'].rstrip('/') + '/?test=1&music=off')
        for _ in range(800):
            if page.evaluate('()=>window.__waterTest?.snapshot().artReady'):
                break
            time.sleep(.025)
        else:
            raise TimeoutError('artReady')
        # The baseline score, note durations, event gains and transport remain identical.
        for track in 'ABC':
            same = page.evaluate("""id=>{
              const old=PoightMusicBaseline.score(id), now=PoightMusicScore.score(id);
              delete old.duty;delete now.duty;
              return JSON.stringify(old)===JSON.stringify(now);
            }""", track)
            assert same, track + ' score changed'
        for version, track in [('old', 'C'), ('new', 'C'), ('old', 'B'), ('new', 'B'),
                               ('new', 'dynamic')]:
            result = page.evaluate(RENDER, [version, track])
            raw = np.frombuffer(base64.b64decode(result.pop('pcm')), dtype='<f4').copy()
            assert np.isfinite(raw).all() and db(np.max(np.abs(raw))) <= -1
            results[version, track] = raw
            metadata[version, track] = result
            wav(OUT / f'{version}-{track}-runtime.wav', raw)
        call = lambda method, value=None: page.evaluate(
            '([m,v])=>window.__waterTest[m](v)', [method, value])
        roster = {c['id']: c for c in call('catalog')['roster']}
        profile = {**call('snapshot')['profile'], 'map': 'arena-formal', 'player': 25, 'enemy': 7,
                   'playerMoves': roster[25]['defaultMoves'], 'enemyMoves': roster[7]['defaultMoves']}
        assert call('select', profile)
        call('reset', True)
        state = call('snapshot')
        bounds, maximum = state['environment']['bounds'], state['player']['maxHP']
        cx = (bounds['left'] + bounds['right']) / 2
        cy = (bounds['top'] + bounds['bottom']) / 2
        for stage, ratio in [('绿血', .8), ('黄血', .4), ('红血', .15)]:
            call('arrange', {'ai': False, 'player': {'hp': maximum * ratio, 'x': cx - 110,
                           'y': cy + 40}, 'enemy': {'x': cx + 110, 'y': cy + 40, 'a': 3.14159}})
            call('step', .02)
            page.screenshot(path=OUT / f'{stage}-实机.png')
        context.close()
        browser.close()
    report = {'baseline': '9f9c0ac', 'jsErrors': errors, 'tracks': {}, 'scoreUnchanged': True,
              'lufsMethod': 'ffmpeg EBU R128' if ffmpeg() else 'BS.1770 De Man K-weighting'}
    # Common gain for every audition: no per-segment loudness normalization hiding differences.
    peak = max(float(np.max(np.abs(raw))) for raw in results.values())
    preview_gain = 10 ** (-2.5 / 20) / peak
    for track in 'CB':
        old, new = results['old', track], results['new', track]
        metrics = {}
        for label, seconds in [('audition10s', 10), ('full60s', 60)]:
            a, b = spectrum(old[:seconds * RATE]), spectrum(new[:seconds * RATE])
            metrics[label] = {'old': a, 'new': b,
                             'centroidReduction': 1 - b['centroidHz'] / a['centroidHz'],
                             'above4kReduction': 1 - b['above4kFraction'] / a['above4kFraction']}
        metrics['oldLUFS'] = lufs(OUT / f'old-{track}-runtime.wav')
        metrics['newLUFS'] = lufs(OUT / f'new-{track}-runtime.wav')
        metrics['lufsDifference'] = metrics['newLUFS'] - metrics['oldLUFS']
        seam = metadata['new', track]['seam']
        center, span = round(seam * RATE), round(.05 * RATE)
        metrics['seamSeconds'] = seam
        metrics['seamPeakDifferenceDB'] = abs(db(np.max(np.abs(new[center-span:center]))) -
                                               db(np.max(np.abs(new[center:center+span]))))
        metrics['runtimePeakDBFS'] = db(np.max(np.abs(new)))
        metrics['clippedSamples'] = int(np.sum(np.abs(new) >= 1))
        metrics['seamSampleJump'] = float(abs(new[center] - new[center - 1]))
        combined = np.concatenate([old[:10 * RATE], new[:10 * RATE]]) * preview_gain
        # Short envelopes only at the audition edit, not production loop seams.
        combined[10 * RATE - 220:10 * RATE] *= np.linspace(1, 0, 220)
        combined[10 * RATE:10 * RATE + 220] *= np.linspace(0, 1, 220)
        combined[-13230:] *= np.linspace(1, 0, 13230)
        wav(OUT / f'柔和-{track}对比.wav', combined)
        waveplot(new, [seam], '柔和-' + track + '-循环')
        waveplot(combined, [10], '柔和-' + track + '对比')
        report['tracks'][track] = metrics
    dynamic = results['new', 'dynamic']
    timing = metadata['new', 'dynamic']
    wav(OUT / '柔和-全程R3.wav', dynamic * preview_gain)
    waveplot(dynamic, [timing['yellow'], timing['red'], timing['red'] + .6], '柔和-全程R3')
    report['dynamic'] = {'yellow': timing['yellow'], 'red': timing['red'],
                         'alarmEvents': timing['alarmEvents'],
                         'runtimePeakDBFS': db(np.max(np.abs(dynamic))),
                         'clippedSamples': int(np.sum(np.abs(dynamic) >= 1))}
    (OUT / '音色核验.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('BGM3 AUDIO ' + json.dumps(report, ensure_ascii=False), flush=True)
    assert not errors
    for metrics in report['tracks'].values():
        for label in ['audition10s', 'full60s']:
            assert metrics[label]['centroidReduction'] >= .25, metrics
            assert metrics[label]['above4kReduction'] >= .4, metrics
        assert abs(metrics['lufsDifference']) <= 1, metrics
        assert metrics['seamPeakDifferenceDB'] < 3 and not metrics['clippedSamples']
    assert not report['dynamic']['alarmEvents']


if __name__ == '__main__':
    main()
