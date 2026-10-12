"""Original Route110 two-layer movement and live keyboard/AI in the full Hoenn world."""
import base64
import hashlib
import json
import math
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/桥梁通行"
SHOTS = OUT / "截图"
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8863/").rstrip("/")
checks, errors, journey = [], [], []
failure = None


def check(name, ok, detail=None):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    assert ok, (name, detail)


def snap(page):
    return page.evaluate("window.__waterTest.snapshot()")


def step(page, seconds):
    page.evaluate("s=>window.__waterTest.step(s)", seconds)


def arrange(page, **spec):
    page.evaluate("s=>window.__waterTest.arrange(s)", spec)


try:
    catalog = json.loads((ROOT / "素材/绿宝石场景/场景目录.json").read_text())
    t = catalog["terrains"][0]
    n, s = t["columns"], t["cellSize"]
    route = next(a for a in t["areas"] if a["sourceName"] == "Route110")
    gx, gy = route["gridX"], route["gridY"]
    masks = {k: base64.b64decode(t["bridges"][k + "B64"])
             for k in ["deck", "land", "water", "gateway"]}
    collision, elevation, behavior = [base64.b64decode(t[k + "B64"])
                                      for k in ["collision", "elevation", "behavior"]]
    route_cells = {(gy + y) * n + gx + x for y in range(route["rows"])
                   for x in range(route["columns"])}
    for key, mask in masks.items():
        check(key + " retains original collision=0 and bridge behavior",
              all(not v or (collision[i] == 0 and behavior[i] in {0x70, 0x7f})
                  for i, v in enumerate(mask) if i in route_cells))
    check("Deck only original heights 0/4/15; transitions only height 0",
          all(not v or elevation[i] in {0, 4, 15} for i, v in enumerate(masks["deck"]) if i in route_cells)
          and sum(masks["gateway"]) == 4
          and all(not v or elevation[i] == 0 for i, v in enumerate(masks["gateway"])))
    index = json.loads((ROOT / "素材/绿宝石场景/地图索引.json").read_text())
    events = next(m["warp_events"] for m in index["maps"] if m["id"] == route["id"])
    for gate in t["bridges"]["gates"]:
        a, b = events[gate["sourceEvent"]], events[gate["targetEvent"]]
        check("Gate shortcut pairs original two outside doors " + str(gate["sourceEvent"]),
              a["dest_map"] == b["dest_map"] == gate["gateMap"]
              and gate["from"] == (gy + a["y"] + 1) * n + gx + a["x"]
              and gate["to"] == (gy + b["y"] + 1) * n + gx + b["x"])
        for event in [a, b]:
            at = (gy + event["y"]) * n + gx + event["x"]
            check("Animated original gate door remains a wall", collision[at] == 1
                  and behavior[at] == 0x69 and not masks["deck"][at])
    check("W2 49 outdoors + independent city + 2 interiors retain bridge layers",
          len(t["areas"]) == 49 and sum(len(q["areas"]) for q in catalog["terrains"]) == 52
          and all("bridges" in q for q in catalog["terrains"]))

    def point(x, y, upper=None):
        q = {"x": (gx + x + .5) * s, "y": (gy + y + .5) * s}
        if upper is not None:
            q["onBridge"] = upper
        return q

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        p = browser.new_page(viewport={"width": 1440, "height": 900})
        p.on("pageerror", lambda e: errors.append(str(e)))
        p.goto(URL + "/?test=1", wait_until="load")
        deadline = time.monotonic() + 30
        while not p.evaluate("window.__waterTest?.snapshot().artReady"):
            assert time.monotonic() < deadline, "artReady timeout"
            time.sleep(.03)
        roster = {c["id"]: c for c in p.evaluate("window.__waterTest.catalog().roster")}
        check("Select fast grounded Pikachu", p.evaluate("v=>window.__waterTest.select(v)", {
            **snap(p)["profile"], "player": 25, "enemy": 25, "tier": "master",
            "map": "emerald-littleroottown", "playerMoves": roster[25]["defaultMoves"],
            "enemyMoves": roster[25]["defaultMoves"],
        }))

        def reset(q):
            p.evaluate("window.__waterTest.reset(true)")
            arrange(p, ai=False, player=q, enemy=point(4, 90, False))

        presses = {}

        def walk(q, label):
            before = snap(p)["player"]
            dx, dy = q["x"] - before["x"], q["y"] - before["y"]
            assert abs(dx) < .01 or abs(dy) < .01, (label, dx, dy)
            key = ("d" if dx > 0 else "a") if abs(dx) > .01 else ("s" if dy > 0 else "w")
            duration = math.hypot(dx, dy) / before["speed"]
            clock = snap(p)["elapsed"]
            if key in presses and clock - presses[key] <= .25:
                step(p, .26)  # Avoid a real double-tap dash on the short apron segment.
            presses[key] = snap(p)["elapsed"]
            p.keyboard.down(key)
            left = duration
            while left > 1e-7:
                dt = min(.08, left)
                old = snap(p)["player"]
                step(p, dt)
                new = snap(p)["player"]
                check(label + " advances each swept segment",
                      math.hypot(new["x"] - old["x"], new["y"] - old["y"]) > .01)
                left -= dt
            p.keyboard.up(key)
            after = snap(p)["player"]
            check(label + " reaches target without sticking",
                  math.hypot(after["x"] - q["x"], after["y"] - q["y"]) < .02,
                  {"target": q, "actual": {k: after[k] for k in ["x", "y", "onBridge", "swimming"]}})
            journey.append({"label": label, "elapsed": snap(p)["elapsed"],
                            "x": after["x"], "y": after["y"], "onBridge": after["onBridge"]})

        for x, y, target_x in [(16, 90, 19), (19, 90, 16),
                                (15, 18, 18), (18, 18, 15)]:
            reset(point(x, y, False))
            before = snap(p)["player"]
            p.keyboard.down("w")
            step(p, .2)
            p.keyboard.up("w")
            after = snap(p)["player"]
            check(f"Walk original gatehouse shortcut {x},{y}->{target_x}",
                  abs(after["x"] - point(target_x, y)["x"]) < .01
                  and not after["onBridge"] and after["hp"] == before["hp"], after)
            step(p, .4)
            check("Gate arrival lock prevents immediate bounce", snap(p)["player"]["x"] == after["x"])
        reset(point(28, 92, False))
        step(p, 1)  # Camera follows arranged bridgehead; AI remains disabled.
        p.screenshot(path=str(SHOTS / "桥头-1440x900.png"))
        started = snap(p)["elapsed"]
        checkpoints = [(28, 91), (28, 86), (28, 85), (28, 78), (17, 78),
                       (17, 55), (12, 55), (12, 31), (27, 31), (27, 8),
                       (21, 8), (21, 13), (21, 14)]
        for index, (x, y) in enumerate(checkpoints):
            walk(point(x, y), f"South->north {index}:({x},{y})")
            state = snap(p)["player"]
            check("Deck actor keeps upper layer until exit " + str(index),
                  state["onBridge"] == (index < len(checkpoints) - 1))
            check("Deck never slows to swimming " + str(index), not state["swimming"])
            if index == 6:
                p.screenshot(path=str(SHOTS / "桥中间-1440x900.png"))
        elapsed = snap(p)["elapsed"] - started
        check("Entire bridge walk completes within 30 simulation seconds", elapsed < 30, elapsed)
        p.screenshot(path=str(SHOTS / "桥另一端-1440x900.png"))
        # Reverse traversal also enters via apron, never via a crossing underneath.
        for index, (x, y) in enumerate(reversed([(28, 92), *checkpoints[:-1]])):
            walk(point(x, y), f"North->south {index}:({x},{y})")
        check("Reverse exits onto land", not snap(p)["player"]["onBridge"])

        for y, x1, x2, swim in [(15, 24, 31, False), (40, 9, 15, False),
                               (70, 14, 20, False), (25, 24, 31, True)]:
            reset(point(x1, y, False))
            p.keyboard.down("d")
            step(p, (x2 - x1) * s / snap(p)["player"]["speed"] / (.75 if swim else 1))
            p.keyboard.up("d")
            a = snap(p)["player"]
            check(f"Underpass y={y} crosses original {'water' if swim else 'land'}",
                  abs(a["x"] - point(x2, y)["x"]) < .02 and not a["onBridge"]
                  and a["swimming"] == swim, a)
        reset(point(12, 38, True))
        barrier = snap(p)["player"]
        occupancy = p.evaluate("q=>[true,false].map(layer=>window.__waterTest.freeAt("
                               "q.x,q.y,q.body.moveRadius,layer))", barrier)
        check("Original 0x7f barrier is walkable above, blocked below", occupancy == [True, False])
        reset(point(12, 40, False))
        for source, target in [(False, True), (True, False)]:
            path = p.evaluate("q=>window.__waterTest.findPath(q.x,q.y,q.x,q.y,q.a,q.b)",
                              {**point(12, 40), "a": source, "b": target})
            check(f"Layered A* {source}->{target} uses apron, never same-cell teleport",
                  len(path) > 50 and any(masks["gateway"][int(q["y"] // s) * n
                                                                       + int(q["x"] // s)]
                                                for q in path), len(path))
        p.keyboard.down("s")
        step(p, 1)
        p.keyboard.up("s")
        a = snap(p)["player"]
        check("Below cannot climb from height15 onto exclusive height4 deck",
              not a["onBridge"] and a["y"] <= (gy + 42) * s - a["body"]["moveRadius"] + .01)
        for y in [25, 46]:
            reset(point(27 if y == 25 else 12, y, True))
            xedge = (gx + (26 if y == 25 else 11)) * s
            p.keyboard.down("a")
            step(p, 1)
            p.keyboard.up("a")
            a = snap(p)["player"]
            check(f"Deck y={y} cannot walk off into below-water/wall",
                  a["onBridge"] and not a["swimming"]
                  and a["x"] >= xedge + a["body"]["moveRadius"] - .01)
            p.evaluate("window.__waterTest.dash('player',-1,0)")
            step(p, .25)
            a = snap(p)["player"]
            check(f"Deck y={y} dash also respects rail boundary",
                  a["onBridge"] and a["x"] >= xedge + a["body"]["moveRadius"] - .01)
        reset(point(21, 14, False))
        arrange(p, ai=True, enemy=point(15, 19, False))
        p.evaluate("window.__waterTest.equip('enemy',['protect','recover','focusenergy','synthesis'])")
        step(p, 3)
        a = snap(p)
        check("Live AI uses original north gatehouse connection",
              a["enemy"]["x"] > point(17, 19)["x"], a["enemy"])
        reset(point(28, 85, True))
        arrange(p, ai=True, enemy=point(28, 92, False))
        p.evaluate("window.__waterTest.equip('enemy',['protect','recover','focusenergy','synthesis'])")
        before = snap(p)
        step(p, 3)
        a = snap(p)
        check("Live AI enters apron and approaches player on deck",
              a["enemy"]["onBridge"] and not a["enemy"]["swimming"]
              and a["enemy"]["y"] < before["enemy"]["y"] - 160, a["enemy"])
        reset(point(12, 31, True))
        arrange(p, ai=True, enemy=point(27, 25, True))
        p.evaluate("window.__waterTest.equip('enemy',['protect','recover','focusenergy','synthesis'])")
        before = snap(p)
        step(p, 5)
        a = snap(p)
        check("Live AI follows deck around right-angle bend",
              a["enemy"]["onBridge"] and a["enemy"]["x"] < before["enemy"]["x"] - 160,
              a["enemy"])

        # Route104 wooden deck is MB_REFLECTION_UNDER_BRIDGE at height3, not swimming water.
        wood = next(a for a in t["areas"] if a["sourceName"] == "Route104")
        old_gx, old_gy = gx, gy
        gx, gy = wood["gridX"], wood["gridY"]
        reset(point(24, 8, False))
        for x, y in [(24, 15), (30, 15), (30, 23)]:
            walk(point(x, y), f"Route104 wood ({x},{y})")
        check("Wood bridge stays on original land layer", not snap(p)["player"]["onBridge"])
        for x, y in [(30, 15), (24, 15), (24, 8)]:
            walk(point(x, y), f"Route104 wood reverse ({x},{y})")
        for start, target in [((24, 8), (30, 23)), ((30, 23), (24, 8))]:
            reset(point(*target, False))
            arrange(p, ai=True, enemy=point(*start, False))
            p.evaluate("window.__waterTest.equip('enemy',['protect','recover','focusenergy','synthesis'])")
            step(p, 20)
            a = snap(p)["enemy"]
            q = point(*target)
            check(f"Live AI follows complete Z wood bridge {start}->{target}",
                  math.hypot(a["x"] - q["x"], a["y"] - q["y"]) < 180
                  and not a["onBridge"] and not a["swimming"], a)
        # The Route104 sea pier and Route116 rock stairs already use original
        # elevation-0 transitions. Exercise them, without flattening their heights.
        for name, start, targets in [
            ("Route104", (17, 51), [(15, 51), (12, 51), (17, 51)]),
            ("Route116", (52, 12), [(52, 11), (52, 10), (53, 10),
                                     (53, 8), (53, 7), (53, 10)]),
            ("Route116", (34, 8), [(34, 7), (34, 6), (34, 8)]),
        ]:
            area = next(a for a in t["areas"] if a["sourceName"] == name)
            gx, gy = area["gridX"], area["gridY"]
            reset(point(*start, False))
            presses.clear()
            for x, y in targets:
                walk(point(x, y), f"{name} pier/stairs ({x},{y})")
        gx, gy = old_gx, old_gy
        for width, height in [(390, 844), (844, 390)]:
            p.set_viewport_size({"width": width, "height": height})
            p.evaluate("() => new Promise(resolve => requestAnimationFrame(() => "
                       "requestAnimationFrame(resolve)))")
            reset(point(12, 46, True))
            step(p, 1.2)
            state = snap(p)
            check(f"Bridge actor centered after resize {width}x{height}",
                  all(.2 * state["viewport"][size] < state["player"][axis] - state["camera"][axis]
                      < .8 * state["viewport"][size]
                      for axis, size in [("x", "width"), ("y", "height")]))
            p.screenshot(path=str(SHOTS / f"桥面-{width}x{height}.png"))
        check("No JS errors", not errors, errors)
        browser.close()
except Exception as exc:
    failure = repr(exc)
    raise
finally:
    report = {"passed": sum(c["ok"] for c in checks),
              "failed": sum(not c["ok"] for c in checks)
              + int(bool(failure) and all(c["ok"] for c in checks)),
              "jsErrors": len(errors), "errors": errors, "failure": failure,
              "candidateSHA256": hashlib.sha256((ROOT / "候选试玩.html").read_bytes()).hexdigest(),
              "journey": journey, "checks": checks}
    (OUT / "浏览器验收.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in {"journey", "checks"}},
                     ensure_ascii=False, indent=2))
