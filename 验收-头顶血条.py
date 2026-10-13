"""Headless HUD checks against real damage, Canvas pixels and rendered CSS boxes."""

import base64
import hashlib
import json
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/头顶血条"
SHOTS = OUT / "截图"
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8821/").rstrip("/")
checks, errors = [], []


def check(name, ok, detail=None):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    assert ok, (name, detail)


def snap(page):
    return page.evaluate("window.__waterTest.snapshot()")


def step(page, seconds):
    page.evaluate("(v)=>window.__waterTest.step(v)", seconds)


def arrange(page, value):
    page.evaluate("(v)=>window.__waterTest.arrange(v)", value)


def reset(page):
    page.evaluate("window.__waterTest.reset(true)")
    arrange(
        page,
        {"ai": False, "player": {"x": CX - 100, "y": CY}, "enemy": {"x": CX + 20, "y": CY + 65}},
    )
    step(page, 0.5)


def pixel(page, x, y):
    return page.evaluate(
        """([x,y])=>{
      const c=document.getElementById('game'),r=c.getBoundingClientRect();
      return [...c.getContext('2d').getImageData(
        Math.floor(x*c.width/r.width),Math.floor(y*c.height/r.height),1,1).data].slice(0,3);
    }""",
        [x, y],
    )


def intersects(a, b):
    return (
        a["x"] < b["x"] + b["width"]
        and a["x"] + a["width"] > b["x"]
        and a["y"] < b["y"] + b["height"]
        and a["y"] + a["height"] > b["y"]
    )


def alignment(page, label):
    s = snap(page)
    for h in s["hud"]["actors"]:
        p = s[h["side"]]
        expected_head = p["y"] - p["body"]["top"] - p["flightHeight"]
        b = h["box"]
        expected_x = (p["x"] - round(s["camera"]["x"])) * h["sx"]
        expected_y = (expected_head - 10 - round(s["camera"]["y"])) * h["sy"]
        check(
            label + " " + h["side"] + " head-aligned",
            abs(p["headY"] - expected_head) < 1e-7
            and abs(b["x"] + b["width"] / 2 - expected_x) <= 6
            and abs(b["y"] + b["height"] / 2 - expected_y) <= 6,
            h,
        )
        check(
            label + " " + h["side"] + " 48x6 CSS pixels",
            abs(b["width"] - 48) < 0.01 and abs(b["height"] - 6) < 0.01,
        )
        check(
            label + " " + h["side"] + " Canvas HP fill visible",
            pixel(page, b["x"] + 3, b["y"] + 3) == [72, 216, 120],
        )
    return s


def hit(page, move="watergun"):
    p = snap(page)["enemy"]
    page.evaluate(
        "(v)=>window.__waterTest.injectWater(v)",
        {
            "owner": "player",
            "move": move,
            "x": p["x"] - 40,
            "y": p["y"],
            "ux": 1,
            "uy": 0,
            "speed": 650,
            "range": 200,
        },
    )
    step(page, 0.07)


try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(URL + "/?test=1")
        for _ in range(400):
            if page.evaluate("window.__waterTest?.snapshot().artReady"):
                break
            time.sleep(0.025)
        else:
            raise TimeoutError("art ready")
        catalog = page.evaluate("window.__waterTest.catalog()")
        roster = {c["id"]: c for c in catalog["roster"]}
        profile = {
            **snap(page)["profile"],
            "player": 25,
            "enemy": 6,
            "playerMoves": roster[25]["defaultMoves"],
            "enemyMoves": roster[6]["defaultMoves"],
            "map": "emerald-rustborocity",
        }
        check(
            "Pikachu and flying Charizard load",
            page.evaluate("(v)=>window.__waterTest.select(v)", profile),
        )
        t = catalog["terrains"][0]
        area = next(a for a in t["areas"] if a["sourceName"] == "RustboroCity")
        walk, cols = base64.b64decode(t["walkB64"]), t["columns"]
        lane = next(
            (x, y)
            for y in range(area["gridY"] + 3, area["gridY"] + area["rows"] - 3)
            for x in range(area["gridX"] + 4, area["gridX"] + area["columns"] - 4)
            if all(walk[(y + dy) * cols + x + dx] for dy in range(-2, 3) for dx in range(-4, 5))
        )
        CX, CY = (lane[0] + 0.5) * 48, (lane[1] + 0.5) * 48
        reset(page)
        before = alignment(page, "Initial")
        page.keyboard.down("d")
        step(page, 200 / before["player"]["speed"])
        page.keyboard.up("d")
        arrange(page, {"enemy": {"x": before["enemy"]["x"] + 200}})
        after = alignment(page, "After 200 world pixels")
        for side in ["player", "enemy"]:
            check(
                side + " moved 200 world pixels",
                abs(after[side]["x"] - before[side]["x"] - 200) < 0.1,
            )
        step(page, 0.2)
        alignment(page, "Flight bob follows head")
        for fraction, rgb in [
            (0.6, [72, 216, 120]),
            (0.5, [244, 203, 72]),
            (0.4, [244, 203, 72]),
            (0.2, [244, 203, 72]),
            (0.1, [239, 91, 88]),
        ]:
            reset(page)
            s = snap(page)
            arrange(
                page, {side: {"hp": s[side]["maxHP"] * fraction} for side in ["player", "enemy"]}
            )
            for h in snap(page)["hud"]["actors"]:
                b = h["box"]
                actual = pixel(page, b["x"] + 2, b["y"] + 3)
                check(f"{h['side']} {fraction:.0%} actual pixel color", actual == rgb, actual)
        reset(page)
        hp = snap(page)["enemy"]["hp"]
        # Sixfold HP: use a stronger real hit so the trail has whole backing pixels.
        hit(page, "hydropump")
        check("Actual projectile damages enemy", snap(page)["enemy"]["hp"] < hp)
        step(page, 0.2)
        h = snap(page)["hud"]["actors"][1]
        b = h["box"]
        sample_ratio = (h["ratio"] + h["trailRatio"]) / 2
        sample_x = b["x"] + b["width"] * sample_ratio
        check(
            "0.2s white damage trail actual pixel",
            pixel(page, sample_x, b["y"] + 3) == [255, 255, 255],
            h,
        )
        page.screenshot(path=str(SHOTS / "受伤残影-0.2秒.png"))
        step(page, 0.16)
        held = snap(page)["hud"]["actors"][1]
        check("White trail holds before 0.45s", abs(held["trailRatio"] - 1) < 1e-7)
        step(page, 0.2)
        shrinking = snap(page)["hud"]["actors"][1]
        check(
            "White trail shrinks during 0.45-0.80s",
            shrinking["ratio"] < shrinking["trailRatio"] < held["trailRatio"],
        )
        step(page, 0.44)
        h = snap(page)["hud"]["actors"][1]
        check("1.0s white trail completely collapsed", abs(h["ratio"] - h["trailRatio"]) < 1e-7)
        check(
            "1.0s former white pixel is dark background",
            pixel(page, h["box"]["x"] + h["box"]["width"] * sample_ratio,
                  h["box"]["y"] + 3) == [24, 38, 50],
            {"hud": h, "sampleRatio": sample_ratio, "pixel": pixel(
                page, h["box"]["x"] + h["box"]["width"] * sample_ratio, h["box"]["y"] + 3)},
        )
        check("0.8s damage floats expire", not snap(page)["hud"]["floats"])
        reset(page)
        for _ in range(3):
            hit(page)
            # Preserve the original active-time hit spacing, plus actual hitstop.
            step(page, 0.1 + snap(page)["feel"]["duration"])
        s = snap(page)
        fs = s["hud"]["floats"]
        check("Three real quick hits, three floats", s["hits"] == 3 and len(fs) == 3, fs)
        check(
            "Damage and effectiveness share one line",
            all(f["text"].startswith("−") and f["suffix"] == "效果拔群!" for f in fs),
            fs,
        )
        check("Quick hits use distinct slots", [f["slot"] for f in fs] == [0, 1, 2])
        for delay in [0, 0.1, 0.1]:
            step(page, delay)
            fs = snap(page)["hud"]["floats"]
            check(
                f"Outlined float boxes pairwise disjoint t={snap(page)['elapsed']:.2f}",
                all(
                    not intersects(a["box"], b["box"])
                    for i, a in enumerate(fs)
                    for b in fs[i + 1 :]
                ),
                fs,
            )
        page.screenshot(path=str(SHOTS / "三连命中-无叠字.png"))
        reset(page)
        p = snap(page)["enemy"]
        page.evaluate(
            "(v)=>window.__waterTest.injectWater(v)",
            {
                "owner": "player",
                "move": "ember",
                "x": p["x"] - 40,
                "y": p["y"],
                "ux": 1,
                "uy": 0,
                "speed": 650,
                "range": 200,
            },
        )
        step(page, 0.07)
        fs = snap(page)["hud"]["floats"]
        check(
            "Resistance is a small suffix, not a separate float",
            len(fs) == 1 and fs[0]["suffix"] == "抵抗 · 效果不好",
            fs,
        )
        removed = ".battlehud,#playerHealth,#enemyHealth,#hits,#taken,#staminaBox,#staminaMeter"
        check("Old combat DOM panels removed", page.locator(removed).count() == 0)
        reset(page)
        step(page, 2)
        check(
            "Default HUD1 full idle stamina remains visible",
            snap(page)["hud"]["actors"][0]["stamina"]["alpha"] == 1
        )
        page.evaluate("window.__waterTest.dash('player',1,0)")
        step(page, 0.1)
        check(
            "Default HUD1 consumption keeps stamina visible",
            snap(page)["hud"]["actors"][0]["stamina"]["alpha"] == 1
        )
        check("CPU has no stamina bar", snap(page)["hud"]["actors"][1]["stamina"] is None)
        h = snap(page)["hud"]["actors"][0]
        b = h["stamina"]["box"]
        check(
            "Default desktop A stamina is the centered thin DOM resource line",
            h["stamina"]["source"] == "dom" and b["width"] == 244
            and b["height"] == 3 and b["y"] > 450
            and abs(b["x"] + b["width"] / 2 - page.viewport_size["width"] / 2) < 1,
        )
        step(page, 5)
        check(
            "Default HUD1 regenerated full stamina stays visible",
            snap(page)["hud"]["actors"][0]["stamina"]["alpha"] == 1,
        )
        page.keyboard.press("Escape")
        step(page, 0.1)
        check(
            "Pause stays DOM and retains HP numbers",
            page.locator("#matchOverlay").is_visible()
            and "血量" in page.locator("#matchDetail").inner_text(),
        )
        for width, height in [(1440, 900), (390, 844), (844, 390)]:
            page.set_viewport_size({"width": width, "height": height})
            page.wait_for_timeout(100)  # Let ResizeObserver update Canvas backing pixels.
            reset(page)
            arrange(
                page, {"player": {"x": CX - 60}, "enemy": {"x": CX + 30, "y": CY + 60}, "ai": False}
            )
            step(page, 0.5)
            alignment(page, f"{width}x{height}")
            boxes = page.evaluate("""()=>{
              const r=document.getElementById('game').getBoundingClientRect();
              return ['#battleRail','#battleMenuButton','.hud'].map(s=>{
                const b=document.querySelector(s).getBoundingClientRect();
                return {x:b.x-r.x,y:b.y-r.y,width:b.width,height:b.height};
              });
            }""")
            for h in snap(page)["hud"]["actors"]:
                b = h["box"]
                check(
                    f"{width}x{height} {h['side']} HP on screen",
                    b["x"] - 29 >= 0
                    and b["x"] + b["width"] <= width
                    and b["y"] - 4 >= 0
                    and b["y"] + b["height"] <= height,
                    b,
                )
                tag_box = {
                    **b,
                    "x": b["x"] - 29,
                    "width": b["width"] + 29,
                    "y": b["y"] - 4,
                    "height": b["height"] + 8,
                }
                check(
                    f"{width}x{height} {h['side']} no DOM UI overlap",
                    all(not intersects(tag_box, ui) for ui in boxes),
                    boxes,
                )
            page.screenshot(path=str(SHOTS / f"战斗-{width}x{height}.png"))
        reset(page)
        arrange(page, {"enemy": {"hp": 0}})
        step(page, 0.1)
        check("KO leaves final hit visible before settlement", not page.locator("#matchOverlay").is_visible())
        page.wait_for_timeout(850)
        check(
            "Settlement stays DOM with HP numbers after 0.8s",
            page.locator("#matchOverlay").is_visible()
            and "血量" in page.locator(".result-stats").inner_text()
            and " / " in page.locator(".result-stats").inner_text(),
        )
        check(
            "No horizontal overflow",
            page.evaluate("document.documentElement.scrollWidth<=innerWidth+1"),
        )
        check("No JS errors", not errors, errors)
        browser.close()
finally:
    report = {
        "candidateSHA256": hashlib.sha256((ROOT / "候选试玩.html").read_bytes()).hexdigest(),
        "passed": sum(c["ok"] for c in checks),
        "failed": sum(not c["ok"] for c in checks),
        "errors": errors,
        "checks": checks,
        "screenshots": str(SHOTS),
    }
    (OUT / "验收.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ["passed", "failed", "errors"]}, ensure_ascii=False))
