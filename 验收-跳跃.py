"""Headless jump mechanics, real hit pipeline, input, visuals and seeded AI coverage."""
import base64
import hashlib
import json
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/跳跃"
SHOTS = OUT / "截图"
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8861/").rstrip("/")
checks, errors = [], []
failure = None


def check(name, ok, detail=None):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    assert ok, (name, detail)


def snap():
    # Identical full snapshot, serialized in-page to avoid Playwright recursively
    # transporting thousands of nested objects in the 4 x 600-frame AI loop.
    raw = page.evaluate("""() => JSON.stringify(window.__waterTest.snapshot(), (key, value) =>
      typeof value === 'number' && !Number.isFinite(value)
        ? {__nonFiniteNumber: String(value)} : value)""")
    return json.loads(raw, object_hook=lambda value:
                      float(value['__nonFiniteNumber'])
                      if set(value) == {'__nonFiniteNumber'} else value)


def step(seconds):
    page.evaluate("s => window.__waterTest.step(s)", seconds)


def arrange(**value):
    page.evaluate("s => window.__waterTest.arrange(s)", value)


def jump(side="player"):
    return page.evaluate("s => window.__waterTest.jump(s)", side)


def reset(distance=150):
    page.evaluate("window.__waterTest.reset(true)")
    arrange(ai=False, player={"x": cx, "y": cy}, enemy={"x": cx + distance, "y": cy})


def shot(name):
    page.evaluate("window.__waterTest.render()")
    page.screenshot(path=str(SHOTS / name))


try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(str(e)))
        response = page.goto(URL + "/?test=1")
        check("Exact candidate served", hashlib.sha256(response.body()).digest()
              == hashlib.sha256((ROOT / "候选试玩.html").read_bytes()).digest())
        until = time.monotonic() + 45
        while time.monotonic() < until and not page.evaluate("window.__waterTest?.snapshot().artReady"):
            page.wait_for_timeout(30)
        check("Art ready", snap()["artReady"])
        catalog = page.evaluate("window.__waterTest.catalog()")
        moves = catalog["moves"]
        roster = {r["id"]: r for r in catalog["roster"]}
        profile = {**snap()["profile"], "player": 7, "enemy": 7, "shake": False,
                   "map": "emerald-rustborocity", "holdAim": False,
                   "playerMoves": roster[7]["defaultMoves"], "enemyMoves": roster[7]["defaultMoves"]}
        check("Select grounded nonimmune water fighters", page.evaluate(
            "v => window.__waterTest.select(v)", profile))
        terrain = catalog["terrains"][0]
        cols, size = terrain["columns"], terrain["cellSize"]
        walk = base64.b64decode(terrain["walkB64"])
        area = next(a for a in terrain["areas"] if a["sourceName"] == "RustboroCity")
        x, y = next((x, y)
                    for y in range(area["gridY"] + 3, area["gridY"] + area["rows"] - 3)
                    for x in range(area["gridX"] + 4, area["gridX"] + area["columns"] - 4)
                    if all(walk[(y + dy) * cols + x + dx]
                           for dy in range(-2, 3) for dx in range(-4, 5)))
        cx, cy = (x + .5) * size, (y + .5) * size
        rows = [r.split("\t") for r in (ROOT / "协作/J1/空中判定表.tsv").read_text().splitlines()]
        check("121 unique rows and boolean on every move", len(rows) == len(moves) == 121
              and len({r[0] for r in rows}) == 121
              and all(type(m["hitsAirborne"]) is bool for m in moves.values()))
        check("Table matches effective runtime kind/type/flag", all(
            r[2] == moves[r[0]]["kind"] and (r[4] == "true") == moves[r[0]]["hitsAirborne"]
            and len(r) == 7 and r[5] and float(r[6]) == moves[r[0]]["damage"] for r in rows))
        reset()
        arrange(player={"stamina": 11.99})
        page.keyboard.press("Space")
        check("Insufficient stamina blocks Space", not snap()["player"]["jumping"]
              and snap()["player"]["stamina"] == 11.99)
        arrange(player={"stamina": 100})
        page.keyboard.press("Space")
        check("Space costs exactly 12", snap()["player"]["stamina"] == 88
              and snap()["player"]["jumping"])
        check("No double jump", not jump())
        step(.059)
        check("First .06s is vulnerable", not snap()["player"]["airborne"])
        step(.001)
        check("Airborne starts at .06", snap()["player"]["airborne"])
        check("No cast or dash in air", not page.evaluate("window.__waterTest.cast('player','watergun')")
              and not page.evaluate("window.__waterTest.dash('player',1,0)"))
        reset()
        initial = snap()["player"]
        page.keyboard.down("d")
        step(.1)
        page.keyboard.up("d")
        ground = snap()["player"]["x"] - initial["x"]
        reset()
        jump()
        page.keyboard.down("d")
        step(.1)
        page.keyboard.up("d")
        ratio = (snap()["player"]["x"] - initial["x"]) / ground
        check("Air speed is 70% +/-5%", abs(ratio - .7) < .05, ratio)
        reset()
        step(1)  # Camera settles before visual comparison.
        initial = snap()["player"]
        jump()
        step(.225)
        p = snap()["player"]
        check("Parabolic apex .8 body height", abs(p["jumpHeight"] - (p["body"]["top"] + 14) * .8) < .001)
        check("Head HP rises with sprite", abs(initial["headY"] - p["headY"] - p["jumpHeight"]) < .001)
        check("Shadow stays grounded, shrinks to 60%", abs(p["shadowScale"] - .6) < .001
              and (p["x"], p["y"]) == (initial["x"], initial["y"]))
        shot("最高点-1440x900.png")
        step(.165)
        check("Final .06s is vulnerable", not snap()["player"]["airborne"])
        step(.06)
        p = snap()["player"]
        check("Lands at .45, recovery .15 and cooldown .6", not p["jumping"]
              and abs(p["landing"] - .15) < .00001 and abs(p["jumpCooldown"] - .6) < .00001, p)
        check("Landing blocks cast, dash and jump", not jump()
              and not page.evaluate("window.__waterTest.cast('player','watergun')")
              and not page.evaluate("window.__waterTest.dash('player',1,0)"))
        page.keyboard.down("d")
        step(.14)
        page.keyboard.up("d")
        check("Landing blocks movement", snap()["player"]["x"] == p["x"])
        step(.01)
        check("Recovery ends at .15; jump cooldown remains", snap()["player"]["landing"] < 1e-7 and not jump())
        step(.449)
        check("Cannot jump before .6 after landing", not jump())
        step(.001)
        check("Can jump exactly .6 after landing", jump())
        reset()
        check("Desktop hides touch jump button", not page.locator("#jumpButton").is_visible())
        page.keyboard.press("Space")
        check("Desktop Space still starts jump", snap()["player"]["jumping"])

        groups = {
            "小型弹体": (False, ["watergun", "bubble", "ember", "thundershock"]),
            "大型弹体": (True, ["fireblast", "shadowball", "poisongas"]),
            "近身": (False, ["brickbreak", "dragonclaw", "irontail", "crunch"]),
            "突进": (False, ["quickattack", "bodyslam"]),
            "地面": (False, ["earthquake", "bulldoze", "earthpower"]),
            "从天而降": (True, ["thunder", "rockslide", "blizzard", "stoneedge"]),
            "光束大浪": (True, ["thunderbolt", "hyperbeam", "surf", "hydropump"]),
            "飞行": (True, ["airslash", "wingattack", "bravebird", "gust"]),
        }
        for category, (expected, ids) in groups.items():
            for mid in ids:
                check(category + "/" + mid + " data", moves[mid]["hitsAirborne"] == expected)
                for age in [.03, .225, .41]:
                    reset()
                    jump()
                    step(age)
                    hp = snap()["player"]["hp"]
                    hit = page.evaluate("m => window.__waterTest.injectMoveHit('player',m)", mid)
                    want = expected or age != .225
                    check(f"{mid} real damage pipeline @{age}", hit == want
                          and (snap()["player"]["hp"] < hp) == want)

        # Actual casts and emitted projectiles: damage must change while still airborne.
        for mid in ["fireblast", "shadowball", "watergun", "thundershock"]:
            reset(100)
            page.evaluate("m => window.__waterTest.equip('enemy',[m])", mid)
            step(1)
            check(mid + " actual cast", page.evaluate(
                "m => window.__waterTest.cast('enemy',m)", mid))
            step(moves[mid]["windup"] + .001)
            check(mid + " actual projectile emitted", bool(snap()["bullets"]))
            b = snap()["bullets"][0]
            step(max(0, (b["x"] - cx - moves[mid]["radius"] - 20) / b["speed"] - .15))
            check(mid + " start jump before arrival", jump())
            hp = snap()["player"]["hp"]
            hit_in_air = False
            for _ in range(30):
                step(.01)
                state = snap()["player"]
                if state["hp"] < hp:
                    hit_in_air = state["airborne"]
                    break
            expected = mid in {"fireblast", "shadowball"}
            check(mid + " arrival while airborne damage rule",
                  hit_in_air if expected else snap()["player"]["hp"] == hp,
                  {"beforeHP": hp, "player": snap()["player"], "bullets": snap()["bullets"], "emitted": b})

        # Real projectiles must pass through without removal, hit flashes or floats.
        reset()
        step(1)
        jump()
        step(.15)
        hp = snap()["player"]["hp"]
        page.evaluate("s => window.__waterTest.injectWater(s)", {
            "x": cx - 40, "y": cy, "ux": 1, "uy": 0, "speed": 550})
        step(.075)
        p = snap()
        check("Water passes under apex without hit/float/removal", p["player"]["hp"] == hp
              and len(p["bullets"]) == 1 and not p["floats"] and p["taken"] == 0)
        step(.09)
        check("Water continues past target", snap()["bullets"][0]["x"] > cx + 40)
        # Screenshot uses an actual emitted raster water stream, not the minimal injected fixture.
        reset(100)
        step(1)
        check("Real watergun cast", page.evaluate("window.__waterTest.cast('enemy','watergun')"))
        step(moves["watergun"]["windup"] + .001)
        b = snap()["bullets"][0]
        until_cross = (b["x"] - cx) / moves["watergun"]["speed"]
        step(max(0, until_cross - .225))
        jump()
        step(.225)
        check("Real water stream crosses airborne feet", snap()["player"]["hp"] == snap()["player"]["maxHP"]
              and len(snap()["bullets"]) == 1 and abs(snap()["bullets"][0]["x"] - cx) < 3)
        shot("水枪从脚下穿过-1440x900.png")

        # Real nova emission and warning canvas, not only injected hits.
        reset(55)
        page.evaluate("window.__waterTest.equip('enemy',['earthquake'])")
        step(1)
        check("Enemy casts earthquake", page.evaluate("window.__waterTest.cast('enemy','earthquake')"))
        step(moves["earthquake"]["windup"] - .15)
        jump()
        step(.1)
        warning = next(w for w in snap()["warnings"] if w["id"] == "earthquake")
        check("Jump-safe warning marked", warning["jumpSafe"])
        probe = page.evaluate("""() => {
          const c = document.querySelector('#game').getContext('2d');
          const old = c.stroke, text = c.fillText, strokes = [], labels = [], boxes = [];
          c.stroke = function(...a) { strokes.push([this.strokeStyle,this.getLineDash()]);
            return old.apply(this,a); };
          c.fillText = function(s,...a) {
            labels.push(s);
            if (['这招跳得过','1P','CPU'].includes(s)) {
              const m = this.measureText(s), t = this.getTransform(),
                r = this.canvas.getBoundingClientRect(),
                w = m.width, h = m.actualBoundingBoxAscent + m.actualBoundingBoxDescent,
                x = a[0] - w / 2, y = a[1] - m.actualBoundingBoxAscent,
                q = t.transformPoint({x,y});
              boxes.push({text:s,x:q.x*r.width/this.canvas.width,
                y:q.y*r.height/this.canvas.height,
                width:w*t.a*r.width/this.canvas.width,
                height:h*t.d*r.height/this.canvas.height});
            }
            return text.call(this,s,...a);
          };
          try {window.__waterTest.render();} finally {c.stroke=old; c.fillText=text;}
          return {strokes,labels,boxes};
        }""")
        check("Actual brown nova dashed border and jump-safe hint drawn",
              ["#d6af62", [7, 5]] in probe["strokes"]
              and "这招跳得过" in probe["labels"])
        hint = next(b for b in probe["boxes"] if b["text"] == "这招跳得过")
        heads = [b for b in probe["boxes"] if b["text"] != "这招跳得过"]
        heads += [a["box"] for a in snap()["hud"]["actors"]]
        check("Hint pixel bounding box disjoint from every head label/HP bar", all(
            hint["x"] + hint["width"] <= b["x"] or b["x"] + b["width"] <= hint["x"]
            or hint["y"] + hint["height"] <= b["y"] or b["y"] + b["height"] <= hint["y"]
            for b in heads), {"hint": hint, "heads": heads})
        shot("地震预警-1440x900.png")
        hp = snap()["player"]["hp"]
        step(.125)
        check("Real earthquake misses airborne", snap()["player"]["hp"] == hp
              and snap()["generated"]["emitted"] > 0)
        shot("地震时跳起-1440x900.png")

        reset()
        page.evaluate("r => window.__waterTest.grassRegions(r)", [
            {"x": cx - 35, "y": cy - 35, "width": 70, "height": 70}])
        step(.8)
        check("Grass hidden prerequisite", snap()["player"]["stealth"]["hidden"])
        page.keyboard.press("Space")
        check("Space immediately reveals grass actor", snap()["player"]["jumping"]
              and not snap()["player"]["stealth"]["hidden"])
        step(.2)
        check("Cannot rehide midair", not snap()["player"]["stealth"]["hidden"])
        water = base64.b64decode(terrain["waterB64"])
        i = next(i for i in range(cols, len(water) - cols)
                 if all(water[i + dx + dy * cols] for dx in [-1, 0, 1] for dy in [-1, 0, 1]))
        reset()
        arrange(player={"x": (i % cols + .5) * size, "y": (i // cols + .5) * size})
        check("Dive starts in water", page.evaluate("window.__waterTest.dive()"))
        sp = snap()["player"]["stamina"]
        page.keyboard.press("Space")
        check("Space in dive has no effect or cost", snap()["player"]["diving"]
              and not snap()["player"]["jumping"] and snap()["player"]["stamina"] == sp)

        flying = next(r for r in roster.values() if r.get("flightHeight"))
        check("Select flying actor", page.evaluate("v => window.__waterTest.select(v)", {
            **profile, "player": flying["id"], "playerMoves": flying["defaultMoves"]}))
        reset()
        base_height = snap()["player"]["flightHeight"]
        check("Flying actor jumps normally", jump())
        step(.225)
        check("Flying baseline plus jump lift", snap()["player"]["flightHeight"] > base_height + 15
              and snap()["player"]["airborne"])
        check("Flying actor follows same airborne hit rule", not page.evaluate(
            "window.__waterTest.injectMoveHit('player','watergun')"))
        page.evaluate("v => window.__waterTest.select(v)", profile)

        # Deterministic game PRNG; normal decision path, no force-jump or probability patch.
        reset()
        page.evaluate("window.__waterTest.equip('enemy',['splash'])")
        arrange(ai=True, tier="master")
        step(10)
        check("AI does not jump without incoming threats", snap()["enemy"]["jumps"] == 0)
        for mid in ["fireblast", "shadowball"]:
            reset()
            page.evaluate("window.__waterTest.equip('enemy',['splash'])")
            arrange(ai=True, tier="master")
            for _ in range(20):
                state = snap()
                arrange(enemy={"x": cx + 100, "y": cy, "hp": state["enemy"]["maxHP"]})
                page.evaluate("s => window.__waterTest.injectWater(s)", {
                    "move": mid, "owner": "player", "x": cx - 120, "y": cy,
                    "ux": 1, "uy": 0, "speed": 250, "range": 600})
                step(.5)
            check(mid + " AI never jumps for large projectile", snap()["enemy"]["jumps"] == 0)
        ai_results = []
        for tier in catalog["tiers"]:
            reset()
            page.evaluate("window.__waterTest.equip('enemy',['splash'])")
            arrange(ai=True, tier=tier["id"])
            last_jumps, last_time, events = 0, -10, []
            for frame in range(600):  # 60 simulation seconds, incoming visible threats every .5s.
                state = snap()
                e = state["enemy"]
                if frame % 5 == 0:
                    arrange(player={"x": cx - 120, "y": cy, "hp": state["player"]["maxHP"]},
                            enemy={"x": cx + 100, "y": cy, "hp": e["maxHP"]})
                    page.evaluate("s => window.__waterTest.injectWater(s)", {
                        "owner": "player", "x": cx - 120, "y": cy, "ux": 1, "uy": 0,
                        "speed": 250, "range": 600})
                step(.1)
                state = snap()
                e = state["enemy"]
                if e["jumps"] > last_jumps:
                    when = state["elapsed"] - e["jumpAge"]
                    check(tier["id"] + " AI respects jump duration + cooldown", when - last_time >= 1.05 - 1e-6)
                    events.append(when)
                    last_jumps, last_time = e["jumps"], when
            check(tier["id"] + " AI jumps within 60s", bool(events), events)
            ai_results.append({"tier": tier["id"], "jumps": len(events), "times": events})
        (OUT / "AI跳跃.json").write_text(json.dumps(ai_results, ensure_ascii=False, indent=2) + "\n")
        for width, height in [(390, 844), (844, 390)]:
            page.set_viewport_size({"width": width, "height": height})
            reset()
            step(1)
            page.keyboard.press("Space")
            step(.225)
            check(f"{width}x{height} desktop Space usable", snap()["player"]["airborne"])
            check(f"{width}x{height} no overflow", page.evaluate("document.documentElement.scrollWidth<=innerWidth+1"))
            shot(f"最高点-{width}x{height}.png")
        touch_context = browser.new_context(viewport={"width": 390, "height": 844},
                                            has_touch=True, is_mobile=True)
        touch_page = touch_context.new_page()
        touch_page.on("pageerror", lambda e: errors.append(str(e)))
        touch_page.goto(URL + "/?test=1")
        for _ in range(600):
            if touch_page.evaluate("window.__waterTest?.snapshot().artReady"):
                break
            time.sleep(.025)
        check("Touch portrait shows rotation prompt", touch_page.locator("#rotatePhone").is_visible())
        touch_page.set_viewport_size({"width": 844, "height": 390})
        touch_page.wait_for_timeout(100)
        touch_page.evaluate("window.__waterTest.reset(true)")
        touch_page.locator("#jumpButton").tap()
        touch_page.evaluate("window.__waterTest.step(.225)")
        check("Touch landscape pointer button starts actual airborne jump",
              touch_page.evaluate("window.__waterTest.snapshot().player.airborne"))
        touch_context.close()
        check("No JS errors", not errors, errors)
        browser.close()
except Exception as exc:  # noqa: BLE001 - Always persist the failing acceptance report.
    failure = str(exc)
finally:
    report = {"passed": sum(c["ok"] for c in checks), "failed": sum(not c["ok"] for c in checks)
              + int(bool(failure) and all(c["ok"] for c in checks)),
              "jsErrors": len(errors), "errors": errors, "failure": failure, "checks": checks}
    (OUT / "报告.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
if failure or errors:
    raise SystemExit(1)
