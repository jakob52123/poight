"""Headless integration acceptance for Hoenn swimming/diving/original entrance warps."""
import base64
import hashlib
import json
import math
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/大地图通行"
SHOTS = OUT / "截图"
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8827/").rstrip("/")
checks, errors = [], []
failure = None


def check(name, ok, detail=None):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    assert ok, (name, detail)


def wait(page, expr):
    until = time.monotonic() + 30
    while time.monotonic() < until:
        if page.evaluate(expr):
            return
        time.sleep(.03)
    raise AssertionError("timeout " + expr)


def snap(p):
    return p.evaluate("window.__waterTest.snapshot()")


def step(p, seconds):
    p.evaluate("s=>window.__waterTest.step(s)", seconds)


def arrange(p, spec):
    p.evaluate("s=>window.__waterTest.arrange(s)", spec)


def move(p, key, seconds):
    p.keyboard.down(key)
    step(p, seconds)
    p.keyboard.up(key)


try:
    data = json.loads((ROOT / "素材/绿宝石场景/场景目录.json").read_text())
    main = data["terrains"][0]
    cols, size = main["columns"], main["cellSize"]
    walk, water, behavior, collision = [base64.b64decode(main[k + "B64"])
                                        for k in ["walk", "water", "behavior", "collision"]]
    shore = next(i for i in range(cols, len(walk) - cols)
                 if water[i] and walk[i - 1] and walk[i - 2]
                 and all(water[i + dx + dy * cols] for dx in range(7) for dy in [-1, 0, 1]))
    wx, wy = (shore % cols + .5) * size, (shore // cols + .5) * size
    dry = {"x": wx - size, "y": wy}
    wet = {"x": wx + size * 3, "y": wy}
    rules = main['traversalRules']
    check("Water requires explicit policy and original collision or authorized override",
          all(not v or (rules.get(str(behavior[i]), {}).get('mode') == 'water'
                        and (collision[i] == 0 or rules[str(behavior[i])].get('overrideCollision')))
              for i, v in enumerate(water)))
    check("Free-exploration waterfalls/current swim; bridges/unknown never water",
          all(bool(water[i]) == (b == 19 or 0x50 <= b <= 0x53) for i, b in enumerate(behavior)
              if b in {19, 24, 25, 26, 43} or 0x50 <= b <= 0x53 or 0x70 <= b <= 0x7F))
    check("49+1+2 original maps and 18 directed warp cells including Verdanturf",
          sum(len(t["areas"]) for t in data["terrains"]) == 52
          and sum(len(t["warps"]) for t in data["terrains"]) == 18)
    index = json.loads((ROOT / "素材/绿宝石场景/地图索引.json").read_text())
    maps = {m["id"]: m for m in index["maps"]}
    owners = {a["id"]: a for t in data["terrains"] for a in t["areas"]}
    for t in data["terrains"]:
        for w in t["warps"]:
            event = maps[w["sourceMap"]]["warp_events"][w["sourceWarp"]]
            dest = maps[event["dest_map"]]["warp_events"][int(event["dest_warp_id"])]
            a, b = owners[w["sourceMap"]], owners[w["destMap"]]
            check("Original warp source+destination " + w["id"],
                  [w["col"], w["row"]] == [a["gridX"] + event["x"], a["gridY"] + event["y"]]
                  and [w["x"], w["y"]] == [(b["gridX"] + dest["x"] + .5) * size,
                                              (b["gridY"] + dest["y"] + .5) * size])
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        p = browser.new_page(viewport={"width": 1440, "height": 900})
        p.on("pageerror", lambda e: errors.append(str(e)))
        p.goto(URL + "/?test=1", wait_until="load")
        wait(p, "window.__waterTest?.snapshot().artReady")
        catalog = p.evaluate("window.__waterTest.catalog()")
        base = snap(p)["profile"]
        roster = {r["id"]: r for r in catalog["roster"]}

        def select(mon=7, tier="great"):
            check("Select " + str(mon), p.evaluate("v=>window.__waterTest.select(v)", {
                **base, "map": "emerald-littleroottown", "player": mon, "enemy": 7,
                "playerMoves": roster[mon]["defaultMoves"],
                "enemyMoves": roster[7]["defaultMoves"], "tier": tier,
            }))

        def reset(point=wet):
            p.evaluate("window.__waterTest.reset(true)")
            arrange(p, {"ai": False, "player": point,
                        "enemy": {"x": wx + 6 * size, "y": wy}})

        for mon in roster.values():
            select(mon["id"])
            reset(dry)
            move(p, "d", .5)
            check(f"{mon['name']} shore -> water", snap(p)["player"]["swimming"])
            move(p, "a", .6)
            check(f"{mon['name']} water -> shore", not snap(p)["player"]["swimming"]
                  and snap(p)["player"]["x"] < wx - size / 2)
            reset({"x": wx - 1.5 * size, "y": wy})
            a = snap(p)["player"]
            move(p, "d", .08)
            land_speed = (snap(p)["player"]["x"] - a["x"]) / .08
            reset()
            a = snap(p)["player"]
            move(p, "d", .2)
            swim_speed = (snap(p)["player"]["x"] - a["x"]) / .2
            check(f"{mon['name']} water speed 75%", abs(swim_speed / land_speed - .75) < .0001,
                  {"land": land_speed, "water": swim_speed})
            p.keyboard.press("c")
            check(f"{mon['name']} can dive regardless of type", snap(p)["player"]["diving"])

        select()
        reset()
        step(p, 1.2)  # Allow the normal following camera to reach the arranged shoreline.
        p.screenshot(path=str(SHOTS / "水面游泳-1440x900.png"))
        # Real attacks still cast and hit across open water, rather than a rendering-only rule.
        arrange(p, {"enemy": {"x": wet["x"] + 100, "y": wy}})
        hp = snap(p)["enemy"]["hp"]
        check("Surface actual Water Gun can cast", p.evaluate("window.__waterTest.cast('player','watergun')"))
        step(p, 1.4)
        check("Surface projectile crosses water and damages opponent", snap(p)["enemy"]["hp"] < hp)
        reset()
        p.keyboard.press("c")
        a = snap(p)
        check("C enters dive with 3 seconds oxygen", a["player"]["diving"] and a["player"]["oxygen"] == 3)
        move(p, "d", .2)
        b = snap(p)
        check("Dive speed is 90% surface speed",
              abs((b["player"]["x"] - a["player"]["x"]) / .2 / roster[7]["speed"] - .675) < .001)
        p.keyboard.down("j")
        step(p, .2)
        p.keyboard.up("j")
        check("Underwater keyboard attack spends nothing and emits nothing",
              not snap(p)["player"]["attack"] and not snap(p)["bullets"] and snap(p)["player"]["spent"] == 0)
        check("Underwater direct cast rejected", not p.evaluate("window.__waterTest.cast('player','watergun')"))
        p.screenshot(path=str(SHOTS / "潜水暗影-1440x900.png"))
        step(p, 2.58)
        check("Still diving before 3 seconds", snap(p)["player"]["diving"])
        step(p, .02)
        a = snap(p)["player"]
        check("At 3 seconds auto surface and full cooldown", not a["diving"] and a["diveCooldown"] > 2.99, a)
        p.keyboard.press("c")
        check("Cooldown prevents immediate redive", not snap(p)["player"]["diving"])
        step(p, 2.98)
        p.keyboard.press("c")
        check("Cooldown still applies before 3 seconds", not snap(p)["player"]["diving"])
        step(p, .03)
        p.keyboard.press("c")
        check("Cooldown expires after 3 seconds", snap(p)["player"]["diving"])
        p.keyboard.press("Escape")
        before = snap(p)["player"]["oxygen"]
        step(p, 1)
        check("Pause freezes oxygen", snap(p)["player"]["oxygen"] == before)
        p.keyboard.press("Escape")
        for mid, damages in [("flamethrower", False), ("watergun", True), ("thundershock", True)]:
            reset()
            p.keyboard.press("c")
            hp = snap(p)["player"]["hp"]
            p.evaluate("v=>window.__waterTest.injectWater(v)", {
                "owner": "enemy", "move": mid, "x": wet["x"] - 70, "y": wy,
                "ux": 1, "uy": 0, "speed": 300, "range": 500,
            })
            step(p, .45)
            a = snap(p)
            check(mid + " underwater damage rule", (a["player"]["hp"] < hp) == damages, a["player"]["hp"])
            if not damages:
                check("Fire passes through shadow, not consumed", len(a["bullets"]) == 1
                      and a["bullets"][0]["x"] > wet["x"] + 50)
        reset(dry)
        p.keyboard.press("c")
        check("C on land does nothing", not snap(p)["player"]["diving"])
        reset()
        p.locator("#diveButton").click()
        check("Touch/click dive button enters water", snap(p)["player"]["diving"])
        p.locator("#diveButton").click()
        check("Touch/click surfaces with cooldown", not snap(p)["player"]["diving"]
              and snap(p)["player"]["diveCooldown"] == 3)
        # A* and real AI movement use the same water cells, with weighted cost.
        reset({"x": wx + 5 * size, "y": wy})
        arrange(p, {"ai": True, "enemy": dry})
        p.evaluate("window.__waterTest.equip('enemy',['protect','recover','focusenergy','synthesis'])")
        path = p.evaluate("v=>window.__waterTest.findPath(v[0],v[1],v[2],v[3])",
                          [dry["x"], wy, wx + 5 * size, wy])
        check("A* includes water route", any(water[int(q["y"] // size) * cols + int(q["x"] // size)] for q in path))
        before = abs(snap(p)["enemy"]["x"] - snap(p)["player"]["x"])
        step(p, 1.5)
        a = snap(p)
        check("Actual AI swims closer", a["enemy"]["swimming"]
              and abs(a["enemy"]["x"] - a["player"]["x"]) < before - 80, a["enemy"])
        # Reproducible bounded AI policy: no chance roll can grant novice diving.
        policy = p.evaluate("""()=>{const c=window.__waterTest.catalog(),T=window.PoightTraversal;
          const world=new window.PoightWorld(c.terrains[0],new Map());
          world.capabilities={swim:true,dive:true};const a=new T();
          const p={x:__X__,y:__Y__,hp:100,hurt:0};
          return {novice:a.tryAI(p,world,'poke',{projectile:true},()=>0),
            noThreat:a.tryAI(p,world,'great',null,()=>0),
            chanceMiss:a.tryAI(p,world,'great',{projectile:true},()=>.99),
            great:a.tryAI(p,world,'great',{projectile:true},()=>0),oxygen:p.diveLeft,
            parameters:T.parameters};} """.replace("__X__", str(wet["x"])).replace("__Y__", str(wy)))
        check("Great+ AI probabilistic policy and same oxygen", not policy["novice"]
              and not policy["noThreat"] and not policy["chanceMiss"] and policy["great"] and policy["oxygen"] == 3)
        seen_dive = False
        for trial in range(16):
            reset(dry)
            arrange(p, {"ai": True, "tier": "master", "enemy": {"x": wet["x"] + 100, "y": wy}})
            p.evaluate("window.__waterTest.equip('enemy',['protect','recover','focusenergy','synthesis'])")
            # Advance normal decisions between seeded trials, rather than repeating one identical roll.
            step(p, trial * .7)
            arrange(p, {"player": dry, "enemy": {"x": wet["x"] + 100, "y": wy}})
            p.evaluate("v=>window.__waterTest.injectWater(v)", {
                "owner": "player", "move": "flamethrower", "x": wet["x"] - 120,
                "y": wy, "ux": 1, "uy": 0, "speed": 400,
            })
            for j in range(16):
                step(p, .03)
                seen_dive |= snap(p)["enemy"]["diving"]
            if seen_dive:
                break
        check("Live AI dives in response to aimed projectile", seen_dive)
        # Synthetic no-capability scene uses the same water metadata, but rejects passage/diving.
        reset()
        p.evaluate("window.__waterTest.capabilities({})")
        p.keyboard.press("c")
        check("No-capability scene: no swim/dive/button", not snap(p)["player"]["swimming"]
              and not snap(p)["player"]["diving"] and p.locator("#diveButton").is_hidden())
        check("No-capability scene: water blocks occupancy", not p.evaluate("q=>window.__waterTest.freeAt(q.x,q.y)", wet))
        arrange(p, {"player": dry})
        move(p, "d", .6)
        check("No-capability scene: actual walking cannot enter water", snap(p)["player"]["x"] <= wx - size / 2)
        no_cap_warp = main["warps"][0]
        arrange(p, {"player": {"x": (no_cap_warp["col"] + .5) * size,
                                "y": (no_cap_warp["row"] + .5) * size}})
        before = snap(p)["environment"]["id"]
        step(p, .2)
        check("No-capability scene: original warp events inactive",
              snap(p)["environment"]["id"] == before and not snap(p)["environment"]["warpPending"])
        select()
        weighted = p.evaluate("""()=>{const n=13,m=5,land=Array(n*m).fill(0),water=[...land];
          for(let y=1;y<=3;y++)for(let x=1;x<=11;x++)land[y*n+x]=1;
          for(let x=2;x<=10;x++){land[2*n+x]=0;water[2*n+x]=1;}
          const enc=a=>btoa(String.fromCharCode(...a));
          const w=new window.PoightWorld({cellSize:48,columns:n,rows:m,areas:[],chunks:[],
            walkB64:enc(land),waterB64:enc(water),elevationB64:enc(Array(n*m).fill(3)),
            behaviorB64:enc(Array(n*m).fill(0))},new Map());w.capabilities={swim:true};
          const path=w.findPath(72,120,552,120);let x=72,y=120,cost=0;
          for(const q of path){cost+=Math.hypot(q.x-x,q.y-y)/48*(w.isWater(q.x,q.y)?1.3:1);
            x=q.x;y=q.y;}return {cost,path};}""")
        check("A* water cost 1.3 chooses cheaper land detour",
              abs(weighted["cost"] - (8 + 2 * math.sqrt(2))) < 1e-6)
        # Without the explicit exploration policy, conservative waterfall/bridge blocking remains.
        # Full-world policy-enabled source movement is covered by 验收-丰缘全图.py.
        fixture = p.evaluate("""()=>{const encode=a=>btoa(String.fromCharCode(...a));
          const w=new window.PoightWorld({cellSize:48,columns:5,rows:3,areas:[],chunks:[],
            walkB64:encode([0,0,0,0,0,0,1,0,0,0,0,0,0,0,0]),
            waterB64:encode([0,0,0,0,0,0,0,1,0,0,0,0,0,0,0]),
            elevationB64:encode(Array(15).fill(3)),
            behaviorB64:encode([0,0,0,0,0,0,0,16,19,0,0,0,0,0,0])},new Map());
          w.capabilities={swim:true};const p={x:72,y:72};w.move(p,200,0,20);
          return {x:p.x,blocked:!w.pass(3,1),path:w.findPath(72,72,120,72)};}""")
        check("Waterfall fixture stops swept movement and A* remains on legal water",
              fixture["blocked"] and fixture["x"] <= 144 - 20 and len(fixture["path"]) == 1)

        def portal(w):
            # Walk from an adjacent source cell, not a direct scene-select hook.
            target = {"x": (w["col"] + .5) * size, "y": (w["row"] + .5) * size}
            choices = [(0, 1, "w"), (0, -1, "s"), (-1, 0, "d"), (1, 0, "a")]
            start = None
            for dx, dy, key in choices:
                q = {"x": target["x"] + dx * size, "y": target["y"] + dy * size}
                if p.evaluate("q=>window.__waterTest.freeAt(q.x,q.y,20)", q):
                    start = q
                    break
            assert start, w
            arrange(p, {"ai": False, "player": {**start, "hp": 57, "stamina": 61},
                        "enemy": {"hp": 63, "stamina": 58}, "clearProjectiles": True})
            # Release arrival lock by taking an ordinary simulation step outside all warp cells.
            step(p, .01)
            p.evaluate("v=>window.__waterTest.injectWater(v)", {
                "owner": "enemy", "x": start["x"] + 500, "y": start["y"],
                "ux": 1, "uy": 0, "speed": 1,
            })
            before = snap(p)
            travel = .16 * 216 / before['player']['speed']
            move(p, key, travel)
            wait(p, "!window.__waterTest.snapshot().environment.warpPending")
            a = snap(p)
            check("Walked original entrance " + w["id"], a["environment"]["id"] == w["destScene"], a["environment"])
            check("Warp lands at original target " + w["id"],
                  math.hypot(a["player"]["x"] - w["x"], a["player"]["y"] - w["y"]) < .01)
            check("Warp retains both HP and nonreset stamina " + w["id"],
                  a["player"]["hp"] == before["player"]["hp"] == 57
                  and a["enemy"]["hp"] == before["enemy"]["hp"] == 63
                  and before["player"]["stamina"] <= a["player"]["stamina"] <= before["player"]["stamina"] + 25*travel + .01
                  and before["enemy"]["stamina"] <= a["enemy"]["stamina"] <= before["enemy"]["stamina"] + 25*travel + .01)
            check("Warp clears projectiles and AI paths " + w["id"], not a["bullets"]
                  and not a["zones"] and a["generated"]["active"] == 0 and a["ai"]["pathSearches"] == 0)
            check("AI not yet in new scene " + w["id"], a["enemy"]["worldAbsent"])
            step(p, .98)
            check("AI still waiting before 1 second " + w["id"], snap(p)["enemy"]["worldAbsent"])
            step(p, .03)
            a = snap(p)
            check("AI follows after 1 second at safe separated landing " + w["id"],
                  not a["enemy"]["worldAbsent"]
                  and math.hypot(a["player"]["x"] - a["enemy"]["x"],
                                 a["player"]["y"] - a["enemy"]["y"]) >= 120
                  and p.evaluate("q=>window.__waterTest.freeAt(q.x,q.y,q.body.moveRadius)",
                                 a["enemy"]))
            step(p, .2)
            check("Standing on arrival does not bounce " + w["id"], snap(p)["environment"]["id"] == w["destScene"])

        for entry in main["warps"]:
            select()
            reset(dry)
            portal(entry)
            current_t = next(t for t in data["terrains"] if t["areas"][0]["id"] == entry["destMap"])
            if entry["sourceWarp"] in [0, 4]:
                name = "森林内" if "woods" in entry["destScene"] else "隧道内"
                p.screenshot(path=str(SHOTS / (name + "-1440x900.png")))
            # Solid original tree/rock tiles block both walking and dash, regardless of entry permission.
            tw = base64.b64decode(current_t["walkB64"])
            n = current_t["columns"]
            pair = next((i for i in range(n + 1, len(tw) - n - 1)
                         if tw[i] and not tw[i - 1] and i % n > 1 and tw[i + 1]), None)
            px, py = (pair % n + .5) * size, (pair // n + .5) * size
            arrange(p, {"player": {"x": px, "y": py}})
            move(p, "a", .8)
            a = snap(p)["player"]
            check("Interior tree/rock blocks movement " + entry["id"],
                  a["x"] >= (pair % n) * size + a["body"]["moveRadius"] - .01)
            p.evaluate("window.__waterTest.dash('player',-1,0)")
            step(p, .3)  # B2: complete the whole 300ms dash before the return-warp walk.
            check("Interior tree/rock blocks dash " + entry["id"],
                  snap(p)["player"]["x"] >= (pair % n) * size + a["body"]["moveRadius"] - .01)
            back = next(w for w in current_t["warps"] if w["sourceWarp"] == entry["destWarp"])
            portal(back)
        # Responsive screenshots and real mobile tap on the new independent button.
        select()
        for width, height in [(390, 844), (844, 390)]:
            p.set_viewport_size({"width": width, "height": height})
            reset()
            step(p, 1.2)
            p.locator("#diveButton").click()
            step(p, .1)
            check(f"Mobile dive button usable {width}x{height}", snap(p)["player"]["diving"])
            p.screenshot(path=str(SHOTS / f"潜水-{width}x{height}.png"))
        check("No JS errors", not errors, errors)
        browser.close()
except Exception as exc:
    failure = repr(exc)
    raise
finally:
    report = {"passed": sum(c["ok"] for c in checks),
              "failed": sum(not c["ok"] for c in checks) + int(bool(failure) and all(c["ok"] for c in checks)),
              "jsErrors": len(errors), "errors": errors, "failure": failure,
              "candidateSHA256": hashlib.sha256((ROOT / "候选试玩.html").read_bytes()).hexdigest(),
              "checks": checks}
    (OUT / "浏览器验收.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "checks"}, ensure_ascii=False, indent=2))
