"""Headless arena integration checks; variant rebuild is restored in finally."""

import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent
OUT = ROOT / "验收记录/竞技场"
SHOTS = OUT / "截图"
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8823/").rstrip("/")
CHECKS, ERRORS, METRICS = [], [], []


def check(name, ok, detail=None):
    CHECKS.append({"name": name, "ok": bool(ok), "detail": detail})
    assert ok, (name, detail)


def ready(page):
    for _ in range(600):
        if page.evaluate("window.__waterTest?.snapshot().artReady"):
            return
        time.sleep(.025)
    raise TimeoutError("assets")


def snap(page):
    return page.evaluate("window.__waterTest.snapshot()")


def call(page, method, value=None):
    return page.evaluate("([m,v])=>window.__waterTest[m](v)", [method, value])


def fresh(page):
    call(page, "reset", True)
    call(page, "arrange", {"ai": False})


def rebuild():
    with (OUT / "变体构建.log").open("a") as log:
        subprocess.run([sys.executable, "构建完整版.py"], cwd=ROOT, stdout=log,
                       stderr=subprocess.STDOUT, check=True)


def main():
    catalog_path = ROOT / "素材/竞技场/竞技场目录.json"
    original = catalog_path.read_bytes()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()
            page.on("pageerror", lambda e: ERRORS.append(str(e)))
            page.goto(URL + "/?test=1&hud=2")
            ready(page)
            check("清空存档首次默认正规场", snap(page)["environment"]["id"] == "arena-formal")
            catalog = page.evaluate("window.__waterTest.catalog()")
            profile = snap(page)["profile"]
            arenas = [s for s in catalog["scenes"] if s.get("type") == "arena"]
            pikachu = next(c for c in catalog["roster"] if c["id"] == 25)
            for scene in arenas:
                page.goto(URL + "/?test=1&hud=2")
                ready(page)
                name = scene["name"]
                check(name + "加载", call(page, "select", {**profile, "map": scene["id"],
                      "player": 25, "playerMoves": pikachu["defaultMoves"]}))
                fresh(page)
                state = snap(page)
                for side in ["player", "enemy"]:
                    s, p = scene["spawns"][side], state[side]
                    check(name + side + "出生坐标±4", math.hypot(s["x"] - p["x"], s["y"] - p["y"]) <= 4)
                check(name + "双方面对面", abs(math.cos(state["player"]["a"] - state["enemy"]["a"]) + 1) < 1e-6)
                for width, height in [(1440, 900), (390, 844), (844, 390)]:
                    page.set_viewport_size({"width": width, "height": height})
                    time.sleep(.1)
                    state = snap(page)
                    v, c = state["viewport"], state["camera"]
                    check(f"{name}{width}x{height}跟随镜头不越场地边界",
                          c["x"] >= 0 and c["y"] >= 0 and
                          c["x"] + v["width"] <= 2100 + 1e-6 and
                          c["y"] + v["height"] <= 1400 + 1e-6)
                    if height == 390:
                        check(name + "方案2共用跟随镜头且旧顶栏隐藏", page.evaluate("""()=>{
                          return __waterTest.snapshot().hud.variant==='2' &&
                            !document.querySelector('.battlehud') && ['header','.status'].every(q=>
                              getComputedStyle(document.querySelector(q)).display==='none') &&
                            [...document.querySelectorAll('.skill')].every(b=>{
                              const r=b.getBoundingClientRect();
                              return r.width>=48 && r.left>=0 && r.bottom<=innerHeight;
                            });
                        }"""))
                    call(page, "arrange", {"player": {"x": scene["spawns"]["enemy"]["x"]}})
                    call(page, "step", .2)
                    check(f"{name}{width}x{height}镜头跟随玩家", snap(page)["camera"]["x"] > c["x"])
                    fresh(page)
                    page.screenshot(path=str(SHOTS / f"{name}-{width}x{height}.png"))
                    METRICS.append({"scene": name, "viewport": [width, height], "camera": c, "fit": v})
                page.set_viewport_size({"width": 1440, "height": 900})
                # Every annotation must block the actual terrain movement and shot geometry.
                geometry = page.evaluate("""async id=>{
                  const scene=__waterTest.catalog().scenes.find(s=>s.id===id);
                  const arena=await PoightArena.load(scene,src=>new Promise((yes,no)=>{
                    const im=new Image();im.onload=()=>yes(im);im.onerror=no;im.src=src;
                  }));
                  return scene.collisionContract.map(o=>{
                    const y=o.y+o.h/2,p={x:o.x-25,y};
                    arena.move(p,o.w+50,0,18);
                    return {id:o.id,solid:!arena.freeAt(o.x+o.w/2,y,1),
                      swept:p.x<=o.x-18+1e-6,
                      ray:!__waterTest.clearLine(o.x-25,y,o.x+o.w+25,y,3)};
                  });
                }""", scene["id"])
                for g in geometry:
                    check(g["id"] + "移动/闪避扫掠与射线阻挡", g["solid"] and g["swept"] and g["ray"], g)
                # Live keyboard movement and dash against all four battle boundaries.
                b = scene["bounds"]
                cx, cy = (b["left"] + b["right"]) / 2, (b["top"] + b["bottom"]) / 2
                for key, dx, dy in [("a", -1, 0), ("d", 1, 0), ("w", 0, -1), ("s", 0, 1)]:
                    fresh(page)
                    call(page, "arrange", {"player": {"x": cx, "y": cy}})
                    page.keyboard.down(key)
                    call(page, "step", 4)
                    page.keyboard.up(key)
                    page.evaluate("([x,y])=>__waterTest.dash('player',x,y)", [dx, dy])
                    call(page, "step", .3)
                    p = snap(page)["player"]
                    r = p["body"]["moveRadius"]
                    check(name + key + "走路与闪避不出战斗区", b["left"] + r - .01 <= p["x"] <= b["right"] - r + .01
                          and b["top"] + r - .01 <= p["y"] <= b["bottom"] - r + .01)
                    call(page, "injectWater", {"owner": "player", "x": p["x"], "y": p["y"], "ux": dx, "uy": dy})
                    call(page, "step", 2)
                    check(name + key + "飞行物出边界消失", not snap(page)["bullets"])
                rocks = [o for o in scene["collisionContract"] if o.get("kind") == "rock"
                         and b["left"] < o["x"] and o["x"] + o["w"] < b["right"]]
                for o in rocks:
                    fresh(page)
                    left = {"x": o["x"] - 35, "y": o["y"] + o["h"] / 2}
                    right = {"x": o["x"] + o["w"] + 35, "y": left["y"]}
                    call(page, "arrange", {"player": left, "enemy": right})
                    page.keyboard.down("d")
                    call(page, "step", .5)
                    page.keyboard.up("d")
                    p = snap(page)["player"]
                    check(o["id"] + "实走脚印不进入岩石", p["x"] + p["body"]["moveRadius"] <= o["x"] + .01)
                    page.evaluate("__waterTest.dash('player',1,0)")
                    call(page, "step", .3)
                    p = snap(page)["player"]
                    check(o["id"] + "实闪避不穿石", p["x"] + p["body"]["moveRadius"] <= o["x"] + .01)
                    call(page, "arrange", {"player": {"x": o["x"] - 65, "y": left["y"]}})
                    page.evaluate("__waterTest.equip('player',['watergun','protect','agility','tackle'])")
                    hp = snap(page)["enemy"]["hp"]
                    check(o["id"] + "实际水枪发射", page.evaluate("__waterTest.cast('player','watergun')"))
                    saw, last_x = False, None
                    for _ in range(180):
                        call(page, "step", 1 / 120)
                        bullets = snap(page)["bullets"]
                        if bullets:
                            saw, last_x = True, bullets[0]["x"]
                        elif saw:
                            break
                    check(o["id"] + "水枪在岩石边缘消失且身后不掉血", saw and not snap(page)["bullets"]
                          and abs(last_x - o["x"]) < 25 and snap(page)["enemy"]["hp"] == hp, last_x)
                    fresh(page)
                    call(page, "arrange", {"ai": True, "player": left, "enemy": right})
                    reached = False
                    for _ in range(100):
                        call(page, "step", .1)
                        s = snap(page)
                        if math.hypot(s["player"]["x"] - s["enemy"]["x"], s["player"]["y"] - s["enemy"]["y"]) < 140 and page.evaluate(
                            "()=>{const s=__waterTest.snapshot();return __waterTest.clearLine(s.player.x,s.player.y,s.enemy.x,s.enemy.y,5)}"):
                            reached = True
                            break
                    check(o["id"] + "AI十秒内绕路到可见射程", reached and snap(page)["ai"]["pathSearches"] > 0, snap(page)["ai"])
                call(page, "reset", True)
                call(page, "step", 10)
                check(name + "出生后AI十秒内接近并出招", snap(page)["ai"]["casts"] > 0, snap(page)["ai"])
                fresh(page)
                path = page.evaluate("()=>{const s=__waterTest.snapshot();return __waterTest.findPath(s.player.x,s.player.y,s.enemy.x,s.enemy.y)}")
                check(name + "障碍生成网格可寻路", bool(path))
                # Menu both entry points use the same three choices (two if natural not ready).
                page.locator("#battleMenuButton").click()
                page.locator("#sceneButton").click()
                names = page.locator("#sceneCards strong").all_text_contents()
                check(name + "对战菜单顺序", names == [s["name"] for s in arenas] + ["丰缘大地图 · 彩蛋"], names)
                page.locator('#sceneCards [data-scene="emerald-littleroottown"]').click()
                page.locator("#applyScene").click()
                ready(page)
                for _ in range(200):
                    if snap(page)["environment"]["id"] == "emerald-littleroottown":
                        break
                    time.sleep(.025)
                page.locator("#game").click()
                call(page, "step", 2)
                check("彩蛋可战斗并保留滚动世界", snap(page)["world"]["width"] > 1050 and snap(page)["ai"]["decisions"] > 0)
                page.locator("#battleMenuButton").click()
                page.locator("#sceneButton").click()
                page.locator(f'#sceneCards [data-scene="{scene["id"]}"]').click()
                page.locator("#applyScene").click()
                for _ in range(200):
                    if snap(page)["environment"]["id"] == scene["id"]:
                        break
                    time.sleep(.025)
                s = snap(page)
                check(name + "切回无飞行物/寻路/镜头残留", not s["bullets"] and s["generated"]["active"] == 0
                      and s["ai"]["pathSearches"] == 0 and s["environment"]["terrain"]["lastPathVisited"] == 0
                      and s["world"] == {"width": 2100, "height": 1400})
                page.locator("#battleMenuButton").click()
                page.locator("#setupButton").click()
                page.locator("#setupMapButton").click()
                check(name + "选人菜单同序", page.locator("#sceneCards strong").all_text_contents() == names)
                page.locator("#cancelScene").click()
                page.locator("#closeSetup").click()
                # Debug overlay renders the exact runtime boxes, not separate approximate geometry.
                page.goto(URL + "/?test=1&hud=2&arenaDebug=1")
                ready(page)
                fresh(page)
                page.screenshot(path=str(SHOTS / f"{name}-碰撞框.png"))
                for g in scene["grassRegions"]:
                    fresh(page)
                    point = {"x": g["x"] + g["width"] / 2, "y": g["y"] + g["height"] / 2}
                    check(g["id"] + "高草可走不是障碍", page.evaluate("p=>__waterTest.freeAt(p.x,p.y,10)", point))
                    call(page, "arrange", {"player": point})
                    page.screenshot(path=str(SHOTS / f'{name}-{g["id"]}-遮脚.png'))
                expected = json.loads((ROOT / "素材/竞技场/扩建" / (name + "-A.json")).read_text()).get("grassRegions", [])
                check(name + "高草区域换算保留", len(expected) == len(scene["grassRegions"]) and all(
                    abs(a["x"] * 2100 - c["x"]) < 1e-8 and abs(a["height"] * 1400 - c["height"]) < 1e-8
                    for a, c in zip(expected, scene["grassRegions"])))
            # Old town saves must survive startup, not just the select API.
            call(page, "select", {**profile, "map": "emerald-rustborocity"})
            page.reload()
            ready(page)
            check("旧存档仍载入卡那兹市", snap(page)["environment"]["id"] == "emerald-rustborocity")
            # Only a single variant field is changed per scene, then the real builder/server is exercised.
            for scene in arenas:
                changed = json.loads(original)
                next(s for s in changed["scenes"] if s["id"] == scene["id"])["variant"] = "B"
                catalog_path.write_text(json.dumps(changed, ensure_ascii=False, indent=2) + "\n")
                rebuild()
                page.reload()
                ready(page)
                call(page, "select", {**profile, "map": scene["id"]})
                s = snap(page)
                png = (ROOT / "素材/竞技场/扩建" / (scene["name"] + "-B.png")).read_bytes()
                expected_src = "assets/arena-" + hashlib.sha256(png).hexdigest()[:12] + ".png"
                check(scene["name"] + "改一个字段构建后实际加载B图", s["environment"]["variant"] == "B"
                      and s["environment"]["groundSrc"] == expected_src and page.request.get(URL + "/" + expected_src).status == 200)
                manifest = json.loads((ROOT / "候选发布清单.json").read_text())["assets"]
                for variant in "AC":
                    data = (ROOT / "素材/竞技场/扩建" / (scene["name"] + f"-{variant}.png")).read_bytes()
                    src = "assets/arena-" + hashlib.sha256(data).hexdigest()[:12] + ".png"
                    check(scene["name"] + variant + "未选不入包且HTTP拒绝", src not in manifest and page.request.get(URL + "/" + src).status == 404)
                catalog_path.write_bytes(original)
            check("无JS错误", not ERRORS, ERRORS)
            browser.close()
    finally:
        catalog_path.write_bytes(original)
        rebuild()
        roster = json.loads((ROOT / "素材/角色库/角色库.json").read_text())
        mon = next(c for c in roster if c["id"] == 25)
        idle = mon["art"]["idle"]
        with Image.open(ROOT / "素材/角色库" / idle["file"]) as im:
            fw, fh = idle["frameWidth"], idle["frameHeight"]
            heights = [im.crop((x*fw, y*fh, (x+1)*fw, (y+1)*fh)).getbbox()
                       for x in range(idle["frames"]) for y in range(idle["rows"])]
        mapping = json.loads((ROOT / "数值资料/体型校准/映射记录.json").read_text())
        body_profile = next(c for c in mapping["species"] if c["id"] == 25)
        scale = body_profile["scale"]
        camera_scale = 900 * .046 / body_profile["body"]["visibleSize"][1]
        receipt = {"passed": sum(c["ok"] for c in CHECKS), "failed": sum(not c["ok"] for c in CHECKS),
                   "errors": ERRORS, "checks": CHECKS, "metrics": METRICS,
                   "pikachu": {"maxNativeIdle": max(b[3]-b[1] for b in heights), "scale": scale,
                               "desktopHeight": max(b[3]-b[1] for b in heights) * scale * camera_scale}}
        (OUT / "浏览器验收.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({k: receipt[k] for k in ["passed", "failed", "errors", "pikachu"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
