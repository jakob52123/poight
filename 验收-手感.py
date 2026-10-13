"""H1: archived M4/live H1, real input, rendered 60 Hz samples and input invariants.

Both HTMLs share unchanged assets and CSP on the one assigned preview origin.
Time is the test engine's clock (not machine/network wall time). Key hold is 5
render frames on both builds. Damage is observed on a fixed nearby target, never
estimated by advancing damage ahead of a visible release. AI refusal sampling
uses the existing player autopilot with identical 0.5s round-robin key stimuli.
"""
import base64
import hashlib
import json
import math
import os
import time
from pathlib import Path
from statistics import median

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/手感"
SHOTS = OUT / "截图"
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8868/").rstrip("/")
BASE = "f64982be201b70212a8a6b3e0ff5fad6618f6cad"
checks, errors = [], []
CSP = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'"


def check(name, ok, detail=None):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def ready(page):
    for _ in range(2400):
        if page.evaluate("window.__waterTest?.snapshot().artReady"):
            return
        time.sleep(0.025)
    detail = page.evaluate("""()=>({message:document.querySelector('#setupMessage')?.textContent,
      state:window.__waterTest?.snapshot().phase})""")
    raise TimeoutError(json.dumps({'artReadyTimeout': detail, 'jsErrors': errors}, ensure_ascii=False))


def load(browser, path):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.on("pageerror", lambda e: errors.append(str(e)))
    # M5's serving manifest only exposes the new 49-map candidate. Replay the archived
    # M4 asset references locally; do not widen the production preview allowlist.
    if path.name == "M4-baseline.html":
        page.route(URL + "/assets/*", lambda route: route.fulfill(
            path=ROOT / "assets" / route.request.url.rsplit("/", 1)[-1]))
    html = path.read_text().replace(
        "function rejectCast(slot, reason) {",
        "window.__h1Refusals = {cool:0, stamina:0, busy:0}; window.__h1Seen={};\n"
        "function rejectCast(slot, reason) {\n"
        "if(reason && window.__h1Seen[reason.code]!==window.__h1Attempt) {"
        "window.__h1Seen[reason.code]=window.__h1Attempt;"
        "window.__h1Refusals[reason.code] = (window.__h1Refusals[reason.code]||0)+1;}")
    html = html.replace("function impact(p, a, target) {",
                        "function impact(p, a, target) { if(p.isPlayer) window.__h1Release=true;")
    page.route(URL + "/?test=1", lambda route: route.fulfill(
        body=html, content_type="text/html; charset=utf-8",
        headers={"Content-Security-Policy": CSP}))
    page.goto(URL + "/?test=1")
    ready(page)
    return page


def snap(page):
    return page.evaluate("window.__waterTest.snapshot()")


def setup(page, profile, x, y, move=None, distance=70):
    assert page.evaluate("v => window.__waterTest.select(v)", profile), profile
    assert snap(page)["environment"]["id"] == profile["map"]
    page.evaluate("window.__waterTest.reset(true)")
    if move:
        page.evaluate("v => window.__waterTest.equip('player',[v])", move)
    page.evaluate("v => window.__waterTest.arrange(v)", {
        "ai": False, "player": {"x": x, "y": y, "hp": 50},
        "enemy": {"x": x + distance, "y": y}})
    page.evaluate("window.__waterTest.step(1)")
    page.locator("#game").focus()


def measure(page, catalog, x, y):
    roster = {c["id"]: c for c in catalog["roster"]}
    original = snap(page)["profile"]
    rows = {}
    for mid, move in catalog["moves"].items():
        owner = 25 if mid in roster[25]["defaultMoves"] else 6 if mid in roster[6]["defaultMoves"] else next(
            c["id"] for c in catalog["roster"] if mid in c["learnset"])
        profile = {**original, "map": "emerald-rustborocity", "player": owner,
                   "enemy": 7, "playerMoves": roster[owner]["defaultMoves"],
                   "enemyMoves": roster[7]["defaultMoves"], "holdAim": True}
        distance = 30 if move['kind'] in ['melee','spin'] else 70
        setup(page, profile, x, y, mid, distance)
        result = page.evaluate("""() => {
          const t = window.__waterTest, dt = 1/60, hp = t.snapshot().enemy.hp;
          const key = type => window.dispatchEvent(new KeyboardEvent(type,
            {code:'KeyJ', key:'j', bubbles:true}));
          window.__h1Release=false;
          key('keydown');
          let pose = null, release = null, damage = null, unsafe = false;
          for(let i=1; i<=240; i++) {
            if(i===6) key('keyup');
            t.step(dt); // renders the same role/frame that snapshot reports
            const s=t.snapshot(), a=s.player.attack;
            if(pose===null && a && ['shoot','melee','hurt'].includes(s.player.anim)) pose=i*dt*1000;
            if(release===null && (a?.emitted || window.__h1Release)) release=i*dt*1000;
            if(s.enemy.hp<hp && damage===null) {
              damage=i*dt*1000; unsafe=release===null;
            }
            if(release!==null && (damage!==null || i>120)) break;
          }
          key('keyup');
          return {pose,release,damage,unsafe};
        }""")
        rows[mid] = {"name": move["name"], "owner": owner, **result}
        check(mid + ": rendered pose and release measured", result["pose"] is not None and result["release"] is not None, result)
        check(mid + ": no damage before visible release", not result["unsafe"], result)
    return rows


def ai_refusals(page, catalog):
    roster = {c["id"]: c for c in catalog["roster"]}
    profile = {**snap(page)["profile"], "map": "emerald-rustborocity", "player": 25,
               "enemy": 6, "playerMoves": roster[25]["defaultMoves"],
               "enemyMoves": roster[6]["defaultMoves"], "tier": "poke", "holdAim": True}
    page.evaluate("v => window.__waterTest.select(v)", profile)
    # run(maxSeconds=epsilon) initializes exactly the existing seeded AI setup.
    page.evaluate("window.__waterTest.simulate({seed:1,tier:'poke',maxSeconds:1/120})")
    page.locator("#game").focus()
    return page.evaluate("""() => {
      const t=window.__waterTest, codes=['KeyJ','KeyK','KeyL','KeyI'];
      window.__h1Refusals={cool:0,stamina:0,busy:0}; window.__h1Seen={};
      window.__h1Attempt=0;
      let pressed=0, i=0;
      for(;i<7200 && t.snapshot().phase==='playing';i++) {
        const code=codes[Math.floor(i/60)%4];
        if(i%60===0) {window.__h1Attempt++;window.dispatchEvent(new KeyboardEvent('keydown',{code,bubbles:true}));pressed++;}
        if(i%60===10) window.dispatchEvent(new KeyboardEvent('keyup',{code,bubbles:true}));
        t.step(1/120,false);
      }
      for(const code of codes) window.dispatchEvent(new KeyboardEvent('keyup',{code,bubbles:true}));
      return {seconds:i/120,pressed,refusals:window.__h1Refusals};
    }""")


def movement(page, profile, x, y):
    result = {}
    for mid in ["thunderbolt", "irontail", "recover"]:
        setup(page, profile, x, y, mid)
        page.evaluate("v => window.__waterTest.cast('player',v)", mid)
        page.keyboard.down("KeyS")
        first = snap(page)["player"]
        page.evaluate("window.__waterTest.step(.05)")
        last = snap(page)["player"]
        result[mid] = (last["y"]-first["y"])/(first["speed"]*.05)
        page.keyboard.up("KeyS")
    return result


def p90(values):
    return sorted(values)[math.ceil(len(values)*0.9)-1]


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    before = load(browser, OUT / "M4-baseline.html")
    catalog = before.evaluate("window.__waterTest.catalog()")
    def lane_position(data):
        terrain = data["terrains"][0]
        walk, cols = base64.b64decode(terrain["walkB64"]), terrain["columns"]
        area = next(a for a in terrain["areas"] if a["sourceName"] == "RustboroCity")
        lane = next((x,y) for y in range(area["gridY"]+3,area["gridY"]+area["rows"]-3)
                    for x in range(area["gridX"]+7,area["gridX"]+area["columns"]-7)
                    if all(walk[(y+dy)*cols+x+dx] for dy in range(-2,3) for dx in range(-6,7)))
        return ((lane[0]+0.5)*terrain["cellSize"], (lane[1]+0.5)*terrain["cellSize"])

    x, y = lane_position(catalog)
    baseline = measure(before, catalog, x, y)
    baseline_ai = ai_refusals(before, catalog)
    old_roster = {c["id"]: c for c in catalog["roster"]}
    baseline_profile = {**snap(before)["profile"], "map":"emerald-rustborocity", "player":25, "enemy":143,
                        "playerMoves":old_roster[25]["defaultMoves"],
                        "enemyMoves":old_roster[143]["defaultMoves"], "holdAim":True}
    baseline_ratios = movement(before, baseline_profile, x, y)
    setup(before, baseline_profile, x, y)
    before.keyboard.press("KeyA")
    before.evaluate("window.__waterTest.step(.03)")
    before.keyboard.press("KeyA")
    old_x = snap(before)["player"]["x"]
    before.evaluate("window.__waterTest.step(1/120)")
    check("Baseline double tap starts displacement on next tick", snap(before)["player"]["x"] < old_x)
    before.close()
    after = load(browser, ROOT / "候选试玩.html")
    new_catalog = after.evaluate("window.__waterTest.catalog()")
    # W2 rebased RustboroCity by +122 rows; use the same map-local lane, not M4 world XY.
    x, y = lane_position(new_catalog)
    for mid, old in catalog["moves"].items():
        new = new_catalog["moves"][mid]
        expected_windup = 0 if old["windup"] == 0 else min(.35, max(.05, old["windup"]*.5))
        if new.get("fangs"):
            expected_windup = max(.10, expected_windup)
        expected_recovery = (.7 if mid == 'crunch' else .38) if new.get('fangs') else old['recovery']
        expected_cd = old["cd"] if old["kind"] in ["heal","buff","splash"] else min(3,max(.45,old["cd"]*.4))
        check(mid + ": windup transformed once", abs(new["windup"]-expected_windup)<1e-9)
        check(mid + ": recovery transformed once", abs(new["recovery"]-expected_recovery*.6)<1e-9)
        check(mid + ": cooldown with support exception", abs(new["cd"]-expected_cd)<1e-9)
        expected_status = {k: v for k, v in old.items()
                           if k != 'burn' and not (k == 'slow' and old['type'] == 13)}
        check(mid + ": damage/range/resources/anchors retained with S1 field migration",
              all(new.get(k)==expected_status.get(k) for k in
                  ["damage","range","rangeBodies","cost","speed","radius","delay","slow","anchor"]))
        if old.get("limb"):
            check(mid + ": contact delay zero and window retained", new["contactDelay"]==0 and new["contactWindow"]==old["contactWindow"])
    current = measure(after, new_catalog, x, y)
    current_ai = ai_refusals(after, new_catalog)
    roster = {c["id"]: c for c in catalog["roster"]}
    profile = {**snap(after)["profile"], "map": "emerald-rustborocity", "player": 25,
               "enemy": 143, "playerMoves": roster[25]["defaultMoves"],
               "enemyMoves": roster[143]["defaultMoves"], "holdAim": True}
    setup(after, profile, x, y)
    after.keyboard.down("KeyJ")
    check("Keyboard casts on down, not release", snap(after)["player"]["attack"]["id"] == "thunderbolt")
    after.evaluate("window.__waterTest.step(.1)")
    after.screenshot(path=str(SHOTS / "皮卡丘-十万伏特-按下100ms-1440x900.png"))
    after.keyboard.up("KeyJ")
    setup(after, profile, x, y)
    after.locator("#skills .skill").first.dispatch_event("pointerdown", {"button":0,"pointerType":"mouse"})
    check("Mouse skill casts on pointerdown", snap(after)["player"]["attack"]["id"] == "thunderbolt")
    setup(after, profile, x, y)
    start = snap(after)["player"]
    after.keyboard.press("Shift")
    check("Shift starts dash without input direction", snap(after)["player"]["dashing"])
    after.evaluate("window.__waterTest.step(1/120)")
    end = snap(after)["player"]
    dodge_ms = 1000/120
    check("Shift moves away on first tick", end["x"] < start["x"])
    after.evaluate("window.__waterTest.step(.3216666667)")
    after.keyboard.press("Shift")
    s = snap(after)
    check("Last 80ms dash memory does not pre-spend", s["dashMemory"] is not None and s["player"]["spent"] == 15 and not s["player"]["protected"])
    after.evaluate("window.__waterTest.step(.075)")
    check("Dash memory executes at cooldown end", snap(after)["player"]["dodges"] == 2)
    setup(after, profile, x, y)
    after.evaluate("window.__waterTest.feedbackHit(30,1)")
    after.keyboard.press("KeyJ")
    after.evaluate("window.__waterTest.step(.09)")
    check("Skill buffer pauses in freeze", abs(snap(after)["queued"]["remaining"]-.12)<1e-8)
    after.evaluate("window.dispatchEvent(new Event('blur'))")
    check("Blur clears skill and dodge memory", snap(after)["queued"] is None and snap(after)["dashMemory"] is None)
    ratios = {}
    for mid in ["thunderbolt","irontail","recover"]:
        setup(after, profile, x, y, mid)
        after.keyboard.down("KeyS")
        after.keyboard.down("KeyJ")
        first = snap(after)["player"]
        after.evaluate("window.__waterTest.step(.05)")
        last = snap(after)["player"]
        ratios[mid] = (last["y"]-first["y"])/(first["speed"]*.05)
        after.keyboard.up("KeyS")
        after.keyboard.up("KeyJ")
        check(mid + ": move ratio", abs(ratios[mid]-{"thunderbolt":.9,"irontail":.75,"recover":.5}[mid])<.01, ratios[mid])
    for label, hurt, hurt_age, slow, expected in [
            ('fresh ordinary hit', .4, 0, 0, .65),
            ('ordinary hit older than 200ms', .18, .22, 0, 1),
            ('status slow plus ordinary hit uses max, not product', .4, 0, 2, .65)]:
        setup(after, profile, x, y)
        after.evaluate('v => window.__waterTest.arrange({player:v})',
                       {'hurt':hurt, 'hurtAge':hurt_age, 'slow':slow})
        first = snap(after)['player']
        after.keyboard.down('KeyS')
        after.evaluate('window.__waterTest.step(.05)')
        last = snap(after)['player']
        after.keyboard.up('KeyS')
        ratio = (last['y']-first['y'])/(first['speed']*.05)
        check(label, abs(ratio-expected)<.01, ratio)
    setup(after,profile,x,y)
    after.evaluate('window.__waterTest.arrange({player:{hurt:.4}})')
    after.keyboard.press('KeyJ')
    after.evaluate('window.__waterTest.step(.13)')
    check('Expired skill memory cannot cast later', snap(after)['queued'] is None and snap(after)['player']['attack'] is None)
    for width,height in [(390,844),(844,390)]:
        after.set_viewport_size({"width":width,"height":height})
        setup(after,profile,x,y)
        after.keyboard.press("KeyJ")
        after.evaluate("window.__waterTest.step(.1)")
        after.screenshot(path=str(SHOTS / f"皮卡丘-十万伏特-{width}x{height}.png"))
    check("Sound defaults on", snap(after)["sound"])
    after.close()
    browser.close()

poses = [v["pose"] for v in current.values() if v["pose"] is not None]
releases = [v["release"] for v in current.values() if v["release"] is not None]
old_releases = [v["release"] for v in baseline.values() if v["release"] is not None]
reduction = 1-median(releases)/median(old_releases)
old_cool, new_cool = baseline_ai["refusals"]["cool"], current_ai["refusals"]["cool"]
cool_reduction = 1-new_cool/old_cool if old_cool else None
check("All-move pose median <=50ms", median(poses)<=50, median(poses))
check("All-move release median reduction >=45%", reduction>=.45, reduction)
check("Cooldown refusals reduced >=60%", cool_reduction is not None and cool_reduction>=.6,
      {"before":baseline_ai,"after":current_ai,"reduction":cool_reduction})
check("No JS errors", not errors, errors)
report = {"baselineSHA":BASE,"baselineHTMLSHA256":hashlib.sha256((OUT/"M4-baseline.html").read_bytes()).hexdigest(),
          "before":baseline,"after":current,"aiBefore":baseline_ai,"aiAfter":current_ai,
          "poseMedianMs":median(poses),"poseP90Ms":p90(poses),
          "releaseMedianBeforeMs":median(old_releases),"releaseMedianMs":median(releases),
          "releaseP90Ms":p90(releases),"releaseReduction":reduction,
          "cooldownReduction":cool_reduction,"dodgeMs":dodge_ms,"baselineDodgeMs":1000/120,
          "ratios":ratios,"baselineRatios":baseline_ratios,
          "passed":sum(c["ok"] for c in checks),"failed":sum(not c["ok"] for c in checks),
          "jsErrors":len(errors),"errors":errors,"checks":checks}
(OUT/"浏览器验收.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
lines = ["# H1 手感对比", "", f"基线：`{BASE}`；采样60Hz，误差上界16.67ms；每次按键保持83.33ms。",
         "姿态首帧以渲染后的角色动画状态统计；首次伤害是固定杰尼龟靶位实测（近身30px/其他70px；支持招为—，未命中为—），不是提前伤害结算。",
         "AI为现有poke双侧托管、seed=1，另施加每0.5秒一次轮换技能按键；同样策略与按键保持时间。死亡后不伪造60秒存活或继续计键。",
         "", "|指标|M4|H1|", "|---|---:|---:|",
         f"|全部招式姿态中位数(ms)|{median([v['pose'] for v in baseline.values() if v['pose'] is not None]):.2f}|{median(poses):.2f}|",
         f"|放出中位数 / P90(ms)|{median(old_releases):.2f} / {p90(old_releases):.2f}|{median(releases):.2f} / {p90(releases):.2f}|",
         f"|冷却拒绝|{old_cool}|{new_cool}|", f"|观测时长(s)|{baseline_ai['seconds']}|{current_ai['seconds']}|",
         f"|闪避触发→位移(ms)|{1000/120:.2f}（第二次方向按下）|{dodge_ms:.2f}（Shift按下）|", "",
         f"放出缩短：{reduction:.2%}；冷却拒绝下降：{cool_reduction:.2%}" if cool_reduction is not None else "基线无冷却拒绝，下降率无定义。",
         f"出招移动比例（M4→H1）：{baseline_ratios} → {ratios}", "", "## 三栏逐招（M4→H1，ms）", "",
         "|招式|姿态首帧|招式放出|固定靶首次伤害|", "|---|---:|---:|---:|"]
hero = roster[25]["defaultMoves"] + roster[6]["defaultMoves"]
for mid in hero + [m for m in current if m not in hero]:
    old,new = baseline[mid],current[mid]
    def cell(key, old=old, new=new):
        return " → ".join("—" if v is None else f"{v:.2f}" for v in [old[key],new[key]])
    lines.append(f"|{new['name']}{'（主角）' if mid in hero else ''}|{cell('pose')}|{cell('release')}|{cell('damage')}|")
lines += ["", "## 验收", "", *[f"- {'通过' if c['ok'] else '失败'}：{c['name']} {c['detail'] if not c['ok'] else ''}" for c in checks if not c['ok'] or c['name'].startswith('All-move')]]
(OUT/"对比.md").write_text("\n".join(lines)+"\n")
print(json.dumps({k:report[k] for k in ["passed","failed","jsErrors","poseMedianMs","releaseReduction","cooldownReduction"]},ensure_ascii=False))
raise SystemExit(bool(report["failed"] or errors))
