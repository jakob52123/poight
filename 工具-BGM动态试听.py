"""Jade-only dynamic audition using the production layer/envelope/transport helpers."""
import base64
import json
import math
import os
import time
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/战斗音乐/动态试听"
OUT.mkdir(parents=True, exist_ok=True)
URL = os.environ["POIGHT_TEST_URL"].rstrip("/")
RENDER = """async () => {
  const {buffer,...timing} = await PoightMusicScore.renderDynamic(45,1);
  const bytes=new Uint8Array(buffer.getChannelData(0).buffer), chunks=[];
  for(let i=0;i<bytes.length;i+=16384)
    chunks.push(String.fromCharCode(...bytes.subarray(i,i+16384)));
  return {...timing,rate:buffer.sampleRate,pcm:btoa(chunks.join(''))};
}"""


def call(page, method, value=None):
    return page.evaluate("([m,v])=>window.__waterTest[m](v)", [method, value])


def db(value):
    return 20 * math.log10(max(float(value), 1e-12))


def waveform(samples, rate, boundary, name):
    image = Image.new("RGB", (1600, 800), "#101c30")
    draw = ImageDraw.Draw(image)
    draw.text((25, 15), f"DYNAMIC {name}  t={boundary:.6f}s | 162 BPM / 600ms crossfade",
              fill="white")
    for row, span in enumerate([.65, .005]):
        top, bottom = 70 + row * 365, 390 + row * 365
        mid, left, right = (top + bottom) / 2, 70, 1530
        part = samples[round((boundary - span) * rate):round((boundary + span) * rate)]
        scale = (bottom - top) * .45 / max(float(np.max(np.abs(part))), .01)
        draw.line((left, mid, right, mid), fill="#52637a")
        for x in range(right - left):
            a = int(x * len(part) / (right - left))
            b = max(a + 1, int((x + 1) * len(part) / (right - left)))
            vals = part[a:b]
            draw.line((left + x, mid - float(vals.max()) * scale,
                       left + x, mid - float(vals.min()) * scale), fill="#69dfcd")
        if len(part) < right - left:
            draw.line([(left + i * (right - left) / (len(part) - 1), mid - float(v) * scale)
                       for i, v in enumerate(part)], fill="#69dfcd")
        draw.line((800, top, 800, bottom), fill="#ff8a88", width=2)
        draw.text((left, top - 20), f"+/- {span * 1000:g} ms, auto-scaled", fill="white")
    image.save(OUT / f"{name}-波形.png")


def main():
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(URL + "/?test=1&music=dynamic")
        for _ in range(800):
            if page.evaluate("()=>window.__waterTest?.snapshot().artReady"):
                break
            time.sleep(.025)
        else:
            raise TimeoutError("artReady")
        catalog = call(page, "catalog")
        roster = {c["id"]: c for c in catalog["roster"]}
        profile = {**call(page, "snapshot")["profile"], "map": "arena-formal",
                   "player": 25, "enemy": 7, "playerMoves": roster[25]["defaultMoves"],
                   "enemyMoves": roster[7]["defaultMoves"]}
        assert call(page, "select", profile)
        call(page, "reset", True)
        bounds = call(page, "snapshot")["environment"]["bounds"]
        cx, cy = (bounds["left"] + bounds["right"]) / 2, (bounds["top"] + bounds["bottom"]) / 2
        maximum = call(page, "snapshot")["player"]["maxHP"]
        for name, ratio in [("绿血", .8), ("黄血", .4), ("红血", .15)]:
            call(page, "arrange", {"ai": False, "player": {"hp": maximum * ratio,
                                   "x": cx - 110, "y": cy + 40},
                                   "enemy": {"x": cx + 110, "y": cy + 40, "a": 3.14159}})
            call(page, "step", .02)
            page.screenshot(path=OUT / f"{name}-实机.png")
        result = page.evaluate(RENDER)
        raw = np.frombuffer(base64.b64decode(result.pop("pcm")), dtype="<f4").copy()
        assert len(raw) == 44100 * 45 and np.isfinite(raw).all()
        raw_peak = float(np.max(np.abs(raw)))
        samples = raw * (10 ** (-1.5 / 20) / raw_peak)
        pcm = np.round(samples * 32767).astype("<i2")
        with wave.open(str(OUT / "动态切换.wav"), "wb") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(44100)
            wav.writeframes(np.column_stack([pcm, pcm]).tobytes())
        metrics = {**result, "seconds": 45, "runtime100PeakDBFS": db(raw_peak),
                   "previewPeakDBFS": db(np.max(np.abs(pcm.astype(float))) / 32768),
                   "clippedSamples": int(np.sum(np.abs(pcm.astype(int)) >= 32767)),
                   "jsErrors": errors, "healthChangeSeconds": [15, 30]}
        for key, label in [("yellow", "C到B"), ("red", "红血报警")]:
            center = round(result[key] * 44100)
            metrics[key + "SampleJump"] = float(abs(samples[center] - samples[center - 1]))
            assert metrics[key + "SampleJump"] < .02, (key, metrics)
            waveform(samples, 44100, result[key], label)
        waveform(samples, 44100, result["yellow"] + result["crossfade"], "淡化结束")
        (OUT / "音频核验.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n")
        assert raw_peak < 10 ** (-1 / 20) and metrics["previewPeakDBFS"] <= -1
        assert not metrics["clippedSamples"] and not errors
        print("DYNAMIC AUDIO " + json.dumps(metrics, ensure_ascii=False), flush=True)
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
