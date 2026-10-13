"""Local ffmpeg packaging, shared audition gain, decoded AAC peak verification."""
import importlib
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / '验收记录/战斗音乐/BGM3试听'
OUT = ROOT.parent / 'BGM试听'
FONT = '/System/Library/Fonts/STHeiti Medium.ttc'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    audio = importlib.import_module('工具-BGM3试听')
    measured = json.loads((SOURCE / '音色核验.json').read_text())
    lufs_receipts = []
    for track in 'CB':
        for version in ['old', 'new']:
            path = SOURCE / f'{version}-{track}-runtime.wav'
            reference, portable = audio.lufs(path), audio.integrated_lufs(path)
            difference = abs(reference - portable)
            assert difference <= .1
            assert abs(reference - measured['tracks'][track][version + 'LUFS']) <= .1
            lufs_receipts.append({'track': track, 'version': version, 'ffmpegLUFS': reference,
                                  'portableLUFS': portable, 'difference': difference})
    (OUT / '柔和-LUFS复核.json').write_text(json.dumps(lufs_receipts, ensure_ascii=False,
                                                  indent=2) + '\n')
    print('BGM3 LUFS ' + json.dumps(lufs_receipts), flush=True)
    title = ImageFont.truetype(FONT, 50)
    small = ImageFont.truetype(FONT, 28)
    specs = {
        '柔和-C对比': [('绿血', '旧 C · 9f9c0ac', '0–10秒 · 原音色'),
                    ('绿血', '新 C · 跃步电光', '10–20秒 · 50%方波 / 低通 / 柔和起音')],
        '柔和-B对比': [('黄血', '旧 B · 9f9c0ac', '0–10秒 · 原窄脉冲音色'),
                    ('黄血', '新 B · 暗棱警报', '10–20秒 · 50%方波 / 暖色混音')],
        '柔和-全程R3': [('绿血', '绿血 80% · 柔和 C', '0–10秒 · 跃步电光'),
                     ('黄血', '黄血 40% · 柔和 B', '10–20秒 · 暗棱警报'),
                     ('红血', '红血 15% · 默认 R3', '20–30秒 · 只留低音和鼓 / 无报警')],
    }
    receipts = []
    for name, stages in specs.items():
        command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y']
        for index, (stage, text, detail) in enumerate(stages):
            image = Image.open(SOURCE / f'{stage}-实机.png').convert('RGBA')
            assert image.size == (1920, 1080)
            overlay = Image.new('RGBA', image.size)
            draw = ImageDraw.Draw(overlay)
            color = {'绿血': '#96f1c7', '黄血': '#f4cb48', '红血': '#ff8a88'}[stage]
            draw.rounded_rectangle((250, 125, 1670, 310), radius=12, fill=(12, 23, 40, 235),
                                   outline=color, width=3)
            draw.text((290, 142), text, font=title, fill=color)
            draw.text((295, 220), detail, font=small, fill='#f5e9d4')
            draw.text((295, 263), '原创代码合成 · 同段/同母带增益 · 旋律与节奏保持',
                      font=small, fill='#f5e9d4')
            frame = OUT / f'{name}-{index + 1}.png'
            Image.alpha_composite(image, overlay).convert('RGB').save(frame)
            command += ['-loop', '1', '-framerate', '24', '-t', '10', '-i', str(frame)]
        duration = 10 * len(stages)
        inputs = ''.join(f'[{i}:v]' for i in range(len(stages)))
        video = OUT / f'{name}.mp4'
        wav = OUT / f'{name}.wav'
        shutil.copy2(SOURCE / wav.name, wav)
        command += ['-i', str(wav), '-filter_complex',
                    inputs + f'concat=n={len(stages)}:v=1:a=0[v]',
                    '-map', '[v]', '-map', f'{len(stages)}:a', '-t', str(duration),
                    '-c:v', 'libx264', '-preset', 'medium', '-tune', 'stillimage', '-crf', '18',
                    '-pix_fmt', 'yuv420p', '-threads', '2', '-c:a', 'aac', '-b:a', '192k',
                    '-movflags', '+faststart', '-metadata', f'title=POIGHT - {name}', str(video)]
        subprocess.run(command, check=True, timeout=300)
        metadata = json.loads(subprocess.check_output([
            'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(video)]))
        v = next(s for s in metadata['streams'] if s['codec_type'] == 'video')
        a = next(s for s in metadata['streams'] if s['codec_type'] == 'audio')
        pcm = np.frombuffer(subprocess.check_output([
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(video), '-vn',
            '-f', 'f32le', '-acodec', 'pcm_f32le', 'pipe:1']), dtype='<f4')
        receipt = {'name': name, 'width': v['width'], 'height': v['height'],
                   'seconds': float(metadata['format']['duration']), 'audioCodec': a['codec_name'],
                   'audioBitrate': a['bit_rate'],
                   'decodedPeakDBFS': float(20 * np.log10(np.max(np.abs(pcm)))),
                   'clippedSamples': int(np.sum(np.abs(pcm) >= 1))}
        assert (receipt['width'], receipt['height']) == (1920, 1080)
        assert receipt['seconds'] == duration and receipt['audioCodec'] == 'aac'
        assert receipt['decodedPeakDBFS'] <= -1 and receipt['clippedSamples'] == 0
        shutil.copy2(SOURCE / f'{name}-波形.png', OUT / f'{name}-波形.png')
        receipts.append(receipt)
        print('BGM3 VIDEO ' + json.dumps(receipt, ensure_ascii=False), flush=True)
    for track in 'BC':
        shutil.copy2(SOURCE / f'柔和-{track}-循环-波形.png', OUT / f'柔和-{track}-循环-波形.png')
    shutil.copy2(SOURCE / '音色核验.json', OUT / '柔和-音色核验.json')
    (OUT / '柔和-视频核验.json').write_text(json.dumps(receipts, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
