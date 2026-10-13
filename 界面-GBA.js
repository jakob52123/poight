/* Presentation only. Explicit hud= comparison routes and demo recordings stay reproducible. */
"use strict";
window.PoightGBA = class {
  constructor(enabled, api) {
    this.enabled = enabled;
    this.popoverOK = typeof HTMLElement !== "undefined" && "showPopover" in HTMLElement.prototype;
    if (!enabled) return;
    this.api = api;
    document.documentElement.dataset.gba = "true";
    document.documentElement.classList.add("gba");
    document.documentElement.style.setProperty("--gba-roster", `url("${api.roster}")`);
    this.pixel(document.getElementById("setupTitle"), "SELECT YOUR POKEMON");
    this.pixel(document.querySelector(".vs-middle > b"), "VS");
    const app = document.getElementById("app");
    const add = (tag, id, html) => {
      const el = document.createElement(tag);
      el.id = id;
      el.innerHTML = html;
      app.append(el);
      return el;
    };
    this.short = add(
      "dialog",
      "gbaShort",
      "<h2>屏幕太矮</h2><p>请退出全屏工具栏或横屏。对战已暂停，不会在遮挡下继续。</p><button>全屏 ⛶</button>",
    );
    this.short.addEventListener("cancel", (e) => e.preventDefault());
    this.short.addEventListener("keydown", (e) => e.stopPropagation());
    this.short.querySelector("button").onclick = () =>
      document.getElementById("fullscreen").click();
    const layout = (front = false) => {
      const css = getComputedStyle(document.documentElement),
        height =
          Math.min(innerHeight, window.visualViewport?.height || innerHeight) -
          (parseFloat(css.getPropertyValue("--safe-top")) || 0) -
          (parseFloat(css.getPropertyValue("--safe-bottom")) || 0);
      document.documentElement.dataset.compact = String(
        window.PoightMobile.touchDevice() && innerWidth > innerHeight && height < 330,
      );
      document.documentElement.dataset.setupShort = String(
        window.PoightMobile.touchDevice() && height < 210,
      );
      const preparing = document.getElementById("setup").open ||
        !document.getElementById("vsScreen").hidden;
      const inBattle = !preparing && this.phase !== "over" &&
        !document.documentElement.hasAttribute("data-ko") &&
        (api.playing() || this.shortResume || ["idle", "playing", "paused"].includes(this.phase));
      if (height < 210 && inBattle) {
        if (api.playing()) {
          this.shortResume = true;
          api.togglePause();
        }
        if (front && this.short.open) this.short.close();
        if (!this.short.open) this.short.showModal();
      } else {
        if (this.short.open) this.short.close();
        const resume = this.shortResume && inBattle && height >= 210;
        this.shortResume = false;
        if (resume) api.resume();
      }
    };
    this.layout = layout;
    window.addEventListener("resize", () => layout());
    window.visualViewport?.addEventListener("resize", () => layout());
    // Insets can change the usable setup area without changing the viewport box.
    if (window.PoightMobile.touchDevice())
      new ResizeObserver(() => requestAnimationFrame(() => layout())).observe(
        document.querySelector("#setup .setup-body"),
      );
    new MutationObserver(() => layout(true)).observe(document.getElementById("setup"), {
      attributes: true,
      attributeFilter: ["open"],
    });
    requestAnimationFrame(() => layout());
    this.clock = add("div", "gbaClock", "<b>00:00</b><span></span>");
    this.resources = add(
      "section",
      "gbaResources",
      `<div>能量 <b></b></div>
      <div class="resource-bar energy"><i></i></div><div>体力 <span>SP</span><b></b></div>
      <div class="resource-bar stamina"><i></i></div>`,
    );
    this.resources.title = "能量与体力共用原有 SP；出招、跳跃和闪避消耗，停手恢复";
    for (const p of document.querySelectorAll("#helpPanel p"))
      if (p.textContent.includes("你的体力是"))
        p.textContent = p.textContent.replace(
          /你的体力是[^，]+/,
          "能量与体力共用 SP，底部黄色条是体力",
        );
    add("aside", "gbaKeys", "WASD 移动 · Shift 闪避<br>空格 跳跃 · Esc 暂停");
    this.pause = add("button", "gbaPause", "暂停");
    this.pause.onclick = () => api.togglePause();
    const menuReturn = document.createElement("button");
    menuReturn.id = "gbaMenuReturn";
    menuReturn.textContent = "返回对战 →";
    menuReturn.onclick = () => api.resume();
    document.getElementById("battleMenu")?.append(menuReturn);
    const helpClose = document.createElement("button");
    helpClose.id = "gbaHelpClose";
    helpClose.textContent = "返回对战 ×";
    helpClose.onclick = () => {
      document.getElementById("helpPanel").hidden = true;
      document.getElementById("help").setAttribute("aria-expanded", "false");
      api.resume();
    };
    document.getElementById("helpPanel").prepend(helpClose);
    this.result = document.getElementById("matchOverlay");
    const decor = document.createElement("div");
    decor.className = "gba-result-art";
    decor.innerHTML = `<div class="result-rays"></div><div class="result-band"></div>
      <div class="result-heading">BATTLE RESULT <span>对战结束 · MATCH RESULT</span></div>
      <div class="result-word" aria-hidden="true"></div>
      <div class="winner-art portrait-stage"><canvas id="winnerPortrait"
      class="select-portrait" width="320" height="320" aria-label="胜者立绘"></canvas></div>
      <div class="winner-tag"></div><div class="result-stats"></div>
      <div class="result-footer"><div><b>精彩的一战。</b><span>下一场，换一种打法。</span></div>
      <div><button id="gbaChange">换宝可梦</button>
      <button id="gbaRematch" class="primary">再战一局 →</button></div></div>`;
    this.result.prepend(decor);
    document.getElementById("gbaChange").onclick = () => api.setup();
    document.getElementById("gbaRematch").onclick = () => api.rematch();
    // Gate all input during the final-hit presentation, including menu and restart shortcuts.
    for (const type of ["keydown", "keyup", "pointerdown", "pointerup", "click"])
      window.addEventListener(
        type,
        (event) => {
          if (this.locked()) {
            event.preventDefault();
            event.stopImmediatePropagation();
          }
        },
        true,
      );
    this.result.addEventListener("pointerdown", (event) => event.stopPropagation());
  }
  locked() {
    return this.enabled && this.koAt != null && performance.now() < this.koAt + 800;
  }
  reset() {
    if (!this.enabled) return;
    this.koAt = null;
    if (this.popoverOK && this.result.matches(":popover-open")) this.result.hidePopover();
    this.result.removeAttribute("popover");
    this.result.classList.remove("gba-result");
    this.result.hidden = true;
    delete document.documentElement.dataset.ko;
  }
  finish(outcome, player, enemy, seconds) {
    if (!this.enabled) return;
    this.koAt = performance.now();
    document.documentElement.dataset.ko = "true";
    const winner = outcome === "loss" ? enemy : player;
    this.api.portrait(document.getElementById("winnerPortrait"), winner.id, "enemy");
    this.pixel(
      this.result.querySelector(".result-word"),
      outcome === "win" ? "VICTORY" : outcome === "loss" ? "DEFEAT" : "DRAW",
    );
    this.result.querySelector(".winner-tag").textContent =
      `${outcome === "loss" ? "CPU" : "1P"} · ${winner.char.name}`;
    this.result.querySelector(".result-stats").innerHTML =
      `<div>对战用时<b>${this.time(seconds)}</b></div><div>剩余血量<b>${Math.ceil(player.hp)} / ${player.maxHP}</b></div>
      <div>对手血量<b>${Math.ceil(enemy.hp)} / ${enemy.maxHP}</b></div>`;
    this.result.querySelector(".result-footer b").textContent =
      outcome === "win" ? "精彩的一战。" : outcome === "loss" ? "下一次，赢回来。" : "势均力敌。";
    document.getElementById("matchDetail").textContent =
      `你的血量 ${player.hp} / ${player.maxHP}　 ·　对手 ${enemy.hp} / ${enemy.maxHP}`;
    const magikarp = player.id === 129 || enemy.id === 129;
    const hint = magikarp ? "鲤鱼王尽力了。" : "点场地再战 · R 重新准备 · 换精灵试试别的打法";
    document.getElementById("matchHint").textContent = hint;
    this.result.querySelector(".result-footer span").textContent = magikarp ? hint : "下一场，换一种打法。";
    this.result.classList.add("gba-result");
    if (this.popoverOK && document.documentElement.dataset.touchGame === "true")
      this.result.setAttribute("popover", "manual");
    this.result.hidden = true;
  }
  showResult(outcome) {
    if (!this.enabled || this.koAt == null || this.locked()) return false;
    this.result.hidden = false;
    if (this.popoverOK && this.result.hasAttribute("popover") && !this.result.matches(":popover-open"))
      this.result.showPopover();
    document.getElementById("matchTitle").textContent =
      outcome === "win" ? "胜利" : outcome === "loss" ? "失败" : "平局";
    return true;
  }
  pixel(el, text) {
    if (el.dataset.pixel === text) return;
    el.dataset.pixel = text;
    const glyphs = {
      A: "0e11111f111111",
      B: "1e11111e11111e",
      C: "0e11101010110e",
      D: "1e11111111111e",
      E: "1f10101e10101f",
      F: "1f10101e101010",
      G: "0e11101711110f",
      H: "1111111f111111",
      I: "1f04040404041f",
      J: "0702020212120c",
      K: "11121418141211",
      L: "1010101010101f",
      M: "111b1515111111",
      N: "11191513111111",
      O: "0e11111111110e",
      P: "1e11111e101010",
      Q: "0e11111115120d",
      R: "1e11111e141211",
      S: "0f10100e01011e",
      T: "1f040404040404",
      U: "1111111111110e",
      V: "11111111110a04",
      W: "11111115151b11",
      X: "11110a040a1111",
      Y: "11110a04040404",
      Z: "1f01020408101f",
      0: "0e11131519110e",
      1: "040c040404040e",
      2: "0e11010204081f",
      3: "1e01010e01011e",
      4: "02060a121f0202",
      5: "1f10101e01011e",
      6: "0e10101e11110e",
      7: "1f010204080808",
      8: "0e11110e11110e",
      9: "0e11110f01010e",
      ":": "00040400040400",
    };
    let path = "";
    [...text].forEach((c, i) => {
      const bits = glyphs[c] || "00000000000000";
      for (let y = 0; y < 7; y++)
        for (let x = 0; x < 5; x++)
          if (parseInt(bits.slice(y * 2, y * 2 + 2), 16) & (16 >> x))
            path += `M${i * 6 + x} ${y}h1v1h-1z`;
    });
    el.innerHTML = `<span class="pixel-label">${text}</span><svg viewBox="0 0 ${text.length * 6 - 1} 7"
      aria-hidden="true" shape-rendering="crispEdges"><path fill="currentColor" d="${path}"/></svg>`;
  }
  time(seconds) {
    return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
  }
  sync(player, enemy, seconds, scene, phase) {
    if (!this.enabled) return;
    if (this.phase !== phase) {
      this.phase = phase;
      this.layout();
    }
    this.pixel(this.clock.querySelector("b"), this.time(seconds));
    this.clock.querySelector(":scope > span").textContent = scene;
    this.pause.textContent = phase === "paused" ? "继续" : "暂停";
    const sp = Math.ceil(player.stamina);
    this.resources.querySelectorAll("b").forEach((el) => {
      el.textContent = `${sp}/100`;
    });
    this.resources.querySelectorAll("i").forEach((el) => {
      el.style.width = `${player.stamina}%`;
    });
    document.querySelectorAll(".battle-card").forEach((card, i) => {
      let number = card.querySelector(".gba-hp-number");
      if (!number) {
        number = document.createElement("small");
        number.className = "gba-hp-number";
        card.querySelector(".battle-info").append(number);
      }
      const p = i ? enemy : player;
      number.textContent = `HP ${Math.ceil(p.hp)} / ${p.maxHP}`;
    });
  }
};
