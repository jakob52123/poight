"""F2: real keyboard/pointer input, bounded buffering and visible cast refusals."""

import base64
import json
import math
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/出招反馈"
SHOTS = OUT / "截图"
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8864/").rstrip("/")
checks, errors, screenshots = [], [], []


def check(name, ok, detail=None):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    assert ok, (name, detail)


def snap():
    return p.evaluate("window.__waterTest.snapshot()")


def step(seconds):
    p.evaluate("n => window.__waterTest.step(n)", seconds)


def arrange(**values):
    p.evaluate("v => window.__waterTest.arrange(v)", values)


def reset(hold=False):
    p.evaluate("v => window.__waterTest.select(v)", {**default, "holdAim": hold})
    p.evaluate("window.__waterTest.reset(true)")
    arrange(ai=False, player={"x": CX, "y": CY}, enemy={"x": CX + 100, "y": CY})
    step(1)  # Settle the existing camera after test-only teleportation, also on mobile.
    p.locator("#game").focus()


def press(key="KeyJ"):
    p.keyboard.down(key)
    p.keyboard.up(key)


def rejected(slot=0):
    return p.locator("#skills .skill").nth(slot).evaluate(
        "b => ({count:Number(b.dataset.rejections || 0), "
        "red:b.classList.contains('cast-rejected'), "
        "animation:getComputedStyle(b).animationName, "
        "frames:[...document.styleSheets].flatMap(s=>[...s.cssRules])"
        ".filter(r=>r.name==='cast-rejected').flatMap(r=>[...r.cssRules])"
        ".map(r=>({transform:r.style.transform}))})"
    )


def texts():
    return [f["text"] for f in snap()["hud"]["floats"]]


def shot(name):
    path = SHOTS / (name + ".png")
    p.evaluate("window.__waterTest.render()")
    p.screenshot(path=str(path))
    screenshots.append(str(path))


try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        p = browser.new_page(viewport={"width": 1440, "height": 900})
        p.on("pageerror", lambda e: errors.append(str(e)))
        p.goto(URL + "/?test=1")
        for _ in range(500):
            if p.evaluate("window.__waterTest?.snapshot().artReady"):
                break
            time.sleep(0.02)
        else:
            raise TimeoutError("art ready")
        catalog = p.evaluate("window.__waterTest.catalog()")
        roster = {c["id"]: c for c in catalog["roster"]}
        default = {**snap()["profile"], "map": "emerald-rustborocity", "player": 25,
                   "enemy": 143, "playerMoves": roster[25]["defaultMoves"],
                   "enemyMoves": roster[143]["defaultMoves"]}
        terrain = catalog["terrains"][0]
        walk = base64.b64decode(terrain["walkB64"])
        cols = terrain["columns"]
        area = next(a for a in terrain["areas"] if a["sourceName"] == "RustboroCity")
        lane = next((x, y)
                    for y in range(area["gridY"] + 3, area["gridY"] + area["rows"] - 3)
                    for x in range(area["gridX"] + 7, area["gridX"] + area["columns"] - 7)
                    if all(walk[(y + dy) * cols + x + dx]
                           for dy in range(-2, 3) for dx in range(-6, 7)))
        CX, CY = (lane[0] + 0.5) * 48, (lane[1] + 0.5) * 48

        reset()
        # The hero-adjusted range is observable in attack state; no move data is changed.
        press("KeyI")
        step(0.01)
        reach = snap()["player"]["attack"]["range"]
        reset()
        arrange(enemy={"x": CX + reach * 2, "y": CY})
        before = snap()
        check("Opponent at twice thunder range", abs(before["enemy"]["x"] - CX - 2 * reach) < 1)
        press("KeyI")
        step(0.01)
        state = snap()
        attack = state["player"]["attack"]
        check("I starts out-of-range thunder", attack and attack["id"] == "thunder", attack)
        point = attack["targetPoint"]
        dx, dy = point["x"] - CX, point["y"] - CY
        check("Landing at max range", abs(math.hypot(dx, dy) - reach) < 1, point)
        check("Landing toward opponent within 5 degrees", abs(math.atan2(dy, dx)) < math.radians(5))
        warning = next(w for w in state["warnings"] if w["id"] == "thunder")
        check("Warning circle at fixed landing", warning["x"] == point["x"] and warning["y"] == point["y"])
        shot("超距打雷-预警-1440x900")
        arrange(enemy={"x": CX + reach * 2, "y": CY + 48})
        step(attack["hitTime"] + 0.02)
        generated = next(e for e in snap()["generated"]["states"] if e["id"] == "thunder")
        check("Thunder emitted at original landing despite enemy movement",
              generated["ex"] == point["x"] and generated["ey"] == point["y"], generated)
        step(catalog["moves"]["thunder"]["delay"])
        landed = next(e for e in snap()["generated"]["states"] if e["id"] == "thunder")
        check("Out-of-range thunder lands at clamped point", landed["landed"] and
              landed["x"] == point["x"] and landed["y"] == point["y"])
        check("Out-of-range thunder does not damage distant opponent",
              snap()["enemy"]["hp"] == before["enemy"]["hp"])
        shot("超距打雷-落雷-1440x900")

        reset()
        arrange(player={"hurt": 0.09})
        press()
        check("Buffer is 0.12 actionable seconds", abs(snap()["queued"]["remaining"] - 0.12) < 1e-6)
        step(0.08)
        check("No cast before hurt ends", not snap()["player"]["attack"])
        step(0.03)
        check("0.09s hurt executes buffered J", snap()["player"]["attack"]["id"] == "thunderbolt")
        check("Successful buffer has no refusal", rejected()["count"] == 0)

        reset()
        arrange(player={"hurt": 0.5})
        p.keyboard.down("KeyJ")
        step(0.13)
        state = snap()
        check("0.5s hurt expires buffer", not state["player"]["attack"] and state["queued"] is None)
        check("Busy refusal shakes/red button, no floating text", rejected()["red"] and not texts())
        check("Shake has nonzero keyframes", any("4px" in f.get("transform", "") for f in rejected()["frames"]))
        step(0.2)
        check("Held expired press cannot bypass timeout", not snap()["player"]["attack"])
        p.keyboard.up("KeyJ")

        reset()
        arrange(player={"stamina": 3})
        press()
        step(0.13)
        check("Stamina 3 refuses with floating text", texts().count("体力不足") == 1 and not snap()["player"]["attack"])
        check("Stamina refusal button shakes/red", rejected()["red"] and rejected()["animation"] == "cast-rejected")
        shot("体力不足-1440x900")
        arrange(player={"stamina": 3})
        press()
        step(0.06)
        press()
        step(0.13)
        check("Three presses within 0.8s float only once", texts().count("体力不足") == 1 and rejected()["count"] == 3, texts())
        step(0.7)
        arrange(player={"stamina": 3})
        press()
        step(0.13)
        check("Same reason can float again after 0.8s", texts().count("体力不足") == 1 and rejected()["count"] == 4)

        reset()
        press()
        step(0.9)
        press()
        step(0.13)
        check("Cooldown refusal has one-decimal remaining time",
              any(t.startswith("冷却 ") and t.endswith(" 秒") and "." in t for t in texts()), texts())
        check("Cooldown refusal shakes", rejected()["red"])

        reset()
        p.evaluate("window.__waterTest.equip('player',['recover'])")
        press()
        step(0.13)
        check("Full HP healing refusal", "血量已满" in texts() and rejected()["red"])

        for hold, reason, setup in [(True, "体力不足", {"stamina": 3}),
                                    (True, None, {"hurt": 0.5})]:
            reset(hold)
            arrange(player=setup)
            p.mouse.down(button="right")
            p.keyboard.down("KeyJ")
            check("Denied hold aim never starts: " + str(reason), snap()["aim"] is None)
            check("Denied hold aim immediate button feedback: " + str(reason), rejected()["red"])
            if reason:
                check("Denied hold aim same reason", texts().count(reason) == 1)
            else:
                check("Busy aim no floating text", not texts())
            p.keyboard.up("KeyJ")
            p.mouse.up(button="right")
            step(0.13)
            if reason:
                check("Aim + timeout do not duplicate float", texts().count(reason) == 1)

        reset()
        arrange(player={"hurt": 0.09})
        press()
        step(0.04)
        press("KeyK")
        step(0.07)
        check("Only last pressed skill buffered", snap()["player"]["attack"]["id"] == "quickattack")

        reset()
        p.evaluate("window.__waterTest.cast('player','quickattack')")
        duration = snap()["player"]["attack"]["duration"]
        while snap()["player"]["attack"]["age"] < duration - 0.08:
            step(0.005)  # Count actionable recovery, not wall time including hitstop.
        press()
        step(0.18)  # Includes the unchanged light-hit freeze from Quick Attack.
        check("Recovery buffer executes", snap()["player"]["attack"]["id"] == "thunderbolt", snap()["player"]["attack"])

        reset()
        p.evaluate("window.__waterTest.dash('player',1,0)")
        step(0.22)  # B2: still tap in the last 80ms of the now-300ms dash.
        press()
        step(0.1)
        check("Dash buffer executes", snap()["player"]["attack"]["id"] == "thunderbolt")

        reset()
        p.evaluate("window.__waterTest.feedbackHit(30,1)")
        press()
        step(0.05)
        check("Hitstop buffers without casting", not snap()["player"]["attack"] and snap()["queued"] is not None)
        check("Buffer clock pauses during hitstop", abs(snap()["queued"]["remaining"] - 0.12) < 1e-6)
        step(0.08)
        check("Hitstop end executes buffered move", snap()["player"]["attack"]["id"] == "thunderbolt")

        reset()
        p.evaluate("window.__waterTest.equip('enemy',['thunder'])")
        arrange(enemy={"x": CX + 2 * reach, "y": CY})
        check("AI thunder range refusal unchanged", not p.evaluate("window.__waterTest.cast('enemy','thunder')"))

        for width, height in [(390, 844), (844, 390)]:
            p.set_viewport_size({"width": width, "height": height})
            reset(True)
            arrange(player={"stamina": 3})
            p.locator("#skills .skill").first.dispatch_event("pointerdown", {"button": 0, "pointerId": 1})
            check(f"Pointer aim refusal {width}x{height}", snap()["aim"] is None and "体力不足" in texts() and rejected()["red"])
            p.locator("#skills .skill").first.dispatch_event("pointerup", {"button": 0, "pointerId": 1})
            shot(f"体力不足-{width}x{height}")

        p.set_viewport_size({"width": 1440, "height": 900})
        reset(True)
        p.evaluate("window.__waterTest.testDamage('player',10,1,0)")
        arrange(player={"stamina": 3})
        press()
        boxes = [f["box"] for f in snap()["hud"]["floats"]]
        check("Refusal text and damage number never overlap", len(boxes) >= 2 and all(
            a["x"] + a["width"] <= b["x"] or b["x"] + b["width"] <= a["x"] or
            a["y"] + a["height"] <= b["y"] or b["y"] + b["height"] <= a["y"]
            for i, a in enumerate(boxes) for b in boxes[i + 1:]))
        check("No JS errors", not errors, errors)
        browser.close()
finally:
    report = {"passed": sum(c["ok"] for c in checks), "failed": sum(not c["ok"] for c in checks),
              "jsErrors": len(errors), "errors": errors, "checks": checks, "screenshots": screenshots}
    (OUT / "报告.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "checks"}, ensure_ascii=False, indent=2))
