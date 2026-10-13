"""Headless music lifecycle and red-health variants; run via tools/远程执行.sh."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import Error, sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/战斗音乐"
SHOTS = OUT / "截图"
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8941/").rstrip("/")
CHECKS, ERRORS = [], []


def check(name, ok, detail=None):
    CHECKS.append({"name": name, "ok": bool(ok), "detail": detail})
    assert ok, (name, detail)


def call(page, method, value=None):
    return page.evaluate("([m,v])=>window.__waterTest[m](v)", [method, value])


def snap(page):
    return call(page, "snapshot")


def ready(page, query="", manual=True):
    page.goto(URL + ("/?test=1" if manual else "/?observe=1") + query)
    for _ in range(800):
        # PERF intentionally leaves production artwork unloaded until the VS click.
        # Await the real selection readiness for observe mode, not a hidden battle.
        if page.evaluate('''manual => manual ? !!window.__waterTest?.snapshot().artReady
          : document.querySelector('#setup')?.open &&
            [...document.querySelectorAll('#playerPortrait,#enemyPortrait')]
              .every(n => n.dataset.frame)''', manual):
            return
        time.sleep(.025)
    raise TimeoutError("artReady")


def eventually(page, predicate):
    for _ in range(100):
        if predicate(snap(page)):
            return True
        page.wait_for_timeout(25)
    return False


def start(page):
    call(page, "reset", True)
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(100)


def leave_menu(page):
    # UI2 pauses while configuring; use its real explicit return before checking audio.
    if page.locator("#gbaMenuReturn").count():
        if not page.locator("#gbaMenuReturn").is_visible():
            page.locator("#battleMenuButton").click()
        page.locator("#gbaMenuReturn").click()
    else:
        page.locator("#battleMenuButton").click()


def main():
    check("音乐模块<35000字节（新增流式9曲轮换）", (ROOT / "战斗音乐.js").stat().st_size < 35000)
    subprocess.run([sys.executable, str(ROOT / "工具-BGM3试听.py")], check=True)
    audio = json.loads((OUT / "BGM3试听/音色核验.json").read_text())
    check("BGM3 冻结9f9c0ac同段对比、谱面完全不变", audio["baseline"] == "9f9c0ac"
          and audio["scoreUnchanged"])
    for track, metrics in audio["tracks"].items():
        for segment in ["audition10s", "full60s"]:
            data = metrics[segment]
            check(track + " " + segment + " 频谱质心下降≥25%",
                  data["centroidReduction"] >= .25, data)
            check(track + " " + segment + " 4kHz以上能量占比下降≥40%",
                  data["above4kReduction"] >= .4, data)
        check(track + " 整体LUFS差≤1dB", abs(metrics["lufsDifference"]) <= 1, metrics)
        check(track + " 柔和循环50ms峰值差<3dB", metrics["seamPeakDifferenceDB"] < 3)
        check(track + " 柔和渲染峰值≤-1dBFS、无削波", metrics["runtimePeakDBFS"] <= -1
              and not metrics["clippedSamples"])
    check("BGM3 渲染0JS错误", not audio["jsErrors"])
    check("BGM3 动态R3渲染无报警", not audio["dynamic"]["alarmEvents"])
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        context.add_init_script("""(() => {
          window.musicContexts = [];
          const Original = window.AudioContext;
          window.AudioContext = new Proxy(Original, {construct(target, args) {
            const ctx = new target(...args); ctx.liveSources=0;
            for(const method of ['createOscillator','createBufferSource']) {
              const original=ctx[method].bind(ctx);
              ctx[method]=(...args)=>{
                const source=original(...args), start=source.start.bind(source);
                source.start=(...args)=>{ctx.liveSources++;return start(...args);};
                source.addEventListener('ended',()=>ctx.liveSources--,{once:true});
                return source;
              };
            }
            window.musicContexts.push(ctx); return ctx;
          }});
        })();""")
        p = context.new_page()
        p.on("pageerror", lambda e: ERRORS.append(str(e)))
        ready(p, "&music=dynamic")
        check("显式原创dynamic开、40%", snap(p)["music"]["enabled"]
              and snap(p)["music"]["mode"] == "dynamic" and snap(p)["music"]["track"] == "C"
              and snap(p)["music"]["volume"] == .4)
        check("默认红血方案R3", snap(p)["music"]["redMode"] == "r3")
        check("首次手势前不创建AudioContext", p.evaluate("()=>musicContexts.length===0"))
        start(p)
        maximum = snap(p)["player"]["maxHP"]
        call(p, "arrange", {"ai": False, "player": {"hp": maximum * .15}})
        check("默认R3红血B无报警、旋律0低音鼓>0", eventually(p, lambda s:
              s["music"]["track"] == "B" and not s["music"]["pending"]
              and not s["music"]["alarm"] and s["music"]["melodyGain"] == 0
              and s["music"]["rhythmGain"] > 0))
        p.locator("#battleMenuButton").click()
        check("默认面板低血提示无", p.locator("#musicRedMode").input_value() == "r3"
              and p.locator("#musicRedMode option:checked").text_content() == "低血提示：无")
        for track in "ABC":
            ready(p, "&music=" + track)
            check(track + " URL指定曲目", snap(p)["music"]["track"] == track
                  and snap(p)["music"]["enabled"])
            call(p, "reset", True)
            check(track + " 非手势开打不启动音乐", snap(p)["music"]["scheduled"] == 0)
            p.keyboard.press("ArrowRight")
            check(track + " 开打后AudioContext运行、有节点在播", eventually(
                p, lambda s: s["music"]["state"] == "running" and s["music"]["audible"] > 0))
            check(track + " 与音效共用一个Context", p.evaluate("()=>musicContexts.length===1"))
            p.locator("#battleMenuButton").click()
            p.locator("#musicVolume").fill("73")
            check(track + " 音量保存", snap(p)["music"]["volume"] == .73
                  and p.evaluate("()=>JSON.parse(localStorage.getItem('poight.music.v1')).volume===.73"))
            p.locator("#musicVolume").fill("0")
            check(track + " 支持0%", snap(p)["music"]["volume"] == 0)
            p.locator("#musicVolume").fill("100")
            check(track + " 支持100%", snap(p)["music"]["volume"] == 1)
            p.locator("#musicToggle").click()
            check(track + " 菜单关闭", eventually(p, lambda s: not s["music"]["enabled"]
                  and s["music"]["scheduled"] == 0))
            check(track + " 关闭localStorage", p.evaluate(
                "()=>JSON.parse(localStorage.getItem('poight.music.v1')).enabled===false"))
            p.locator("#musicToggle").click()
            check(track + " 菜单配置不绕过GBA暂停", snap(p)["phase"] == "paused"
                  and snap(p)["music"]["enabled"] and snap(p)["music"]["scheduled"] == 0)
            p.locator("#musicVolume").fill("40")
            leave_menu(p)
            check(track + " 菜单打开音乐后返回实际发声", eventually(p, lambda s:
                  s["phase"] == "playing" and s["music"]["audible"] > 0))
            p.keyboard.press("Escape")
            check(track + " 暂停停音乐", eventually(p, lambda s: s["phase"] == "paused"
                  and s["music"]["scheduled"] == 0))
            p.keyboard.press("Escape")
            check(track + " 恢复播放", eventually(p, lambda s: s["music"]["audible"] > 0))
            for outcome, hp in [("win", {"enemy": {"hp": 0}}),
                                ("loss", {"player": {"hp": 0}}),
                                ("draw", {"player": {"hp": 0}, "enemy": {"hp": 0}})]:
                start(p)
                call(p, "arrange", {"ai": False, **hp})
                call(p, "step", .02)
                p.wait_for_timeout(450)
                check(track + " " + outcome + " 胜负页淡出并停音乐", snap(p)["phase"] == "over"
                      and snap(p)["outcome"] == outcome and snap(p)["music"]["scheduled"] == 0)
            start(p)
            call(p, "reset", False)
            check(track + " 重置回准备页停音乐", snap(p)["music"]["scheduled"] == 0)
        ready(p, "&music=off")
        start(p)
        check("music=off 无音乐节点", snap(p)["music"]["scheduled"] == 0
              and not snap(p)["music"]["enabled"])
        ready(p, "&music=A")
        start(p)
        p.locator("#battleMenuButton").click()
        p.locator("#musicTrack").select_option("B")
        p.locator("#musicVolume").fill("61")
        leave_menu(p)
        check("菜单切曲B", eventually(p, lambda s: s["music"]["track"] == "B"
              and s["music"]["audible"] > 0))
        ready(p)
        check("无参数测试模式静音、曲目改为每局随机、音量记忆", not snap(p)["music"]["enabled"]
              and snap(p)["music"]["mode"] == "random" and snap(p)["music"]["volume"] == .61)
        check("刷新仍需首次手势", snap(p)["music"]["scheduled"] == 0)
        ready(p, "&demo=1")
        start(p)
        check("demo默认off覆盖已存偏好", not snap(p)["music"]["enabled"]
              and snap(p)["music"]["scheduled"] == 0)
        ready(p, "&demo=1&music=C")
        start(p)
        check("demo显式曲目可试听", eventually(p, lambda s: s["music"]["audible"] > 0))
        ready(p, "&music=dynamic")
        start(p)
        # Keep every legacy alarm-behavior assertion, under its explicit R2 strategy.
        p.locator("#battleMenuButton").click()
        p.locator("#musicRedMode").select_option("r2")
        leave_menu(p)
        call(p, "arrange", {"ai": False})
        maximum = snap(p)["player"]["maxHP"]

        def health(ratio):
            call(p, "arrange", {"ai": False, "player": {"hp": maximum * ratio}})

        def settled(track, alarm=False):
            return eventually(p, lambda s: s["music"]["track"] == track
                              and s["music"]["alarm"] == alarm and not s["music"]["pending"])

        health(.8)
        check("80%绿血C运行", eventually(p, lambda s: s["music"]["track"] == "C"
              and not s["music"]["pending"] and s["music"]["audible"] > 0), snap(p))
        origin = snap(p)["music"]["audioTime"]
        health(.4)
        pending = snap(p)["music"]["pending"]
        check("黄血切换预排到下一小节、不超过一小节", pending is not None
              and 0 <= pending["boundary"] - origin <= 180 / 162 + .05, pending)
        check("交叉淡化0.6秒", abs(pending["end"] - pending["boundary"] - .6) < 1e-6)
        check("40%黄血B、共用162BPM不断拍", settled("B") and snap(p)["music"]["bpm"] == 162)
        check("切换后完成节点回收", eventually(p, lambda s: s["music"]["pending"] is None))
        health(.15)
        check("15%红血B加报警", settled("B", True))
        check("报警有真实节点发声", eventually(p, lambda s: s["music"]["alarmAudible"] > 0))
        check("动态共用音效Context", p.evaluate("()=>musicContexts.length===1"))
        count = snap(p)["music"]["transitions"]
        for ratio in [.18, .22, .19, .21] * 3:
            health(ratio)
        check("红血阈值附近±2%不切换", snap(p)["music"]["transitions"] == count
              and snap(p)["music"]["level"] == "red")
        health(.24)
        check("回升超过23%关闭报警", settled("B"))
        count = snap(p)["music"]["transitions"]
        for ratio in [.48, .52, .49, .51] * 3:
            health(ratio)
        check("黄血阈值附近±2%不切换", snap(p)["music"]["transitions"] == count
              and snap(p)["music"]["level"] == "yellow")
        health(.54)
        check("回血超过53%反向切回C", settled("C"))
        health(.5)
        check("50%包含在黄血", settled("B"))
        health(.2)
        check("20%包含在红血", settled("B", True))
        call(p, "arrange", {"enemy": {"hp": 0}})
        call(p, "step", .02)
        p.wait_for_timeout(450)
        check("红血胜负页停音乐和报警", snap(p)["music"]["scheduled"] == 0
              and not snap(p)["music"]["alarm"])
        check("淡出后真实音源全部ended、不只是清快照", eventually(p, lambda _: p.evaluate(
            "()=>musicContexts.every(ctx=>ctx.liveSources===0)")),
            p.evaluate("()=>musicContexts.map(ctx=>({time:ctx.currentTime,live:ctx.liveSources}))"))
        ready(p, "&music=off")
        start(p)
        maximum = snap(p)["player"]["maxHP"]
        health(.15)
        check("off红血无音乐无报警", snap(p)["music"]["scheduled"] == 0
              and not snap(p)["music"]["alarm"])
        ready(p, "&music=C")
        start(p)
        maximum = snap(p)["player"]["maxHP"]
        health(.15)
        check("固定C不被血量覆盖", settled("C"))
        p.locator("#battleMenuButton").click()
        p.locator("#musicTrack").select_option("dynamic")
        leave_menu(p)
        check("菜单动态选项立刻应用红血", settled("B", True))
        ready(p)
        check("旧dynamic偏好不覆盖每局随机", snap(p)["music"]["mode"] == "random")
        ready(p, "&music=dynamic", manual=False)
        p.locator("#startBattle").click()
        check("真实时间模式音乐运行", eventually(p, lambda s: s["music"]["audible"] > 0))
        p.keyboard.press("Shift")
        p.wait_for_timeout(30)
        check("招式音效时报警让位20%", snap(p)["music"]["alarmDuck"] < .25)
        p.wait_for_timeout(240)
        check("招式音效后报警音量恢复", snap(p)["music"]["alarmDuck"] > .99)
        for track in "ABC":
            data = p.evaluate("id=>{const s=PoightMusicScore.score(id);return {bpm:s.bpm,"
                              "intro:s.introBars,loop:s.loopBars,duration:s.loopDuration,"
                              "seam:.05+s.introDuration+s.loopDuration,duty:s.duty};}", track)
            check(track + " 原创结构/速度/60秒含接缝", 150 <= data["bpm"] <= 175
                  and data["intro"] <= 4 and 48 <= data["loop"] <= 64
                  and data["seam"] < 60, data)
        for mode in ["r1", "r2", "r3"]:
            ready(p, "&music=" + mode)
            start(p)
            maximum = snap(p)["player"]["maxHP"]
            check(mode + " URL选项为动态模式", snap(p)["music"]["mode"] == "dynamic"
                  and snap(p)["music"]["redMode"] == mode)
            health(.8)
            check(mode + " 绿血C不变", settled("C"))
            health(.4)
            check(mode + " 黄血B完整配器不变", settled("B")
                  and snap(p)["music"]["musicGain"] == 1
                  and snap(p)["music"]["melodyGain"] == 1
                  and snap(p)["music"]["rhythmGain"] == 1)
            origin = snap(p)["music"]["audioTime"]
            health(.15)
            pending = snap(p)["music"]["pending"]
            check(mode + " 红血下一小节起点", pending is not None
                  and 0 <= pending["boundary"] - origin <= 180 / 162 + .05, pending)
            check(mode + " 红血方案完成", settled("B", mode != "r3"))
            p.wait_for_timeout(2100)
            music = snap(p)["music"]
            if mode == "r1":
                check("R1 音乐层增益0、仅报警", music["musicGain"] == 0)
                events = music["alarmEvents"]
                check("R1 每对间隔≥0.9秒", len(events) >= 4 and all(
                    events[i + 2] - events[i] >= .9 for i in range(0, len(events) - 2, 2)),
                    events)
                check("R1 音乐0.8秒淡出", abs(
                    pending["end"] - pending["boundary"] - .8) < 1e-6)
            elif mode == "r2":
                events = music["alarmEvents"]
                check("R2 刚进入红血恰好4个报警音", len(events) == 4, events)
                check("R2 约1.5秒内结束", events[-1] - events[0] + .14 <= 1.6)
                check("R2 保留完整B", music["musicGain"] == music["melodyGain"]
                      == music["rhythmGain"] == 1)
                p.wait_for_timeout(1600)
                check("R2 之后零事件零报警音源", snap(p)["music"]["alarmEvents"] == events
                      and snap(p)["music"]["alarmAudible"] == 0)
                p.keyboard.press("Escape")
                p.keyboard.press("Escape")
                p.wait_for_timeout(1800)
                check("R2 暂停恢复不重复报警", snap(p)["music"]["audible"] > 0
                      and not snap(p)["music"]["alarmEvents"])
                p.locator("#battleMenuButton").click()
                p.locator("#musicToggle").click()
                p.locator("#musicToggle").click()
                leave_menu(p)
                p.wait_for_timeout(1800)
                check("R2 关开音乐不重复报警", snap(p)["music"]["audible"] > 0
                      and not snap(p)["music"]["alarmEvents"])
            else:
                check("R3 主旋律与和声层0", music["melodyGain"] == 0)
                check("R3 低音鼓层>0", music["musicGain"] > 0 and music["rhythmGain"] > 0)
                check("R3 不发报警", not music["alarmEvents"] and music["alarmAudible"] == 0)
            count = music["transitions"]
            for ratio in [.18, .22, .19, .21] * 3:
                health(ratio)
            check(mode + " 红血迟滞不抖动", snap(p)["music"]["transitions"] == count)
            health(.24)
            check(mode + " 回血恢复B全部层", settled("B")
                  and snap(p)["music"]["musicGain"] == 1
                  and snap(p)["music"]["melodyGain"] == 1)
            health(.15)
            check(mode + " 再次跌入红血", settled("B", mode != "r3"))
            p.wait_for_timeout(1800)
            if mode == "r2":
                repeat = snap(p)["music"]["alarmEvents"]
                check("R2 回血再跌入才再响4音", len(repeat) == 4
                      and repeat[0] > events[-1], repeat)
            health(.8)
            check(mode + " 回血恢复C全部层", settled("C")
                  and snap(p)["music"]["musicGain"] == 1
                  and snap(p)["music"]["melodyGain"] == 1)
            health(.15)
            check(mode + " C可直接进入红血", settled("B", mode != "r3"))
            call(p, "arrange", {"enemy": {"hp": 0}})
            call(p, "step", .02)
            p.wait_for_timeout(450)
            check(mode + " 胜负页停止全部节点", snap(p)["music"]["scheduled"] == 0)
        ready(p, "&music=dynamic")
        start(p)
        maximum = snap(p)["player"]["maxHP"]
        health(.15)
        check("菜单策略测试进入红血", settled("B", snap(p)["music"]["redMode"] != "r3"))
        for mode in ["r1", "r2", "r3"]:
            p.locator("#battleMenuButton").click()
            p.locator("#musicRedMode").select_option(mode)
            leave_menu(p)
            check(mode + " 面板红血实时应用", eventually(p, lambda s, mode=mode:
                  s["music"]["track"] == "B" and s["music"]["alarm"] == (mode != "r3")
                  and not s["music"]["pending"]
                  and s["music"]["musicGain"] == (0 if mode == "r1" else 1)
                  and s["music"]["melodyGain"] == (0 if mode == "r3" else 1)))
            check(mode + " 面板选择保存", snap(p)["music"]["redMode"] == mode
                  and p.evaluate("()=>JSON.parse(localStorage.getItem('poight.music.v1')).redMode")
                  == mode)
        ready(p)
        check("红血偏好刷新持久化", snap(p)["music"]["redMode"] == "r3")
        ready(p, "&demo=1&music=r2")
        check("demo显式r2覆盖off", snap(p)["music"]["enabled"]
              and snap(p)["music"]["redMode"] == "r2")
        ready(p, "&music=A")
        start(p)
        p.locator("#battleMenuButton").click()
        p.screenshot(path=SHOTS / "桌面-1440x900.png")
        context.close()
        for width, height in [(390, 844), (844, 390)]:
            ctx = browser.new_context(viewport={"width": width, "height": height},
                                      has_touch=True, is_mobile=True)
            page = ctx.new_page()
            page.on("pageerror", lambda e: ERRORS.append(str(e)))
            ready(page, "&music=A")
            if width > height:
                call(page, "reset", True)
                page.locator("#battleMenuButton").tap()
                check("手机菜单音乐开关可见", page.locator("#musicToggle").is_visible())
                page.locator("#musicToggle").tap()
                check("手机菜单关闭音乐", not snap(page)["music"]["enabled"])
            page.screenshot(path=SHOTS / f"手机-{width}x{height}.png")
            ctx.close()
        ctx = browser.new_context()
        ctx.add_init_script("""for(const method of ['getItem','setItem']) {
          const original=Storage.prototype[method];
          Storage.prototype[method]=function(key,...args){
            if(key==='poight.music.v1')throw new Error('storage denied');
            return original.call(this,key,...args);
          };
        }""")
        page = ctx.new_page()
        page.on("pageerror", lambda e: ERRORS.append(str(e)))
        ready(page, "&music=A")
        start(page)
        page.locator("#battleMenuButton").click()
        page.locator("#musicToggle").click()
        check("localStorage被拒绝时不影响开关", not snap(page)["music"]["enabled"])
        ctx.close()
        browser.close()
    check("0 JS错误", not ERRORS, ERRORS)


if __name__ == "__main__":
    failure = None
    try:
        main()
        sys.path.insert(0, str(ROOT / "tests"))
        from aud_music import external_main
        external_main(check, CHECKS, ERRORS, OUT)
    except (AssertionError, TimeoutError, OSError, ValueError, Error,
            subprocess.CalledProcessError) as exc:
        failure = repr(exc)
    report = {"passed": sum(c["ok"] for c in CHECKS),
              "failed": sum(not c["ok"] for c in CHECKS) + int(bool(failure)),
              "jsErrors": len(ERRORS), "errors": ERRORS, "failure": failure, "checks": CHECKS}
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(int(bool(report["failed"] or ERRORS)))
