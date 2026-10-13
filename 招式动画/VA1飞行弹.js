// SPDX-License-Identifier: AGPL-3.0-or-later
// VA1 visual-only shot recipes. Positions and contact clocks belong to M4 physics.
(() => {
  const recipes = {
    waterpulse: { color: "#60ffff", shape: "rings", trail: "ring", debris: "water" },
    energyball: { color: "#aaff12", shape: "spin", trail: "leaf", debris: "leaf" },
    thundershock: { color: "#fff118", shape: "bolt", trail: "spark", debris: "spark" },
    rockthrow: { color: "#703000", shape: "rock", trail: "rock", debris: "rock" },
    mudshot: { color: "#682900", shape: "mud", trail: "mud", debris: "mud" },
    shadowball: { color: "#4109a0", shape: "spin", trail: "ghost", debris: "ghost" },
    confusion: { color: "#a40864", shape: "warp", trail: "ring", debris: "warp" },
    dragonpulse: { color: "#6506bb", shape: "pulse", trail: "ring", debris: "ring" },
    sludgebomb: { color: "#8606ae", shape: "sludge", trail: "drop", debris: "drop" },
    moonblast: { color: "#b90866", shape: "moon", trail: "star", debris: "star" },
    brine: { color: "#60ffff", shape: "brine", trail: "water", debris: "water" },
    scald: { color: "#60ffff", shape: "steam", trail: "water", debris: "steam" },
    seedbomb: { color: "#174b00", shape: "seed", trail: "leaf", debris: "seed" },
    electroball: { color: "#fff118", shape: "electric", trail: "spark", debris: "spark" },
    iceshard: { color: "#38faff", shape: "ice", trail: "ice", debris: "ice" },
    aurasphere: { color: "#123ddd", shape: "aura", trail: "aura", debris: "aura" },
    focusblast: { color: "#fff019", shape: "focus", trail: "focus", debris: "focus" },
    powergem: { color: "#fff21a", shape: "gem", trail: "gem", debris: "gem" },
    venoshock: { color: "#710095", shape: "venom", trail: "drop", debris: "drop" },
    storedpower: { color: "#b90c69", shape: "stored", trail: "ring", debris: "ring" },
    darkpulse: { color: "#310868", shape: "dark", trail: "ring", debris: "ring" },
  };
  window.PoightVA1Shots = recipes;
  const proto = window.PoightMoveAnimations.prototype;
  const uses = proto.uses, prepare = proto.prepare, path = proto.path, draw = proto.draw;
  const anchor = proto.anchor, reset = proto.reset, bullet = proto.bullet, impact = proto.impact;
  proto.reset = function () {
    this.va1Queue = [];
    return reset.call(this);
  };
  proto.bullet = function (ctx, b, lift, api) {
    if (this.enabled && recipes[b.m.id] && b.coreShot) {
      // M4 sorts shots below actors at equal foot-Y. Do not let a giant caster's
      // native shoot frame hide the readable head: defer ONLY VA1 to the FX layer.
      (this.va1Queue ||= []).push({ b, lift, api });
      return true;
    }
    return bullet.call(this, ctx, b, lift, api);
  };
  const large = new Set(["energyball", "shadowball", "dragonpulse", "moonblast", "seedbomb",
    "aurasphere", "focusblast", "powergem", "storedpower", "darkpulse"]);
  proto.anchor = function (p, m, angle, api) {
    if (recipes[m.id] && m.anchor) {
      const root = api.anchor(p, m, angle);
      if (root) return root;
    }
    return anchor.call(this, p, m, angle, api);
  };
  proto.uses = function (id) {
    return uses.call(this, id) || (this.enabled && Object.hasOwn(recipes, id));
  };
  proto.prepare = function (b, api) {
    const result = prepare.call(this, b, api);
    if (this.enabled && recipes[b.m.id] && b.coreShot) b.coreShot.fx = "va1-" + b.m.id;
    return result;
  };
  proto.impact = function (target, source, m, ...args) {
    const previous = this.bursts.at(-1);
    const result = impact.call(this, target, source, m, ...args);
    const burst = this.bursts.at(-1);
    if (this.enabled && recipes[m.id] && burst && burst !== previous) {
      // Exact .8H can rasterize one pixel short at the arena's fractional scale.
      // VA1-only sampling margin; do not change amount, timing or other move stars.
      burst.size += 2;
      this.contacts.at(-1).size = burst.size;
    }
    return result;
  };
  // Extra margin compensates the actual opaque sprite contour, NOT a glow/canvas box.
  proto.va1Size = function (id, height) {
    return Math.max(16, height * (large.has(id) ? .40 : .30)) * 1.4;
  };
  proto.va1Ring = function (ctx, x, y, size, color, alpha, angle = 0) {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(angle);
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = color;
    ctx.lineWidth = Math.max(2, size * .12);
    ctx.beginPath();
    ctx.ellipse(0, 0, size * .30, size * .5, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  };
  proto.path = function (ctx, id, root, front, age, alpha = 1, height = 48) {
    const r = recipes[id];
    if (!r) return path.call(this, ctx, id, root, front, age, alpha, height);
    const dx = front.x - root.x, dy = front.y - root.y;
    const length = Math.hypot(dx, dy), angle = Math.atan2(dy, dx);
    const size = this.va1Size(id, height), tail = Math.min(length, size * 2.4);
    // A SHORT local trail, not a fake full-length beam or another damaging projectile.
    for (let i = 3; i > 0; i--) {
      const behind = tail * i / 4;
      const x = front.x - Math.cos(angle) * behind, y = front.y - Math.sin(angle) * behind;
      const a = alpha * (.18 + (4 - i) * .12);
      if (r.trail === "ring") this.va1Ring(ctx, x, y, size * (.75 + i * .10), r.color, a, angle);
      else this.sprite(ctx, "va1-" + id, x, y, size * (.36 + (4 - i) * .12), a,
        r.shape === "ice" || r.shape === "bolt" ? angle : -age * 7 + i);
    }
    // Muzzle flash is bound to the same release anchor in every direction.
    if (age < .09) {
      this.va1Ring(ctx, root.x, root.y, size * .7, r.color, alpha * (1 - age / .09), angle);
      this.sprite(ctx, "core-impact-" + (id === "thundershock" ? 13 : -1),
        root.x, root.y, 10, alpha * (1 - age / .09));
    }
    let rotation = ["ice", "bolt", "venom"].includes(r.shape) ? angle : 0;
    if (["spin", "rock", "aura"].includes(r.shape)) rotation = age * 8;
    this.sprite(ctx, "va1-" + id, front.x, front.y, size, alpha, rotation);
    if (["rings", "pulse", "dark", "stored"].includes(r.shape)) {
      for (let i = 0; i < 3; i++) this.va1Ring(ctx, front.x - Math.cos(angle) * i * size * .23,
        front.y - Math.sin(angle) * i * size * .23, size * (1 - i * .12),
        r.color, alpha, angle);
    }
    if (r.shape === "mud" || r.shape === "brine" || r.shape === "venom") {
      for (let i = 1; i <= 2; i++) {
        const t = Math.min(length, size * i * .7), wobble = Math.sin(age * 24 + i) * 3;
        this.sprite(ctx, "va1-" + id, front.x - Math.cos(angle) * t - Math.sin(angle) * wobble,
          front.y - Math.sin(angle) * t + Math.cos(angle) * wobble, size * .67, alpha, angle);
      }
    }
    if (r.shape === "steam") {
      for (let i = 0; i < 3; i++) this.sprite(ctx, "va1-steam",
        front.x - Math.cos(angle) * size * i * .4,
        front.y - Math.sin(angle) * size * i * .4 - size * (.6 + i * .15),
        size * .55, alpha * .7);
    }
  };
  proto.va1Impact = function (ctx, b) {
    const r = recipes[b.id], t = b.age / .26, alpha = 1 - t;
    if (!r) return;
    if (["water", "steam"].includes(r.debris)) {
      this.sprite(ctx, "core-splash", b.x, b.y, b.size * (1 + t), alpha);
    }
    if (["ring", "warp", "aura", "focus"].includes(r.debris)) {
      // Psychic squeeze / pulse fronts are local; no actor coordinates are written back.
      for (let i = 0; i < 2; i++) this.va1Ring(ctx, b.x, b.y,
        b.size * (.8 + t * 1.1 + i * .3), r.color, alpha, i ? .5 : -.5);
    }
    const key = r.debris === "steam" ? "va1-steam" :
      r.debris === "water" ? "core-drop" : "va1-" + b.id;
    for (let i = 0; i < 7; i++) {
      const a = i * Math.PI * 2 / 7, distance = b.size * (.22 + t * .65);
      this.sprite(ctx, key, b.x + Math.cos(a) * distance,
        b.y + Math.sin(a) * distance + (r.debris === "steam" ? -t * 28 : t * t * 8),
        b.size * (r.debris === "steam" ? .42 : .25), alpha, a + t * 2);
    }
  };
  proto.draw = function (ctx) {
    const queue = this.va1Queue || [];
    this.va1Queue = [];
    for (const q of queue) bullet.call(this, ctx, q.b, q.lift, q.api);
    ctx.save();
    this.clipContactCenters(ctx);
    for (const b of this.bursts) this.va1Impact(ctx, b);
    ctx.restore();
    return draw.call(this, ctx); // Existing .8H+ Emerald star stays on top.
  };
})();
