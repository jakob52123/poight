"""T2: real browser input, shared telegraphs, hitstop and swept body knockback."""

import base64
import hashlib
import json
import math
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/打击感瞄准"
SHOTS = OUT / "截图"
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8822/").rstrip("/")
checks, errors, screenshots = [], [], []


def check(name, ok, detail=None):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    assert ok, (name, detail)


def ready(page):
    for _ in range(500):
        if page.evaluate("window.__waterTest?.snapshot().artReady"):
            return
        time.sleep(0.02)
    raise TimeoutError("art ready")


def snap():
    return p.evaluate("window.__waterTest.snapshot()")


def step(seconds):
    p.evaluate("n => window.__waterTest.step(n)", seconds)


def reset(a=7, b=143, distance=100):
    profile = {
        **default,
        "player": a,
        "enemy": b,
        "playerMoves": roster[a]["defaultMoves"],
        "enemyMoves": roster[b]["defaultMoves"],
        "shake": True,
        "holdAim": True,
    }
    p.evaluate("v => window.__waterTest.select(v)", profile)
    p.evaluate("window.__waterTest.reset(true)")
    p.evaluate(
        "v => window.__waterTest.arrange(v)",
        {
            "ai": False,
            "player": {"x": CX, "y": CY, "hp": 50},
            "enemy": {"x": CX + distance, "y": CY},
        },
    )
    step(1)
    p.locator("#game").focus()


def equip(move, side="player"):
    ids = [move] + [
        m for m in ["watergun", "protect", "agility", "brickbreak"] if m != move
    ][:3]
    p.evaluate("v => window.__waterTest.equip(...v)", [side, ids])


def cast(move, side="player"):
    return p.evaluate("v => window.__waterTest.cast(...v)", [side, move])


def hit(amount=10, side="enemy", dx=1, dy=0):
    p.evaluate("v => window.__waterTest.testDamage(...v)", [side, amount, dx, dy])


def shot(name):
    path = SHOTS / (name + ".png")
    p.evaluate("window.__waterTest.render()")
    p.screenshot(path=str(path))
    screenshots.append(str(path))


def signature(s):
    return [
        (s[k]["x"], s[k]["y"], s[k]["anim"], s[k]["animFrame"], s[k]["cool"])
        for k in ["player", "enemy"]
    ] + [s["bullets"], s["generated"]["states"], s["elapsed"]]


try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        p = browser.new_page(viewport={"width": 1440, "height": 900})
        p.on("pageerror", lambda e: errors.append(str(e)))
        p.goto(URL + "/?test=1")
        ready(p)
        c = p.evaluate("window.__waterTest.catalog()")
        roster = {m["id"]: m for m in c["roster"]}
        moves = c["moves"]
        default = {**snap()["profile"], "map": "emerald-rustborocity"}
        terrain = c["terrains"][0]
        cols = terrain["columns"]
        walk = base64.b64decode(terrain["walkB64"])
        area = next(a for a in terrain["areas"] if a["sourceName"] == "RustboroCity")
        lane = next(
            (x, y)
            for y in range(area["gridY"] + 3, area["gridY"] + area["rows"] - 3)
            for x in range(area["gridX"] + 4, area["gridX"] + area["columns"] - 4)
            if all(
                walk[(y + dy) * cols + x + dx]
                for dy in range(-2, 3)
                for dx in range(-4, 5)
            )
        )
        CX, CY = (lane[0] + 0.5) * 48, (lane[1] + 0.5) * 48

        # Hit the actual damage pipeline, leave another projectile in flight.
        durations = []
        for amount in [10, 30]:
            reset()
            p.evaluate(
                "v => window.__waterTest.injectWater(v)",
                {
                    "owner": "player",
                    "x": CX - 60,
                    "y": CY + 60,
                    "ux": 1,
                    "uy": 0,
                    "speed": 100,
                },
            )
            p.keyboard.down("KeyS")
            hit(amount)
            before = snap()
            durations.append(before["feel"]["remaining"])
            step(0.03)
            check(
                f"{amount}: actors/animation/cooldown/projectiles frozen at 30ms",
                signature(snap()) == signature(before),
                {"before": before, "after": snap()},
            )
            check(
                f"{amount}: nonzero decaying shake",
                0
                < math.hypot(*snap()["feel"]["offset"].values())
                < (3 if amount == 10 else 6),
            )
            step(0.12)
            check(
                f"{amount}: simulation resumes at 150ms",
                snap()["elapsed"] > before["elapsed"]
                and snap()["player"]["y"] > before["player"]["y"],
            )
            p.keyboard.up("KeyS")
            step(0.15)
            check(
                f"{amount}: shake zero by 300ms",
                snap()["feel"]["offset"] == {"x": 0, "y": 0},
            )
        check("60ms light / 100ms heavy", durations == [0.06, 0.1], durations)
        reset()
        p.evaluate("window.__waterTest.feedbackHit(1,2)")
        check(
            "Super-effective light damage counts as heavy",
            snap()["feel"]["remaining"] == 0.1,
        )
        p.evaluate(
            "window.__waterTest.feedbackHit(1,1);window.__waterTest.feedbackHit(30,1)"
        )
        check(
            "Same-frame impacts use max, never sum", snap()["feel"]["remaining"] == 0.1
        )
        p.evaluate("document.getElementById('shakeSetting').click()")
        step(0.3)
        hit()
        offsets = []
        for _ in range(40):
            offsets.append(snap()["feel"]["offset"])
            step(0.01)
        check(
            "Shake off: all offsets remain zero",
            all(v == {"x": 0, "y": 0} for v in offsets),
        )
        check(
            "Shake persisted in existing profile",
            not p.evaluate(
                "JSON.parse(localStorage.getItem('pocket-arena-loadout-v1')).shake"
            ),
        )
        p.reload()
        ready(p)
        check("Reload restores shake setting", not snap()["profile"]["shake"])
        reset()
        p.evaluate("window.__waterTest.arrange({enemy:{hp:1}})")
        hit(10)
        step(0.3)
        check(
            "Lethal-hit shake also decays at match end",
            snap()["phase"] == "over" and snap()["feel"]["offset"] == {"x": 0, "y": 0},
        )

        distances = []
        for target in [25, 143]:
            reset(b=target)
            x = snap()["enemy"]["x"]
            hit(20)
            step(1)
            distances.append(snap()["enemy"]["x"] - x)
        check(
            "Same damage: Pikachu/Snorlax knockback >=1.6",
            distances[0] / distances[1] >= 1.6,
            distances,
        )
        reset(b=25)
        x = snap()["enemy"]["x"]
        hit(40)
        step(1)
        check(
            "Knockback capped at 40 world pixels",
            39 < snap()["enemy"]["x"] - x <= 40.0001,
        )
        wall = next(
            (x, y)
            for y in range(area["gridY"] + 2, area["gridY"] + area["rows"] - 2)
            for x in range(area["gridX"] + 3, area["gridX"] + area["columns"] - 2)
            if not walk[y * cols + x] and all(walk[y * cols + x - d] for d in [1, 2, 3])
        )
        for target in [25, 143]:
            reset(b=target)
            r = snap()["enemy"]["body"]["moveRadius"]
            p.evaluate(
                "v => window.__waterTest.arrange(v)",
                {
                    "enemy": {"x": wall[0] * 48 - r - 2, "y": (wall[1] + 0.5) * 48},
                },
            )
            hit(30)
            step(0.6)
            s = snap()["enemy"]
            check(
                f"{target}: knockback respects body footprint at wall",
                s["x"] <= wall[0] * 48 - r + 0.01
                and p.evaluate(
                    "v => window.__waterTest.freeAt(...v)", [s["x"], s["y"], r]
                ),
            )

        # All 120 runtime move records, including generated overrides, not legacy kinds.
        kinds, saved_shapes = set(), set()
        for move, m in moves.items():
            reset(distance=100)
            equip(move)
            check(move + ": begins", cast(move))
            warnings = snap()["warnings"]
            if m["windup"] == 0:
                check(move + ": no artificial windup/telegraph", not warnings)
                continue
            kinds.add(m["kind"])
            s = warnings[0]
            check(
                move + ": warning throughout windup",
                s["kind"] == m["kind"] and abs(s["remaining"] - m["windup"]) < 1e-6,
            )
            if s["shape"] in ["strip", "fan"]:
                check(
                    move + ": actual range preserved",
                    all(abs(r["length"] - (
                        min(m["range"], roster[7]["body"]["nominalSize"] * m["rangeBodies"])
                        if any(m.get(flag) for flag in ("hero", "limb", "batch2", "r3")) else m["range"]
                    )) < 2 for r in s["rays"]),
                )
                if m["kind"] == "fan":
                    check(
                        move + ": actual pellet angles",
                        len(s["rays"]) == m.get("count", 3)
                        and abs(s["halfAngle"] - (len(s["rays"]) - 1) * 0.08) < 1e-8,
                    )
            if move == "fireblast":
                check(
                    "Fire Blast is straight projectile, not target circle",
                    s["shape"] == "strip" and s["projectile"],
                )
            if move == "agility":
                check(
                    "Agility buff telegraphs its actual forward displacement",
                    s["shape"] == "strip"
                    and not s["projectile"]
                    and s["length"] == m["range"],
                )
                shot("预警-strip-agility")
            if move == "earthquake":
                check(
                    "Earthquake uses caster-centered ground ring (damage keeps 3x3 grid)",
                    s["shape"] == "ground-ring" and abs(s["radius"] - math.hypot(72, 72)) < 1e-8
                    and s["x"] == snap()["player"]["x"] and s["y"] == snap()["player"]["y"],
                )
            if (s["shape"] not in saved_shapes and not s.get("support")) or move in [
                "rapidspin",
                "discharge",
            ]:
                shot("预警-" + s["shape"] + "-" + move)
                saved_shapes.add(s["shape"])
            step(max(0, m["windup"] - 0.04))
            check(move + ": warning remains until release", bool(snap()["warnings"]))
            step(0.041)
            after = snap()
            check(move + ": warning ends on emission", not after["warnings"])
            if m["kind"] == "zone":
                actual = after["zones"] or [
                    v for v in after["generated"]["states"] if v["id"] == move
                ]
                check(
                    move + ": actual landing center/radius equals warning",
                    bool(actual)
                    and math.hypot(
                        actual[0].get("ex", actual[0]["x"]) - s["x"],
                        actual[0].get("ey", actual[0]["y"]) - s["y"],
                    )
                    < 4
                    and actual[0]["radius"] == s["radius"],
                    actual,
                )
            elif s["shape"] in ["strip", "fan"] and after["bullets"]:
                bullet = after["bullets"][0]
                check(
                    move + ": emitted trajectory equals telegraph",
                    any(
                        abs(
                            bullet["range"]
                            + bullet["age"] * bullet["speed"]
                            - ray["length"]
                        )
                        < 2
                        and math.hypot(
                            bullet["x"]
                            - bullet["ux"] * bullet["speed"] * bullet["age"]
                            - ray["x"],
                            bullet["y"]
                            - bullet["uy"] * bullet["speed"] * bullet["age"]
                            - ray["y"],
                        )
                        < 2
                        for ray in s["rays"]
                    ),
                )
        check(
            "Every kind covered",
            kinds == {m["kind"] for m in moves.values()},
            sorted(kinds),
        )
        reset()
        equip("watergun", "enemy")
        cast("watergun", "enemy")
        check("CPU has red-side warning", snap()["warnings"][0]["player"] is False)
        shot("电脑红色预警")

        # Real desktop mouse/key events: no direction injection hook.
        reset()
        equip("watergun")
        rect = p.locator("#game").bounding_box()
        s = snap()
        mx = (
            rect["x"]
            + (s["player"]["x"] - round(s["camera"]["x"]))
            / s["viewport"]["width"]
            * rect["width"]
        )
        my = (
            rect["y"]
            + (s["player"]["y"] - round(s["camera"]["y"]) + 80)
            / s["viewport"]["height"]
            * rect["height"]
        )
        p.mouse.move(mx, my)
        p.mouse.down(button="right")
        p.keyboard.down("KeyJ")
        step(0.3)
        check(
            "Right modifier enters aim without cost/CD",
            snap()["aim"]["active"]
            and snap()["player"]["cool"]["watergun"] == 0
            and snap()["player"]["spent"] == 0,
        )
        shot("按住瞄准-桌面1440x900")
        p.keyboard.up("KeyJ")
        step(moves["watergun"]["windup"] + 0.02)
        bullets = snap()["bullets"]
        check(
            "Release fires downward within 10 degrees",
            bool(bullets)
            and abs(math.atan2(bullets[0]["uy"], bullets[0]["ux"]) - math.pi / 2)
            < math.radians(10),
            bullets,
        )

        p.mouse.up(button="right")
        reset()
        equip("watergun")
        p.mouse.down(button="right")
        p.keyboard.down("KeyJ")
        step(0.3)
        p.keyboard.down("KeyS")
        start = snap()["player"]
        step(0.2)
        end = snap()["player"]
        p.keyboard.up("KeyS")
        check(
            "Aiming walks at 60% normal speed",
            abs((end["y"] - start["y"]) / (start["speed"] * 0.2) - 0.6) < 0.05,
        )
        before = snap()["player"]
        p.keyboard.press("Escape")
        p.keyboard.up("KeyJ")
        step(0.01)
        check(
            "Esc cancels for free without pausing",
            snap()["aim"] is None
            and snap()["phase"] == "playing"
            and snap()["player"]["stamina"] == before["stamina"]
            and snap()["player"]["cool"] == before["cool"],
        )
        p.keyboard.down("KeyJ")
        step(0.3)
        p.mouse.up(button="right")
        p.keyboard.up("KeyJ")
        check(
            "Right release fires exactly once",
            snap()["aim"] is None and snap()["player"]["spent"] == moves["watergun"]["cost"],
        )

        reset()
        equip("watergun")
        p.keyboard.down("KeyJ")
        step(0.03)
        p.keyboard.up("KeyJ")
        step(0.01)
        s = snap()
        expected = math.atan2(
            s["enemy"]["y"] - s["player"]["y"], s["enemy"]["x"] - s["player"]["x"]
        )
        check(
            "Tap retains automatic target direction",
            abs(s["player"]["attack"]["aim"] - expected) < 1e-6,
        )
        # Cooldown/not enough stamina preserve normal rejection/buffer, no aiming state.
        p.keyboard.down("KeyJ")
        step(0.3)
        check("Cooldown cannot enter aim", snap()["aim"] is None)
        p.keyboard.up("KeyJ")
        reset()
        p.evaluate("window.__waterTest.arrange({player:{stamina:0}})")
        p.keyboard.down("KeyJ")
        step(0.19)
        check("Insufficient stamina cannot enter aim", snap()["aim"] is None)
        p.keyboard.up("KeyJ")

        reset()
        equip("watergun")
        step(1.1)  # stale mouse -> held direction
        p.mouse.down(button="right")
        p.keyboard.down("KeyJ")
        p.keyboard.down("KeyW")
        step(0.3)
        check(
            "Stale mouse falls back to direction key",
            abs(snap()["aim"]["angle"] + math.pi / 2) < 1e-6,
        )
        p.keyboard.up("KeyW")
        p.keyboard.press("Escape")
        p.keyboard.up("KeyJ")
        p.keyboard.down("KeyJ")
        step(0.3)
        s = snap()
        check(
            "No direction falls back to auto target",
            abs(
                s["aim"]["angle"]
                - math.atan2(
                    s["enemy"]["y"] - s["player"]["y"],
                    s["enemy"]["x"] - s["player"]["x"],
                )
            )
            < 1e-6,
        )
        p.keyboard.press("Escape")
        p.keyboard.up("KeyJ")

        p.mouse.up(button="right")
        reset()
        equip("watergun")
        p.evaluate("window.__waterTest.feedbackHit(30)")
        p.keyboard.press("KeyJ")
        step(0.03)
        check("Input buffers during hitstop", snap()["player"]["attack"] is None)
        step(0.08)
        check(
            "Buffered tap executes after hitstop",
            snap()["player"]["attack"]["id"] == "watergun",
        )
        reset()
        p.evaluate("window.__waterTest.feedbackHit(30)")
        before = snap()
        p.keyboard.press("KeyD")
        step(0.03)
        p.keyboard.press("KeyD")
        check(
            "Double-tap buffers without changing frozen animation or stamina",
            signature(snap()) == signature(before)
            and snap()["player"]["spent"] == 0,
        )
        step(0.08)
        check(
            "Buffered dash executes when simulation resumes",
            snap()["player"]["dashing"] and snap()["player"]["spent"] == 15,
        )
        reset()
        p.evaluate("document.getElementById('aimSetting').click()")
        p.keyboard.down("KeyJ")
        step(0.02)
        check(
            "Setting off restores immediate auto cast",
            snap()["aim"] is None and snap()["player"]["attack"] is not None,
        )
        p.keyboard.up("KeyJ")
        check(
            "Aim setting persisted",
            not p.evaluate(
                "JSON.parse(localStorage.getItem('pocket-arena-loadout-v1')).holdAim"
            ),
        )

        # Touch pointer capture with actual Chromium touch events on mobile viewports.
        for width, height in [(390, 844), (844, 390)]:
            p.set_viewport_size({"width": width, "height": height})
            reset()
            equip("watergun")
            r = p.locator("#water").bounding_box()
            x, y = r["x"] + r["width"] / 2, r["y"] + r["height"] / 2
            session = p.context.new_cdp_session(p)

            def touch(kind, tx=x, ty=y, session=session):
                session.send(
                    "Input.dispatchTouchEvent",
                    {
                        "type": kind,
                        "touchPoints": []
                        if kind == "touchEnd"
                        else [{"x": tx, "y": ty}],
                    },
                )

            touch("touchStart")
            step(0.3)
            touch("touchMove", x - 65, y - 65)
            step(0.01)
            check(
                f"Touch hold/drag {width}x{height}",
                snap()["aim"]["active"]
                and abs(snap()["aim"]["angle"] + math.pi * 0.75) < 1e-5,
            )
            shot(f"按住瞄准-手机{width}x{height}")
            touch("touchEnd")
            step(0.01)
            check(
                f"Touch release casts once {width}x{height}",
                snap()["player"]["spent"] == moves["watergun"]["cost"],
            )
            reset()
            touch("touchStart")
            step(0.3)
            touch("touchMove", x - 60, y - 60)
            touch("touchMove", x, y)
            touch("touchEnd")
            step(0.01)
            check(
                f"Touch return-to-center cancels {width}x{height}",
                snap()["player"]["spent"] == 0 and snap()["player"]["attack"] is None,
            )
            session.detach()
        check("No JS errors", not errors, errors)
        browser.close()
finally:
    report = {
        "candidateSHA256": hashlib.sha256(
            (ROOT / "候选试玩.html").read_bytes()
        ).hexdigest(),
        "passed": sum(q["ok"] for q in checks),
        "failed": sum(not q["ok"] for q in checks),
        "jsErrors": len(errors),
        "errors": errors,
        "checks": checks,
        "screenshots": screenshots,
    }
    (OUT / "浏览器验收.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {k: report[k] for k in ["passed", "failed", "jsErrors"]}, ensure_ascii=False
        )
    )
