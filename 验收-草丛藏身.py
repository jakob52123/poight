"""Headless stealth rules, real canvas/HUD probes and native/general scene coverage."""

import hashlib
import json
import math
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/草丛藏身"
SHOTS = OUT / "截图"
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8826/")
checks = []
errors = []


def check(name, value, detail=None):
    checks.append({"name": name, "ok": bool(value), "detail": detail})
    assert value, (name, detail)


def snap(page):
    return page.evaluate("window.__waterTest.snapshot()")


def step(page, seconds):
    page.evaluate("(s) => window.__waterTest.step(s)", seconds)


def arrange(page, **setup):
    page.evaluate("(s) => window.__waterTest.arrange(s)", setup)


def reset(page):
    page.evaluate("window.__waterTest.reset(true)")
    arrange(page, ai=False)


def shot(page, name):
    page.screenshot(path=str(SHOTS / name))


def draw_probe(page):
    return page.evaluate("""() => {
      const ctx = document.getElementById('game').getContext('2d');
      const image = ctx.drawImage, text = ctx.fillText, rect = ctx.fillRect;
      const calls = [], labels = [], rects = [];
      ctx.fillRect = function(x, y, w, h) {
        const m = this.getTransform(), c = this.canvas, b = c.getBoundingClientRect();
        rects.push({x: (m.a*x+m.e)*b.width/c.width, y: (m.d*y+m.f)*b.height/c.height,
          width: m.a*w*b.width/c.width, height: m.d*h*b.height/c.height,
          color: this.fillStyle});
        return rect.call(this, x, y, w, h);
      };
      ctx.drawImage = function(im, ...rest) {
        calls.push({src: im.src || '', alpha: this.globalAlpha});
        return image.call(this, im, ...rest);
      };
      ctx.fillText = function(s, ...rest) {
        labels.push(s); return text.call(this, s, ...rest);
      };
      try { window.__waterTest.render(); }
      finally { ctx.drawImage = image; ctx.fillText = text; ctx.fillRect = rect; }
      return {calls, labels, rects};
    }""")


def hp_drawn(page, probe, side="enemy"):
    hud = next(h for h in snap(page)["hud"]["actors"] if h["side"] == side)
    box = hud["box"]
    return any(r["color"] == hud["color"] and all(
        abs(r[k] - box[k] * (hud["ratio"] if k == "width" else 1)) < 0.1
        for k in ["x", "y", "width", "height"]
    ) for r in probe["rects"])


try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(URL + "?test=1")
        for _ in range(240):
            if page.evaluate("window.__waterTest?.snapshot().artReady"):
                break
            time.sleep(0.05)
        check("Art ready", snap(page)["artReady"])
        page.evaluate("v => window.__waterTest.select(v)",
                      {**snap(page)["profile"], "map": "emerald-littleroottown"})
        sites = page.evaluate("""() => {
          const api = window.__waterTest, t = api.catalog().terrains[0];
          const a = t.areas.find(a => a.sourceName === 'Route101');
          const s = t.cellSize, beh = atob(t.behaviorB64);
          const grass = (x,y) => beh[Math.floor(y/s)*t.columns+Math.floor(x/s)]?.charCodeAt(0)===2;
          const free = (x,y) => api.freeAt(x,y,10);
          let g, e;
          for(let row=a.gridY; row<a.gridY+a.rows && !g; row++)
            for(let col=a.gridX; col<a.gridX+a.columns && !g; col++) {
              const x=(col+.5)*s, y=(row+.5)*s;
              if(!grass(x,y) || !free(x,y) || !free(x+60,y)) continue;
              for(const [dx,dy] of [[-144,0],[144,0],[0,-144],[0,144]]) {
                if(free(x+dx,y+dy) && !grass(x+dx,y+dy) && api.clearLine(x,y,x+dx,y+dy,10)) {
                  g={x,y}; e={x:x+dx,y:y+dy}; break;
                }
              }
            }
          let remote;
          for(let row=0; row<t.rows && !remote; row++)
            for(let col=0; col<t.columns && !remote; col++) {
              const x=(col+.5)*s,y=(row+.5)*s;
              if(grass(x,y) && free(x,y) && Math.hypot(x-g.x,y-g.y)>1500) remote={x,y};
            }
          return {g,e,remote,regions:t.grassRegions.length};
        }""")
        g, e, remote = sites["g"], sites["e"], sites["remote"]
        check("Native grass generates scene regions", sites["regions"] > 0, sites)
        reset(page)
        arrange(page, player=g, enemy=e)
        step(page, 0.79)
        check("Not hidden before 0.8s in grass", not snap(page)["player"]["stealth"]["hidden"])
        step(page, 0.01)
        check("Native player hidden at 0.8s", snap(page)["player"]["stealth"]["hidden"])
        probe = draw_probe(page)
        player_src = page.evaluate("window.__waterTest.catalog().art[7].idle.src")
        check("Real player sprite uses 40% alpha", any(
            c["src"].endswith(player_src) and abs(c["alpha"] - 0.4) < 0.001
            for c in probe["calls"]
        ), probe)
        shot(page, "桌面-玩家藏身-1440x900.png")
        check("Player attack accepted", page.evaluate("window.__waterTest.cast('player','watergun')"))
        check("Attack immediately reveals player", not snap(page)["player"]["stealth"]["hidden"])
        cast_duration = snap(page)["player"]["attack"]["duration"]
        step(page, 0.79)
        check("Cast suppresses hiding for 0.8s", not snap(page)["player"]["stealth"]["hidden"])
        step(page, max(0, cast_duration - 0.8))
        check("Active R3 stream cannot hide", not snap(page)["player"]["stealth"]["hidden"])
        state = snap(page)
        # A longer R3 stream can now reach this target, so drain actual hitstop
        # before measuring the remaining cast time (combat clock stays frozen).
        step(page, state['feel']['remaining'] + max(0, cast_duration - (state['elapsed'] - 0.8)) + 0.03)
        check("Quiet player hides again after full stream pose", snap(page)["player"]["stealth"]["hidden"], snap(page))
        arrange(page, player=e, clearProjectiles=True)
        check("Leaving grass immediately reveals", not snap(page)["player"]["stealth"]["hidden"])
        reset(page)
        arrange(page, player=e, enemy=g)
        step(page, 0.8)
        check("Native AI hides", snap(page)["enemy"]["stealth"]["hidden"])
        enemy_src = page.evaluate("window.__waterTest.catalog().art[4].idle.src")
        probe = draw_probe(page)
        check("Hidden AI sprite is not drawn", not any(c["src"].endswith(enemy_src) for c in probe["calls"]))
        check("Hidden CPU label is not drawn", "CPU" not in probe["labels"] and "1P" in probe["labels"])
        check("AI head HP not drawn and old DOM absent", not hp_drawn(page, probe)
              and hp_drawn(page, probe, "player") and page.locator("#enemyHealth").count() == 0)
        shot(page, "桌面-AI藏身-1440x900.png")
        arrange(page, player={"x": g["x"] + 60, "y": g["y"]})
        check("Distance under70 reveals both immediately", not snap(page)["player"]["stealth"]["hidden"] and not snap(page)["enemy"]["stealth"]["hidden"])
        probe = draw_probe(page)
        check("Revealed AI sprite and HUD return", any(c["src"].endswith(enemy_src) for c in probe["calls"])
              and hp_drawn(page, probe) and "CPU" in probe["labels"])
        shot(page, "桌面-近距离现身-1440x900.png")
        reset(page)
        arrange(page, player=g, enemy=e)
        step(page, 0.8)
        page.evaluate("(g) => window.__waterTest.injectWater({owner:'enemy',x:g.x,y:g.y,ux:1,uy:0,speed:1})", g)
        step(page, 1 / 120)
        check("Actual hit reveals hidden player", snap(page)["player"]["damageTaken"] > 0 and not snap(page)["player"]["stealth"]["hidden"])
        step(page, snap(page)["feel"]["remaining"])
        step(page, 1.48)
        check("Cannot rehide before1.5s since hit", not snap(page)["player"]["stealth"]["hidden"])
        step(page, 0.02)
        check("Can rehide1.5s after hit", snap(page)["player"]["stealth"]["hidden"])
        reset(page)
        arrange(page, player=e, enemy=g)
        page.evaluate("window.__waterTest.cast('enemy','protect')")
        step(page, 0.4)
        guard_prefix = "animation-vc-" if page.evaluate("!!window.PoightVC") and snap(page)["animation"]["enabled"] else "move-fx-"
        check("Visible guard artwork really draws", any(guard_prefix in c["src"] for c in draw_probe(page)["calls"]))
        step(page, 0.4)
        state = snap(page)
        check("AI can hide while shield still active", state["enemy"]["stealth"]["hidden"] and state["enemy"]["shield"] > 0)
        check("Attached guard effect cannot disclose hidden AI", not any(guard_prefix in c["src"] for c in draw_probe(page)["calls"]))
        reset(page)
        arrange(page, player=g, enemy=e)
        step(page, 0.8)
        known = snap(page)["ai"]["lastSeen"]
        arrange(page, player=remote, ai=True)
        before = snap(page)["enemy"]
        step(page, 0.2)
        state = snap(page)
        old_dist = math.hypot(before["x"] - known["x"], before["y"] - known["y"])
        new_dist = math.hypot(state["enemy"]["x"] - known["x"], state["enemy"]["y"] - known["y"])
        check("AI walks toward last seen, not live target", new_dist < old_dist and state["ai"]["lastSeen"] == known, state["ai"])
        angles, seen_bullets, searching = [], set(), False
        for _ in range(50):
            step(page, 0.1)
            state = snap(page)
            check_hidden = state["player"]["stealth"]["hidden"]
            assert check_hidden, "player unexpectedly exposed in direction test"
            searching |= state["ai"]["mode"] == "附近搜索"
            for bullet in state["bullets"]:
                if bullet["owner"] != "enemy" or bullet["id"] in seen_bullets:
                    continue
                seen_bullets.add(bullet["id"])
                target = state["player"]
                a = math.atan2(bullet["uy"], bullet["ux"])
                b = math.atan2(target["y"] - bullet["y"], target["x"] - bullet["x"])
                angles.append(abs(math.degrees(math.atan2(math.sin(a - b), math.cos(a - b)))))
        check("5s: no precisely aimed shots at hidden player", all(a > 20 for a in angles), angles)
        check("AI searches around last known location", searching, state["ai"])
        check("AI last known position stays frozen", state["ai"]["lastSeen"] == known)
        check("No transient casts/shots between5s samples", state["ai"]["casts"] == 0 and state["enemy"]["shots"] == 0)
        check("Manual AI cast also cannot lock hidden target", not page.evaluate("window.__waterTest.cast('enemy','ember')"))
        reset(page)
        arrange(page, player=remote, enemy={**e, "stamina": 10}, tier="great", ai=True)
        entered = rested = False
        modes = []
        for _ in range(24):
            step(page, 0.1)
            state = snap(page)
            entered |= state["enemy"]["stealth"]["inGrass"]
            rested |= state["enemy"]["stealth"]["hidden"]
            modes.append(state["ai"]["mode"])
        check("Low stamina AI reaches nearby native grass", entered and "进草丛回体力" in modes, modes)
        check("AI hides to rest and regenerates", rested and state["enemy"]["stamina"] > 10, state["enemy"])
        reset(page)
        arrange(page, player=remote, enemy={**e, "stamina": 10}, tier="poke", ai=True)
        step(page, 0.1)
        check("Red-white tier does not use grass recovery", snap(page)["ai"]["retreat"] is None)
        profile = snap(page)["profile"]
        roster = page.evaluate("window.__waterTest.catalog().roster")
        char = next(c for c in roster if c["id"] == 6)
        page.evaluate("(v) => window.__waterTest.select(v)", {**profile, "player": 6, "playerMoves": char["defaultMoves"]})
        reset(page)
        arrange(page, player=g, enemy=e)
        step(page, 2)
        check("Flying Pokemon cannot hide in native grass", snap(page)["player"]["stealth"]["inGrass"] and not snap(page)["player"]["stealth"]["hidden"])
        page.evaluate("(v) => window.__waterTest.select(v)", profile)
        reset(page)
        # Temporary test scene on ordinary town ground, without using native cells.
        spawns = snap(page)["environment"]["spawns"]
        centre = spawns["player"]
        rect = {"x": centre["x"] - 40, "y": centre["y"] - 40, "w": 160, "h": 80}
        page.evaluate("(r) => window.__waterTest.grassRegions([r])", rect)
        arrange(page, player=centre, enemy=spawns["enemy"])
        step(page, 0.8)
        check("Injected rectangle hides on ordinary town ground", snap(page)["player"]["stealth"]["hidden"])
        arrange(page, enemy={"x": centre["x"] + 70, "y": centre["y"]})
        step(page, 0.8)
        check("Exactly70 does not reveal either side", snap(page)["player"]["stealth"]["hidden"] and snap(page)["enemy"]["stealth"]["hidden"])
        arrange(page, enemy={"x": centre["x"] + 69, "y": centre["y"]})
        check("Injected scene uses same proximity rule", not snap(page)["player"]["stealth"]["hidden"] and not snap(page)["enemy"]["stealth"]["hidden"])
        page.evaluate("(c) => window.__waterTest.grassRegions([{points:[{x:c.x-40,y:c.y-40},{x:c.x+40,y:c.y-40},{x:c.x,y:c.y+40}]}])", centre)
        arrange(page, enemy=spawns["enemy"])
        step(page, 0.8)
        check("Injected polygon hides footprint centre", snap(page)["player"]["stealth"]["hidden"])
        arrange(page, player={"x": centre["x"] + 35, "y": centre["y"] + 35})
        check("Polygon bounding-box corner is not grass", not snap(page)["player"]["stealth"]["inGrass"])
        page.evaluate("window.__waterTest.grassRegions([])")
        arrange(page, player=g, enemy=e)
        step(page, 2)
        check("Scene without regions has no stealth", not snap(page)["player"]["stealth"]["hidden"])
        check("Missing scene field cannot hide", page.evaluate("""() => {
          const s = new window.PoightGrassStealth(); s.configure({}, null);
          const p = {x:0,y:0,hp:100,char:{},isPlayer:true};
          const e = {x:200,y:0,hp:100,char:{},isPlayer:false};
          s.update(0,p,e); s.update(2,p,e); return !s.hidden(p) && !s.hidden(e);
        }"""))
        # Reload restores native scene data; take both required mobile viewports.
        page.evaluate("(v) => window.__waterTest.select(v)", profile)
        for width, height, name in [(390, 844, "手机竖屏-玩家藏身"), (844, 390, "手机横屏-玩家藏身")]:
            page.set_viewport_size({"width": width, "height": height})
            page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
            reset(page)
            arrange(page, player=g, enemy=e)
            step(page, 0.8)
            shot(page, f"{name}-{width}x{height}.png")
        check("No JS errors", not errors, errors)
        browser.close()
finally:
    report = {
        "candidateSHA256": hashlib.sha256((ROOT / "候选试玩.html").read_bytes()).hexdigest(),
        "passed": sum(c["ok"] for c in checks),
        "failed": sum(not c["ok"] for c in checks),
        "errors": errors,
        "checks": checks,
    }
    (OUT / "验收.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "checks"}, ensure_ascii=False))
