"""New device defaults; explicit 0 is the legacy diagnostic comparison, not a default.

All four layouts retain desktop narrow-window stress and actual CDP touch cast tests.
Touch portrait suppression/pause is exercised separately by 验收-手机操作.py.
"""
import json
import os
import time
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/界面方案"
OUT.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8862/").rstrip("/")
CHECKS, ERRORS = [], []
VIEWS = [(1440, 900), (390, 844), (844, 390)]


def check(name, ok, detail=None):
    CHECKS.append({"name": name, "ok": bool(ok), "detail": detail})
    assert ok, (name, detail)


def call(page, method, value=None):
    return page.evaluate("([m,v])=>window.__waterTest[m](v)", [method, value])


def snap(page):
    return call(page, "snapshot")


def fresh(page):
    call(page, "reset", True)
    b = snap(page)["environment"]["bounds"]
    cy = (b["top"] + b["bottom"]) / 2
    cx = (b["left"] + b["right"]) / 2
    call(page, "arrange", {"ai": False, "player": {"x": cx-48, "y": cy+12},
                          "enemy": {"x": cx+48, "y": cy-12}})
    # A1: wait five camera time constants after teleporting the test fixture.
    call(page, "step", .6)


def boxes(page, label):
    result = page.evaluate("""()=>({overflow:document.documentElement.scrollWidth>innerWidth,
      buttons:[...document.querySelectorAll('button')].filter(b=>b.checkVisibility())
        .map(b=>({id:b.id,...b.getBoundingClientRect().toJSON()}))})""")
    check(label + " 无横向滚动", not result["overflow"])
    buttons = result["buttons"]
    w, h = page.viewport_size.values()
    check(label + " 按钮在屏幕内", all(b["x"] >= 0 and b["y"] >= 0
          and b["right"] <= w+.1 and b["bottom"] <= h+.1 for b in buttons), buttons)
    overlapping = []
    for i, a in enumerate(buttons):
        for b in buttons[i+1:]:
            if (a["left"] < b["right"]-.1 and b["left"] < a["right"]-.1
                    and a["top"] < b["bottom"]-.1 and b["top"] < a["bottom"]-.1):
                overlapping.append([a["id"], b["id"]])
    check(label + " 可见按钮两两不重叠", not overlapping, overlapping)


def sp_pixels(page, mode, label):
    if mode in (0, 2):
        s = snap(page)["hud"]["actors"][0]["stamina"]
        b = s["box"]
        rgb = page.evaluate("""([x,y])=>{const c=document.querySelector('#game'),
          r=c.getBoundingClientRect();return [...c.getContext('2d').getImageData(
          Math.floor(x*c.width/r.width),Math.floor(y*c.height/r.height),1,1).data].slice(0,3)}""",
                            [b["x"]+3, b["y"]+2])
        check(label + " SP Canvas 像素可见", rgb == ([87, 221, 217] if mode == 0
                                               else [255, 212, 94]), rgb)
    else:
        selector = ".player .battle-sp" if mode == 1 else ".player .sp-arc"
        box = page.locator(selector).bounding_box()
        image = Image.open(BytesIO(page.screenshot())).convert("RGB")
        crop = image.crop((int(box["x"]), int(box["y"]),
                           int(box["x"]+box["width"]), int(box["y"]+box["height"])))
        count = sum(r > 220 and g > 150 and b < 120
                    for r, g, b in (crop.getpixel((x, y)) for x in range(crop.width)
                                    for y in range(crop.height)))
        check(label + " SP 黄色像素可见", count > 25, count)


def touch(page, cancel=False):
    fresh(page)
    b = page.locator(".skill").first.bounding_box()
    x, y = b["x"] + b["width"]/2, b["y"] + b["height"]/2
    session = page.context.new_cdp_session(page)
    def send(kind, px=x, py=y):
        session.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": []
                     if kind == "touchEnd" else [{"x": px, "y": py, "id": 1}]})
    send("touchStart")
    call(page, "step", .24)
    held = snap(page)
    check("触屏未拖动不进入瞄准且不消费体力", held["aim"] and not held["aim"]["active"]
          and held["player"]["spent"] == 0)
    send("touchMove", x+48, y-35)
    call(page, "step", .02)
    active = snap(page)["aim"]  # H1 aims only after dragging more than 12px.
    if cancel:
        send("touchMove", x, y)
    send("touchEnd")
    call(page, "step", .03)
    session.detach()
    return active, snap(page)


def screenshot_battle(page, mode, width, height):
    fresh(page)
    s = snap(page)
    p = s["player"]
    # Real preceding projectile hit + simultaneous enemy cast warning, not painted mock UI.
    call(page, "injectWater", {"owner": "enemy", "move": "flamethrower", "x": p["x"]-35,
                              "y": p["y"], "ux": 1, "uy": 0, "speed": 650, "range": 150})
    call(page, "step", .06)
    check(f"{mode}/{width} 截图真实伤害数字", bool(snap(page)["hud"]["floats"]))
    check(f"{mode}/{width} 大字爆炎出招", page.evaluate(
        "()=>window.__waterTest.cast('enemy','fireblast')"))
    call(page, "step", .06)
    check(f"{mode}/{width} 截图出招预警", bool(snap(page)["warnings"]))
    name = f"方案{mode}-{width}x{height}.png" if mode else f"现状-{width}x{height}.png"
    page.screenshot(path=OUT / name)


def overview():
    cellw, cellh = 480, 440
    result = Image.new("RGB", (4*cellw, 3*cellh), "#0b1523")
    draw = ImageDraw.Draw(result)
    for row, (w, h) in enumerate(VIEWS):
        for mode in range(4):
            name = f"方案{mode}-{w}x{h}.png" if mode else f"现状-{w}x{h}.png"
            image = Image.open(OUT / name).convert("RGB")
            image.thumbnail((cellw-16, cellh-38), Image.Resampling.LANCZOS)
            x = mode*cellw + (cellw-image.width)//2
            y = row*cellh + 30 + (cellh-38-image.height)//2
            result.paste(image, (x, y))
            draw.text((mode*cellw+12, row*cellh+10),
                      f"{'CURRENT' if mode == 0 else 'HUD '+str(mode)}  /  {w} x {h}",
                      fill="#ffdc88")
    result.save(OUT / "总览.png")


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        for touch_device, expected in [(False, "1"), (True, "3")]:
            context = browser.new_context(viewport={"width": 844, "height": 390},
                                          has_touch=touch_device, is_mobile=touch_device)
            page = context.new_page()
            page.on("pageerror", lambda e: ERRORS.append(str(e)))
            page.goto(URL + "/?test=1")
            for _ in range(600):
                if page.evaluate("window.__waterTest?.snapshot().artReady"):
                    break
                time.sleep(.025)
            check("新默认触屏" if touch_device else "新默认桌面",
                  snap(page)["hud"]["variant"] == expected)
            context.close()
        for mode in range(4):
            for width, height in VIEWS:
                label = f"HUD{mode} {width}x{height}"
                context = browser.new_context(viewport={"width": width, "height": height},
                                              has_touch=False)
                page = context.new_page()
                page.on("pageerror", lambda e: ERRORS.append(str(e)))
                page.goto(URL + f"/?test=1&hud={mode}")
                for _ in range(600):
                    if page.evaluate("window.__waterTest?.snapshot().artReady"):
                        break
                    time.sleep(.025)
                else:
                    raise TimeoutError(label)
                catalog = call(page, "catalog")
                roster = {c["id"]: c for c in catalog["roster"]}
                profile = {**snap(page)["profile"], "player": 25, "enemy": 6,
                           "playerMoves": roster[25]["defaultMoves"],
                           "enemyMoves": roster[6]["defaultMoves"], "map": "arena-formal"}
                check(label + " 对战加载", call(page, "select", profile))
                fresh(page)
                check(label + " URL切换未改变场地边界", snap(page)["environment"]["bounds"] ==
                      next(s["bounds"] for s in catalog["scenes"] if s["id"] == "arena-formal"))
                boxes(page, label)
                sp_pixels(page, mode, label)
                if mode:
                    call(page, "step", 4)
                    sp_pixels(page, mode, label + " 满体力4秒后常显")
                    check(label + " 去掉调试标签", not page.locator("#status").is_visible())
                    page.locator("#battleMenuButton").click()
                    boxes(page, label + " 菜单展开")
                    check(label + " 菜单入口完整", all(page.locator("#"+i).is_visible()
                          for i in ["sceneButton", "tierLabel", "setupButton", "fullscreen",
                                    "sound", "help", "battleMoveHints"]))
                    page.locator("#battleMoveHints").click()
                    check(label + " 出招提示可选开启", page.locator("#battleMoveHints").get_attribute(
                        "aria-pressed") == "true")
                    page.locator("#battleMoveHints").click()
                    page.locator("#help").click()
                    check(label + " 操作入口可打开", page.locator("#helpPanel").is_visible())
                    page.locator("#game").click(position={"x": 2, "y": height-2})
                    check(label + " 操作面板可收起", not page.locator("#helpPanel").is_visible())
                    page.locator("#battleMenuButton").click()
                    page.locator("#sound").click()
                    check(label + " 默认声音可关闭", page.locator("#sound").get_attribute(
                        "aria-pressed") == "false")
                    page.locator("#battleMenuButton").click()
                    page.locator("#sound").click()
                    s = snap(page)
                    if mode in (1, 3):
                        check(label + " 近景无竞技场外留白", s["camera"]["x"] >= 0
                              and s["camera"]["y"] >= 0 and s["camera"]["x"] +
                              s["viewport"]["width"] <= 2100.1 and s["camera"]["y"] +
                              s["viewport"]["height"] <= 1400.1)
                    arena = s["viewport"]["scale"]
                    if width > height:
                        battle_height = (s["environment"]["bounds"]["bottom"] -
                                         s["environment"]["bounds"]["top"]) * arena
                        check(label + " 横屏竞技场不被HUD压缩",
                              1400 * arena >= 300 if mode == 2 else battle_height > 220,
                              {"完整场地高度": 1400 * arena, "战斗区高度": battle_height})
                for index, move in enumerate(profile["playerMoves"]):
                    fresh(page)
                    button = page.locator(".skill").nth(index)
                    button.click()
                    call(page, "step", .02)
                    s = snap(page)
                    check(label + f" 鼠标技能{index+1}实际出招", s["player"]["spent"] > 0
                          and s["player"]["attack"]["id"] == move)
                    c1 = float(button.evaluate("b=>b.style.getPropertyValue('--cool')"))
                    text1 = button.locator("small").inner_text()
                    call(page, "step", .3)
                    c2 = float(button.evaluate("b=>b.style.getPropertyValue('--cool')"))
                    check(label + f" 技能{index+1}冷却扫光与秒数变化", c1 > c2 > 0
                          and button.locator("small").inner_text() != text1)
                    spent = snap(page)["player"]["spent"]
                    button.click()
                    call(page, "step", .02)
                    check(label + f" 技能{index+1}冷却阻止重复施放",
                          snap(page)["player"]["spent"] == spent)
                fresh(page)
                call(page, "arrange", {"player": {"stamina": 0}})
                check(label + " 体力不足变灰", page.locator(".skill.insufficient").count()
                      == len(profile["playerMoves"]) and page.locator(".skill").first.evaluate(
                          "b=>Number(getComputedStyle(b).opacity)<1"))
                page.locator(".skill").first.click()
                call(page, "step", .02)
                check(label + " 体力不足不能出招", not snap(page)["player"]["attack"])
                active, s = touch(page)
                check(label + " 真实触屏按住拖动释放出招", active and active["active"]
                      and s["player"]["attack"] and s["player"]["spent"] > 0)
                active, s = touch(page, True)
                check(label + " 真实触屏拖回按钮取消", active and not s["player"]["attack"]
                      and s["player"]["spent"] == 0)
                if mode in (1, 3) and width < height:
                    s = snap(page)
                    check(label + " 竖屏近景铺满战斗画面", s["viewport"]["scale"] *
                          (s["environment"]["bounds"]["bottom"] -
                           s["environment"]["bounds"]["top"] + 68) >= height-120)
                    b = s["environment"]["bounds"]
                    call(page, "arrange", {"player": {"x": b["left"]+30},
                                          "enemy": {"x": b["right"]-35}})
                    call(page, "step", .08)
                    s = snap(page)
                    check(label + " 镜头跟随玩家并保留场外CPU方位", 0 <
                          s["player"]["x"]-s["camera"]["x"] < s["viewport"]["width"])
                screenshot_battle(page, mode, width, height)
                # One-move layouts, including a real click on Splash.
                check(label + " 鲤鱼王单招加载", call(page, "select", {**profile, "player": 129,
                      "playerMoves": roster[129]["defaultMoves"]}))
                fresh(page)
                check(label + " 只有一招", page.locator(".skill").count() == 1)
                boxes(page, label + " 单招")
                page.locator(".skill").click()
                call(page, "step", .03)
                check(label + " 单招能点击出招", snap(page)["player"]["spent"] > 0)
                if mode and width == 390:
                    page.screenshot(path=OUT / f"单招-方案{mode}-{width}x{height}.png")
                context.close()
        browser.close()
    overview()
    check("12张场景截图及等比总览存在", len(list(OUT.glob("方案*-*.png"))) == 9
          and len(list(OUT.glob("现状-*.png"))) == 3 and (OUT / "总览.png").exists())
    check("无 JS 错误", not ERRORS, ERRORS)


try:
    main()
except Exception as error:
    if not any(not c["ok"] for c in CHECKS):
        CHECKS.append({"name": "验收脚本异常", "ok": False, "detail": str(error)})
    raise
finally:
    report = {"passed": sum(c["ok"] for c in CHECKS),
              "failed": sum(not c["ok"] for c in CHECKS), "jsErrors": len(ERRORS),
              "checks": CHECKS, "errors": ERRORS}
    (OUT / "报告.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({k: report[k] for k in ["passed", "failed", "jsErrors"]},
                     ensure_ascii=False))
