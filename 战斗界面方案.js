/* URL-selected presentation only. Existing input binding and battle resources are reused. */
"use strict";
window.PoightBattleHUD = class {
  constructor(mode, data) {
    this.mode = ["0", "1", "2", "3"].includes(mode) ? mode :
      window.PoightMobile.touchDevice() ? "3" : "1";
    this.data = data;
    this.edgeIcon = new Image();
    this.edgeIcon.src = data.icons;
    if (this.mode === "0") return;
    document.documentElement.dataset.hud = this.mode;
    for (const paragraph of document.querySelectorAll("#helpPanel p")) {
      if (!paragraph.textContent.includes("你脚下的青色细条")) continue;
      const description = this.mode === "1" ? "顶部黄色 SP 大槽" :
        this.mode === "2" ? "头顶血条下的黄色 SP 条" : "左上头像旁的黄色 SP 弧线";
      paragraph.textContent = paragraph.textContent.replace(
        "你脚下的青色细条是体力 SP（出招／闪避消耗、停手恢复，满体力时自动淡出）；电脑不显示体力条。",
        `你的体力是${description}，始终可见；出招／闪避消耗、停手恢复，绿色 HP 是血量。`,
      );
    }
    const app = document.getElementById("app");
    this.menuButton = document.createElement("button");
    this.menuButton.id = "battleMenuButton";
    this.menuButton.textContent = "☰ 菜单";
    this.menuButton.setAttribute("aria-controls", "battleMenu");
    this.menuButton.setAttribute("aria-expanded", "false");
    this.menu = document.createElement("nav");
    this.menu.id = "battleMenu";
    this.menu.hidden = true;
    this.menu.setAttribute("aria-label", "对战设置");
    this.menu.append(document.querySelector(".readout"), document.querySelector(".buttons"));
    this.menu.querySelector(".buttons").append(document.getElementById("reset"));
    this.debugButton = document.createElement("button");
    this.debugButton.id = "battleMoveHints";
    this.debug = false;
    try {
      this.debug = localStorage.getItem("poight-hud-move-hints") === "1";
    } catch { /* Storage may be unavailable in private/offline contexts. */ }
    const syncDebug = () => {
      this.debugButton.textContent = "角色出招提示：" + (this.debug ? "开" : "关");
      this.debugButton.setAttribute("aria-pressed", String(this.debug));
    };
    syncDebug();
    this.debugButton.addEventListener("click", () => {
      this.debug = !this.debug;
      try {
        localStorage.setItem("poight-hud-move-hints", this.debug ? "1" : "0");
      } catch { /* Cosmetic preference only. */ }
      syncDebug();
    });
    this.menu.append(this.debugButton);
    this.menuButton.addEventListener("click", () => this.setMenu(this.menu.hidden));
    this.menu.addEventListener("click", (event) => {
      if (event.target.closest("button") !== this.debugButton) this.setMenu(false);
    });
    document.getElementById("game").addEventListener("pointerdown", () => this.setMenu(false));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") this.setMenu(false);
    });
    app.append(this.menuButton, this.menu);
    if (this.mode === "2") return;
    this.rail = document.createElement("section");
    this.rail.id = "battleRail";
    this.rail.setAttribute("aria-label", "双方状态；黄色 SP 是体力，绿色 HP 是血量");
    this.cards = ["player", "enemy"].map((side) => {
      const card = document.createElement("div");
      card.className = "battle-card " + side;
      card.innerHTML = `<div class="battle-avatar"><span class="mon-icon"></span>
        <div class="sp-arc"></div></div><div class="battle-info">
        <div class="battle-name"><b></b><span>${side === "player" ? "1P" : "CPU"}</span></div>
        <div class="battle-hp" aria-label="血量 HP"><i></i></div>
        <div class="battle-sp" aria-label="体力 SP"><i></i></div>
        <small class="battle-sp-label"></small></div>`;
      this.rail.append(card);
      return card;
    });
    app.append(this.rail);
  }
  setMenu(open) {
    this.menu.hidden = !open;
    this.menuButton.setAttribute("aria-expanded", String(open));
    this.onMenuChange?.(open);
  }
  sync(player, enemy) {
    if (!this.cards) return;
    [player, enemy].forEach((p, i) => {
      const card = this.cards[i],
        index = this.data.iconOrder.indexOf(p.id),
        icon = card.querySelector(".mon-icon");
      icon.style.backgroundPosition = `-${(index % this.data.iconColumns) * 48}px ` +
        `-${Math.floor(index / this.data.iconColumns) * 48}px`;
      card.querySelector("b").textContent = p.char.name;
      card.querySelector(".battle-hp i").style.width = `${100 * p.hp / p.maxHP}%`;
      card.querySelector(".battle-sp i").style.width = `${p.stamina}%`;
      card.querySelector(".battle-sp-label").textContent = `SP 体力 ${Math.ceil(p.stamina)}`;
      card.style.setProperty("--sp", p.stamina / 100);
      card.setAttribute("aria-label", `${p.char.name}，血量 ${Math.ceil(p.hp)}/${p.maxHP}，` +
        `体力 ${Math.ceil(p.stamina)}/100`);
    });
  }
  // Same player-following framing for every HUD. Body calibration is never modified.
  viewport(rect) {
    const reference = this.data.roster.find((c) => c.id === 25).body.visibleSize[1],
      scale = rect.height * 0.046 / reference;
    this.closeCamera = true;
    return { scale, x: 0, y: 0 };
  }
  staminaBox() {
    if (document.documentElement.dataset.gba)
      return document.querySelector("#gbaResources .stamina")?.getBoundingClientRect().toJSON();
    const selector = this.mode === "1" ? ".player .battle-sp" : ".player .sp-arc";
    return document.querySelector(selector)?.getBoundingClientRect().toJSON() || null;
  }
  camera(current, player, enemy, width, height, dt, world) {
    if (!player) return current;
    const clamp = (n, a, b) => Math.max(a, Math.min(b, n)),
      k = 1 - Math.exp(-dt / 0.12),
      axis = (at, p, span, extent) => {
        const delta = p - (at + span / 2),
          target = at + delta - clamp(delta, -span * 0.05, span * 0.05);
        // Fast dashes/knockback cannot leave the central 20% tracking envelope.
        // Only the world edge can override that envelope.
        const smooth = clamp(at + (target - at) * k, p - span * 0.6, p - span * 0.4);
        return clamp(smooth, 0, Math.max(0, extent - span));
      };
    return { x: axis(current.x, player.x, width, world.width),
      y: axis(current.y, player.y, height, world.height) };
  }
  drawEdge(ctx, enemy, camera, width, height, screen) {
    if (!this.closeCamera || !enemy || enemy.hp <= 0 || enemy.worldAbsent) return;
    const x = enemy.x - camera.x, y = enemy.y - camera.y,
      unit = width / screen.width;
    this.edge = null;
    if (x >= 0 && x <= width && y >= 0 && y <= height) return;
    const px = Math.max(28 * unit, Math.min(width - 28 * unit, x)),
      py = Math.max(115 * unit, Math.min(height - 165 * unit, y)),
      angle = Math.atan2(y - py, x - px), size = 28 * unit,
      index = this.data.iconOrder.indexOf(enemy.id);
    this.edge = { x: px, y: py, angle, targetX: x, targetY: y };
    ctx.save();
    ctx.fillStyle = "#142232e8";
    ctx.beginPath();
    ctx.arc(px, py, 17 * unit, 0, Math.PI * 2);
    ctx.fill();
    if (this.edgeIcon.complete && this.edgeIcon.naturalWidth)
      ctx.drawImage(this.edgeIcon, (index % this.data.iconColumns) * 48,
        Math.floor(index / this.data.iconColumns) * 48, 48, 48,
        px - size / 2, py - size / 2, size, size);
    ctx.translate(px, py);
    ctx.rotate(angle);
    ctx.fillStyle = "#ffda78";
    ctx.beginPath();
    ctx.moveTo(27 * unit, 0);
    ctx.lineTo(18 * unit, -6 * unit);
    ctx.lineTo(18 * unit, 6 * unit);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }
  drawArenaMap(ctx, ground, player, enemy, camera, width, height, world, screen, hidden,
    recording = false) {
    const gba = !recording && document.documentElement.dataset.gba,
      touch = gba && document.documentElement.dataset.touchGame === "true",
      compact = touch && document.documentElement.dataset.compact === "true",
      small = screen.height < 500 || touch, pixels = compact ? 54 : small ? 90 : 144,
      unit = width / screen.width, w = pixels * unit, h = w * 2 / 3;
    let x = width - w - 12 * unit;
    // Sit just above the right-side skills, including touch/legacy layouts.
    let bottom = screen.height - 12;
    // Recording pixels must not depend on CSS scaling or responsive DOM layout.
    for (const button of recording ? [] : document.querySelectorAll(".skill, #dashButton, #jumpButton, #gbaKeys")) {
      const r = button.getBoundingClientRect();
      if (r.width && r.right > screen.right - pixels - 24)
        bottom = Math.min(bottom, r.top - screen.top - 10);
    }
    let y = bottom * unit - h;
    if (gba) {
      const rail = document.getElementById("battleRail").getBoundingClientRect();
      if (touch) {
        const menu = document.getElementById("battleMenuButton").getBoundingClientRect();
        x = (menu.left - screen.left) * unit;
        y = (rail.bottom - screen.top + 14) * unit;
        // Portrait places the map below the menu, away from the center timer.
        if (screen.height > screen.width) y = (menu.bottom - screen.top + 12) * unit;
        if (compact) { x = (screen.width / 2 - 64) * unit; y = (rail.bottom - screen.top + 12) * unit; }
      } else y = Math.max((rail.bottom - screen.top + 70) * unit, y);
      y = Math.max(4 * unit, Math.min(height - h - 4 * unit, y));
    }
    // UI3 comparison B reserves the bottom-right for the arc; C leaves the map there.
    if (!recording && document.documentElement.dataset.ui3 === "B") {
      const cpu = document.querySelector(".battle-card.enemy").getBoundingClientRect();
      x = (cpu.right - screen.left - pixels) * unit;
      const menu = document.getElementById("battleMenuButton").getBoundingClientRect();
      y = (Math.max(cpu.bottom + 24, menu.bottom + 12) - screen.top) * unit;
    }
    this.minimap = { x: x / unit, y: y / unit, width: pixels, height: h / unit };
    ctx.save();
    ctx.fillStyle = "#142232e8";
    ctx.fillRect(x - 3 * unit, y - 3 * unit, w + 6 * unit, h + 6 * unit);
    ctx.drawImage(ground, x, y, w, h);
    ctx.strokeStyle = "#fff4c4";
    ctx.lineWidth = unit;
    ctx.strokeRect(x + camera.x / world.width * w, y + camera.y / world.height * h,
      width / world.width * w, height / world.height * h);
    for (const [p, color] of [[player, "#52f5ff"], [enemy, "#ff655c"]]) {
      if (!p || p.worldAbsent || (p === enemy && hidden)) continue;
      ctx.fillStyle = "#142232";
      const px = x + p.x / world.width * w, py = y + p.y / world.height * h;
      ctx.beginPath();
      ctx.arc(px, py, 3.5 * unit, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(px, py, 2.5 * unit, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }
  drawHint(ctx, p, h, move) {
    if (this.mode === "0" || !this.debug || !move) return;
    ctx.save();
    ctx.font = `bold ${(document.documentElement.dataset.gba ? 12 : 10) / h.sy}px system-ui`;
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    ctx.strokeStyle = "#142232";
    ctx.lineWidth = 3 / h.sy;
    ctx.fillStyle = "#fff2c0";
    ctx.strokeText(move.name, p.x, h.y - 13 / h.sy);
    ctx.fillText(move.name, p.x, h.y - 13 / h.sy);
    ctx.restore();
  }
};
