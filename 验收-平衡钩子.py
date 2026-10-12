"""Headless isolation, deterministic live-engine simulation, HP and save regressions."""
import importlib
import json
import math
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/平衡钩子"
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "截图").mkdir(exist_ok=True)
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8829/").rstrip("/")
DATA = importlib.import_module("游戏数据")
checks, errors = [], []


def check(name, ok, detail=None):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    assert ok, (name, detail)


def ready(page, observe=True):
    deadline = time.monotonic() + 60
    while not page.evaluate(
        "window.__waterTest?.snapshot().artReady" if observe
        else "!document.getElementById('startBattle').disabled"
    ):
        assert time.monotonic() < deadline, "artReady timeout"
        time.sleep(0.025)


def snap(page):
    return page.evaluate("window.__waterTest.snapshot()")


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(URL)
        ready(page, False)
        check("normal URL has no test hook", page.evaluate("!window.__waterTest"))
        page.goto(URL + "/?observe=1")
        ready(page)
        check("observe has no AI control/simulation", page.evaluate(
            "!window.__waterTest.autopilot && !window.__waterTest.simulate"
        ))
        page.evaluate("localStorage.clear()")
        page.reload()
        ready(page)
        check("fresh save defaults to poke", snap(page)["profile"]["tier"] == "poke")
        check("fresh UI is red-white ball tier", page.locator(
            '#difficulty [data-tier="poke"]'
        ).get_attribute("aria-pressed") == "true")
        profile = snap(page)["profile"]
        for tier in ["poke", "great", "ultra", "master"]:
            page.evaluate("p => localStorage.setItem('pocket-arena-loadout-v1', JSON.stringify(p))",
                          {**profile, "tier": tier})
            page.reload()
            ready(page)
            check(f"old {tier} save respected", snap(page)["profile"]["tier"] == tier)
        page.goto(URL + "/?test=1")
        ready(page)
        check("test URL exposes AI control/simulation", page.evaluate(
            "typeof window.__waterTest.autopilot === 'function' && "
            "typeof window.__waterTest.simulate === 'function'"
        ))
        catalog = page.evaluate("window.__waterTest.catalog()")
        roster = {c["id"]: c for c in catalog["roster"]}
        check("snapshot exposes chosen multiplier", snap(page)["hpMultiplier"] == DATA.HP_MULTIPLIER)
        receipt = json.loads((ROOT / "验收记录/平衡/汇总收据.json").read_text())
        # T9's archived 7350-game report is HPx6 evidence, not current runtime configuration.
        # Preserve its provenance instead of rewriting history after the authorized HPx3 change.
        check("archived report remains HPx6; snapshot uses current multiplier",
              receipt["hpMultiplier"] == 6 and snap(page)["hpMultiplier"] == DATA.HP_MULTIPLIER)
        for c in roster.values():
            check(f"{c['id']} same global HP multiplier", c["hp"] == c["baseHP"] * DATA.HP_MULTIPLIER)
        profile.update(player=25, enemy=6, playerMoves=roster[25]["defaultMoves"],
                       enemyMoves=roster[6]["defaultMoves"], tier="poke", map="emerald-rustborocity")
        check("profile selected", page.evaluate("p => window.__waterTest.select(p)", profile))
        page.evaluate("window.__waterTest.autopilot('poke')")
        before = snap(page)
        page.evaluate("window.__waterTest.step(2)")
        after = snap(page)
        check("player really thinks and moves", after["balance"]["playerDecisions"] > 0 and
              (before["player"]["x"], before["player"]["y"]) !=
              (after["player"]["x"], after["player"]["y"]))
        page.evaluate("window.__waterTest.autopilot(null)")
        check("AI handoff reversible", snap(page)["balance"]["playerTier"] is None)
        page.evaluate("window.__waterTest.reset(true)")
        check("reset clears test AI", snap(page)["balance"]["playerTier"] is None)
        run = "v => window.__waterTest.simulate(v)"
        games = [page.evaluate(run, {"seed": seed, "tier": "poke"}) for seed in range(1, 6)]
        repeated = [page.evaluate(run, {"seed": seed, "tier": "poke"}) for seed in range(1, 6)]
        check("five seeds reproduce full damage ledgers", games == repeated)
        check("different seeds produce different traces", games[0]["composition"] != games[1]["composition"])
        for i, game in enumerate(games):
            for side in ["a", "b"]:
                income = sum(e["amount"] * (-1 if e["kind"] == "heal" else 1)
                             for e in game["composition"] if e["target"] == side)
                dealt = sum(e["amount"] for e in game["composition"]
                            if e["source"] == side and e["kind"] in ["direct", "dot"])
                # S1 percentage DOT introduces fractional HP; preserve both accounting identities
                # with absolute floating-point tolerance (not a relative gameplay allowance).
                check(f"game {i} {side} damage accounting", math.isclose(
                    income, game["maxHP"][side] - game["hp"][side], rel_tol=0, abs_tol=1e-8)
                    and math.isclose(dealt, game["damageDealt"][side], rel_tol=0, abs_tol=1e-8),
                    {'netDelta': income - (game['maxHP'][side] - game['hp'][side]),
                     'dealtDelta': dealt - game['damageDealt'][side]})
        fast = page.evaluate(run, {"seed": 1357911, "tier": "poke"})
        page.evaluate("window.__waterTest.reset(true); window.__waterTest.autopilot('poke')")
        page.evaluate("window.__waterTest.step(120)")
        stepped = snap(page)
        check("fast path equals step120 live path", fast["hp"] == {
            "a": stepped["player"]["hp"], "b": stepped["enemy"]["hp"]
        } and abs(fast["seconds"] - stepped["matchSeconds"]) < 1e-8
          and abs(fast["combatSeconds"] - stepped["elapsed"]) < 1e-8
          and fast["frozenSeconds"] > 0)
        timeout = page.evaluate(run, {"seed": 1, "tier": "poke", "maxSeconds": 0.1})
        check("timeout explicitly censored", timeout["winner"] == "timeout" and timeout["ticks"] == 12)
        mixed = page.evaluate(run, {"seed": 1, "tier": "poke", "playerTier": "master", "maxSeconds": 2})
        check("player tier independently selectable", mixed["playerTier"] == "master" and
              snap(page)["balance"]["playerDecisions"] > snap(page)["ai"]["decisions"])
        check("bad simulation options rejected", page.evaluate("""() => {
          for (const v of [{seed:-1}, {tier:'oops'}, {playerTier:'oops'},
                           {hpMultiplier:0}, {maxSeconds:Infinity}]) {
            try { window.__waterTest.simulate(v); return false; } catch (_) {}
          }
          return true;
        }"""))
        for width, height in [(1440, 900), (390, 844), (844, 390)]:
            page.set_viewport_size({"width": width, "height": height})
            page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => "
                          "requestAnimationFrame(resolve)))")
            page.evaluate("window.__waterTest.reset(true); window.__waterTest.autopilot('poke'); "
                          "window.__waterTest.step(8)")
            state = snap(page)
            check(f"player on camera {width}x{height}", all(
                0 <= state["player"][axis] - state["camera"][axis] <= state["viewport"][size]
                for axis, size in [("x", "width"), ("y", "height")]
            ))
            page.screenshot(path=str(OUT / "截图" / f"AI对AI-{width}x{height}.png"))
            check(f"no horizontal overflow {width}x{height}", page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth + 1"
            ))
        check("no JS errors", not errors, errors)
        browser.close()


if __name__ == "__main__":
    try:
        main()
    finally:
        report = {"passed": sum(c["ok"] for c in checks),
                  "failed": sum(not c["ok"] for c in checks), "errors": errors,
                  "hpMultiplier": DATA.HP_MULTIPLIER, "checks": checks}
        (OUT / "浏览器验收.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({k: report[k] for k in ["passed", "failed", "errors", "hpMultiplier"]},
                         ensure_ascii=False))
