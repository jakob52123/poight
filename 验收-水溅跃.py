"""Splash/loadout contract: source invariants, real keyboard/UI/AI, offline and screenshots."""
import ast
import base64
import csv
import hashlib
import json
import math
import os
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from 游戏数据 import HP_MULTIPLIER, MOVES, roster_metadata

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/水溅跃"
SHOTS = OUT / "截图"
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8828/").rstrip("/")
checks, errors, screenshots = [], [], []


def check(name, ok, detail=None):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    assert ok, (name, detail)


def ready(page):
    deadline = time.monotonic() + 45
    while not page.evaluate("window.__waterTest?.snapshot().artReady"):
        assert time.monotonic() < deadline, "art ready timeout"
        time.sleep(0.05)


def snap(page):
    return page.evaluate("window.__waterTest.snapshot()")


def step(page, seconds):
    page.evaluate("(v)=>window.__waterTest.step(v)", seconds)


def shot(page, name):
    path = SHOTS / name
    page.screenshot(path=str(path))
    screenshots.append(str(path))


try:
    rows = json.loads((ROOT / "素材/角色库/角色库.json").read_text())
    ids = json.loads((ROOT / "首发50.json").read_text())["ids"]
    rows = [row for row in rows if row["id"] in ids]
    old = {"__file__": str(ROOT / "游戏数据.py")}
    exec(subprocess.check_output(["git", "show", "928b570:游戏数据.py"], cwd=ROOT), old)  # noqa: S102 — trusted local T5 commit
    before = {c["id"]: c for c in old["roster_metadata"](rows)}
    after = {c["id"]: c for c in roster_metadata(rows)}
    check("121 moves; Splash zero damage/normal/SP4/CD1/windup0.15", len(MOVES) == 121
          and all(MOVES["splash"][k] == v for k, v in
                  {"damage": 0, "type": 1, "cost": 4, "cd": 1, "windup": 0.15}.items()))
    from 招式特效.第2批参数 import RANGED_REVISIONS
    expected_moves = {mid: {k: v for k, v in m.items()
                           if k != 'burn' and not (k == 'slow' and m['type'] == 13)}
                      for mid, m in old['MOVES'].items()}
    check("T5 source moves unchanged except authorized R2 revisions/S1 field deletions", all(
        MOVES[k] == v for k, v in expected_moves.items() if k not in RANGED_REVISIONS))
    check("All T5-integrated120 moves retain damage/CD/stamina", all(
        all(MOVES[k][field] == v[field] for field in ('damage', 'cd', 'cost'))
        for k, v in old["MOVES"].items()))
    check("Magikarp only Splash and explicit harmless flag", after[129]["defaultMoves"] == ["splash"]
          and after[129]["learnset"] == ["splash"] and after[129]["flags"] == ["无伤配招"])
    for n in ids:
        if n != 129:
            expected = {**before[n], "baseHP": before[n]["hp"],
                        "hp": before[n]["hp"] * HP_MULTIPLIER}
            check(f"{n}: metadata unchanged except global HP multiplier", expected == after[n])

    # Execute the exact build assertion function, without importing/building the entire pack.
    tree = ast.parse((ROOT / "构建完整版.py").read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "assert_default_damage_coverage")
    ns = {"math": math}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "构建完整版.py", "exec"), ns)  # noqa: S102 — exact local build assertion
    coverage = ns["assert_default_damage_coverage"]
    matrix = {}
    for row in csv.DictReader((ROOT / "素材/角色库/原始/type_efficacy.csv").open()):
        matrix.setdefault(int(row["damage_type_id"]), {})[int(row["target_type_id"])] = int(row["damage_factor"]) / 100
    coverage(list(after.values()), MOVES, matrix)
    check("Actual50 build damage coverage passes", True)
    for n, flags, expected in [(129, [], False), (7, [], False), (7, ["无伤配招"], True)]:
        entry = {"id": n, "types": [11], "defaultMoves": ["splash"], "flags": flags}
        try:
            coverage([entry], MOVES, matrix)
            accepted, message = True, "accepted"
        except AssertionError as exc:
            accepted, message = False, str(exc)
        check(f"Build exemption depends only on flag: id={n}, flags={flags}", accepted == expected, message)
    try:
        coverage([{"id": 7, "types": [11], "defaultMoves": ["tackle"]},
                  {"id": 94, "types": [8], "defaultMoves": ["shadowball", "watergun"]}], MOVES, matrix)
        rejected = False
    except AssertionError as exc:
        rejected = True
        counterexample = str(exc)
    check("Unflagged species with damaging but immune loadout still rejects", rejected, counterexample)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(str(e)))
        response = page.goto(URL + "/?test=1", wait_until="load")
        ready(page)
        check("HTTP candidate exact SHA", hashlib.sha256(response.body()).hexdigest()
              == hashlib.sha256((ROOT / "候选试玩.html").read_bytes()).hexdigest())
        catalog = page.evaluate("window.__waterTest.catalog()")
        roster = {c["id"]: c for c in catalog["roster"]}
        check("Runtime121 and Magikarp restricted", len(catalog["moves"]) == 121
              and roster[129]["defaultMoves"] == roster[129]["learnset"] == ["splash"])
        default = {**snap(page)["profile"], "map": "emerald-rustborocity", "tier": "master",
                   "holdAim": False}  # Exercise the supported continuous-cast setting.
        terrain = catalog["terrains"][0]
        walk = base64.b64decode(terrain["walkB64"])
        cols = terrain["columns"]
        area = next(a for a in terrain["areas"] if a["sourceName"] == "RustboroCity")
        lane = next((x, y) for y in range(area["gridY"] + 3, area["gridY"] + area["rows"] - 3)
                    for x in range(area["gridX"] + 4, area["gridX"] + area["columns"] - 4)
                    if all(walk[(y + dy) * cols + x + dx] for dy in range(-2, 3) for dx in range(-4, 5)))
        cx, cy = (lane[0] + 0.5) * 48, (lane[1] + 0.5) * 48

        def select(player=129, enemy=7, player_moves=None):
            profile = {**default, "player": player, "enemy": enemy,
                       "playerMoves": roster[player]["defaultMoves"] if player_moves is None else player_moves,
                       "enemyMoves": roster[enemy]["defaultMoves"]}
            check(f"Profile loads {player}/{enemy}/{profile['playerMoves']}",
                  page.evaluate("(v)=>window.__waterTest.select(v)", profile))
            page.evaluate("window.__waterTest.reset(true)")
            return profile

        def arrange(ai=False):
            page.evaluate("(v)=>window.__waterTest.arrange(v)",
                          {"ai": ai, "player": {"x": cx - 60, "y": cy},
                           "enemy": {"x": cx + 100, "y": cy}})

        profile = select()
        page.evaluate("window.__waterTest.reset(false)")
        for key in ["k", "l", "i"]:
            page.keyboard.press(key)
            check(f"Missing key {key.upper()} does not start idle match", snap(page)["phase"] == "idle")
        page.evaluate("window.__waterTest.reset(true)")
        arrange()
        step(page, 2)
        check("Exactly1 actual skill button labelled J", page.locator("#skills button.skill").count() == 1
              and page.locator("#skills kbd").all_text_contents() == ["J"])
        shot(page, "鲤鱼王技能栏-1440x900.png")
        for key in ["k", "l", "i"]:
            before_key = snap(page)
            page.keyboard.down(key)
            step(page, 0.05)
            page.keyboard.up(key)
            state = snap(page)
            check(f"Missing key {key.upper()} no attack/resource/input/cooldown changes",
                  not state["player"]["attack"] and state["player"]["spent"] == before_key["player"]["spent"]
                  and state["player"]["cool"] == before_key["player"]["cool"]
                  and state["player"]["splashes"] == 0 and not state["held"])
        page.keyboard.down("j")
        step(page, 0.05)
        check("J starts0.075s windup, spends4, not yet hopping", snap(page)["player"]["spent"] == 4
              and snap(page)["player"]["flightHeight"] == 0 and snap(page)["player"]["splashes"] == 0)
        page.keyboard.up("j")
        page.keyboard.down("d")
        start_xy = (snap(page)["player"]["x"], snap(page)["player"]["y"])
        step(page, 0.145)
        state = snap(page)
        check("J mid-hop28px, stationary even with movement held", state["player"]["flightHeight"] > 27
              and (state["player"]["x"], state["player"]["y"]) == start_xy
              and state["player"]["splashes"] == 1)
        shot(page, "水溅跃中段-1440x900.png")
        page.keyboard.up("d")
        check("No HP/hits/hurt/knockback/projectiles at mid-hop", state["enemy"]["hp"] == roster[7]["hp"]
              and state["hits"] == state["taken"] == 0 and state["enemy"]["anim"] == "idle"
              and not state["enemy"]["attack"] and not state["bullets"] and not state["zones"]
              and state["enemy"]["x"] == cx + 100)
        check("Cooldown not bypassable", not page.evaluate('window.__waterTest.cast("player","splash")'))
        step(page, 0.13)
        state = snap(page)
        check("Land after0.24s hop: water ring and floating Easter text", state["player"]["flightHeight"] == 0
              and not state["player"]["attack"] and "splash" in state["effectKinds"]
              and any(f["text"] == "但是什么也没有发生" for f in state["floats"]))
        check("No HP/hit/knockback on landing", state["enemy"]["hp"] == roster[7]["hp"]
              and state["hits"] == 0 and state["enemy"]["x"] == cx + 100)
        shot(page, "水溅跃落地水花-1440x900.png")

        # Previously selected L/I slot must clamp correctly when switching to one-move species.
        select(7)
        page.locator("#battleMenuButton").click()
        page.locator("#setupButton").click()
        page.locator("#toggleLoadout").click()
        page.locator("#moveChoice3").click()
        page.locator("#toggleLoadout").click()
        page.locator("#search").fill("129")
        page.locator('.mon[data-id="129"]').click()
        page.locator("#toggleLoadout").click()
        check("UI one slot; catalog only Splash; add/remove disabled at1", page.locator(".move-card").count() == 1
              and page.locator(".move-card").get_attribute("data-move") == "splash"
              and page.locator("#moveSlots .move-slot").count() == 1
              and page.locator("#moveChoice0").get_attribute("aria-pressed") == "true"
              and page.locator("#addMoveSlot").is_disabled() and page.locator("#removeMoveSlot").is_disabled())
        shot(page, "鲤鱼王配招-1440x900.png")
        page.locator("#toggleLoadout").click()
        page.locator("#search").fill("7")
        page.locator('.mon[data-id="7"]').click()
        page.locator("#toggleLoadout").click()
        for n in [3, 2, 1]:
            page.locator("#removeMoveSlot").click()
            check(f"UI reduce slots to{n}", page.locator("#moveSlots .move-slot").count() == n)
        check("Cannot remove last slot", page.locator("#removeMoveSlot").is_disabled())
        for n in [2, 3, 4]:
            page.locator("#addMoveSlot").click()
            check(f"UI add slots to{n}", page.locator("#moveSlots .move-slot").count() == n)
        check("Cannot exceed4 slots", page.locator("#addMoveSlot").is_disabled())
        page.locator("#toggleLoadout").click()
        page.locator("#closeSetup").click()
        for n in [1, 2, 3, 4]:
            select(7, player_moves=roster[7]["defaultMoves"][:n])
            check(f"Actual skills and key order for{n} slots", page.locator("#skills button.skill").count() == n
                  and page.locator("#skills kbd").all_text_contents() == ["J", "K", "L", "I"][:n])
            for slot, key in enumerate(["j", "k", "l", "i"][:n]):
                page.evaluate("window.__waterTest.reset(true)")
                arrange()
                page.keyboard.down(key)
                step(page, 0.01)
                page.keyboard.up(key)
                check(f"{n} slots: {key.upper()} casts equipped slot{slot + 1}",
                      snap(page)["player"]["attack"]["id"] == roster[7]["defaultMoves"][slot])
            page.reload(wait_until="load")
            ready(page)
            check(f"Saved{n}-slot loadout round trips", snap(page)["profile"]["playerMoves"] == roster[7]["defaultMoves"][:n])
        for moves in [[], ["splash", "splash"], ["watergun"], roster[7]["learnset"][:5]]:
            result = page.evaluate("""async (v)=>{try{await window.__waterTest.select(v);return false;}catch(e){return true;}}""",
                                   {**profile, "playerMoves": moves})
            check(f"Reject empty/duplicate/illegal/overfull Magikarp moves {moves}", result)

        select(7, 129)
        arrange(True)
        ai_start = snap(page)["enemy"]
        step(page, 30)
        state = snap(page)
        check("Single-move AI30s: uses Splash and moves", state["elapsed"] >= 30 - 1e-6
              and state["ai"]["casts"] > 0 and state["enemy"]["splashes"] > 0
              and math.hypot(state["enemy"]["x"] - ai_start["x"], state["enemy"]["y"] - ai_start["y"]) > 10
              and state["player"]["hp"] == roster[7]["hp"], state["ai"])
        dodged = False
        for _ in range(8):
            state = snap(page)
            ex, ey = state["enemy"]["x"], state["enemy"]["y"]
            page.evaluate("(v)=>window.__waterTest.injectWater(v)",
                          {"owner": "player", "x": ex - 100, "y": ey, "ux": 1, "uy": 0, "speed": 150})
            step(page, 0.6)
            if snap(page)["ai"]["dodgeDecisions"] > 0:
                dodged = True
                break
        check("Single-move AI still dodges real projectiles", dodged, snap(page)["ai"])
        page.evaluate('window.__waterTest.arrange({player:{hp:0}})')
        step(page, 0.01)
        check("AI Magikarp match uses DOM Easter hint", page.locator("#matchHint").inner_text() == "鲤鱼王尽力了。")

        select()
        arrange()
        step(page, 2)
        for width, height in [(390, 844), (844, 390)]:
            page.set_viewport_size({"width": width, "height": height})
            page.wait_for_timeout(150)
            step(page, 1)  # Let the manual camera recenter after viewport resize.
            shot(page, f"鲤鱼王技能栏-{width}x{height}.png")
            check(f"Mobile{width}x{height}: one button, no horizontal overflow", page.locator("#skills button").count() == 1
                  and page.evaluate("document.documentElement.scrollWidth<=innerWidth+1"))
        page.evaluate('window.__waterTest.arrange({player:{hp:0}})')
        step(page, 0.01)
        check("Player Magikarp match uses DOM Easter hint", page.locator("#matchHint").inner_text() == "鲤鱼王尽力了。")
        offline = browser.new_page()
        offline.on("pageerror", lambda e: errors.append(str(e)))
        offline.goto((ROOT / "候选试玩.html").as_uri() + "?test=1", wait_until="load")
        ready(offline)
        check("Offline121 moves", snap(offline)["moveCount"] == 121)
        check("No JS errors", not errors, errors)
        browser.close()
finally:
    report = {"candidateSHA256": hashlib.sha256((ROOT / "候选试玩.html").read_bytes()).hexdigest(),
              "passed": sum(c["ok"] for c in checks), "failed": sum(not c["ok"] for c in checks),
              "jsErrors": len(errors), "errors": errors, "checks": checks, "screenshots": screenshots}
    (OUT / "浏览器验收.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ["passed", "failed", "jsErrors", "errors"]}, ensure_ascii=False))
