"""Real CDP multi-touch input; three device contexts and orientation pause/resume."""
import base64
import json
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/手机操作"
SHOTS = OUT / "截图"
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8866/").rstrip("/")
CHECKS, ERRORS = [], []


def check(name, ok, detail=None):
    CHECKS.append({"name": name, "ok": bool(ok), "detail": detail})
    assert ok, (name, detail)


def call(page, method, value=None):
    return page.evaluate("([m,v])=>window.__waterTest[m](v)", [method, value])


def snap(page):
    return call(page, "snapshot")


def ready(page, query="?test=1"):
    page.goto(URL + "/" + query)
    for _ in range(600):
        if page.evaluate("window.__waterTest?.snapshot().artReady" if query else
                         "document.getElementById('setup')?.open"):
            return
        time.sleep(.025)
    raise TimeoutError("artReady")


def arena(page):
    catalog = call(page, "catalog")
    roster = {c["id"]: c for c in catalog["roster"]}
    profile = {**snap(page)["profile"], "player": 25, "enemy": 6,
               "playerMoves": roster[25]["defaultMoves"],
               "enemyMoves": roster[6]["defaultMoves"], "map": "arena-formal"}
    check("竞技场载入", call(page, "select", profile))
    return profile


def fresh(page):
    call(page, "reset", True)
    b = snap(page)["environment"]["bounds"]
    cy = (b["top"] + b["bottom"]) / 2
    call(page, "arrange", {"ai": False, "player": {"x": 400, "y": cy},
                           "enemy": {"x": 740, "y": cy}})
    call(page, "step", .01)


def center(page, selector):
    b = page.locator(selector).first.bounding_box()
    return {"x": b["x"] + b["width"]/2, "y": b["y"] + b["height"]/2, "id": 2}


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        desktop = browser.new_context(viewport={"width": 1440, "height": 900})
        d = desktop.new_page()
        d.on("pageerror", lambda e: ERRORS.append(str(e)))
        ready(d)
        check("桌面默认方案1", snap(d)["hud"]["variant"] == "1")
        arena(d)
        check("桌面技能保留键位字母", all(k.is_visible() for k in d.locator(".skill kbd").all()))
        fresh(d)
        check("桌面无摇杆跳闪", all(not d.locator(s).is_visible()
              for s in ["#mobileJoystick", "#jumpButton", "#dashButton"]))
        d.keyboard.down("d")
        x = snap(d)["player"]["x"]
        call(d, "step", .5)
        d.keyboard.up("d")
        check("桌面键盘照旧", snap(d)["player"]["x"] > x)
        fresh(d)
        d.locator(".skill").first.click()
        call(d, "step", .02)
        check("桌面鼠标技能照旧", snap(d)["player"]["spent"] > 0)
        d.screenshot(path=SHOTS / "桌面-1440x900.png")
        d.set_viewport_size({"width": 390, "height": 844})
        check("桌面窄窗口不显示横屏遮罩", not d.locator("#rotatePhone").is_visible())
        ready(d, "?test=1&hud=2")
        check("桌面URL强制方案2", snap(d)["hud"]["variant"] == "2")
        desktop.close()

        context = browser.new_context(viewport={"width": 844, "height": 390},
                                      has_touch=True, is_mobile=True)
        p = context.new_page()
        p.on("pageerror", lambda e: ERRORS.append(str(e)))
        ready(p)
        check("触屏横屏默认方案3", snap(p)["hud"]["variant"] == "3")
        profile = arena(p)
        check("触屏技能隐藏键位字母", all(not k.is_visible() for k in p.locator(".skill kbd").all()))
        fresh(p)
        check("竞技场不显示潜", not p.locator("#diveButton").is_visible())
        check("跳闪尺寸不少于48", all(p.locator(s).bounding_box()[k] >= 48
              for s in ["#jumpButton", "#dashButton"] for k in ["width", "height"]))
        p.locator("#battleMenuButton").tap()
        check("菜单包含换精灵配招重开声音全屏", all(p.locator("#" + s).is_visible()
              for s in ["setupButton", "reset", "sound", "fullscreen"]))
        p.locator("#reset").tap()
        check("菜单重新开始确实重置", snap(p)["phase"] == "idle"
              and snap(p)["player"]["stamina"] == 100)
        fresh(p)
        # Lock is requested only by explicit fullscreen activation; rejection stays silent.
        p.evaluate("""()=>{window.lockCalls=[];
          screen.orientation.lock=async mode=>{lockCalls.push(mode);throw Error('unsupported');};
          document.documentElement.requestFullscreen=async()=>{};
        }""")
        check("未点全屏不调用方向锁", p.evaluate("lockCalls.length===0"))
        p.locator("#battleMenuButton").tap()
        p.locator("#fullscreen").tap()
        check("点全屏才尝试横屏锁且失败静默", p.evaluate(
              "lockCalls.length===1 && lockCalls[0]==='landscape'"))
        cdp = context.new_cdp_session(p)

        def send(kind, points):
            cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": points})
            # Let coalesced native pointermove reach listeners; manual engine time is unchanged.
            p.wait_for_timeout(25)

        origin = {"x": 170, "y": 260, "id": 1}
        full = {**origin, "x": 224}

        def push(point=full):
            send("touchStart", [origin])
            send("touchMove", [point])

        def release():
            send("touchEnd", [])

        # A simulated second is stepped deterministically, through the real movement channel.
        p.keyboard.down("d")
        x = snap(p)["player"]["x"]
        call(p, "step", 1)
        keyboard_distance = snap(p)["player"]["x"] - x
        p.keyboard.up("d")
        fresh(p)
        x = snap(p)["player"]["x"]
        push()
        call(p, "step", 1)
        distance = snap(p)["player"]["x"] - x
        check("左手右推1秒且不超键盘速度", 0 < distance <= keyboard_distance + .01,
              {"touch": distance, "keyboard": keyboard_distance})
        release()
        check("松手输入归零且摇杆消失", snap(p)["mobile"]["pointerId"] is None
              and snap(p)["mobile"]["vector"] == {"x": 0, "y": 0}
              and "held" not in p.locator("#mobileJoystick").get_attribute("class"))
        fresh(p)
        push({**origin, "x": 224, "y": 314})
        vector = snap(p)["mobile"]["vector"]
        check("斜推归一化不超过键盘", abs((vector["x"]**2 + vector["y"]**2)**.5-1) < 1e-8)
        send("touchCancel", [])
        check("取消触点清零不粘连", snap(p)["mobile"]["pointerId"] is None
              and snap(p)["mobile"]["vector"] == {"x": 0, "y": 0})
        fresh(p)
        x = snap(p)["player"]["x"]
        push({**origin, "x": 197})
        call(p, "step", 1)
        half = snap(p)["player"]["x"] - x
        check("半推速度为满推一半±20%", .4 <= half/distance <= .6, half/distance)
        release()
        fresh(p)
        push({**origin, "x": 174})
        x = snap(p)["player"]["x"]
        call(p, "step", .5)
        check("10%死区不移动", snap(p)["player"]["x"] == x)
        release()
        fresh(p)
        push()
        main_button = center(p, ".skill")
        send("touchStart", [full, main_button])
        call(p, "step", .05)
        check("触屏点按在pointerup前不出招不消费", snap(p)["player"]["attack"] is None
              and snap(p)["player"]["spent"] == 0 and not snap(p)["aim"]["active"])
        send("touchEnd", [main_button])
        call(p, "step", .2)
        state = snap(p)
        check("左移同时右主招发出", state["player"]["spent"] > 0
              and state["player"]["attack"]["emitted"] and state["player"]["shots"] > 0, state["player"])
        check("右手松开不打断左手", state["mobile"]["pointerId"] is not None
              and state["mobile"]["vector"]["x"] == 1)
        x = state["player"]["x"]
        call(p, "step", .2)
        check("出招后移动继续", snap(p)["player"]["x"] > x)
        p.screenshot(path=SHOTS / "触屏对战-844x390.png")
        release()
        fresh(p)
        push()
        main_button = center(p, ".skill")
        send("touchStart", [full, main_button])
        call(p, "step", .24)
        check("左推同时右手按住未拖动不瞄准", not snap(p)["aim"]["active"]
              and snap(p)["player"]["spent"] == 0)
        send("touchMove", [full, {**main_button, "x": main_button["x"]-12}])
        check("触屏拖动12px仍不瞄准", not snap(p)["aim"]["active"])
        drag = {**main_button, "x": main_button["x"]-48, "y": main_button["y"]-35}
        send("touchMove", [full, drag])
        check("左推同时右手拖动超过12px瞄准", snap(p)["aim"]["active"]
              and snap(p)["mobile"]["vector"]["x"] == 1)
        send("touchEnd", [drag])
        call(p, "step", .03)
        check("右手瞄准释放发招且左手保持", snap(p)["player"]["spent"] > 0
              and snap(p)["mobile"]["pointerId"] is not None)
        release()
        fresh(p)
        call(p, "arrange", {"player": {"hurt": .09, "hurtAge": 0}})
        main_button = center(p, ".skill")
        send("touchStart", [main_button])
        call(p, "step", .11)
        check("触屏受击结束也不得在pointerup前提前排队或放招",
              snap(p)["queued"] is None and snap(p)["player"]["attack"] is None
              and snap(p)["player"]["spent"] == 0)
        release()
        check("受击期间按住的触屏请求在pointerup才放招", snap(p)["player"]["attack"] is not None)
        fresh(p)
        call(p, "arrange", {"player": {"hurt": .09, "hurtAge": 0}})
        send("touchStart", [center(p, ".skill")])
        p.evaluate("window.dispatchEvent(new Event('blur'))")
        call(p, "step", .11)
        release()
        check("失焦清除触屏待松手请求", snap(p)["player"]["attack"] is None
              and snap(p)["queued"] is None and snap(p)["player"]["spent"] == 0)
        fresh(p)
        push()
        send("touchStart", [full, center(p, "#jumpButton")])
        call(p, "step", .225)
        check("同时左推右跳进入空中", snap(p)["player"]["airborne"]
              and snap(p)["mobile"]["vector"]["x"] == 1)
        send("touchEnd", [center(p, "#jumpButton")])
        check("跳跃右手释放仍保留左手", snap(p)["mobile"]["pointerId"] is not None)
        release()
        fresh(p)
        down = {**origin, "y": origin["y"]+54}
        push(down)
        x, y = snap(p)["player"]["x"], snap(p)["player"]["y"]
        send("touchStart", [down, center(p, "#dashButton")])
        call(p, "step", .09)
        state = snap(p)
        check("闪朝摇杆方向且不清输入", state["player"]["dashing"]
              and state["player"]["y"] > y+40 and abs(state["player"]["x"]-x) < .1
              and state["mobile"]["vector"]["y"] == 1)
        release()
        fresh(p)
        x = snap(p)["player"]["x"]
        p.locator("#dashButton").tap()
        call(p, "step", .09)
        check("摇杆静止背离对手闪避", snap(p)["player"]["dashing"]
              and snap(p)["player"]["x"] < x)
        p.screenshot(path=SHOTS / "M6a-触屏闪-844x390.png")
        call(p, "step", .24)
        p.locator("#dashButton").tap()
        state = snap(p)
        check("触屏闪冷却末80ms记忆且不预支资源无敌", state["dashMemory"] is not None
              and state["player"]["spent"] == 22 and not state["player"]["protected"])
        call(p, "step", .075)
        check("触屏闪记忆在冷却结束执行一次", snap(p)["player"]["dodges"] == 2
              and snap(p)["player"]["spent"] == 44)
        for label, move, hurt, age, slow, expected in [
                ("远程", "thunderbolt", 0, 0, 0, .9),
                ("近身", "irontail", 0, 0, 0, .75),
                ("治疗", "recover", 0, 0, 0, .5),
                ("瞄准", None, 0, 0, 0, .6),
                ("普通受击", None, .4, 0, 0, .65),
                ("受击超过200ms", None, .18, .22, 0, 1),
                ("受击与slow取较强", None, .4, 0, 2, .65)]:
            fresh(p)
            call(p, "arrange", {"player": {"hp": 50, "hurt": hurt, "hurtAge": age, "slow": slow}})
            push()
            if move:
                p.evaluate("m=>window.__waterTest.equip('player',[m])", move)
                main_button = center(p, ".skill")
                send("touchStart", [full, main_button])
                send("touchEnd", [main_button])
            elif label == "瞄准":
                main_button = center(p, ".skill")
                send("touchStart", [full, main_button])
                send("touchMove", [full, {**main_button, "y": main_button["y"]-30}])
            first = snap(p)["player"]
            call(p, "step", .05)
            ratio = (snap(p)["player"]["x"]-first["x"])/(first["speed"]*.05)
            check("摇杆H1移动倍率："+label, abs(ratio-expected) < .01, ratio)
            release()
        arena(p)
        fresh(p)
        push()
        p.set_viewport_size({"width": 390, "height": 844})
        p.wait_for_timeout(100)
        state = snap(p)
        check("转竖屏显示遮罩并暂停且清输入", p.locator("#rotatePhone").is_visible()
              and state["phase"] == "paused" and state["mobile"]["pointerId"] is None)
        before = (state["elapsed"], state["matchSeconds"], state["player"]["x"])
        call(p, "step", 1)
        state = snap(p)
        check("竖屏时所有对战时钟位置冻结", before ==
              (state["elapsed"], state["matchSeconds"], state["player"]["x"]))
        p.screenshot(path=SHOTS / "竖屏遮罩-390x844.png")
        release()
        p.set_viewport_size({"width": 844, "height": 390})
        p.wait_for_timeout(100)
        check("横屏遮罩消失恢复", not p.locator("#rotatePhone").is_visible()
              and snap(p)["phase"] == "playing")
        elapsed = snap(p)["elapsed"]
        call(p, "step", .1)
        check("恢复后时钟继续", snap(p)["elapsed"] > elapsed)
        # Big-map water button and actual dive action, using original terrain cells.
        main = json.loads((ROOT / "素材/绿宝石场景/场景目录.json").read_text())["terrains"][0]
        cols, size = main["columns"], main["cellSize"]
        walk, water = [base64.b64decode(main[k+"B64"]) for k in ["walk", "water"]]
        shore = next(i for i in range(cols, len(walk)-cols) if water[i] and walk[i-1]
                     and all(water[i+dx+dy*cols] for dx in range(3) for dy in [-1, 0, 1]))
        catalog = call(p, "catalog")
        world = next(s for s in catalog["scenes"] if s.get("terrainID") == main["id"])
        check("载入大地图", call(p, "select", {**profile, "map": world["id"]}))
        call(p, "reset", True)
        call(p, "arrange", {"ai": False, "player": {"x": (shore % cols+.5)*size,
              "y": (shore//cols+.5)*size}})
        call(p, "step", .02)
        check("大地图水边显示潜", p.locator("#diveButton").is_visible()
              and not p.locator("#diveButton").is_disabled())
        p.locator("#diveButton").tap()
        check("潜按钮等价C", snap(p)["player"]["diving"])
        push()
        send("touchStart", [full, {"x": 420, "y": 220, "id": 2}])
        send("touchMove", [{**full, "x": 100}, {"x": 500, "y": 270, "id": 2}])
        release()
        check("页面不滚动不缩放", p.evaluate(
              "visualViewport.scale===1 && scrollY===0 && scrollX===0"))
        ready(p, "?test=1&hud=2")
        check("触屏URL覆盖方案2", snap(p)["hud"]["variant"] == "2")
        context.close()
        portrait = browser.new_context(viewport={"width": 390, "height": 844},
                                       has_touch=True, is_mobile=True)
        q = portrait.new_page()
        q.on("pageerror", lambda e: ERRORS.append(str(e)))
        ready(q, "")
        check("选人页竖屏遮罩同样覆盖", q.locator("#setup").evaluate("d=>d.open")
              and q.locator("#rotatePhone").is_visible())
        q.set_viewport_size({"width": 844, "height": 390})
        q.wait_for_timeout(100)
        check("选人页横屏可继续选择", not q.locator("#rotatePhone").is_visible()
              and q.locator("#setup").evaluate("d=>d.open"))
        portrait.close()
        browser.close()
    check("0 JS错误", not ERRORS, ERRORS)


try:
    main()
except Exception as error:
    if not any(not c["ok"] for c in CHECKS):
        CHECKS.append({"name": "验收异常", "ok": False, "detail": str(error)})
    raise
finally:
    report = {"passed": sum(c["ok"] for c in CHECKS),
              "failed": sum(not c["ok"] for c in CHECKS), "jsErrors": len(ERRORS),
              "checks": CHECKS, "errors": ERRORS}
    (OUT / "报告.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ["passed", "failed", "jsErrors"]}, ensure_ascii=False))
