"""Local ffmpeg packaging of the Jade dynamic audition; preserve previous A/B/C files."""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "验收记录/战斗音乐/动态试听"
OUT = ROOT.parent / "BGM试听"
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"
STAGES = [("绿血", "80% · C 跃步电光", "轻快跳跃 / 血量 >50%", "#96f1c7"),
          ("黄血", "40% · B 暗棱警报", "紧张压迫 / 20%–50%", "#f4cb48"),
          ("红血", "15% · B + 原创低血量报警", "叮—嘟 / 血量 ≤20%", "#ff8a88")]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    title, small = ImageFont.truetype(FONT, 56), ImageFont.truetype(FONT, 30)
    for index, (stage, name, detail, color) in enumerate(STAGES):
        image = Image.open(SOURCE / f"{stage}-实机.png").convert("RGBA")
        assert image.size == (1920, 1080)
        overlay = Image.new("RGBA", image.size)
        draw = ImageDraw.Draw(overlay)
        draw.rounded_rectangle((300, 125, 1620, 290), radius=12, fill=(12, 23, 40, 235),
                               outline=color, width=3)
        draw.text((340, 145), name, font=title, fill=color)
        draw.text((345, 225), detail + " / 162 BPM / 下一小节切换、0.6秒淡化", font=small,
                  fill="#f5e9d4")
        frame = OUT / f"动态切换-{stage}.png"
        Image.alpha_composite(image, overlay).convert("RGB").save(frame)
    shutil.copy2(SOURCE / "动态切换.wav", OUT / "动态切换.wav")
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for stage, *_ in STAGES:
        command += ["-loop", "1", "-framerate", "24", "-t", "15", "-i",
                    str(OUT / f"动态切换-{stage}.png")]
    command += ["-i", str(OUT / "动态切换.wav"), "-filter_complex",
                "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]", "-map", "[v]", "-map", "3:a",
                "-t", "45", "-c:v", "libx264", "-preset", "medium", "-tune", "stillimage",
                "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                "-af", "volume=-1dB", "-movflags", "+faststart",
                "-metadata", "title=POIGHT - 动态血量切曲试听", str(OUT / "动态切换.mp4")]
    subprocess.run(command, check=True, timeout=300)
    metadata = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json",
        str(OUT / "动态切换.mp4")]))
    video = next(s for s in metadata["streams"] if s["codec_type"] == "video")
    audio = next(s for s in metadata["streams"] if s["codec_type"] == "audio")
    pcm = np.frombuffer(subprocess.check_output([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(OUT / "动态切换.mp4"),
        "-vn", "-f", "f32le", "-acodec", "pcm_f32le", "pipe:1"]), dtype="<f4")
    receipt = {"width": video["width"], "height": video["height"],
               "seconds": float(metadata["format"]["duration"]), "audioCodec": audio["codec_name"],
               "audioBitrate": audio["bit_rate"],
               "decodedPeakDBFS": float(20 * np.log10(np.max(np.abs(pcm)))),
               "clippedSamples": int(np.sum(np.abs(pcm) >= 1))}
    assert (receipt["width"], receipt["height"]) == (1920, 1080)
    assert receipt["seconds"] == 45 and receipt["audioCodec"] == "aac"
    assert receipt["decodedPeakDBFS"] <= -1 and receipt["clippedSamples"] == 0
    for name in ["C到B-波形.png", "红血报警-波形.png", "淡化结束-波形.png", "音频核验.json"]:
        shutil.copy2(SOURCE / name, OUT / ("动态切换-" + name))
    (OUT / "动态切换-视频核验.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print("DYNAMIC VIDEO " + json.dumps(receipt, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
