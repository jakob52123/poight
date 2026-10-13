"""M6a suites via tools/远程执行.sh. Restore frozen inputs on the same preview service.

Temporarily swap derived candidate/manifest to the SHA-verified baseline, then restore
in finally. No second server/port and no changed behavioral assertions.
Supply ignored BGM验收基准/ from the archived M/T5 inputs before invoking remotely.
"""
import hashlib
import importlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
STAGE = ROOT / "BGM验收基准"
OUT = ROOT / "验收记录/丰缘全图"
URL = os.environ["POIGHT_TEST_URL"].rstrip("/") + "/"
SUITES = ["竞技场", "主角八招", "选人页", "水溅跃", "头顶血条", "草丛藏身", "平衡钩子",
          "打击感瞄准", "大地图通行", "集成联动", "出招反馈", "界面方案", "跳跃",
          "招式第1批", "招式第2批", "招式第3批", "手机操作", "桥梁通行", "丰缘全图", "手感",
          "战斗音乐"]


def wait(page, expr):
    for _ in range(1200):
        if page.evaluate(expr):
            return
        page.wait_for_timeout(50)
    raise AssertionError(expr)


def measure(browser, root, label):
    html = (root / "候选试玩.html").read_bytes()
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    probe = context.new_page()
    probe.on("pageerror", lambda e: print("BENCH JS", str(e), flush=True))
    probe.on("requestfailed", lambda r: print("BENCH REQUEST", r.url, r.failure, flush=True))
    probe.goto(URL + "?test=1")
    wait(probe, "()=>window.__waterTest?.snapshot().artReady")
    profile = probe.evaluate("()=>window.__waterTest.snapshot().profile")
    profile["map"] = "emerald-littleroottown"
    probe.close()
    context.add_init_script("localStorage.setItem('pocket-arena-loadout-v1', "
                            + json.dumps(json.dumps(profile)) + ");")
    context.add_init_script("""(() => {
      const raf = window.requestAnimationFrame.bind(window);
      window.__costs = new Map();
      window.requestAnimationFrame = cb => raf(t => {
        const before=performance.now(); cb(t);
        if(window.__record)window.__costs.set(t,
          (window.__costs.get(t)||0)+performance.now()-before);
      });
    })();""")
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL + "?observe=1")
    wait(page, "()=>window.__waterTest?.snapshot().artReady")
    initial = page.evaluate("""() => ({state:window.__waterTest.snapshot(),
      resources:performance.getEntriesByType('resource').map(r=>({name:r.name,
        bytes:r.encodedBodySize,transfer:r.transferSize})),
      html:performance.getEntriesByType('navigation')[0].encodedBodySize})""")
    page.locator("#startBattle").click()
    wait(page, "()=>window.__waterTest.snapshot().phase==='playing'")
    page.evaluate("()=>{window.__costs.clear();window.__record=true;}")
    start = time.monotonic()
    for i in range(30):
        if i % 5 == 0:
            page.keyboard.press("r")
        key = ["d", "s", "a", "w"][i % 4]
        page.keyboard.down(key)
        page.keyboard.press("1")
        page.wait_for_timeout(2000)
        page.keyboard.up(key)
    elapsed = time.monotonic() - start
    raw = page.evaluate("()=>{window.__record=false;return [...window.__costs];}")
    context.close()
    costs = [v for _, v in raw]
    intervals = [raw[i][0] - raw[i - 1][0] for i in range(1, len(raw))]
    chunks = [r for r in initial["resources"] if "/emerald-ground-" in r["name"]
              or "/emerald-over-" in r["name"]]
    terrain = json.loads((root / "素材/绿宝石场景/场景目录.json").read_text())["terrains"][0]
    requested = {r["name"].rsplit("/", 1)[-1] for r in chunks}
    chunk_count = sum(any(f"emerald-{layer}-{c[layer]['sha256'][:12]}.png" in requested
                          for layer in ("ground", "over") if layer in c)
                      for c in terrain["chunks"])
    result = {"label": label, "candidateSHA256": hashlib.sha256(html).hexdigest(),
              "viewport": [1440, 900], "realSeconds": elapsed, "frames": len(raw),
              "frameMedianMs": statistics.median(intervals),
              "cpuMedianMs": statistics.median(costs),
              "cpuP95Ms": sorted(costs)[int(len(costs) * .95)],
              "firstEncodedBytes": initial["html"] + sum(r["bytes"] for r in initial["resources"]),
              "chunkRequests": len(chunks), "chunkBytes": sum(r["bytes"] for r in chunks),
              "initialChunkCount": chunk_count, "initialTerrain": initial["state"]["environment"]["terrain"],
              "errors": errors, "rawSamples": raw}
    assert not errors, errors
    assert initial["state"]["environment"]["id"] == "emerald-littleroottown"
    assert result["firstEncodedBytes"] > 0
    (OUT / (label + "-性能.json")).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return {k: v for k, v in result.items() if k not in ("rawSamples", "initialTerrain")}


def main():
    shutil.copytree(STAGE / "记录", ROOT / "验收记录", dirs_exist_ok=True)
    os.environ["POIGHT_T5_BASELINE"] = str(STAGE / "T5")
    frozen = importlib.import_module("验收-丰缘性能").frozen_baseline()
    names = ("候选试玩.html", "候选发布清单.json")
    original = {name: (ROOT / name).read_bytes() for name in names}
    baseline_assets = json.loads((frozen / names[1]).read_text())["assets"]
    for path, receipt in baseline_assets.items():
        asset = ROOT / path
        if not asset.exists():
            shutil.copy2(frozen / path, asset)
        assert hashlib.sha256(asset.read_bytes()).hexdigest() == receipt["sha256"], path
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            for name in names:
                (ROOT / name).write_bytes((frozen / name).read_bytes())
            before = measure(browser, frozen, "M")
        finally:
            for name in names:
                (ROOT / name).write_bytes(original[name])
        results = [before, measure(browser, ROOT, "W2")]
        browser.close()
    m, w = results
    report = {"runs": results, "frameRatio": w["frameMedianMs"] / m["frameMedianMs"],
              "cpuRatio": w["cpuMedianMs"] / m["cpuMedianMs"],
              "firstBytesRatio": w["firstEncodedBytes"] / m["firstEncodedBytes"]}
    (OUT / "性能对比.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print("性能原样 " + json.dumps(report, ensure_ascii=False), flush=True)
    assert report["frameRatio"] <= 1.2
    assert report["firstBytesRatio"] <= 1.5
    label = sys.argv[1] if len(sys.argv) > 1 else "BGM-final"
    result = subprocess.run([sys.executable, "验收记录/集成批次/run.py", label, *SUITES],
                            cwd=ROOT, check=False)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
