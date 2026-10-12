"""A1: real selected variants, scale/render interception, movement, AI and screenshots."""
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent
OUT = ROOT / "验收记录/场地比例"
SHOTS = OUT / "截图"
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8879/").rstrip("/")
CHECKS, ERRORS, METRICS, TIMINGS = [], [], [], {}
CATALOG = ROOT / "素材/竞技场/竞技场目录.json"


def check(name, ok, detail=None):
    CHECKS.append({"name": name, "ok": bool(ok), "detail": detail})
    assert ok, (name, detail)


def call(page, method, value=None):
    return page.evaluate("([m,v])=>__waterTest[m](v)", [method, value])


def snap(page):
    return call(page, "snapshot")


def ready(page):
    for _ in range(800):
        if page.evaluate("window.__waterTest?.snapshot().artReady"):
            return
        time.sleep(.025)
    raise TimeoutError("artReady")


def rebuild():
    with (OUT / "构建.log").open("a") as log:
        subprocess.run([sys.executable, "构建完整版.py"], cwd=ROOT, stdout=log,
                       stderr=subprocess.STDOUT, check=True)


def fresh(page):
    call(page, "reset", True)
    call(page, "arrange", {"ai": False})


def select(page, scene):
    catalog = call(page, "catalog")
    roster = {c["id"]: c for c in catalog["roster"]}
    check(scene + "选择", call(page, "select", {**snap(page)["profile"],
          "player": 25, "enemy": 6, "map": scene, "tier": "great", "shake": False,
          "playerMoves": roster[25]["defaultMoves"], "enemyMoves": roster[6]["defaultMoves"]}))
    fresh(page)


def render_metric(page):
    # Read the actual alpha bounds of the source frame passed to the real canvas drawImage.
    # Transform includes body.scale and viewport.scale; excludes bars/shadows/effects.
    return page.evaluate("""()=>{
      const api=__waterTest, p=api.snapshot().player,
        suffix=api.catalog().art[25].idle.src,
        canvas=document.querySelector('#game'), ctx=canvas.getContext('2d'), old=ctx.drawImage;
      let found=null;
      ctx.drawImage=function(im,...a){
        if(im instanceof HTMLImageElement && im.src.endsWith(suffix) && a.length===8){
          const [sx,sy,sw,sh,dx,dy,dw,dh]=a, scratch=document.createElement('canvas');
          scratch.width=sw; scratch.height=sh;
          const c=scratch.getContext('2d'); c.drawImage(im,sx,sy,sw,sh,0,0,sw,sh);
          const pixels=c.getImageData(0,0,sw,sh).data;
          let lo=sh, hi=-1;
          for(let y=0;y<sh;y++)for(let x=0;x<sw;x++)
            if(pixels[(y*sw+x)*4+3]) {lo=Math.min(lo,y);hi=Math.max(hi,y);}
          const m=this.getTransform(), r=canvas.getBoundingClientRect();
          found={nativeHeight:hi-lo+1, worldVisibleHeight:(hi-lo+1)*dh/sh,
            screenHeight:(hi-lo+1)*dh/sh*m.d*r.height/canvas.height,
            smoothing:this.imageSmoothingEnabled, scale:p.scale, viewport:r.toJSON()};
        }
        return old.call(this,im,...a);
      };
      try{api.render();}finally{ctx.drawImage=old;}
      return found;
    }""")


def geometry(page, scene, original):
    name = scene["name"] + "-" + scene["variant"]
    check(name + "世界尺寸", scene["world"] == {"width": 2100, "height": 1400})
    if scene["id"] == "arena-formal":
        check(name + "球标直径", 440 <= scene["logoDiameter"] <= 520)
        im = Image.open(ROOT / "素材/竞技场/扩建" / (name + ".png")).convert("RGB")
        # Actual painted white circle at y=350, not metadata alone.
        xs = [x for x in range(380, 670) if im.getpixel((x, 350)) == (243, 231, 200)]
        check(name + "图像球标直径", 440 <= (max(xs) - min(xs)) * 2 <= 520)
    else:
        old_rocks = [o for o in original["obstacles"] if o["kind"] == "rock"]
        rocks = [o for o in scene["collisionContract"] if o["kind"] == "rock"]
        check(name + "岩石数量四倍", len(rocks) == len(old_rocks) * 4)
        check(name + "高草数量四倍", len(scene["grassRegions"]) == len(original["grassRegions"]) * 4)
        check(name + "岩石大于精灵", all(o["h"] > 2 * 32.81 for o in rocks))
    b = scene["bounds"]
    for o in scene["collisionContract"] + scene["grassRegions"]:
        area = {"left": 0, "right": 2100, "top": 0, "bottom": 1400} if o.get("perimeter") else b
        check(o["id"] + "完整在对应区域内", area["left"] <= o["x"] < o["x"] + o["width"] <= area["right"]
              and area["top"] <= o["y"] < o["y"] + o["height"] <= area["bottom"])
        if o.get("perimeter"):
            if o["kind"] == "flag":
                check(o["id"] + "角旗伸入战斗区且仍贴看台",
                      o["x"] < b["right"] and o["x"] + o["width"] > b["left"] and
                      o["y"] < b["bottom"] and o["y"] + o["height"] > b["top"] and
                      (o["x"] == b["left"] or o["x"] + o["width"] == b["right"]))
            else:
                check(o["id"] + "外围实体不侵入可走区", o["x"] + o["width"] <= b["left"] or
                      o["x"] >= b["right"] or o["y"] + o["height"] <= b["top"] or o["y"] >= b["bottom"])
    data = page.evaluate("""()=>{
      const api=__waterTest,s=api.snapshot(),scene=api.catalog().scenes.find(c=>c.id===s.environment.id);
      return {spawns:[s.player,s.enemy].map(p=>api.freeAt(p.x,p.y,26)),
        path:api.findPath(s.player.x,s.player.y,s.enemy.x,s.enemy.y),
        grass:scene.grassRegions.map(g=>[0,.5,1].every(x=>[0,.5,1].every(y=>
          api.freeAt(g.x+g.width*x,g.y+g.height*y,1))))};
    }""")
    check(name + "出生安全且连通", all(data["spawns"]) and bool(data["path"]))
    check(name + "全部草丛可走", all(data["grass"]))
    p, e = scene["spawns"]["player"], scene["spawns"]["enemy"]
    check(name + "出生间隔45%", abs(math.hypot(p["x"]-e["x"], p["y"]-e["y"]) / 2100 - .45) < .001)


def framing(page, label):
    s = snap(page)
    c, v, p = s["camera"], s["viewport"], s["player"]
    check(label + "镜头不越界", c["x"] >= 0 and c["y"] >= 0 and
          c["x"] + v["width"] <= 2100 + .001 and c["y"] + v["height"] <= 1400 + .001)
    # A hard world boundary takes precedence over centering (both cannot hold at the edge).
    for axis, span, extent in [("x", v["width"], 2100), ("y", v["height"], 1400)]:
        if .01 < c[axis] < extent - span - .01:
            check(label + axis + "玩家中央±10%", abs((p[axis]-c[axis]) / span - .5) <= .10)


def measure_walk(page, label, start, end, keys):
    fresh(page)
    call(page, "arrange", {"player": start, "enemy": {"x": 1900, "y": 1200}})
    for key in keys:
        page.keyboard.down(key)
    ticks = 0
    try:
        for ticks in range(1, 1801):
            call(page, "step", 1 / 120)
            p = snap(page)["player"]
            if math.hypot(p["x"]-end["x"], p["y"]-end["y"]) < 2:
                break
        else:
            raise AssertionError((label, p, end))
    finally:
        for key in keys:
            page.keyboard.up(key)
    TIMINGS[label] = {"seconds": ticks / 120, "start": start, "end": end,
                      "speed": snap(page)["player"]["speed"]}
    check(label + "未调世界速度", snap(page)["player"]["speed"] == 224)


def main():
    roster_root = ROOT / "素材/角色库"
    pikachu = next(c for c in json.loads((roster_root / "角色库.json").read_text()) if c["id"] == 25)
    for role in ("idle", "walk"):
        art = pikachu["art"][role]
        im = Image.open(roster_root / art["file"])
        fw, fh = art["frameWidth"], art["frameHeight"]
        heights = []
        for row in range(art["rows"]):
            for frame in range(art["frames"]):
                bbox = im.crop((frame*fw, row*fh, (frame+1)*fw, (row+1)*fh)).getbbox()
                heights.append(bbox[3] - bbox[1])
        for height in (900, 390, 1440):
            ratios = [h * 1.4915 * (height * .046 / 32.81) / height for h in heights]
            check(f"{role}/{height}全部方向帧透明包围盒屏高4–6%",
                  min(ratios) >= .04 and max(ratios) <= .06,
                  {"frames": len(ratios), "minimum": min(ratios), "maximum": max(ratios)})
    original = CATALOG.read_bytes()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.on("pageerror", lambda error: ERRORS.append(str(error)))
            for variant in "ABC":
                catalog = json.loads(original)
                for entry in catalog["scenes"]:
                    entry["variant"] = variant
                CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")
                rebuild()
                page.goto(URL + "/?test=1")
                ready(page)
                arenas = [s for s in call(page, "catalog")["scenes"] if s.get("type") == "arena"]
                for scene in arenas:
                    select(page, scene["id"])
                    name = scene["name"] + "-" + variant
                    annotation = json.loads((ROOT / "素材/竞技场" / (name + ".json")).read_text())
                    geometry(page, scene, annotation)
                    fresh(page)
                    call(page, "arrange", {"ai": True})
                    distances = []
                    for _ in range(60):
                        call(page, "step", .1)
                        s = snap(page)
                        distances.append(math.hypot(s["player"]["x"]-s["enemy"]["x"],
                                                    s["player"]["y"]-s["enemy"]["y"]))
                    moves = call(page, "catalog")["moves"]
                    maximum = max(moves[mid]["range"] for mid in
                                  s["player"]["moves"] + s["enemy"]["moves"])
                    check(name + "6秒内主动接近至两倍最大射程", min(distances) <= 2 * maximum
                          and min(distances) < 745 and s["ai"]["decisions"] > 0,
                          {"distance": min(distances), "maximumRange": maximum, "ai": s["ai"]})
                    if variant != "A":
                        continue
                    if scene["id"] == "arena-natural":
                        page.screenshot(path=SHOTS / "自然场-A-战斗-1440x900.png")
                        continue
                    for width, height in [(1440, 900), (844, 390), (2560, 1440)]:
                        page.set_viewport_size({"width": width, "height": height})
                        fresh(page)
                        m = render_metric(page)
                        check(f"{width}实际精灵绘制拦截", m is not None)
                        ratio = m["screenHeight"] / height
                        check(f"{width}皮卡丘屏高4–6%", .04 <= ratio <= .06, m)
                        check(f"{width}绘制关闭平滑", m["smoothing"] is False)
                        check(f"{width}球标屏高60–68%", .60 <= 480 * snap(page)["viewport"]["scale"] / height <= .68)
                        check(f"{width}身体标定不变", m["scale"] == 1.4915)
                        METRICS.append({"viewport": [width, height], "ratio": ratio, **m})
                        framing(page, f"{width}开局")
                        if width == 1440:
                            page.screenshot(path=SHOTS / "正规场-A-开局-1440x900.png")
                        # Wide phone viewport can include the initial enemy's foot.
                        # Move the fixture beyond its actual viewport, not an old zoom assumption.
                        call(page, "arrange", {"enemy": {"x": 1930, "y": 700}})
                        edge = snap(page)["arenaView"]["edge"]
                        check(f"{width}出屏头像箭头出现", edge is not None)
                        angle = math.atan2(edge["targetY"]-edge["y"], edge["targetX"]-edge["x"])
                        check(f"{width}箭头误差≤10度", abs(math.remainder(edge["angle"]-angle, math.tau)) <= math.radians(10))
                        if width == 1440:
                            call(page, "arrange", {"player": {"x": 1050, "y": 700}})
                            call(page, "step", 2)
                            for ex, ey in [(150, 150), (1050, 150), (1950, 150), (1950, 700),
                                           (1950, 1250), (1050, 1250), (150, 1250), (150, 700)]:
                                call(page, "arrange", {"enemy": {"x": ex, "y": ey}})
                                edge = snap(page)["arenaView"]["edge"]
                                check(f"箭头八方向{ex},{ey}出屏", edge is not None)
                                angle = math.atan2(edge["targetY"]-edge["y"], edge["targetX"]-edge["x"])
                                check(f"箭头八方向{ex},{ey}误差≤10度",
                                      abs(math.remainder(edge["angle"]-angle, math.tau)) <= math.radians(10))
                        call(page, "arrange", {"player": {"x": 1000, "y": 700}})
                        call(page, "step", 1)
                        page.keyboard.down("d")
                        for tick in range(120):
                            call(page, "step", 1 / 120)
                            framing(page, f"{width}跟随{tick}")
                        page.keyboard.up("d")
                        page.evaluate("__waterTest.dash('player',-1,0)")
                        for tick in range(30):
                            call(page, "step", 1 / 120)
                            framing(page, f"{width}闪避跟随{tick}")
                        # Continue to boundary and assert clamp, not an impossible centered wall.
                        page.keyboard.down("d")
                        call(page, "step", 8)
                        page.keyboard.up("d")
                        framing(page, f"{width}右边界")
                    page.set_viewport_size({"width": 1440, "height": 900})
                    measure_walk(page, "出生点到出生点", {"x": 577.5, "y": 700},
                                 {"x": 1522.5, "y": 700}, ["d"])
                    measure_walk(page, "横穿可走场地", {"x": 70, "y": 700},
                                 {"x": 2030, "y": 700}, ["d"])
                    # Hold both directions: diagonal normalization is the real input path;
                    # release the vertical key once its boundary is reached, so measure a
                    # straight diagonal with a custom analog vector via the same mobile input.
                    fresh(page)
                    call(page, "arrange", {"player": {"x": 130, "y": 70},
                                          "enemy": {"x": 1900, "y": 150}})
                    diagonal = page.evaluate("""()=>{
                      const a=__waterTest, start=a.snapshot().player,
                        dx=1840,dy=1260,n=Math.hypot(dx,dy);
                      // Keyboard can only steer 45 degrees. The movement API test hook
                      // uses precisely the same terrain/body sweep at the unchanged speed.
                      return {distance:n,speed:start.speed,expected:n/start.speed};
                    }""")
                    TIMINGS["整场世界对角理论值（含不可走看台）"] = math.hypot(2100, 1400) / 224
                    TIMINGS["可走直线对角理论值"] = diagonal
                    # Real diagonal traversal using pointer joystick is tested below.
                    fresh(page)
            # All HUD modes, actual mobile landscape minimap/buttons and portrait overlay.
            CATALOG.write_bytes(original)
            rebuild()
            for mode in (1, 2, 3):
                page.goto(URL + f"/?test=1&hud={mode}")
                ready(page)
                select(page, "arena-formal")
                check(f"HUD{mode}统一镜头", abs(snap(page)["viewport"]["scale"] - 900*.046/32.81) < 1e-8)
                call(page, "arrange", {"player": {"x": 1050, "y": 700}})
                call(page, "step", 2)
                before = snap(page)
                x, span = before["camera"]["x"], before["viewport"]["width"]
                call(page, "arrange", {"player": {"x": x + span * .54}})
                call(page, "step", .3)
                check(f"HUD{mode}10%死区内不移动", abs(snap(page)["camera"]["x"] - x) < 1e-6)
                call(page, "arrange", {"player": {"x": x + span * .58}})
                call(page, "step", .12)
                check(f"HUD{mode}时间常数0.12秒", abs(snap(page)["camera"]["x"] -
                      (x + span * .03 * (1 - math.exp(-1)))) < 1e-6)
            context = browser.new_context(viewport={"width": 844, "height": 390},
                                          has_touch=True, is_mobile=True)
            phone = context.new_page()
            phone.on("pageerror", lambda error: ERRORS.append(str(error)))
            phone.goto(URL + "/?test=1")
            ready(phone)
            select(phone, "arena-formal")
            boxes = phone.evaluate("""()=>{const m=__waterTest.snapshot().arenaView.minimap;
              return {m,buttons:[...document.querySelectorAll('button')].filter(b=>b.checkVisibility())
                .map(b=>b.getBoundingClientRect().toJSON())};}""")
            m = boxes["m"]
            check("手机小地图可见且不挡按钮", m and m["x"] >= 0 and m["y"] >= 0 and
                  all(m["x"]+m["width"] <= b["left"] or m["x"] >= b["right"] or
                      m["y"]+m["height"] <= b["top"] or m["y"] >= b["bottom"] for b in boxes["buttons"]), boxes)
            phone.screenshot(path=SHOTS / "手机横屏-844x390.png")
            fresh(phone)
            call(phone, "arrange", {"player": {"x": 130, "y": 70},
                                     "enemy": {"x": 1900, "y": 150}})
            session = context.new_cdp_session(phone)
            session.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [
                {"x": 130, "y": 200, "id": 1}]})
            length = math.hypot(1840, 1260)
            session.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [
                {"x": 130 + 80 * 1840 / length, "y": 200 + 80 * 1260 / length, "id": 1}]})
            timing = phone.evaluate("""()=>{
              const a=__waterTest, start=a.snapshot().player;
              for(let ticks=1;ticks<=1800;ticks++){
                a.step(1/120,false);
                const p=a.snapshot().player;
                if(Math.hypot(p.x-1970,p.y-1330)<2)
                  return {seconds:ticks/120,start:{x:start.x,y:start.y},
                    end:{x:p.x,y:p.y},speed:p.speed};
              }
              return null;
            }""")
            session.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
            session.detach()
            check("实测整场可走对角完成且不改移速", timing and timing["speed"] == 224, timing)
            TIMINGS["整场可走对角（真实触屏摇杆）"] = timing
            phone.set_viewport_size({"width": 390, "height": 844})
            phone.screenshot(path=SHOTS / "手机竖屏-390x844.png")
            context.close()
            check("0 JS错误", not ERRORS, ERRORS)
            browser.close()
        reference = Image.open(os.environ.get("POIGHT_A1_REFERENCE", ROOT / "验收参考-A2.jpg"))
        ref = reference.crop((450, 298, 900, 580)).convert("RGB")
        game = Image.open(SHOTS / "自然场-A-战斗-1440x900.png").convert("RGB")
        game = game.resize((450, round(game.height * 450 / game.width)), Image.Resampling.NEAREST)
        result = Image.new("RGB", (924, max(ref.height, game.height) + 38), "#162030")
        result.paste(ref, (8, 30))
        result.paste(game, (466, 30))
        draw = ImageDraw.Draw(result)
        draw.text((8, 8), "Reference 10s / game crop / width 450", fill="white")
        draw.text((466, 8), "A1 natural / same width 450 / no stretch", fill="white")
        result.save(SHOTS / "羁绊之旅10秒-等宽对比.png")
    finally:
        if CATALOG.read_bytes() != original:
            CATALOG.write_bytes(original)
            rebuild()
        receipt = {"passed": sum(c["ok"] for c in CHECKS),
                   "failed": sum(not c["ok"] for c in CHECKS), "jsErrors": len(ERRORS),
                   "errors": ERRORS, "metrics": METRICS, "timings": TIMINGS, "checks": CHECKS}
        (OUT / "浏览器验收.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({k: receipt[k] for k in ("passed", "failed", "jsErrors")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
