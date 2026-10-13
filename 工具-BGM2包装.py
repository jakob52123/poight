"""Package 30-second red-health comparisons locally; never overwrite previous auditions."""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "验收记录/战斗音乐/BGM2试听"
OUT = ROOT.parent / "BGM试听"
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"
MODES = {"R1": "只留报警 · 每对1.2秒 · 音乐淡出",
         "R2": "简短提示 · 仅进入时响2对 · 保留B（默认）",
         "R3": "不要报警 · 仅留B低音和鼓"}
STAGES = [("绿血", "80% · C 跃步电光", "轻快跳跃", "#96f1c7"),
          ("黄血", "40% · B 暗棱警报", "完整B / 紧张压迫", "#f4cb48"),
          ("红血", "15% · 红血简化", "", "#ff8a88")]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    title, small = ImageFont.truetype(FONT, 50), ImageFont.truetype(FONT, 28)
    receipts = []
    for mode, description in MODES.items():
        frames = []
        for stage, name, detail, color in STAGES:
            image = Image.open(SOURCE / f"{stage}-实机.png").convert("RGBA")
            assert image.size == (1920, 1080)
            overlay = Image.new("RGBA", image.size)
            draw = ImageDraw.Draw(overlay)
            draw.rounded_rectangle((250, 125, 1670, 310), radius=12, fill=(12, 23, 40, 235),
                                   outline=color, width=3)
            draw.text((290, 142), f"{mode} · {name}", font=title, fill=color)
            draw.text((295, 214), description if stage == "红血" else detail,
                      font=small, fill="#f5e9d4")
            draw.text((295, 259), "0–10秒 C → 10–20秒 B → 20–30秒红血 / 下一小节切换",
                      font=small, fill="#f5e9d4")
            frame = OUT / f"红血-{mode}-{stage}.png"
            Image.alpha_composite(image, overlay).convert("RGB").save(frame)
            frames.append(frame)
        wav = OUT / f"红血-{mode}.wav"
        shutil.copy2(SOURCE / wav.name, wav)
        video = OUT / f"红血-{mode}.mp4"
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        for frame in frames:
            command += ["-loop", "1", "-framerate", "24", "-t", "10", "-i", str(frame)]
        command += ["-i", str(wav), "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
                    "-map", "[v]", "-map", "3:a", "-t", "30", "-c:v", "libx264",
                    "-preset", "medium", "-tune", "stillimage", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-af", "volume=-1dB", "-movflags", "+faststart",
                    "-metadata", f"title=POIGHT - 红血 {mode}", str(video)]
        subprocess.run(command, check=True, timeout=300)
        metadata = json.loads(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)]))
        v = next(s for s in metadata["streams"] if s["codec_type"] == "video")
        a = next(s for s in metadata["streams"] if s["codec_type"] == "audio")
        pcm = np.frombuffer(subprocess.check_output([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video),
            "-vn", "-f", "f32le", "-acodec", "pcm_f32le", "pipe:1"]), dtype="<f4")
        receipt = {"mode": mode, "width": v["width"], "height": v["height"],
                   "seconds": float(metadata["format"]["duration"]), "audioCodec": a["codec_name"],
                   "audioBitrate": a["bit_rate"],
                   "decodedPeakDBFS": float(20 * np.log10(np.max(np.abs(pcm)))),
                   "clippedSamples": int(np.sum(np.abs(pcm) >= 1))}
        assert (receipt["width"], receipt["height"]) == (1920, 1080)
        assert receipt["seconds"] == 30 and receipt["audioCodec"] == "aac"
        assert receipt["decodedPeakDBFS"] <= -1 and receipt["clippedSamples"] == 0
        shutil.copy2(SOURCE / f"红血-{mode}-波形.png", OUT / f"红血-{mode}-波形.png")
        receipts.append(receipt)
        print("BGM2 VIDEO " + json.dumps(receipt, ensure_ascii=False), flush=True)
    shutil.copy2(SOURCE / "音频核验.json", OUT / "红血-音频核验.json")
    (OUT / "红血-视频核验.json").write_text(json.dumps(receipts, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
