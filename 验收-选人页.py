"""SELECT / VS headless acceptance; real UI, sprites and keyboard, no string eval polling."""

import base64
import io
import json
import os
import time
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/选人页"
SHOTS = OUT / "截图"
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8824/").rstrip("/")
checks, errors = [], []


def check(name, ok, detail=None):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    assert ok, (name, detail)


def poll(page, expression, timeout=5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if page.evaluate(expression):
            return True
        page.wait_for_timeout(15)
    return False


def snapshot(page):
    return page.evaluate("window.__waterTest.snapshot()")


def open_setup(page):
    page.locator("#battleMenuButton").click()
    page.locator("#setupButton").click()
    assert poll(page, "document.querySelector('#setup').open")


def cursor(page):
    return int(page.locator('#roster .mon[data-cursor="true"]').get_attribute("data-id"))


# Intersect with clipping ancestors: scrolled-away cards are not visible controls.
GEOMETRY = """() => {
  const visible = e => {
    if (!e.checkVisibility() || e.disabled) return null;
    let r = e.getBoundingClientRect(), x = r.left, y = r.top, right = r.right, bottom = r.bottom;
    for (let a = e.parentElement; a; a = a.parentElement) {
      const c = getComputedStyle(a), b = a.getBoundingClientRect();
      if (['hidden', 'auto', 'scroll', 'clip'].includes(c.overflowX)) {
        x = Math.max(x, b.left); right = Math.min(right, b.right);
      }
      if (['hidden', 'auto', 'scroll', 'clip'].includes(c.overflowY)) {
        y = Math.max(y, b.top); bottom = Math.min(bottom, b.bottom);
      }
    }
    x = Math.max(0, x); y = Math.max(0, y);
    right = Math.min(innerWidth, right); bottom = Math.min(innerHeight, bottom);
    return right > x && bottom > y ? {id: e.id || e.dataset.id, x, y, right, bottom} : null;
  };
  const buttons = [...document.querySelectorAll('#setup button')].map(visible).filter(Boolean);
  const overlaps = [];
  for (let i = 0; i < buttons.length; i++) for (let j = i + 1; j < buttons.length; j++) {
    const a = buttons[i], b = buttons[j];
    if (Math.min(a.right, b.right) - Math.max(a.x, b.x) > .5 &&
        Math.min(a.bottom, b.bottom) - Math.max(a.y, b.y) > .5) overlaps.push([a.id, b.id]);
  }
  const grid = document.querySelector('#roster').getBoundingClientRect();
  const foot = document.querySelector('.setup-foot').getBoundingClientRect();
  const portrait = document.querySelector('#playerPortrait').getBoundingClientRect();
  const stage = document.querySelector('.fighter-player .portrait-stage').getBoundingClientRect();
  const name = document.querySelector('#playerPickName').getBoundingClientRect();
  return {buttons: buttons.length, overlaps, gap: foot.top - grid.bottom,
    scroll: document.documentElement.scrollWidth, width: innerWidth,
    portraitContained: portrait.bottom <= stage.bottom + .5 && portrait.bottom <= name.top + .5};
}"""

try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(URL + "/?test=1")
        check("资源就绪", poll(page, "window.__waterTest?.snapshot().artReady"))
        open_setup(page)
        page.locator('#roster .mon[data-id="25"]').click()
        page.locator("#pickEnemyPanel").click()
        page.locator('#roster .mon[data-id="6"]').click()
        page.locator("#pickPlayerPanel").click()
        check("双侧四招展示", page.locator(".fighter-moves > span").count() == 8)
        check(
            "像素待机就绪",
            poll(page, "document.querySelector('#playerPortrait').dataset.frame !== undefined"),
        )
        for width, height in [(1440, 900), (390, 844), (844, 390)]:
            page.set_viewport_size({"width": width, "height": height})
            page.wait_for_timeout(200)
            geometry = page.evaluate(GEOMETRY)
            check(f"无横向溢出 {width}x{height}", geometry["scroll"] <= width, geometry)
            check(f"可见按钮两两不重叠 {width}x{height}", not geometry["overlaps"], geometry)
            check(f"立绘不覆盖名字 {width}x{height}", geometry["portraitContained"], geometry)
            if width == 1440:
                check("桌面网格下空白 ≤ 6%", geometry["gap"] <= height * 0.06, geometry)
            check(
                f"最近邻插值 {width}x{height}",
                page.locator(".select-portrait").evaluate_all(
                    "els => els.every(e => ['pixelated','crisp-edges'].includes(getComputedStyle(e).imageRendering))"
                ),
            )
            # Read the actual portrait backing pixels: screenshot compositing latency
            # can turn the 0.5s pair into a full 0.64s Charizard loop (sampling alias).
            # Keep the 0.5s interval and pixel-change assertion, without retiming animation.
            for portrait_id in ["playerPortrait", "enemyPortrait"]:
                changed = False
                portrait = page.locator("#" + portrait_id)
                for _ in range(12):
                    first_bytes = base64.b64decode(portrait.evaluate(
                        "e => e.toDataURL('image/png').split(',')[1]"
                    ))
                    page.wait_for_timeout(500)
                    second_bytes = base64.b64decode(portrait.evaluate(
                        "e => e.toDataURL('image/png').split(',')[1]"
                    ))
                    first = Image.open(io.BytesIO(first_bytes)).convert("RGB")
                    second = Image.open(io.BytesIO(second_bytes)).convert("RGB")
                    changed = ImageChops.difference(first, second).getbbox() is not None
                    if changed:
                        (SHOTS / f"{portrait_id}-{width}-前.png").write_bytes(first_bytes)
                        (SHOTS / f"{portrait_id}-{width}-后.png").write_bytes(second_bytes)
                        break
                check(f"0.5 秒待机像素改变 {portrait_id} {width}x{height}", changed)
            page.screenshot(path=str(SHOTS / f"选人-{width}x{height}.png"))

        page.set_viewport_size({"width": 1440, "height": 900})
        page.locator("#search").fill("皮卡")
        check(
            "搜索皮卡只剩皮卡丘",
            page.locator("#roster .mon").count() == 1
            and page.locator("#roster .mon").get_attribute("data-id") == "25",
        )
        page.locator("#search").fill("")
        page.locator("#typeFilterToggle").click()
        # Water is type 11 in the existing data; discover its button by label instead.
        water = page.locator("#typeChoices button").filter(has_text="水").first
        type_id = int(water.get_attribute("data-type"))
        water.click()
        ids = page.locator("#roster .mon").evaluate_all("els => els.map(e => Number(e.dataset.id))")
        catalog = page.evaluate("window.__waterTest.catalog()")
        roster = {c["id"]: c for c in catalog["roster"]}
        check("属性筛选", bool(ids) and all(type_id in roster[i]["types"] for i in ids), ids)
        page.locator("#typeFilterToggle").click()
        page.locator('#typeChoices button[data-type=""]').click()
        page.locator("#randomEnemy").click()
        random_id = int(page.locator('#roster .mon[data-enemy="true"]').get_attribute("data-id"))
        check(
            "随机仍可用", page.locator("#enemyPickName").inner_text() == roster[random_id]["name"]
        )
        page.locator("#setupMapButton").click()
        check("原地图菜单仍可打开", page.locator("#scenePicker").is_visible())
        page.locator("#cancelScene").click()
        page.locator("#toggleLoadout").click()
        check(
            "配招与 AI 强度仍可用",
            page.locator("#moveSlots button").count() == 4
            and page.locator("#difficulty button").count() == 4,
        )
        page.locator("#closeMoves").click()
        page.locator('#roster .mon[data-id="25"]').click()
        page.keyboard.press("ArrowRight")
        player_id = cursor(page)
        check(
            "→ 只移动光标未确认",
            player_id == 26 and page.locator("#playerPickName").inner_text() == "皮卡丘",
        )
        page.keyboard.press("Enter")
        check(
            "Enter 确认 1P",
            page.locator("#playerPickName").inner_text() == roster[player_id]["name"],
        )
        page.keyboard.press("Tab")
        check("Tab 换到 CPU", page.locator("#setup").get_attribute("data-side") == "enemy")
        page.keyboard.press("d")
        enemy_id = cursor(page)
        page.keyboard.press("j")
        check(
            "WASD / J 确认 CPU",
            page.locator("#enemyPickName").inner_text() == roster[enemy_id]["name"],
        )
        ordered = page.locator("#roster .mon").evaluate_all(
            "els => els.map(e => Number(e.dataset.id))"
        )
        page.keyboard.press("w")
        check("W 向上一行", cursor(page) == ordered[ordered.index(enemy_id) - 5])
        page.keyboard.press("s")
        check("S 向下一行", cursor(page) == enemy_id)
        page.keyboard.press("a")
        check("A 向左一格", cursor(page) == player_id)

        started = time.monotonic()
        page.locator("#startBattle").click()
        check("确认出现 VS", poll(page, "window.__waterTest.snapshot().phase === 'versus'", 1))
        page.wait_for_timeout(780)
        page.screenshot(path=str(SHOTS / "VS-过场中帧.png"))
        check(
            "2.2 秒内自动开战",
            poll(page, "window.__waterTest.snapshot().phase === 'playing'", 1.3)
            and time.monotonic() - started <= 2.2,
            {"seconds": time.monotonic() - started},
        )
        check(
            "双方确认角色正确",
            snapshot(page)["profile"]["player"] == player_id
            and snapshot(page)["profile"]["enemy"] == enemy_id,
        )
        page.evaluate("window.__waterTest.arrange({ai:false})")
        before = snapshot(page)["player"]
        page.keyboard.down("d")
        page.evaluate("window.__waterTest.step(.1)")
        page.keyboard.up("d")
        after = snapshot(page)["player"]
        check("开战后键盘可操作", (before["x"], before["y"]) != (after["x"], after["y"]))
        open_setup(page)
        page.locator("#startBattle").click()
        assert poll(page, "window.__waterTest.snapshot().phase === 'versus'")
        started = time.monotonic()
        page.keyboard.press("Enter")
        check(
            "Enter 0.5 秒内跳过",
            poll(page, "window.__waterTest.snapshot().phase === 'playing'", 0.45)
            and time.monotonic() - started <= 0.5,
        )
        open_setup(page)
        page.locator("#startBattle").click()
        assert poll(page, "window.__waterTest.snapshot().phase === 'versus'")
        page.locator("#vsScreen").click(position={"x": 20, "y": 20})
        check("点击过场跳过", snapshot(page)["phase"] == "playing")
        open_setup(page)
        page.emulate_media(reduced_motion="reduce")
        page.locator("#startBattle").click()
        assert poll(page, "window.__waterTest.snapshot().phase === 'versus'")
        started = time.monotonic()
        check(
            "减少动态效果只淡入",
            page.locator(".vs-middle > b").evaluate("e => getComputedStyle(e).animationName")
            == "vs-name",
        )
        check(
            "减少动态效果约 0.6 秒",
            poll(page, "window.__waterTest.snapshot().phase === 'playing'", 0.8)
            and 0.4 <= time.monotonic() - started <= 0.8,
        )
        check("无 JS 错误", not errors, errors)
        browser.close()
finally:
    report = {
        "passed": sum(c["ok"] for c in checks),
        "failed": sum(not c["ok"] for c in checks),
        "jsErrors": len(errors),
        "errors": errors,
        "checks": checks,
    }
    (OUT / "浏览器验收.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ["passed", "failed", "jsErrors"]}, ensure_ascii=False))
