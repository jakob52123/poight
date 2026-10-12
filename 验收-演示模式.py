"""D1 live-engine recording acceptance, headless only; no artificial combat state."""
import base64
import hashlib
import json
import os
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/演示模式"
SHOTS = OUT / "截图"
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8915/")
checks, errors, samples = [], [], []


def check(name, ok):
    checks.append({"name": name, "ok": bool(ok)})
    assert ok, name


def wait(page, expression, timeout=120):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if page.evaluate(expression):
            return
        page.wait_for_timeout(25)
    raise AssertionError(expression)


def load(context, query, controlled=False):
    page = context.new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    if controlled:
        page.add_init_script("""window.__rafQueue = [];
          window.requestAnimationFrame = cb => (window.__rafQueue.push(cb), window.__rafQueue.length);
          window.__pumpRAF = now => { const jobs = window.__rafQueue.splice(0);
            jobs.forEach(cb => cb(now)); };""")
    page.goto(URL + query, timeout=120000)
    wait(page, "window.__demo?.ready")
    return page


def snapshot(page):
    return page.evaluate("__demo.snapshot()")


def pixels(page):
    return base64.b64decode(page.evaluate("document.getElementById('game').toDataURL().split(',')[1]"))


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
    query = "?demo=1&w=1080&h=1920&fps=60&seed=7&paused=1"
    page = load(context, query)
    check("logical canvas exactly 1080x1920", snapshot(page)["canvas"] == {"width": 1080, "height": 1920})
    check("paused readiness at frame 0", page.evaluate("__demo.frame === 0 && __demo.paused"))
    for i in range(61):
        state = snapshot(page)
        check(f"both sprite centers in middle 80% at {i / 2:.1f}s", all(
            0.1 <= p[axis] <= 0.9 for p in state["centers"] for axis in ("nx", "ny")))
        camera = state["camera"]
        check(f"both feet in middle 80% at frame {state['frame']}", all(
            0.1 <= (state[side][axis] - camera[axis]) / camera[dimension] <= 0.9
            for side in ("player", "enemy") for axis, dimension in (("x", "width"), ("y", "height"))))
        samples.append({"seconds": i / 2, "frame": state["frame"], "centers": state["centers"], "zoom": camera["zoom"]})
        if i == 20:
            first = state
            first_pixels = pixels(page)
            (SHOTS / "演示-1080x1920-第600帧.png").write_bytes(first_pixels)
        if i < 60:
            page.evaluate("__demo.step(30)")
    check("30s exactly 1800 frames", page.evaluate("__demo.frame === 1800"))
    check("zoom follows separation", len({round(s['zoom'], 3) for s in samples}) > 10)
    page.evaluate("__demo.reset(); __demo.step(10)")
    check("step(10) exactly ten frames", page.evaluate("__demo.frame === 10"))
    check("fixed title suffix", page.title().endswith("[frame=10]"))
    check("ten steps clock 10/60s", abs(snapshot(page)["matchSeconds"] - 10 / 60) < 1e-12)
    before = snapshot(page)
    page.wait_for_timeout(300)
    check("paused RAF leaves snapshot unchanged", snapshot(page) == before)
    check("invalid step counts rejected", page.evaluate("""() => [-1, 1.5, NaN, Infinity, 100001].every(n => {
      try { __demo.step(n); return false; } catch { return true; } })"""))
    check("step(0) unchanged", page.evaluate("__demo.step(0)") == 10 and snapshot(page) == before)
    page.close()
    page = load(context, query)
    page.evaluate("__demo.step(600)")
    check("seed=7 frame600 snapshots identical", first == snapshot(page))
    check("seed=7 frame600 PNG bytes identical", pixels(page) == first_pixels)
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(100)
    rect = page.locator("#game").bounding_box()
    check("small window proportional CSS scaling, buffer preserved", snapshot(page)["canvas"] == first["canvas"]
          and abs(rect["width"] / rect["height"] - 1080 / 1920) < 1e-5
          and rect["width"] <= 390 and rect["height"] <= 844)
    check("resize preserves logical pixels", pixels(page) == first_pixels)
    page.close()
    page = load(context, "?demo=1&w=1920&h=1080&fps=60&seed=7&paused=1", controlled=True)
    check("landscape exact resolution", snapshot(page)["canvas"] == {"width": 1920, "height": 1080})
    page.evaluate("__demo.resume(); __pumpRAF(1000000)")
    check("late RAF one frame, no catch-up", page.evaluate("__demo.frame === 1"))
    check("one RAF clock 1/60s", abs(snapshot(page)["matchSeconds"] - 1 / 60) < 1e-12)
    check("running step rejected", page.evaluate("""() => {
      try { __demo.step(10); return false; } catch { return true; } }"""))
    for stamp in (1000001, 2000000, 2000000):
        page.evaluate("stamp => __pumpRAF(stamp)", stamp)
    check("4 RAFs = 4 frames regardless of timestamp", page.evaluate("__demo.frame === 4"))
    page.evaluate("__demo.pause(); __pumpRAF(3000000); __demo.step(10)")
    check("paused RAF + step10 only ten frames", page.evaluate("__demo.frame === 14"))
    (SHOTS / "演示-1920x1080.png").write_bytes(pixels(page))
    page.close()
    context.close()

    desktop = browser.new_context(viewport={"width": 1440, "height": 900})
    page = load(desktop, "?demo=1")
    initial = snapshot(page)
    check("default skips selection and VS", initial["phase"] == "playing" and page.evaluate(
        "!document.querySelector('#setup').open && document.querySelector('#vsScreen').hidden"))
    check("defaults 25 vs 6 / formal arena / ultra", initial["player"]["id"] == 25 and
          initial["enemy"]["id"] == 6 and initial["environment"] == "arena-formal" and initial["tier"] == "ultra")
    check("title contains browser title + URL", "Poight" in page.title() and "?demo=1" in page.title())
    start = time.monotonic()
    wait(page, "Object.values(__demo.snapshot().casts).every(n=>n>=3) && "
         "__demo.snapshot().player.damageTaken > 0 && __demo.snapshot().enemy.damageTaken > 0", 20)
    check("no input: both cast >=3 and lose HP within 20 wall seconds", time.monotonic() - start <= 20)
    page.keyboard.press("Space")
    check("Space pauses", page.evaluate("__demo.paused"))
    before = snapshot(page)
    for key in ("w", "j", "k", "l", "i", "r", "Shift", "Escape"):
        page.keyboard.press(key)
    page.wait_for_timeout(100)
    check("operation keys ignored", snapshot(page) == before)
    for speed in (0.5, 1):
        page.keyboard.press("s")
        check(f"S toggles speed {speed}", page.evaluate("__demo.speed") == speed)
    for mode in (0, 1, 2):
        page.keyboard.press("c")
        check(f"C cycles mode {mode}", page.evaluate("__demo.cameraMode") == mode)
    page.keyboard.press("Space")
    check("Space resumes", page.evaluate("!__demo.paused"))
    page.close()

    runs = []
    for run in range(2):
        page = load(desktop, "?demo=1&seed=7&paused=1&loop=0")
        states = []
        for seconds in (5, 10, 15):
            page.evaluate("__demo.step(600)")
            states.append(snapshot(page))
            check(f"run{run}: simulation clock {seconds}s", abs(states[-1]["matchSeconds"] - seconds) < 1e-9)
        runs.append(states)
        page.close()
    for index, seconds in enumerate((5, 10, 15)):
        check(f"seed7 snapshots at {seconds}s identical", runs[0][index] == runs[1][index])
    (OUT / "种子7-5-10-15秒.json").write_text(json.dumps(runs[0], ensure_ascii=False, indent=2) + "\n")
    timings = []
    for speed in (1, 0.5):
        page = load(desktop, f"?demo=1&seed=7&speed={speed}&paused=1")
        start = time.monotonic()
        page.evaluate("__demo.resume()")
        wait(page, "__demo.snapshot().matchSeconds >= 2")
        timings.append(time.monotonic() - start)
        page.close()
    check("speed .5 needs twice wall time", 1.8 <= timings[1] / timings[0] <= 2.2)
    slow_runs = []
    for _ in range(2):
        page = load(desktop, "?demo=1&seed=7&fps=60&speed=0.5&paused=1")
        page.evaluate("__demo.step(120)")
        slow_runs.append(snapshot(page))
        page.close()
    check("fixed fps uses speed/60", abs(slow_runs[0]["matchSeconds"] - 1) < 1e-9)
    check("speed + fps + seed deterministic", slow_runs[0] == slow_runs[1])
    for loop in (0, 1):
        page = load(desktop, f"?demo=1&seed=7&fps=60&paused=1&loop={loop}")
        for _ in range(600):
            page.evaluate("__demo.step(30)")
            if snapshot(page)["phase"] == "over":
                break
        check(f"loop{loop}: natural KO", snapshot(page)["phase"] == "over")
        if loop:
            for _ in range(180):
                if snapshot(page)["round"] == 2:
                    break
                page.evaluate("__demo.step(1)")
            check("loop1 auto round2 within 3 seconds", snapshot(page)["round"] == 2 and
                  snapshot(page)["player"]["hp"] == snapshot(page)["player"]["maxHP"])
        else:
            page.evaluate("__demo.step(300)")
            check("loop0 remains at KO", snapshot(page)["phase"] == "over" and snapshot(page)["round"] == 1)
        page.close()
    page = load(desktop, "?demo=1&vs=1&fps=60&paused=1")
    check("vs1 retains VS", snapshot(page)["phase"] == "versus" and page.locator("#vsScreen").is_visible())
    page.evaluate("__demo.step(95)")
    check("VS stays before 1.6s", snapshot(page)["phase"] == "versus")
    page.evaluate("__demo.step(1)")
    check("VS auto starts at 1.6s, step remains paused", snapshot(page)["phase"] == "paused" and
          page.evaluate("__demo.paused") and not page.locator("#vsScreen").is_visible())
    page.close()
    page = load(desktop, "?demo=1&vs=1&hud=0&fps=60&paused=1")
    check("hud0 hides optional VS too", snapshot(page)["phase"] == "versus" and
          not page.locator("#vsScreen").is_visible())
    page.close()
    page = load(desktop, "?demo=1&p1=7&p2=4&map=arena-natural&tier=poke&moves=watergun&paused=1")
    state = snapshot(page)
    check("p1/p2/tier/moves applied", state["player"]["id"] == 7 and state["enemy"]["id"] == 4 and
          state["tier"] == "poke" and state["player"]["moves"] == ["watergun"])
    check("map applied", state["environment"] == "arena-natural")
    page.close()
    page = load(desktop, "?demo=1&p1=999&p2=oops&map=missing&tier=nope&moves=watergun&fps=-1&speed=7&paused=1")
    state = snapshot(page)
    check("invalid params fall back", state["player"]["id"] == 25 and state["enemy"]["id"] == 6 and
          state["environment"] == "arena-formal" and state["tier"] == "ultra" and state["speed"] == 1 and
          state["fps"] == 120 and "watergun" not in state["player"]["moves"])
    page.close()
    for hiding in ("&hud=0", "&bars=0"):
        page = load(desktop, "?demo=1&fps=60&paused=1" + hiding)
        check(hiding + " overhead painter disabled", snapshot(page)["bars"] is False)
        labels = page.evaluate("""() => {
          const ctx = document.querySelector('#game').getContext('2d'), original = ctx.fillText;
          const seen = [];
          ctx.fillText = function(text, ...args) { seen.push(text); return original.call(this, text, ...args); };
          __demo.step(1); ctx.fillText = original; return seen;
        }""")
        check(hiding + " no Canvas identity labels", "1P" not in labels and "CPU" not in labels)
        if hiding == "&hud=0":
            check("hud0 all DOM HUD hidden", page.evaluate("""() =>
              [...document.querySelectorAll('#app > :not(.stage), .stage > :not(#game)')]
                .every(el => getComputedStyle(el).display === 'none' || el.hidden ||
                  (el.tagName === 'DIALOG' && !el.open))"""))
        else:
            check("bars0 keeps DOM skills", page.locator("#skills").is_visible())
        page.close()
    page = load(desktop, "?demo=1&seed=3&fps=60&hud=0&bars=0&paused=1")
    found = page.evaluate("""() => {
      for (let i = 0; i < 1800; i++) {
        __demo.step(1);
        const a = __demo.snapshot().player.attack;
        if (a?.id === 'thunderbolt' && a.emitted && a.age >= a.hitTime + 0.08) return true;
      }
      return false;
    }""")
    check("real AI-emitted Thunderbolt screenshot", found)
    page.screenshot(path=str(SHOTS / "演示-1440x900-十万伏特.png"))
    page.close()
    page = load(desktop, "?demo=1&seed=3&fps=60&paused=1")
    page.evaluate("__demo.step(300)")
    page.screenshot(path=str(SHOTS / "演示-1440x900-HUD.png"))
    page.close()
    for width, height in ((390, 844), (844, 390)):
        logical = "&w=1080&h=1920" if height > width else "&w=1920&h=1080"
        page = load(desktop, "?demo=1&seed=3&fps=60&hud=0&paused=1" + logical)
        page.set_viewport_size({"width": width, "height": height})
        page.evaluate("__demo.step(300)")
        page.wait_for_timeout(100)
        page.screenshot(path=str(SHOTS / f"演示-{width}x{height}.png"))
        page.close()
    desktop.close()

    touch = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    page = load(touch, query)
    check("demo portrait no rotate mask", page.evaluate("!document.querySelector('#rotatePhone').matches(':popover-open')"))
    page.evaluate("__demo.resume()")
    wait(page, "__demo.frame >= 10")
    check("touch demo runs", snapshot(page)["phase"] == "playing")
    page.close()
    page = touch.new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL + "?test=1", timeout=120000)
    wait(page, "window.__waterTest?.snapshot().artReady")
    check("normal touch portrait retains rotate mask", page.evaluate("document.querySelector('#rotatePhone').matches(':popover-open')"))
    check("normal mode has no demo API", page.evaluate("typeof window.__demo === 'undefined'"))
    page.close()
    touch.close()
    browser.close()

check("no JavaScript errors", not errors)
check("portrait screenshot exact dimensions", Image.open(SHOTS / "演示-1080x1920-第600帧.png").size == (1080, 1920))
report = {"passed": len(checks), "failed": 0, "jsErrors": len(errors), "errors": errors,
          "candidateSHA256": hashlib.sha256((ROOT / "候选试玩.html").read_bytes()).hexdigest(),
          "frame600SnapshotSHA256": hashlib.sha256(json.dumps(first, sort_keys=True).encode()).hexdigest(),
          "frame600PNG_SHA256": hashlib.sha256(first_pixels).hexdigest(),
          "wallTimings": timings, "checks": checks, "portraitSamples": samples}
(OUT / "演示模式验收.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
(OUT / "第600帧快照.json").write_text(json.dumps(first, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k: v for k, v in report.items() if k not in ("checks", "portraitSamples")}, ensure_ascii=False, indent=2))
