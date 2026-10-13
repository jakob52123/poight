"""Local-only ffmpeg packaging; no browser. Final previews go to ../BGM试听/."""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "验收记录/战斗音乐/试听"
OUT = ROOT.parent / "BGM试听"
OUT.mkdir(parents=True, exist_ok=True)
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"
TRACKS = {"A": ("赤焰交锋", "热血正面对决", 168, "#ffb077"),
          "B": ("暗棱警报", "紧张压迫追逐", 174, "#c7b1ff"),
          "C": ("跃步电光", "轻快跳跃切磋", 162, "#96f1c7")}


def main():
    overview = Image.new("RGB", (1920, 1080), "#0c1728")
    draw = ImageDraw.Draw(overview)
    title = ImageFont.truetype(FONT, 64)
    small = ImageFont.truetype(FONT, 30)
    draw.text((64, 40), "POIGHT · 三首原创战斗曲试听", font=title, fill="#f7dfae")
    draw.text((64, 130), "纯代码合成 / 3/4 拍 / 2 小节前奏 + 48 小节循环 / 每首 60 秒",
              font=small, fill="#cad7e7")
    proof = {}
    for index, (track, (name, mood, bpm, color)) in enumerate(TRACKS.items()):
        image = Image.open(SOURCE / f"{track}-实机.png").convert("RGBA")
        assert image.size == (1920, 1080)
        overlay = Image.new("RGBA", image.size)
        pen = ImageDraw.Draw(overlay)
        pen.rounded_rectangle((380, 130, 1540, 290), radius=12, fill=(12, 23, 40, 235),
                              outline=color, width=3)
        pen.text((430, 150), f"{track} · {name}", font=title, fill=color)
        pen.text((435, 232), f"{mood}  /  {bpm} BPM  /  原创芯片合成", font=small,
                 fill="#f5e9d4")
        image = Image.alpha_composite(image, overlay).convert("RGB")
        frame = OUT / f"{track}-画面.png"
        image.save(frame)
        shutil.copy2(SOURCE / f"{track}.wav", OUT / f"{track}.wav")
        shutil.copy2(SOURCE / f"{track}-接缝波形.png", OUT / f"{track}-接缝波形.png")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-loop", "1", "-framerate", "24", "-i", str(frame),
                        "-i", str(OUT / f"{track}.wav"), "-t", "60",
                        "-c:v", "libx264", "-preset", "medium", "-tune", "stillimage",
                        "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                        "-af", "volume=-1dB", "-movflags", "+faststart",
                        "-metadata", f"title={track} - {name}", str(OUT / f"{track}.mp4")],
                       check=True, timeout=300)
        metadata = json.loads(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json",
            str(OUT / f"{track}.mp4")]))
        video = next(s for s in metadata["streams"] if s["codec_type"] == "video")
        audio = next(s for s in metadata["streams"] if s["codec_type"] == "audio")
        decoded = subprocess.check_output(["ffmpeg", "-hide_banner", "-loglevel", "error",
                                           "-i", str(OUT / f"{track}.mp4"), "-vn",
                                           "-f", "f32le", "-acodec", "pcm_f32le", "pipe:1"])
        pcm = np.frombuffer(decoded, dtype="<f4")
        peak = float(np.max(np.abs(pcm)))
        receipt = {"width": video["width"], "height": video["height"],
                   "seconds": float(metadata["format"]["duration"]),
                   "audioCodec": audio["codec_name"], "audioBitrate": audio["bit_rate"],
                   "decodedPeakDBFS": float(20 * np.log10(peak)),
                   "clippedSamples": int(np.sum(np.abs(pcm) >= 1))}
        assert (receipt["width"], receipt["height"]) == (1920, 1080)
        assert receipt["seconds"] == 60 and receipt["audioCodec"] == "aac"
        assert receipt["decodedPeakDBFS"] <= -1 and receipt["clippedSamples"] == 0
        proof[track] = receipt
        print(track, json.dumps(receipt, ensure_ascii=False), flush=True)
        x = 60 + index * 620
        draw.rounded_rectangle((x, 230, x + 590, 920), radius=16, outline=color, width=3,
                               fill="#14233a")
        thumb = Image.open(SOURCE / f"{track}-实机.png").convert("RGB")
        thumb.thumbnail((570, 400), Image.Resampling.LANCZOS)
        overview.paste(thumb, (x + 10, 320))
        draw.text((x + 26, 245), f"{track} · {name}", font=ImageFont.truetype(FONT, 46), fill=color)
        draw.text((x + 26, 700), mood, font=ImageFont.truetype(FONT, 40), fill="#f5e9d4")
        draw.text((x + 26, 780), f"{bpm} BPM · 点击 {track}.mp4 试听", font=small, fill="#c5d7e5")
        draw.text((x + 26, 835), "含完整循环接缝", font=small, fill="#c5d7e5")
    overview.save(OUT / "总览.png")
    shutil.copy2(SOURCE / "音频核验.json", OUT / "音频核验.json")
    (OUT / "视频核验.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n")
    print("VIDEO: 3 x 1920x1080 / 60s / AAC 192k, 0 clipping", flush=True)


if __name__ == "__main__":
    main()
