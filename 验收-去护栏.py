import sys
"""A2: exact art delta, all variants, real keyboard perimeter loop and flag collision."""
import hashlib
import io
import json
import os
import subprocess
import time
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent
OUT = ROOT / "验收记录/去护栏"
SHOTS = OUT / "截图"
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8926/").rstrip("/")
CHECKS, ERRORS, EDGES = [], [], []
CATALOG = ROOT / "素材/竞技场/竞技场目录.json"
BASE = "bbbdf09"


def check(name, ok, detail=None):
    CHECKS.append({"name": name, "ok": bool(ok), "detail": detail})
    assert ok, (name, detail)


def baseline(path):
    return subprocess.check_output(["git", "show", f"{BASE}:{path}"])


def call(page, method, value=None):
    return page.evaluate("([m,v])=>__waterTest[m](v)", [method, value])


def snap(page):
    return call(page, "snapshot")


def ready(page):
    for _ in range(800):
        if page.evaluate("window.__waterTest?.snapshot().artReady"):
            return
        time.sleep(.025)
    raise TimeoutError("assets")


def fresh(page):
    call(page, "reset", True)
    call(page, "arrange", {"ai": False, "enemy": {"x": 1050, "y": 700}})


def rebuild():
    with (OUT / "构建.log").open("a") as log:
        subprocess.run([os.sys.executable, "构建完整版.py"], cwd=ROOT,
                       stdout=log, stderr=log, check=True)


def walk(page, key, target):
    page.keyboard.down(key)
    try:
        result = page.evaluate("""([axis,end])=>{
          const a=__waterTest;
          for(let ticks=0;ticks<1800;ticks++){
            const p=a.snapshot().player;
            if(Math.abs(p[axis]-end)<2)return {ticks,player:p};
            a.step(1/120,false);
          }
          return {ticks:1800,player:a.snapshot().player};
        }""", ["x" if key in ("a", "d") else "y", target])
    finally:
        page.keyboard.up(key)
    check("贴边绕场路段" + key + str(target), result["ticks"] < 1800, result)
    return result["player"]


def art_checks():
    for variant in "ABC":
        stem = f"正规场-{variant}"
        path = f"素材/竞技场/扩建/{stem}.png"
        new = Image.open(ROOT / path).convert("RGB")
        old = Image.open(io.BytesIO(baseline(path))).convert("RGB")
        # Only the four original rail rectangles can change. White lines, flags,
        # stands, trainer frames and the whole central logo remain pixel-identical.
        rail_mask = Image.new("L", new.size)
        draw = ImageDraw.Draw(rail_mask)
        for x, y, right, bottom in [(45, 45, 1005, 68), (45, 632, 1005, 655),
                                    (45, 68, 68, 632), (982, 68, 1005, 632)]:
            draw.rectangle((x, y, right - 1, bottom - 1), fill=255)
        changed = ImageChops.difference(old, new)
        check(stem + "四条护栏之外画面逐像素不变",
              Image.composite(Image.new("RGB", new.size), changed, rail_mask).getbbox() is None)
        patch = Image.open(ROOT / f"素材/竞技场/{stem}.png").convert("RGB").crop(
            (300, 350, 420, 470)).resize((60, 60), Image.Resampling.NEAREST)
        ground = Image.new("RGB", new.size)
        for y in range(0, 700, 60):
            for x in range(0, 1050, 60):
                ground.paste(patch, (x, y))
        # Flags are deliberately preserved over the restored ground at the corners.
        for x in (30, 990):
            for y in (28, 630):
                draw.rectangle((x, y, x + 29, y + 39), fill=0)
        check(stem + "旧护栏全区域为同一连续地面无阴影色块",
              Image.composite(ImageChops.difference(new, ground),
                              Image.new("RGB", new.size), rail_mask).getbbox() is None)
        data = json.loads((ROOT / f"素材/竞技场/扩建/{stem}.json").read_text())
        previous = json.loads(baseline(f"素材/竞技场/扩建/{stem}.json"))
        check(stem + "无fence且四看台四角旗保留",
              [o["kind"] for o in data["obstacles"]] == ["stands"] * 4 + ["flag"] * 4)
        check(stem + "其他元数据出生球标与碰撞实体不变",
              {k: v for k, v in data.items() if k not in ("obstacles", "battleArea")} ==
              {k: v for k, v in previous.items() if k not in ("obstacles", "battleArea")} and
              data["obstacles"] == [o for o in previous["obstacles"] if o["kind"] != "fence"])
        for name in (f"自然场-{variant}", f"扩建/自然场-{variant}"):
            for suffix in ("png", "json"):
                path = f"素材/竞技场/{name}.{suffix}"
                check(path + "字节不变", (ROOT / path).read_bytes() == baseline(path))


def perimeter(page, scene, variant):
    b = scene["bounds"]
    check(variant + "四边battle与看台内沿间距0px",
          b == {"left": 60, "top": 60, "right": 2040, "bottom": 1340})
    check(variant + "运行时没有fence",
          all(o["kind"] != "fence" for o in scene["collisionContract"]))
    fresh(page)
    call(page, "arrange", {"player": {"x": 134, "y": 70}})
    # Continuous clockwise circuit; detour around each solid corner flag.
    route = [("d", 1966), ("s", 150), ("d", 2030), ("s", 1246),
             ("a", 1966), ("s", 1330), ("a", 134), ("w", 1246),
             ("a", 70), ("w", 150), ("d", 134), ("w", 70)]
    for key, end in route:
        walk(page, key, end)
        check(variant + "路段脚印不进入任何可见实体", page.evaluate("()=>{const s=__waterTest.snapshot();"
                    "return __waterTest.freeAt(s.player.x,s.player.y,s.player.body.moveRadius)}"))
    for label, key, axis, edge, start in [
        ("上", "w", "y", 60, {"x": 1050, "y": 100}),
        ("右", "d", "x", 2040, {"x": 2000, "y": 700}),
        ("下", "s", "y", 1340, {"x": 1050, "y": 1300}),
        ("左", "a", "x", 60, {"x": 100, "y": 700}),
    ]:
        fresh(page)
        call(page, "arrange", {"player": start})
        page.keyboard.down(key)
        call(page, "step", 1)
        page.keyboard.up(key)
        p = snap(page)["player"]
        gap = abs(p[axis] - edge)
        check(variant + label + "贴看台内沿±12px", 10 - .01 <= gap <= 12, p)
        EDGES.append({"variant": variant, "side": label, "gap": gap, "player": p})
    for flag in [o for o in scene["collisionContract"] if o["kind"] == "flag"]:
        fresh(page)
        left = flag["x"] < 1050
        start = {"x": flag["x"] + flag["w"] + 35 if left else flag["x"] - 35,
                 "y": max(80, flag["y"] + flag["h"] / 2)}
        call(page, "arrange", {"player": start})
        key, dx = ("a", -1) if left else ("d", 1)
        page.keyboard.down(key)
        call(page, "step", .6)
        page.keyboard.up(key)
        page.evaluate("dx=>__waterTest.dash('player',dx,0)", dx)
        call(page, "step", .3)
        p = snap(page)["player"]
        check(variant + flag["id"] + "角旗挡住真实走路及闪避",
              p["x"] - 10 >= flag["x"] + flag["w"] - .01 if left else
              p["x"] + 10 <= flag["x"] + .01, p)
    if variant == "A":
        fresh(page)
        call(page, "arrange", {"player": {"x": 134, "y": 1300}})
        page.keyboard.down("s")
        call(page, "step", 1)
        page.keyboard.up("s")
        call(page, "step", 1)
        check("角落截图玩家贴看台", 10 <= 1340 - snap(page)["player"]["y"] <= 12)
        page.screenshot(path=SHOTS / "正规场-A-角落-1440x900.png")


def main():
    original = CATALOG.read_bytes()
    failure = None
    try:
        art_checks()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.on("pageerror", lambda error: ERRORS.append(str(error)))
            for variant in "ABC":
                data = json.loads(original)
                next(s for s in data["scenes"] if s["id"] == "arena-formal")["variant"] = variant
                CATALOG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
                rebuild()
                page.goto(URL + "/?test=1")
                ready(page)
                catalog = call(page, "catalog")
                scene = next(s for s in catalog["scenes"] if s["id"] == "arena-formal")
                roster = {c["id"]: c for c in catalog["roster"]}
                check(variant + "真实选择正规场", call(page, "select", {
                    **snap(page)["profile"], "map": scene["id"], "player": 25, "enemy": 6,
                    "playerMoves": roster[25]["defaultMoves"], "enemyMoves": roster[6]["defaultMoves"]}))
                fresh(page)
                if variant == "A":
                    page.screenshot(path=SHOTS / "正规场-A-开局-1440x900.png")
                perimeter(page, scene, variant)
            CATALOG.write_bytes(original)
            rebuild()
            phone = browser.new_page(viewport={"width": 844, "height": 390},
                                     is_mobile=True, has_touch=True)
            phone.on("pageerror", lambda error: ERRORS.append(str(error)))
            phone.goto(URL + "/?test=1")
            ready(phone)
            roster = {c["id"]: c for c in call(phone, "catalog")["roster"]}
            check("手机真实选择皮卡丘正规场A", call(phone, "select", {
                **snap(phone)["profile"], "map": "arena-formal", "player": 25, "enemy": 6,
                "playerMoves": roster[25]["defaultMoves"], "enemyMoves": roster[6]["defaultMoves"]}))
            fresh(phone)
            phone.screenshot(path=SHOTS / "手机横屏-844x390.png")
            minimap = phone.evaluate("""async()=>{
              const a=__waterTest,s=a.snapshot(), ctx=document.querySelector('#game').getContext('2d'),
                old=ctx.drawImage;
              let mini=null,main=false;
              ctx.drawImage=function(im,...args){
                if(im instanceof HTMLImageElement && im.src.endsWith(s.environment.groundSrc))
                  main=true;
                if(im instanceof HTMLCanvasElement && im.width===1050 && im.height===700 &&
                   args.length===4)mini=im;
                return old.call(this,im,...args);
              };
              try{a.render();}finally{ctx.drawImage=old;}
              if(!mini)return {main,mini:false,exact:false};
              const im=await new Promise((yes,no)=>{
                const image=new Image();image.onload=()=>yes(image);image.onerror=no;
                image.src=s.environment.groundSrc;
              }),c=document.createElement('canvas');c.width=1050;c.height=700;
              c.getContext('2d').drawImage(im,0,0);
              const expected=c.getContext('2d').getImageData(0,0,1050,700).data,
                actual=mini.getContext('2d').getImageData(0,0,1050,700).data;
              return {main,mini:true,exact:actual.every((v,i)=>v===expected[i])};
            }""")
            check("小地图逐像素复用无护栏的实际ground图",
                  all(minimap.values()), minimap)
            phone.set_viewport_size({"width": 390, "height": 844})
            phone.screenshot(path=SHOTS / "手机竖屏-390x844.png")
            check("0 JS错误", not ERRORS, ERRORS)
            browser.close()
    except Exception as error:
        failure = repr(error)
        raise
    finally:
        if CATALOG.read_bytes() != original:
            CATALOG.write_bytes(original)
            rebuild()
        report = {"passed": sum(c["ok"] for c in CHECKS),
                  "failed": max(sum(not c["ok"] for c in CHECKS), int(bool(failure))),
                  "jsErrors": len(ERRORS), "failure": failure, "errors": ERRORS,
                  "checks": CHECKS, "edges": EDGES,
                  "candidateSHA256": hashlib.sha256((ROOT / "候选试玩.html").read_bytes()).hexdigest()}
        (OUT / "浏览器验收.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({k: report[k] for k in ("passed", "failed", "jsErrors")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
