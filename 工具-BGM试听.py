"""Run via tools/远程执行.sh on Jade: OfflineAudioContext WAV + real game shots + seam audit."""
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
OUT = ROOT / "验收记录/战斗音乐/试听"
OUT.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8941/").rstrip("/")
RENDER = """async id => {
  const {buffer,seam,score} = await PoightMusicScore.render(id,60,1);
  const mono=buffer.getChannelData(0), bytes=new Uint8Array(mono.buffer);
  let base64='', chunks=[];
  // Convert once, without spreading multi-megabyte arrays onto the call stack.
  for(let i=0;i<bytes.length;i+=16384)chunks.push(String.fromCharCode(...bytes.subarray(i,i+16384)));
  base64=btoa(chunks.join(''));
  return {pcm:base64,seam,rate:buffer.sampleRate,score};
}"""


def call(page, method, value=None):
    return page.evaluate("([m,v])=>window.__waterTest[m](v)", [method, value])


def ready(page, track):
    page.goto(URL + "/?test=1&music=" + track)
    for _ in range(800):
        if page.evaluate("()=>window.__waterTest?.snapshot().artReady"):
            return
        time.sleep(.025)
    raise TimeoutError("artReady")


def db(value):
    return 20 * math.log10(max(float(value), 1e-12))


def waveform(samples, rate, seam, track, metrics):
    image = Image.new("RGB", (1600, 800), "#101c30")
    draw = ImageDraw.Draw(image)
    draw.text((25, 15), f"{track} LOOP SEAM  t={seam:.6f}s  |  "
              f"50ms peak difference {metrics['seamPeakDifferenceDB']:.3f} dB", fill="white")
    for row, window in enumerate([.05, .005]):
        top, bottom = 70 + row * 365, 390 + row * 365
        mid = (top + bottom) / 2
        left, right = 70, 1530
        start, end = round((seam - window) * rate), round((seam + window) * rate)
        part = samples[start:end]
        scale = (bottom - top) * .45 / max(np.max(np.abs(part)), .01)
        draw.line((left, mid, right, mid), fill="#52637a")
        for x in range(right - left):
            a = int(x * len(part) / (right - left))
            b = max(a + 1, int((x + 1) * len(part) / (right - left)))
            vals = part[a:b]
            draw.line((left + x, mid - float(vals.max()) * scale,
                       left + x, mid - float(vals.min()) * scale), fill="#69dfcd")
        if len(part) < right - left:
            draw.line([(left + i * (right - left) / (len(part) - 1),
                        mid - float(value) * scale) for i, value in enumerate(part)],
                      fill="#69dfcd", width=1)
        center = (left + right) / 2
        draw.line((center, top, center, bottom), fill="#ff8a88", width=2)
        draw.text((left, top - 20), f"+/- {window * 1000:g} ms, auto-scaled, no crossfade",
                  fill="#d7e4f1")
    image.save(OUT / f"{track}-接缝波形.png")


def main():
    metrics_all, errors = {}, []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        for index, track in enumerate("ABC"):
            ready(page, track)
            catalog = call(page, "catalog")
            roster = {c["id"]: c for c in catalog["roster"]}
            player, enemy = [(6, 9), (94, 65), (25, 7)][index]
            profile = {**call(page, "snapshot")["profile"], "map": "arena-formal",
                       "player": player, "enemy": enemy,
                       "playerMoves": roster[player]["defaultMoves"],
                       "enemyMoves": roster[enemy]["defaultMoves"]}
            assert call(page, "select", profile)
            bounds = call(page, "snapshot")["environment"]["bounds"]
            cx = (bounds["left"] + bounds["right"]) / 2
            cy = (bounds["top"] + bounds["bottom"]) / 2
            call(page, "arrange", {"ai": False, "player": {"x": cx - 110, "y": cy + 40},
                                   "enemy": {"x": cx + 110, "y": cy + 40, "a": 3.14159}})
            call(page, "step", .05)
            page.screenshot(path=OUT / f"{track}-实机.png")
            result = page.evaluate(RENDER, track)
            raw = np.frombuffer(base64.b64decode(result.pop("pcm")), dtype="<f4").copy()
            assert len(raw) == result["rate"] * 60 and np.isfinite(raw).all()
            raw_peak = float(np.max(np.abs(raw)))
            # Auditions only: linear mastering to -1.5 dBFS. Runtime mix remains unchanged.
            samples = raw * (10 ** (-1.5 / 20) / raw_peak)
            pcm = np.round(samples * 32767).astype("<i2")
            stereo = np.column_stack([pcm, pcm])
            with wave.open(str(OUT / f"{track}.wav"), "wb") as wav:
                wav.setnchannels(2)
                wav.setsampwidth(2)
                wav.setframerate(result["rate"])
                wav.writeframes(stereo.tobytes())
            seam = result["seam"]
            center, span = round(seam * result["rate"]), round(.05 * result["rate"])
            before = float(np.max(np.abs(samples[center-span:center])))
            after = float(np.max(np.abs(samples[center:center+span])))
            metrics = {"seconds": 60, "seamSeconds": seam, "runtime100PeakDBFS": db(raw_peak),
                       "previewPeakDBFS": db(np.max(np.abs(pcm.astype(float))) / 32768),
                       "rmsDBFS": db(np.sqrt(np.mean(samples ** 2))),
                       "before50msPeakDBFS": db(before), "after50msPeakDBFS": db(after),
                       "seamPeakDifferenceDB": abs(db(before)-db(after)),
                       "seamSampleJump": float(abs(samples[center]-samples[center-1])),
                       "clippedSamples": int(np.sum(np.abs(pcm.astype(int)) >= 32767)),
                       "bpm": result["score"]["bpm"], "introBars": result["score"]["introBars"],
                       "loopBars": result["score"]["loopBars"]}
            waveform(samples, result["rate"], seam, track, metrics)
            (OUT / f"{track}-谱面.json").write_text(json.dumps(result["score"], ensure_ascii=False,
                                                         indent=2) + "\n")
            metrics_all[track] = metrics
            print(track, json.dumps(metrics, ensure_ascii=False), flush=True)
        context.close()
        browser.close()
    (OUT / "音频核验.json").write_text(json.dumps({"tracks": metrics_all, "jsErrors": errors},
                                            ensure_ascii=False, indent=2) + "\n")
    assert not errors, errors
    for track, m in metrics_all.items():
        assert m["seamPeakDifferenceDB"] < 3, (track, m)
        assert m["runtime100PeakDBFS"] <= -1 and m["previewPeakDBFS"] <= -1, (track, m)
        assert m["clippedSamples"] == 0, (track, m)
    print("AUDIO: 3 tracks, 60 seconds each, 0 clipping, 0 JS errors", flush=True)


if __name__ == "__main__":
    main()
