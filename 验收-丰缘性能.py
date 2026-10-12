"""Identical 60-second real RAF/gameplay benchmark; use the task's assigned port."""
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/丰缘全图"
OUT.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8840/")
PORT = str(urlparse(URL).port or 8840)


def wait(page, expr):
    for _ in range(1200):
        if page.evaluate(expr):
            return
        page.wait_for_timeout(50)
    raise AssertionError(expr)


def frozen_baseline():
    # Use the read-only frozen source export supplied with W2 (copied into this task).
    # Never recursively clone ROOT/M into its own acceptance directory.
    target = OUT / 'M-fd1eb0f'
    expected = 'b58057af941f7f216dacc1c6da89dc335c5483b2613023e428e556462c41be16'
    if not target.exists():
        subprocess.run(['cp', '-cR', str(ROOT.parent / 'W2' / '验收记录/丰缘全图/M-fd1eb0f'), str(target)], check=True)
        if (target / '.git').exists():
            shutil.rmtree(target / '.git')
        archive = OUT / 'baseline.tar'
        with archive.open('wb') as file:
            subprocess.run(['git', 'archive', 'fd1eb0f'], cwd=ROOT, stdout=file, check=True)
        subprocess.run(['tar', '-xf', str(archive), '-C', str(target)], check=True)
        archive.unlink()
        with (OUT / 'baseline-build.log').open('w') as log:
            for script in ('素材/绿宝石场景/构建丰缘.py', '构建完整版.py'):
                subprocess.run([sys.executable, script], cwd=target, stdout=log, stderr=log, check=True)
    assert hashlib.sha256((target / '候选试玩.html').read_bytes()).hexdigest() == expected
    return target


def measure(root, label):
    log = (OUT / (label + "-server.log")).open("w")
    replay = os.environ.get("POIGHT_BENCH_REPLAY") == "1"
    # The remote wrapper owns this port. Replay each frozen candidate on that
    # same origin instead of trying to bind a second server or stop its process.
    process = None if replay else subprocess.Popen(
        [sys.executable, str(root / "预览服务.py"), "--candidate",
         "--host", "localhost", "--port", PORT], cwd=ROOT, stdout=log, stderr=log)
    if process is not None:
        (OUT / (label + "-server.pid")).write_text(str(process.pid))

    def route_candidate(context):
        if not replay:
            return
        context.route(URL + "**", lambda route: route.fulfill(
            path=root / ("assets/" + route.request.url.rsplit("/", 1)[-1]
                         if "/assets/" in route.request.url else "候选试玩.html")))
    try:
        for _ in range(200):
            if process is not None and process.poll() is not None:
                raise RuntimeError("benchmark server could not bind")
            try:
                urlopen(URL, timeout=1).close()
                break
            except OSError:
                time.sleep(.05)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            probe = browser.new_page()
            route_candidate(probe.context)
            probe.goto(URL + "?test=1")
            wait(probe, "window.__waterTest?.snapshot().artReady")
            profile = probe.evaluate("window.__waterTest.snapshot().profile")
            profile["map"] = "emerald-littleroottown"
            probe.close()
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            route_candidate(context)
            context.add_init_script("localStorage.setItem('pocket-arena-loadout-v1', "
                                    + json.dumps(json.dumps(profile)) + ");")
            context.add_init_script("""(() => {
              const raf = window.requestAnimationFrame.bind(window);
              window.__costs = new Map(); window.__wall = [];
              window.requestAnimationFrame = (cb) => raf((t) => {
                const before = performance.now(); cb(t);
                if (window.__record) {
                  window.__costs.set(t, (window.__costs.get(t) || 0) + performance.now() - before);
                }
              });
            })();""")
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(URL + "?observe=1", wait_until="load")
            wait(page, "window.__waterTest?.snapshot().artReady")
            initial = page.evaluate("""() => ({state:window.__waterTest.snapshot(),
              resources: performance.getEntriesByType('resource').map(r=>({name:r.name,
                bytes:r.encodedBodySize,transfer:r.transferSize})),
              html:performance.getEntriesByType('navigation')[0].encodedBodySize})""")
            page.locator("#startBattle").click()
            wait(page, "window.__waterTest.snapshot().phase === 'playing'")
            page.evaluate("window.__costs.clear(); window.__record=true")
            start = time.monotonic()
            # Real keyboard input, live fixed-step simulation and AI, not manual test stepping.
            for i in range(30):
                if i % 5 == 0:
                    page.keyboard.press("r")
                key = ["d", "s", "a", "w"][i % 4]
                page.keyboard.down(key)
                page.keyboard.press("1")
                page.wait_for_timeout(2000)
                page.keyboard.up(key)
            elapsed = time.monotonic() - start
            raw = page.evaluate("window.__record=false; [...window.__costs]")
            costs = [v for _, v in raw]
            intervals = [raw[i][0] - raw[i - 1][0] for i in range(1, len(raw))]
            chunks = [r for r in initial["resources"] if "/emerald-ground-" in r["name"]
                      or "/emerald-over-" in r["name"]]
            terrain = json.loads((root / '素材/绿宝石场景/场景目录.json').read_text())['terrains'][0]
            requested = {r['name'].rsplit('/', 1)[-1] for r in chunks}
            chunk_count = sum(any(f"emerald-{layer}-{c[layer]['sha256'][:12]}.png" in requested
                                 for layer in ('ground', 'over') if layer in c)
                              for c in terrain['chunks'])
            result = {"label": label, "candidateSHA256": hashlib.sha256((root / "候选试玩.html").read_bytes()).hexdigest(),
                      "viewport": [1440, 900], "realSeconds": elapsed,
                      "frames": len(raw), "frameMedianMs": statistics.median(intervals),
                      "cpuMedianMs": statistics.median(costs),
                      "cpuP95Ms": sorted(costs)[int(len(costs) * .95)],
                      "firstEncodedBytes": initial["html"] + sum(r["bytes"] for r in initial["resources"]),
                      "chunkRequests": len(chunks), "chunkBytes": sum(r["bytes"] for r in chunks),
                      "initialChunkCount": chunk_count,
                      "initialTerrain": initial["state"]["environment"]["terrain"],
                      "errors": errors, "rawSamples": raw}
            assert not errors, errors
            assert initial["state"]["environment"]["id"] == "emerald-littleroottown"
            (OUT / (label + "-性能.json")).write_text(json.dumps(result, ensure_ascii=False, indent=2))
            browser.close()
            return {k: v for k, v in result.items() if k not in ("rawSamples", "initialTerrain")}
    finally:
        if process is not None:
            command = subprocess.check_output(
                ["ps", "-o", "command=", "-p", str(process.pid)], text=True)
            if str(root / "预览服务.py") in command and PORT in command:
                process.terminate()
                process.wait(timeout=10)
        log.close()


if __name__ == "__main__":
    results = [measure(frozen_baseline(), "M"), measure(ROOT, "W2")]
    m, w = results
    report = {"runs": results, "frameRatio": w["frameMedianMs"] / m["frameMedianMs"],
              "cpuRatio": w["cpuMedianMs"] / m["cpuMedianMs"],
              "firstBytesRatio": w["firstEncodedBytes"] / m["firstEncodedBytes"]}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    (OUT / "性能对比.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    assert report["frameRatio"] <= 1.2
    assert report["firstBytesRatio"] <= 1.5
