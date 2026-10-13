"""Render production red-health helpers with Chromium OfflineAudioContext (serial)."""
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
OUT = ROOT / "验收记录/战斗音乐/BGM2试听"
OUT.mkdir(parents=True, exist_ok=True)
URL = os.environ["POIGHT_TEST_URL"].rstrip("/")
RENDER = """async mode => {
  const {buffer,...timing} = await PoightMusicScore.renderDynamic(30,1,mode);
  const bytes=new Uint8Array(buffer.getChannelData(0).buffer), chunks=[];
  for(let i=0;i<bytes.length;i+=16384)
    chunks.push(String.fromCharCode(...bytes.subarray(i,i+16384)));
  return {...timing,rate:buffer.sampleRate,pcm:btoa(chunks.join(''))};
}"""


def call(page, method, value=None):
    return page.evaluate("([m,v])=>window.__waterTest[m](v)", [method, value])


def db(value):
    return 20 * math.log10(max(float(value), 1e-12))


def waveform(samples, boundary, mode):
    image = Image.new("RGB", (1600, 1080), "#101c30")
    draw = ImageDraw.Draw(image)
    draw.text((30, 15), f"BGM2 {mode.upper()} | RED at {boundary:.6f}s | 162 BPM", fill="white")
    for row, (a, b, label) in enumerate([
        (0, 30, "30 seconds: C -> B -> RED"),
        (boundary - .1, boundary + 2.5, "RED entry / fade / alarm pairs"),
        (boundary - .005, boundary + .005, "RED boundary +/- 5ms"),
    ]):
        top, bottom = 70 + row * 335, 350 + row * 335
        mid, left, right = (top + bottom) / 2, 70, 1530
        part = samples[round(a * 44100):round(b * 44100)]
        scale = (bottom - top) * .45 / max(float(np.max(np.abs(part))), .01)
        draw.text((left, top - 20), label + " (auto-scaled)", fill="white")
        draw.line((left, mid, right, mid), fill="#52637a")
        for x in range(right - left):
            i = int(x * len(part) / (right - left))
            j = max(i + 1, int((x + 1) * len(part) / (right - left)))
            vals = part[i:j]
            draw.line((left + x, mid - float(vals.max()) * scale,
                       left + x, mid - float(vals.min()) * scale), fill="#69dfcd")
        if len(part) < right - left:
            draw.line([(left + i * (right - left) / (len(part) - 1), mid - float(v) * scale)
                       for i, v in enumerate(part)], fill="#69dfcd")
        x = left + (boundary - a) / (b - a) * (right - left)
        draw.line((x, top, x, bottom), fill="#ff8a88", width=2)
    image.save(OUT / f"红血-{mode.upper()}-波形.png")


def main():
    errors, reports = [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(URL + "/?test=1&music=off")
        for _ in range(800):
            if page.evaluate("()=>window.__waterTest?.snapshot().artReady"):
                break
            time.sleep(.025)
        else:
            raise TimeoutError("artReady")
        roster = {c["id"]: c for c in call(page, "catalog")["roster"]}
        profile = {**call(page, "snapshot")["profile"], "map": "arena-formal",
                   "player": 25, "enemy": 7, "playerMoves": roster[25]["defaultMoves"],
                   "enemyMoves": roster[7]["defaultMoves"]}
        assert call(page, "select", profile)
        call(page, "reset", True)
        state = call(page, "snapshot")
        bounds, maximum = state["environment"]["bounds"], state["player"]["maxHP"]
        cx, cy = (bounds["left"] + bounds["right"]) / 2, (bounds["top"] + bounds["bottom"]) / 2
        for name, ratio in [("绿血", .8), ("黄血", .4), ("红血", .15)]:
            call(page, "arrange", {"ai": False, "player": {"hp": maximum * ratio,
                                   "x": cx - 110, "y": cy + 40},
                                   "enemy": {"x": cx + 110, "y": cy + 40, "a": 3.14159}})
            call(page, "step", .02)
            page.screenshot(path=OUT / f"{name}-实机.png")
        rendered = []
        for mode in ["r1", "r2", "r3"]:
            result = page.evaluate(RENDER, mode)
            raw = np.frombuffer(base64.b64decode(result.pop("pcm")), dtype="<f4").copy()
            assert len(raw) == 44100 * 30 and np.isfinite(raw).all()
            rendered.append((mode, result, raw))
        reference = rendered[0][2][:20 * 44100]
        differences = {mode: float(np.max(np.abs(raw[:20 * 44100] - reference)))
                       for mode, _, raw in rendered}
        print("GREEN/YELLOW MAX DIFFERENCE " + json.dumps(differences), flush=True)
        assert all(value < 1e-6 for value in differences.values()), differences
        shared_peak = max(float(np.max(np.abs(raw))) for _, _, raw in rendered)
        for mode, result, raw in rendered:
            raw_peak = float(np.max(np.abs(raw)))
            samples = raw * (10 ** (-1.5 / 20) / shared_peak)
            pcm = np.round(samples * 32767).astype("<i2")
            with wave.open(str(OUT / f"红血-{mode.upper()}.wav"), "wb") as wav:
                wav.setnchannels(2)
                wav.setsampwidth(2)
                wav.setframerate(44100)
                wav.writeframes(np.column_stack([pcm, pcm]).tobytes())
            metrics = {**result, "seconds": 30, "runtime100PeakDBFS": db(raw_peak),
                       "previewPeakDBFS": db(np.max(np.abs(pcm.astype(float))) / 32768),
                       "clippedSamples": int(np.sum(np.abs(pcm.astype(int)) >= 32767)),
                       "jsErrors": errors, "healthChangeSeconds": [10, 20],
                       "greenYellowMaxDifference": differences[mode], "sharedMasterPeak": shared_peak}
            for key, boundary in [("yellow", result["yellow"]), ("red", result["red"]),
                                  ("redFadeEnd", result["red"] + (.8 if mode == "r1" else .6))]:
                center = round(boundary * 44100)
                metrics[key + "SampleJump"] = float(abs(samples[center] - samples[center - 1]))
                assert metrics[key + "SampleJump"] < .02, (key, metrics)
            assert raw_peak < 10 ** (-1 / 20) and metrics["previewPeakDBFS"] <= -1
            assert not metrics["clippedSamples"] and not errors
            if mode == "r2":
                assert len(result["alarmEvents"]) == 4
            if mode == "r3":
                assert not result["alarmEvents"]
            waveform(samples, result["red"], mode)
            reports.append(metrics)
            print("BGM2 AUDIO " + json.dumps(metrics, ensure_ascii=False), flush=True)
        context.close()
        browser.close()
    (OUT / "音频核验.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
