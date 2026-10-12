/* Hoenn traversal only. Scene capabilities, never species/type, grant access. */
"use strict";
window.PoightTraversal = class PoightTraversal {
  static parameters = Object.freeze({
    swimSpeed: 0.75,
    diveSpeed: 0.9,
    oxygen: 3,
    cooldown: 3,
    aiChance: 0.45,
    followDelay: 1,
    underwaterTypes: [11, 13], // Water / Electric; existing type efficacy still applies.
  });
  constructor() {
    this.reset();
  }
  reset() {
    this.epoch = (this.epoch || 0) + 1;
    this.pending = false;
    this.arrivalLock = false;
    this.follow = 0;
    this.error = "";
  }
  swimming(p, terrain) {
    return !!(p && terrain?.isWater(p.x, p.y, p.onBridge));
  }
  submerged(p, terrain) {
    return !!(terrain?.capabilities.dive && this.swimming(p, terrain) && p.diveLeft > 0);
  }
  speed(p, terrain) {
    const c = PoightTraversal.parameters;
    return this.swimming(p, terrain)
      ? c.swimSpeed * (this.submerged(p, terrain) ? c.diveSpeed : 1)
      : 1;
  }
  surface(p) {
    p.diveLeft = 0;
    p.diveCool = PoightTraversal.parameters.cooldown;
  }
  toggle(p, terrain) {
    if (!p || p.hp <= 0 || this.pending || p.worldAbsent) return false;
    if (this.submerged(p, terrain)) {
      this.surface(p);
      return true;
    }
    if (
      !terrain?.capabilities.dive ||
      !this.swimming(p, terrain) ||
      p.diveCool > 1e-6 ||
      p.hurt > 0
    )
      return false;
    p.diveLeft = PoightTraversal.parameters.oxygen;
    // Do not cancel already-emitted projectiles; cancel preparation and attached attacks.
    p.attack = p.dash = null;
    p.vx = p.vy = 0;
    return true;
  }
  canHit(p, move, terrain) {
    return (
      !p.worldAbsent &&
      (!this.submerged(p, terrain) ||
        PoightTraversal.parameters.underwaterTypes.includes(move.type))
    );
  }
  tick(p, dt, terrain) {
    p.diveCool = Math.max(0, (p.diveCool || 0) - dt);
    if (p.diveLeft > 0) {
      p.diveLeft = Math.max(0, p.diveLeft - dt);
      if (p.diveLeft < 1e-6 || !this.swimming(p, terrain) || !terrain?.capabilities.dive)
        this.surface(p);
    }
  }
  tryAI(p, terrain, tier, danger, random) {
    return !!(
      danger?.projectile &&
      ["great", "ultra", "master"].includes(tier) &&
      !this.submerged(p, terrain) &&
      terrain?.capabilities.dive &&
      this.swimming(p, terrain) &&
      !(p.diveCool > 1e-6) &&
      random() < PoightTraversal.parameters.aiChance &&
      this.toggle(p, terrain)
    );
  }
  atWarp(p, terrain) {
    if (!terrain?.capabilities.warps) return null;
    const col = Math.floor(p.x / terrain.cell),
      row = Math.floor(p.y / terrain.cell);
    return terrain.data.warps?.find((w) => w.col === col && w.row === row) || null;
  }
  updateWarps(dt, player, enemy, terrain, change, radius) {
    if (this.follow > 0) {
      this.follow = Math.max(0, this.follow - dt);
      if (this.follow < 1e-6) {
        // Player may have moved during the one-second delay: validate at reveal time too.
        if (this.arrival(enemy, terrain, enemy.x, enemy.y, radius(enemy),
          { ...player, radius: radius(player) })) {
          this.follow = 0;
          enemy.worldAbsent = false;
        } else this.follow = dt;
      }
    }
    const warp = this.atWarp(player, terrain);
    if (!warp) this.arrivalLock = false;
    if (!warp || this.arrivalLock || this.pending || this.follow) return;
    this.arrivalLock = true;
    this.error = "";
    this.pending = true;
    const ticket = this.epoch;
    Promise.resolve(change(warp, () => ticket === this.epoch))
      .then((ok) => {
        if (ticket !== this.epoch) return;
        this.pending = false;
        if (ok) {
          this.follow = PoightTraversal.parameters.followDelay;
          enemy.worldAbsent = true;
        }
      })
      .catch((err) => {
        if (ticket !== this.epoch) return;
        this.pending = false;
        this.error = String(err.message || err);
      });
  }
  arrival(p, terrain, x, y, radius, avoid = null) {
    // Search local original walkable centers; never relocate through a wall.
    const queue = [{ x, y }],
      seen = new Set([terrain.index(x, y)]),
      candidates = [];
    for (let i = 0; i < queue.length && i < 400; i++) {
      const q = queue[i],
        at = terrain.index(q.x, q.y);
      if (
        terrain.freeAt(q.x, q.y, radius) &&
        (!avoid || Math.hypot(q.x - avoid.x, q.y - avoid.y) >= Math.max(120, radius + avoid.radius + 5))
      ) {
        if (!avoid) {
          Object.assign(p, q, { onBridge: terrain.bridges?.layer(at) ?? false });
          return true;
        }
        candidates.push(q);
      }
      for (const [dx, dy] of [
        [0, -1],
        [1, 0],
        [-1, 0],
        [0, 1],
      ]) {
        const nx = q.x + dx * terrain.cell,
          ny = q.y + dy * terrain.cell;
        const next = terrain.index(nx, ny);
        if (!seen.has(next) && Math.hypot(nx - x, ny - y) <= terrain.cell * 6 &&
          terrain.freeAt(nx, ny, radius) && terrain.traversable(at, next)) {
          seen.add(next);
          queue.push({ x: nx, y: ny });
        }
      }
    }
    // Prefer a lateral nearby cell: the CPU should not land behind the bottom skill HUD.
    const score = (q) => Math.hypot(q.x - avoid.x, q.y - avoid.y) +
      1.5 * Math.abs(q.y - avoid.y);
    candidates.sort((a, b) => score(a) - score(b));
    if (!candidates.length) return false;
    Object.assign(p, candidates[0], {
      onBridge: terrain.bridges?.layer(terrain.index(candidates[0].x, candidates[0].y)) ?? false,
    });
    return true;
  }
  drawActor(ctx, p, terrain, elapsed, radius, sprite) {
    if (p.worldAbsent) return true;
    if (!this.swimming(p, terrain)) return false;
    const dive = this.submerged(p, terrain);
    ctx.save();
    if (dive) {
      ctx.fillStyle = "#153e65b8";
      ctx.beginPath();
      ctx.ellipse(p.x, p.y, radius * 1.25, radius * 0.6, p.a * 0.15, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#cff9ff";
      ctx.lineWidth = 1.5;
      for (let i = 0; i < 4; i++) {
        const age = (elapsed * 0.7 + i * 0.24) % 1;
        ctx.beginPath();
        ctx.arc(p.x + Math.sin(i * 3 + age) * radius, p.y - age * 35, 2 + (i % 2), 0, Math.PI * 2);
        ctx.stroke();
      }
      // Oxygen is drawn by the shared head HUD, directly below HP.
    } else {
      // Native sprites already extend below the foot anchor. Clip their lower body,
      // rather than sinking twice (which hid almost the entire head on small species).
      const waterline = p.y + radius * 0.35;
      ctx.save();
      ctx.beginPath();
      ctx.rect(p.x - 250, p.y - 300, 500, 300 + radius * 0.35);
      ctx.clip();
      sprite(p.y);
      ctx.restore();
      ctx.strokeStyle = "#d3faffcc";
      ctx.lineWidth = 2;
      for (let i = 0; i < 2; i++) {
        const r = radius + 6 + ((elapsed * 12 + i * 8) % 16);
        ctx.beginPath();
        ctx.ellipse(p.x, waterline, r, r * 0.28, 0, 0, Math.PI * 2);
        ctx.stroke();
      }
    }
    ctx.restore();
    return true;
  }
  bindButton(action) {
    const button = document.createElement("button");
    button.id = "diveButton";
    button.textContent = "潜 · C";
    button.title = "丰缘水中按 C 潜水／上浮；3秒氧气，3秒冷却，水电仍可命中";
    Object.assign(button.style, {
      position: "fixed",
      left: "12px",
      bottom: "104px",
      zIndex: "12",
      minWidth: "84px",
      minHeight: "44px",
      touchAction: "manipulation",
      pointerEvents: "auto",
    });
    button.onclick = (e) => {
      e.preventDefault();
      action();
    };
    document.getElementById("app").append(button);
    this.button = button;
  }
  syncButton(p, terrain, playing) {
    if (!this.button) return;
    this.button.hidden = !terrain?.capabilities.dive;
    this.button.disabled =
      !playing || this.pending || !this.swimming(p, terrain) || p.diveCool > 1e-6;
    this.button.textContent = this.submerged(p, terrain) ? "上浮 · C" : "潜水 · C";
    this.button.setAttribute("aria-pressed", String(this.submerged(p, terrain)));
  }
};
